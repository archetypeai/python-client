# An example that demonstrates how to hook up a real-time RTSP camera to a lens.
# usage:
#   python -m examples.lens_rtsp_camera --api_key=<YOUR_API_KEY> --rtsp_url=<YOUR_RTSP_URL>
import logging
import time

from archetypeai import ArchetypeAI, ArgParser, pformat


def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Create a custom lens and automatically launch the lens session.
    client.lens.create_and_run_lens(f"""
       lens_name: Custom Activity Monitor
       lens_config:
        model_parameters:
            model_version: Newton::c2_4_7b_251215a172f6d7
            instruction: Monitor the real-time camera stream and describe the activites.
            focus: human activity
            temporal_focus: 5
            max_new_tokens: 128
        input_streams:
            - stream_type: rtsp_video_reader
              stream_config:
                rtsp_url: {args.rtsp_url}
                target_image_size: [360, 640]
                target_frame_rate_hz: 1.0
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
        logging.info(event)

    # Close any active reader.
    sse_reader.close()


if __name__ == "__main__":
    parser = ArgParser()
    parser.add_argument("--rtsp_url", required=True, type=str)
    parser.add_argument("--max_run_time_sec", default=10.0, type=float)
    args = parser.parse_args(configure_logging=True)
    main(args)