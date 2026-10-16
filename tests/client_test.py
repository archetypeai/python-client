import pytest

from archetypeai import ArchetypeAI


def test_client_init():
    client = ArchetypeAI("fake_api_key")
    assert client


def test_agents_api_init():
    client = ArchetypeAI("fake_api_key")
    assert client.agents.blueprints
    assert client.agents.bundles
    assert client.agents.instances
    assert callable(client.agents.bundles.create)
    assert callable(client.agents.bundles.delete)
    assert callable(client.agents.bundles.run)


def test_client_default_endpoint():
    assert ArchetypeAI.get_default_endpoint() == "https://platform.u1.archetypeai.app/api"


@pytest.mark.parametrize(
    "api, subpath, expected",
    [
        ("files", "files/info", "https://platform.example.com/api/files/info"),
        ("agents", "agents/blueprints", "https://platform.example.com/api/agents/blueprints"),
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
