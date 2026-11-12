from __future__ import annotations

from archetypeai._agents import _AgentApiBase, _drop_missing


class ProjectsApi(_AgentApiBase):
    """Main class for handling all project API calls.

    A project groups the blueprints of one agent effort and everything derived
    from them: packages, deployments, sessions, evals and optimizations. Only a
    package in a project can be deployed.
    """

    def list(self, limit: int | None = None, after: str | None = None, before: str | None = None) -> dict:
        """Lists the projects visible to you, newest first.

        You see the projects you created; an org admin sees every project of the org.
        Pass the previous page's next_cursor as after to fetch the next page.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "projects")
        params = _drop_missing({"limit": limit, "after": after, "before": before})
        return self.requests_get(api_endpoint, params=params)

    def get(self, project_id: str) -> dict:
        """Gets a single project by its `prj_` ID."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"projects/{project_id}")
        return self.requests_get(api_endpoint)

    def create(self, name: str, description: str = "") -> dict:
        """Creates an empty project and returns it.

        The API refuses with a 409 when you already created a project of that name,
        ignoring case.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, "projects")
        return self.post_json(api_endpoint, {"name": name, "description": description})

    def update(self, project_id: str, name: str | None = None, description: str | None = None) -> dict:
        """Changes a project's name or description and returns the project. Fields left as None keep their value."""
        api_endpoint = self._get_endpoint(self.api_endpoint, f"projects/{project_id}")
        return self.patch_json(api_endpoint, _drop_missing({"name": name, "description": description}))

    def delete(self, project_id: str) -> dict:
        """Deletes an empty project by its `prj_` ID.

        The API refuses with a 409 while the project still holds anything: delete its
        sessions, deployments, packages and blueprints first.
        """
        api_endpoint = self._get_endpoint(self.api_endpoint, f"projects/{project_id}")
        return self.requests_delete(api_endpoint)
