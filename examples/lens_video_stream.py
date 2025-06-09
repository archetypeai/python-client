# An example that demonstrates how to hook up a video and stream it to a lens.
# usage:
#   python -m examples.files_api --api_key=<YOUR_API_KEY> --filename=<PATH_TO_LOCAL_VIDEO_FILE>
#   python -m examples.lens_video_stream --api_key=<YOUR_API_KEY> --file_id=<VIDEO_FILE_ID>
import argparse
import logging
from pprint import pformat
import time
import secrets

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

    # Adjust the focus of the lens.
    event = {
        "type": "session.modify",
        "event_data": {
            "instruction": args.instruction,
            "focus": args.focus,
            "max_new_tokens": args.max_new_tokens,
            "camera_buffer_size": args.camera_buffer_size,
            "camera_buffer_step_size": args.camera_buffer_step_size,
        }
    }
    response = client.lens.sessions.process_event(session_id, event)

    # Attach a video file reader as input to the lens.
    event = {
        "type": "input_stream.set",
        "event_data": {
            "stream_type": "video_file_reader",
            "stream_config": {
                "file_id": args.file_id,
                "step_size": args.step_size,     # How granular to step through the video.
            }
        }
    }
    response = client.lens.sessions.process_event(session_id, event)
    logging.info(f"response: \n {pformat(response, indent=4)}")

    # Attach a server-side events writer as output from the lens.
    event = {
        "type": "output_stream.set",
        "event_data": {
            "stream_type": "server_side_events_writer",
            "stream_config": {},
        }
    }
    response = client.lens.sessions.process_event(session_id, event)
    logging.info(f"response: \n {pformat(response, indent=4)}")

    # Create a SSE reader to read the output of the lens.
    sse_reader = client.lens.sessions.create_sse_consumer(
        session_id, max_read_time_sec=args.max_run_time_sec)

    # Read events from the SSE stream until either the last message is
    # received or the max read time has been reached.
    for event in sse_reader.read(block=True):
        logging.info(event)

    # Close any active reader.
    sse_reader.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file_id", required=True, type=str)
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    parser.add_argument("--lens_id", default="lns-fd669361822b07e2-bc608aa3fdf8b4f9", type=str)
    parser.add_argument("--max_run_time_sec", default=10.0, type=float)
    parser.add_argument("--step_size", default=30, type=int)
    parser.add_argument("--camera_buffer_size", default=5, type=int)
    parser.add_argument("--camera_buffer_step_size", default=5, type=int)
    parser.add_argument("--instruction", default="Analyze the video with the following focus.", type=str)
    parser.add_argument("--focus", default="Describe the actions in the video.", type=str)
    parser.add_argument("--max_new_tokens", default=256, type=int)
    args = parser.parse_args()
    main(args)