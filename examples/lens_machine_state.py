# Machine State Anomaly Detection Example
# 
# This example demonstrates real-time anomaly detection on sensor data using n-shot learning.
# The lens learns to classify machine states as NORMAL or WARNING based on example data.
#
# Usage:
#   python -m examples.lens_machine_state \
#     --api_key=<YOUR_API_KEY> \
#     --file_path=<SENSOR_DATA_CSV_PATH> \
#     --normal_file_path=<NORMAL_OPERATION_CSV_PATH> \
#     --anomaly_file_path=<ANOMALOUS_OPERATION_CSV_PATH> \
#     --data_columns <VARIATE_1_COLUMN_NAME> <VARIATE_2_COLUMN_NAME> <VARIATE_3_COLUMN_NAME> <VARIATE_4_COLUMN_NAME> ...

from archetypeai.api_client import ArchetypeAI
import time
from pprint import pformat
import logging
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main(api_key, file_path, normal_file_path, anomaly_file_path, data_columns):
    logging.info("Initializing Machine State Anomaly Detection...")

    LENS_ID = "lns-1d519091822706e2-bc108andqxf8b4os"
    WINDOW_SIZE = 1024
    STEP_SIZE = 1024
    LOOP_RECORDING = False
    CUT_OFF_INCOMPLETE_WINDOW = True
    API_KEY = api_key
    FILE_PATH = file_path
    NORMAL_FILE_PATH = normal_file_path
    ANOMALY_FILE_PATH = anomaly_file_path
    DATA_COLUMNS = data_columns

    
    # Initialize counters
    sensor_data_count = 0
    inference_result_count = 0
    session_modify_count = 0
    
    # Create client
    client = ArchetypeAI(API_KEY)
    
    # Create and connect session
    logging.info("Creating lens session...")
    session_id, session_endpoint = client.lens.create_session(lens_id=LENS_ID)
    logging.info(f"Session ID: {session_id}")
    
    # Connect to session
    logging.info("Connecting to lens session...")
    response = client.lens.sessions.connect(session_id=session_id, session_endpoint=session_endpoint)
    logging.info(f"Connection response: {response}")
    
    # Create SSE reader
    logging.info("Creating SSE consumer...")
    sse_reader = client.lens.sessions.create_sse_consumer(session_id)
    time.sleep(2)  # Wait for the session to be ready
    
    # Upload CSV files
    logging.info(f"Uploading main CSV file: {FILE_PATH}")
    upload_response = client.files.local.upload(FILE_PATH)
    file_id = upload_response["file_id"]
    logging.info(f"Main file uploaded with ID: {file_id}")
    
    logging.info(f"Uploading normal operation example: {NORMAL_FILE_PATH}")
    normal_upload_response = client.files.local.upload(NORMAL_FILE_PATH)
    file_id_1 = normal_upload_response["file_id"]
    logging.info(f"Normal example uploaded with ID: {file_id_1}")
    
    logging.info(f"Uploading anomaly example: {ANOMALY_FILE_PATH}")
    anomaly_upload_response = client.files.local.upload(ANOMALY_FILE_PATH)
    file_id_2 = anomaly_upload_response["file_id"]
    logging.info(f"Anomaly example uploaded with ID: {file_id_2}")
    
    # Configure lens with n-shot learning examples
    logging.info("Configuring lens with training examples...")
    modify_event = {
        "type": "session.modify",
        "event_data": {
            "input_n_shot": {
                "NORMAL": file_id_1, 
                "WARNING": file_id_2
            },
            "csv_configs": {
                "data_columns": DATA_COLUMNS,
                "window_size": WINDOW_SIZE,
                "step_size": STEP_SIZE,
                "cut_off_incomplete_window": LOOP_RECORDING,
            },
        }
    }
    
    logging.info(f"Sending modify event: {pformat(modify_event, indent=2, depth=2)}")
    response = client.lens.sessions.process_event(session_id, modify_event)
    logging.info(f"Session modify response: {pformat(response, indent=2)}")
    
    # Set up input stream with CSV file
    logging.info("Configuring input stream...")
    input_event = {
        "type": "input_stream.set",
        "event_data": {
            "stream_type": "csv_file_reader",
            "stream_config": {
                "file_id": file_id,
                "window_size": WINDOW_SIZE,
                "step_size": STEP_SIZE,
                "loop_recording": LOOP_RECORDING,
                "cut_off_incomplete_window": CUT_OFF_INCOMPLETE_WINDOW,
                "output_format": "json",
            }
        }
    }
    
    logging.info(f"Sending input event: {pformat(input_event, indent=2, depth=2)}")
    response = client.lens.sessions.process_event(session_id, input_event)
    logging.info(f"Input stream response: {pformat(response, indent=2)}")
    
    # Set up output stream with SSE
    logging.info("Configuring output stream for SSE...")
    output_event = {
        "type": "output_stream.set",
        "event_data": {
            "stream_type": "server_side_events_writer",
            "stream_config": {}
        }
    }
    
    response = client.lens.sessions.process_event(session_id, output_event)
    logging.info(f"Output stream response: {pformat(response, indent=2)}")
    
    logging.info("="*60)
    logging.info("STARTING EVENT PROCESSING...")
    logging.info("="*60)

    try:
        for event in sse_reader.read(block=True):
            try:
                data = event
                
                if data["type"] == "inference.result":
                    file_id_meta = data["event_data"].get("query_metadata", {}).get("query_metadata", {}).get("file_id", None)
                    read_index = data["event_data"].get("query_metadata", {}).get("query_metadata", {}).get("read_index", None)
                    window_size = data["event_data"].get("query_metadata", {}).get("query_metadata", {}).get("window_size", None)
                    total_rows = data["event_data"].get("query_metadata", {}).get("query_metadata", {}).get("total_rows", None)
                    logging.info(f"\nMetadata - File ID: {file_id_meta}, Read Index: {read_index}, Window Size: {window_size}, Total Rows: {total_rows}")
                    result = data["event_data"].get("response", None)
                    logging.info(f"Inference result: {pformat(result, indent=2)}")

            except Exception as e:
                logging.error(f"Error processing event: {e}")
                logging.debug(f"Problematic event: {event}")
                    
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    
    finally:
        
        # Clean up
        logging.info("Cleaning up SSE reader and session...")
        sse_reader.close()
        client.lens.sessions.destroy(session_id=session_id)
        logging.info("Session cleaned up successfully")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Machine State Anomaly Detection Example")
    parser.add_argument("--api_key", type=str, required=True, help="Your Archetype AI API key")
    parser.add_argument("--file_path", type=str, help="Path to the main sensor data CSV file")
    parser.add_argument("--normal_file_path", type=str, help="Path to the normal operation example CSV")
    parser.add_argument("--anomaly_file_path", type=str, help="Path to the anomalous operation example CSV")
    parser.add_argument("--data_columns", type=str, nargs='+', help="List of sensor data columns to analyze")
    args = parser.parse_args()
    main(args.api_key, args.file_path, args.normal_file_path, args.anomaly_file_path, args.data_columns)
