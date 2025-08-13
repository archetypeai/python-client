# An example that demonstrates how to hook up a video and stream it to a lens.
# usage:
#   python -m examples.quickstart --api_key=<YOUR_API_KEY> --filename=<VIDEO_FILE_ID>
import argparse
import logging

import yaml

from archetypeai.api_client import ArchetypeAI
from archetypeai.utils import pformat


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Define a custom lens.
    lens_config = f"""
       lens_name: Custom Activity Monitor
       lens_config:
        model_parameters:
            model_version: Newton::c2_1_250408d4362cc9
            instruction: {args.instruction}
            focus: {args.focus}
            max_new_tokens: {args.max_new_tokens}
            camera_buffer_size: {args.camera_buffer_size}
            camera_buffer_step_size: {args.camera_buffer_step_size}
    """
    lens_config = yaml.safe_load(lens_config)
    logging.info(f"Lens config:\n{pformat(lens_config)}")

    # Register the custom lens with the Archetype AI platform.
    lens_metadata = client.lens.register(lens_config)
    lens_id = lens_metadata.get("lens_id", None)
    assert lens_id, f"Missing lens_id: {lens_metadata}"

    # Create and run a new session, using the session function below.
    client.lens.create_and_run_session(
        lens_id, session_fn, auto_destroy=True, client=client, args=args)

    # Delete the custom lens to clean things up.
    client.lens.delete(lens_id)

def session_fn(
        session_id: str,
        session_endpoint: str,
        client: ArchetypeAI,
        args: dict
    ) -> None:
    """Main function to run the logic of a custom lens session."""

    # Upload the video file to the archetype platform.
    response_data = client.files.local.upload(args.filename)
    assert "file_id" in response_data, response_data
    file_id = response_data["file_id"]

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
    assert response["event_data"]["is_valid"], response

    # Attach an output stream using the ServerSideEvents protocol so we can recieve real-time outputs from the lens.
    event = {
        "type": "output_stream.set",
        "event_data": {
            "stream_type": "server_side_events_writer",
            "stream_config": {},
        }
    }
    response = client.lens.sessions.process_event(session_id, event)
    assert response["event_data"]["is_valid"], response

    # Lastly, attach the an input stream to start recording data from a video file reader as input to the lens.
    event = {
        "type": "input_stream.set",
        "event_data": {
            "stream_type": "video_file_reader",
            "stream_config": {
                "file_id": file_id,
                "step_size": args.step_size,     # How granular to step through the video.
            }
        }
    }
    response = client.lens.sessions.process_event(session_id, event)
    assert response["event_data"]["is_valid"], response

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
    parser.add_argument("--filename", required=True, type=str)
    parser.add_argument("--api_key", required=True, type=str)
    parser.add_argument("--api_endpoint", default=ArchetypeAI.get_default_endpoint(), type=str)
    parser.add_argument("--instruction", default="Analyze the video with the following focus.", type=str)
    parser.add_argument("--focus", default="Describe the actions in the video.", type=str)
    parser.add_argument("--max_run_time_sec", default=10.0, type=float)
    parser.add_argument("--step_size", default=30, type=int)
    parser.add_argument("--camera_buffer_size", default=5, type=int)
    parser.add_argument("--camera_buffer_step_size", default=5, type=int)
    parser.add_argument("--max_new_tokens", default=256, type=int)
    args = parser.parse_args()

    # Validate the input.
    assert args.filename.endswith(".mp4"), "Enter an .mp4 video file"

    main(args)