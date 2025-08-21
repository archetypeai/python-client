# An example that demonstrates how to hook up a video and stream it through a custom lens.
# usage:
#   python -m examples.quickstart --api_key=<YOUR_API_KEY> --filename=<VIDEO_FILE_ID>
import argparse
import logging
import sys

from archetypeai.api_client import ArchetypeAI

def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Upload the video file to the archetype platform.
    file_response = client.files.local.upload(args.filename)

    # Create a custom lens and automatically launch the lens session.
    client.lens.create_and_run_lens(f"""
       lens_name: Custom Activity Monitor
       lens_config:
        model_parameters:
            model_version: Newton::c2_1_250408d4362cc9
            instruction: {args.instruction}
            focus: {args.focus}
            temporal_focus: 5
            max_new_tokens: {args.max_new_tokens}
            camera_buffer_size: {args.camera_buffer_size}
            camera_buffer_step_size: {args.camera_buffer_step_size}
        input_streams:
            - stream_type: video_file_reader
              stream_config:
                file_id: {file_response['file_id']}
                step_size: {args.step_size}
        output_streams:
            - stream_type: server_sent_events_writer
    """, session_callback, client=client, args=args)

def session_callback(
        session_id: str,
        session_endpoint: str,
        client: ArchetypeAI,
        args: dict
    ) -> None:
    """Main function to run the logic of a custom lens session."""

    # Create a SSE reader to read the output of the lens.
    sse_reader = client.lens.sessions.create_sse_consumer(
        session_id, max_read_time_sec=args.max_run_time_sec)

    # Read events from the SSE stream until either the last message is
    # received or the max read time has been reached.
    for event in sse_reader.read(block=True):
        logging.info(f"[sse_reader] {event}")

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
    parser.add_argument("--logging_level", default=logging.INFO, type=str)
    args = parser.parse_args()
    logging.basicConfig(level=args.logging_level, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S", stream=sys.stdout)

    # Validate the input.
    assert args.filename.endswith(".mp4"), "Enter an .mp4 video file"

    main(args)