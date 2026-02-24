# An example that demonstrates how to apply analysis to a JSONL file with sensor logs.
# usage:
#   python -m examples.lens_sensor_logs --api_key=<YOUR_API_KEY> --filename=<VIDEO_FILE_ID>
import logging

from archetypeai import ArchetypeAI, ArgParser

def main(args):
    # Create a new client using your unique API key.
    client = ArchetypeAI(args.api_key, api_endpoint=args.api_endpoint)

    # Upload the video file to the archetype platform.
    file_response = client.files.local.upload(args.filename)

    # Create a custom lens and automatically launch the lens session.
    client.lens.create_and_run_lens(f"""
       lens_name: Sensor Log Detector
       lens_config:
        model_pipeline:
          - processor_name: lens_sensor_logs_processor
        model_parameters:
            model_version: Newton::c2_4_7b_251215a172f6d7
            instruction: {args.instruction}
            focus: {args.focus}
        input_streams:
            - stream_type: jsonl_file_reader
              stream_config:
                file_id: {file_response['file_id']}
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
    # Validate the session is ready.
    event_message = {"type": "session.validate"}
    response = client.lens.sessions.process_event(session_id, event_message)
    assert response["event_data"]["is_valid"], response

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
    parser = ArgParser()
    parser.add_argument("--filename", required=True, type=str)
    parser.add_argument("--instruction", default="Analyze the sensor data in the text logs with the following focus.", type=str)
    parser.add_argument("--focus", default="Output an alert if a user enters the kitchen.", type=str)
    parser.add_argument("--max_run_time_sec", default=-1.0, type=float)
    args = parser.parse_args()

    # Validate the input.
    assert args.filename.endswith(".jsonl"), "Enter a valid .jsonl file"

    main(args)