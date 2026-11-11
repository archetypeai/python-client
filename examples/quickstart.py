# A quick start that runs a Manual Generation (MGA) agent on a short procedure video.
#
# Lifecycle: blueprints -> packages -> deployments -> sessions
#   upload the video, copy the canonical `mga` blueprint into a project, package it,
#   deploy it as batch, run a session on the video, read the results.
#
# Default input is example_data/mga_quick_start_ac_capacitor.mp4 (replacing an
# air conditioner capacitor). Pass --filename for your own video.
# usage:
#   python -m examples.quickstart --api_key=<YOUR_API_KEY>
import logging
import uuid

from archetypeai import ArchetypeAI, ArgParser, pformat


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Upload the video file to the Archetype AI platform.
    file_id = client.files.local.upload(args.filename)["file_id"]
    logging.info(f"Uploaded file_id: {file_id}")

    # Create a project, then copy the canonical Manual Generation blueprint into it:
    # only a blueprint in a project can be packaged and deployed.
    suffix = uuid.uuid4().hex[:8]
    project_id = client.projects.create(f"Quickstart {suffix}")["id"]
    blueprint_id = client.agents.blueprints.copy("mga", project_id=project_id, blueprint_key=f"mga-{suffix}")["id"]
    logging.info(f"Created project_id: {project_id} with blueprint_id: {blueprint_id}")

    package_id = deployment_id = session_id = None
    try:
        # Package the blueprint: its models are resolved once, so the package always
        # runs the same ones.
        package_id = client.agents.packages.create(blueprint_id, name=f"quickstart_{suffix}")["id"]
        package = client.agents.packages.wait_until_ready(package_id)
        if package.get("status") != "ready":
            logging.error(f"Package {package_id} did not build: {pformat(package)}")
            return
        logging.info(f"Built package_id: {package_id}")

        # Deploy the package as batch: each session on it is one run over its own files.
        deployment_id = client.agents.deployments.create(package_id, kind="batch")["id"]
        deployment = client.agents.deployments.wait_until_ready(deployment_id)
        if deployment.get("status") != "ready":
            logging.error(f"Deployment {deployment_id} is not ready: {pformat(deployment)}")
            return
        logging.info(f"Deployed deployment_id: {deployment_id}")

        # Run a session on the video and wait for it to finish.
        session_id = client.agents.sessions.create(deployment_id, source=[file_id])["id"]
        logging.info(f"Opened session_id: {session_id}")
        session = client.agents.sessions.wait_until_done(session_id, timeout_sec=args.max_run_time_sec)
        status = session.get("status")
        logging.info(f"Session finished with status: {status}")

        if status == "completed":
            results = client.agents.sessions.get_results(session_id)
            logging.info(f"Session results: {pformat(results)}")
        else:
            events = client.agents.sessions.get_events(session_id)
            logging.error(f"Session did not complete: {pformat(events)}")
    finally:
        # Delete everything the quick start created, so repeated runs do not accumulate it
        # in your org. Each one blocks deleting the next: the session, the deployment
        # (stopped first), the package, the blueprint, then the empty project.
        if session_id:
            if client.agents.sessions.get(session_id).get("status") not in ("completed", "failed", "cancelled"):
                client.agents.sessions.cancel(session_id)
            client.agents.sessions.delete(session_id)
        if deployment_id:
            if client.agents.deployments.get(deployment_id).get("status") not in ("stopped", "failed"):
                client.agents.deployments.stop(deployment_id)
            client.agents.deployments.wait_until_ready(deployment_id)
            client.agents.deployments.delete(deployment_id)
        if package_id:
            client.agents.packages.delete(package_id)
        client.agents.blueprints.delete(blueprint_id)
        client.projects.delete(project_id)


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--filename", default="example_data/mga_quick_start_ac_capacitor.mp4", type=str)
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float)
    args = parser.parse_args(configure_logging=True)

    main(args)
