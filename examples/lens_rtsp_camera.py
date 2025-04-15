# An example that demonstrates how to hook up a real-time RTSP camera to a lens.
# usage:
#   python -m examples.lens_rtsp_camera --api_key=<YOUR_API_KEY> --rtsp_url=<YOUR_RTSP_URL>
import argparse
import logging
from pprint import pformat
import time

from archetypeai.api_client import ArchetypeAI


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Create and run a new session, using the session function below.
    client.lens.create_and_run_session(
        args.lens_id, session_fn, auto_destroy=True, client=client, args=args)

def session_fn(
        session_id: str,
        session_endpoint: str,
        client: ArchetypeAI,
        args: dict
    ) -> None:
    """Main function to run the logic of a custom lens session."""

    # Attach an RTSP camera to the input of the lens.
    event = {
        "type": "input_stream.set",
        "event_data": {
            "stream_type": "rtsp_video_streamer",
            "stream_config": {
                "rtsp_url": args.rtsp_url,
                "target_image_size": [360, 640],
                "target_frame_rate_hz": 0.2
            }
        }
    }
    response = client.lens.sessions.process_event(session_id, event)
    logging.info(f"response: \n {pformat(response, indent=4)}")

    start_time = time.time()
    while time.time() - start_time < args.max_run_time_sec:
        # Read the latest logs from the lens.
        event = {"type": "session.read", "event_data": {"client_id": client.get_client_id()}}
        response = client.lens.sessions.process_event(session_id, event)
        if response["event_data"] is not None:
            event = response["event_data"]
            logging.info(f"response: \n {pformat(event, indent=4)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rtsp_url", required=True, type=str)
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    parser.add_argument("--lens_id", default="lns-fd669361822b07e2-237ab3ffd79199b2", type=str)
    parser.add_argument("--max_run_time_sec", default=10.0, type=float)
    args = parser.parse_args()
    main(args)