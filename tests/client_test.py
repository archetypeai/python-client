from unittest import mock

import pytest

from archetypeai import ArchetypeAI
from archetypeai._errors import ApiError


def test_client_init():
    client = ArchetypeAI("fake_api_key")
    assert client


def test_agents_api_init():
    client = ArchetypeAI("fake_api_key")
    assert client.projects
    assert client.agents.blueprints
    assert client.agents.packages
    assert client.agents.deployments
    assert client.agents.sessions
    assert callable(client.agents.blueprints.copy)
    assert callable(client.agents.deployments.create)
    assert callable(client.agents.sessions.create)
    assert not hasattr(client.agents, "bundles")
    assert not hasattr(client.agents, "instances")


def test_client_default_endpoint():
    assert ArchetypeAI.get_default_endpoint() == "https://platform.u1.archetypeai.app/api"


@pytest.mark.parametrize(
    "api, subpath, expected",
    [
        ("files", "files/info", "https://platform.example.com/api/files/info"),
        ("agents", "agents/blueprints", "https://platform.example.com/api/agents/blueprints"),
        ("projects", "projects", "https://platform.example.com/api/projects"),
        ("lens", "lens/sessions/create", "https://platform.example.com/api/lens/sessions/create"),
    ],
)
def test_client_endpoints_under_api_root(api, subpath, expected):
    client = ArchetypeAI("fake_api_key", api_endpoint="https://platform.example.com/api")
    module = client._lens if api == "lens" else getattr(client, api)
    assert module._get_endpoint(module.api_endpoint, subpath) == expected


def test_client_lens_deprecated():
    client = ArchetypeAI("fake_api_key")
    with pytest.warns(FutureWarning, match="lens API is deprecated"):
        assert client.lens.sessions


def test_client_removed_apis():
    client = ArchetypeAI("fake_api_key")
    for name in ("capabilities", "messaging", "sensors", "kafka"):
        assert not hasattr(client, name)
    assert not hasattr(client.files, "s3")


def _agents_client() -> ArchetypeAI:
    return ArchetypeAI("fake_api_key", api_endpoint="https://platform.example.com/api")


def _ok_response() -> mock.MagicMock:
    response = mock.MagicMock(status_code=200)
    response.json.return_value = {}
    return response


def _client_headers_sent(client: ArchetypeAI) -> list[str | None]:
    with (
        mock.patch("archetypeai._base.requests.get", return_value=_ok_response()) as get,
        mock.patch("archetypeai._agents.requests.post", return_value=_ok_response()) as post,
    ):
        client.files.local.get_info()
        client.projects.list()
        client.agents.blueprints.list()
        client.agents.sessions.query("ses_1", {"text": "hi"})
    calls = [*get.call_args_list, *post.call_args_list]
    return [call.kwargs["headers"].get("X-Atai-Client") for call in calls]


def test_client_sends_sdk_header_by_default():
    assert _client_headers_sent(_agents_client()) == ["sdk", "sdk", "sdk", "sdk"]


def test_client_header_override():
    client = ArchetypeAI("fake_api_key", api_endpoint="https://platform.example.com/api", client="agent_skills")
    assert _client_headers_sent(client) == ["agent_skills"] * 4


def test_lens_socket_sends_client_header():
    sessions = ArchetypeAI("fake_api_key", client="agent_skills")._lens.sessions
    with mock.patch("archetypeai._lens.LensSessionSocket") as socket:
        assert sessions.connect("ses_1", "wss://platform.example.com/lens")
    header = socket.call_args.args[1]
    assert header["X-Atai-Client"] == "agent_skills"
    assert header["Authorization"] == "Bearer fake_api_key"


def test_lens_sse_consumer_sends_client_header():
    sessions = ArchetypeAI("fake_api_key", client="agent_skills")._lens.sessions
    with mock.patch("archetypeai._lens.ServerSideEventsReader") as reader:
        sessions.create_sse_consumer("ses_1")
    assert reader.call_args.args[1]["X-Atai-Client"] == "agent_skills"


def test_packages_create_payload():
    packages = _agents_client().agents.packages
    with mock.patch.object(packages, "post_json", return_value={"id": "pkg_1"}) as post:
        packages.create("blp_1", description="demo")
    post.assert_called_once_with(
        "https://platform.example.com/api/agents/packages",
        {"blueprint_ids": ["blp_1"], "target": {"kind": "platform"}, "description": "demo"},
    )


def test_packages_create_sends_name():
    packages = _agents_client().agents.packages
    with mock.patch.object(packages, "post_json", return_value={"id": "pkg_1"}) as post:
        packages.create("blp_1", name="Pump line 3")
    post.assert_called_once_with(
        "https://platform.example.com/api/agents/packages",
        {"blueprint_ids": ["blp_1"], "target": {"kind": "platform"}, "description": "", "name": "Pump line 3"},
    )


def test_packages_list_drops_unset_params():
    packages = _agents_client().agents.packages
    with mock.patch.object(packages, "requests_get", return_value={"data": []}) as get:
        packages.list(limit=10, project_id="none")
    get.assert_called_once_with(
        "https://platform.example.com/api/agents/packages", params={"limit": 10, "project_id": "none"}
    )


def test_packages_list_sends_query():
    packages = _agents_client().agents.packages
    with mock.patch.object(packages, "requests_get", return_value={"data": []}) as get:
        packages.list(query="pump")
    get.assert_called_once_with("https://platform.example.com/api/agents/packages", params={"query": "pump"})


def test_deployments_list_filters_by_package():
    deployments = _agents_client().agents.deployments
    with mock.patch.object(deployments, "requests_get", return_value={"data": []}) as get:
        deployments.list(package_id="pkg_1")
    get.assert_called_once_with("https://platform.example.com/api/agents/deployments", params={"package_id": "pkg_1"})


def test_packages_wait_until_ready_returns_on_failed():
    packages = _agents_client().agents.packages
    statuses = iter([{"status": "building"}, {"status": "failed"}])
    with mock.patch.object(packages, "get", side_effect=lambda _id: next(statuses)):
        assert packages.wait_until_ready("pkg_1", poll_interval_sec=0)["status"] == "failed"


def test_blueprints_copy_payload():
    blueprints = _agents_client().agents.blueprints
    with mock.patch.object(blueprints, "post_json", return_value={"id": "blp_2"}) as post:
        blueprints.copy("osm", project_id="prj_1", blueprint_key="osm-copy")
    post.assert_called_once_with(
        "https://platform.example.com/api/agents/blueprints/osm/copy",
        {"project_id": "prj_1", "blueprint_key": "osm-copy"},
    )


def test_blueprints_copy_payload_with_overrides():
    blueprints = _agents_client().agents.blueprints
    with mock.patch.object(blueprints, "post_json", return_value={"id": "blp_2"}) as post:
        blueprints.copy("od", project_id="prj_1", blueprint_key="od-copy", overrides={"values": {"window_size": 360}})
    post.assert_called_once_with(
        "https://platform.example.com/api/agents/blueprints/od/copy",
        {"project_id": "prj_1", "blueprint_key": "od-copy", "overrides": {"values": {"window_size": 360}}},
    )


def test_blueprints_create_payload():
    blueprints = _agents_client().agents.blueprints
    with mock.patch.object(blueprints, "post_json", return_value={"id": "blp_2"}) as post:
        blueprints.create("osm-mine", document={"name": "osm"}, project_id="prj_1")
    post.assert_called_once_with(
        "https://platform.example.com/api/agents/blueprints",
        {"blueprint_key": "osm-mine", "document": {"name": "osm"}, "project_id": "prj_1"},
    )


def test_blueprints_get_resolves_key_in_project():
    blueprints = _agents_client().agents.blueprints
    with mock.patch.object(blueprints, "requests_get", return_value={"id": "blp_2"}) as get:
        blueprints.get("osm-copy", project_id="prj_1")
    get.assert_called_once_with(
        "https://platform.example.com/api/agents/blueprints/osm-copy", params={"project_id": "prj_1"}
    )


def test_projects_create_and_update_payloads():
    projects = _agents_client().projects
    with mock.patch.object(projects, "post_json", return_value={"id": "prj_1"}) as post:
        projects.create("Pump line 3")
    post.assert_called_once_with(
        "https://platform.example.com/api/projects", {"name": "Pump line 3", "description": ""}
    )
    with mock.patch.object(projects, "patch_json", return_value={"id": "prj_1"}) as patch:
        projects.update("prj_1", description="Vibration")
    patch.assert_called_once_with("https://platform.example.com/api/projects/prj_1", {"description": "Vibration"})


def test_projects_update_sends_patch():
    projects = _agents_client().projects
    with mock.patch("archetypeai._agents.requests.patch", return_value=_response(200, {"id": "prj_1"})) as patch:
        assert projects.update("prj_1", name="Renamed") == {"id": "prj_1"}
    assert patch.call_args.args[0] == "https://platform.example.com/api/projects/prj_1"
    assert patch.call_args.kwargs["data"] == '{"name": "Renamed"}'


def test_deployments_create_payload():
    deployments = _agents_client().agents.deployments
    with mock.patch.object(deployments, "post_json", return_value={"id": "dpl_1"}) as post:
        deployments.create("pkg_1", kind="serving")
    post.assert_called_once_with(
        "https://platform.example.com/api/agents/deployments", {"package_id": "pkg_1", "kind": "serving"}
    )


def test_deployments_wait_until_ready_stops_on_ready_and_ended():
    deployments = _agents_client().agents.deployments
    for final in ("ready", "stopped", "failed"):
        statuses = iter([{"status": "deploying"}, {"status": final}])
        with mock.patch.object(deployments, "get", side_effect=lambda _id, s=statuses: next(s)):
            assert deployments.wait_until_ready("dpl_1", poll_interval_sec=0)["status"] == final


def test_sessions_create_batch_payload():
    sessions = _agents_client().agents.sessions
    with mock.patch.object(sessions, "post_json", return_value={"id": "ses_1"}) as post:
        sessions.create("dpl_1", source=["file_1"], sink="out.csv")
    post.assert_called_once_with(
        "https://platform.example.com/api/agents/sessions",
        {
            "deployment_id": "dpl_1",
            "connectors": {"source": [{"type": "file", "id": "file_1"}], "sink": {"type": "file", "id": "out.csv"}},
        },
    )


def test_sessions_create_serving_sends_no_connectors():
    sessions = _agents_client().agents.sessions
    with mock.patch.object(sessions, "post_json", return_value={"id": "ses_1"}) as post:
        sessions.create("dpl_1")
    post.assert_called_once_with("https://platform.example.com/api/agents/sessions", {"deployment_id": "dpl_1"})


def test_sessions_wait_until_running_stops_on_running_and_failed():
    sessions = _agents_client().agents.sessions
    for final in ("running", "failed"):
        statuses = iter([{"status": "pending"}, {"status": final}])
        with mock.patch.object(sessions, "get", side_effect=lambda _id, s=statuses: next(s)):
            assert sessions.wait_until_running("ses_1", poll_interval_sec=0)["status"] == final


def test_sessions_wait_until_done_refuses_serving_session():
    sessions = _agents_client().agents.sessions
    with (
        mock.patch.object(sessions, "get", return_value={"kind": "serving", "status": "running"}),
        pytest.raises(ValueError, match="wait_until_running"),
    ):
        sessions.wait_until_done("ses_1", poll_interval_sec=0)


def test_sessions_wait_until_done_polls_batch_session():
    sessions = _agents_client().agents.sessions
    statuses = iter([{"kind": "batch", "status": "running"}, {"kind": "batch", "status": "completed"}])
    with mock.patch.object(sessions, "get", side_effect=lambda _id: next(statuses)):
        assert sessions.wait_until_done("ses_1", poll_interval_sec=0)["status"] == "completed"


def _response(status: int, body: dict, headers: dict | None = None) -> mock.MagicMock:
    response = mock.MagicMock(status_code=status, headers=headers or {})
    response.json.return_value = body
    return response


def test_sessions_query_returns_answer():
    sessions = _agents_client().agents.sessions
    with mock.patch("archetypeai._agents.requests.post", return_value=_response(200, {"status": "completed"})) as post:
        assert sessions.query("ses_1", {"query": "hi"}) == {"status": "completed"}
    assert post.call_args.args[0] == "https://platform.example.com/api/agents/sessions/ses_1/query"
    assert post.call_args.kwargs["data"] == '{"query": "hi"}'


def test_sessions_query_retries_busy_agent_after_retry_after():
    sessions = _agents_client().agents.sessions
    responses = [_response(429, {}, {"Retry-After": "3"}), _response(503, {}), _response(200, {"status": "completed"})]
    with (
        mock.patch("archetypeai._agents.requests.post", side_effect=responses) as post,
        mock.patch("archetypeai._agents.time.sleep") as sleep,
    ):
        assert sessions.query("ses_1", {})["status"] == "completed"
    assert post.call_count == 3
    assert [c.args[0] for c in sleep.call_args_list] == [3.0, 2.0]


def test_sessions_query_gives_up_after_max_retries():
    sessions = _agents_client().agents.sessions
    unavailable = _response(503, {"errors": [{"code": "unavailable"}]})
    with (
        mock.patch("archetypeai._agents.requests.post", return_value=unavailable) as post,
        mock.patch("archetypeai._agents.time.sleep"),
        pytest.raises(ApiError) as error,
    ):
        sessions.query("ses_1", {}, max_retries=2)
    assert post.call_count == 3
    assert error.value.validate_error_code_exists("unavailable")


def test_sessions_query_does_not_retry_timeout():
    sessions = _agents_client().agents.sessions
    timeout = _response(504, {"errors": [{"code": "query_timeout"}]})
    with mock.patch("archetypeai._agents.requests.post", return_value=timeout) as post, pytest.raises(ApiError):
        sessions.query("ses_1", {})
    assert post.call_count == 1
