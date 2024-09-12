# Archetype AI Python Client
The official python client for the Archetype AI API.

## API Key
The Archetype AI API and python client requires an API key to upload, stream, and analyze your data.

Developers can request early access to the Archetype AI platform via: https://www.archetypeai.io

## Installation
As a best practice, we recomend using a virtual environment such as Conda.

You can install the Archetype AI python client via:
```
git clone git@github.com:archetypeai/python-client.git
cd python-client
python -m pip install .
```

## Examples
You can find examples of how to use the python client in the examples directory.

### Image Summarization
```
python -m examples.image_summarization --api_key=<YOU_API_KEY> --filename=<YOUR_IMAGE> --query="Describe the image."
```

### Video Description
```
python -m examples.video_description --api_key=<YOU_API_KEY> --filename=<YOUR_VIDEO> --query="Describe the video."
```

### Sensor Streaming
An example of how to stream real-time sensor data and events to the Archetype AI platform, using a simple counter.
```
python -m examples.sensor_streaming --api_key=<YOU_API_KEY> --sensor_name="example_sensor"
```

### Sensor PubSub
An example of how to send and receive event messages across one or more distributed sensors.
```
python -m examples.sensor_pubsub --api_key=<YOU_API_KEY> --sensor_name="example_sensor"
```

## Requirements
* An Archetype AI developer key (request one at https://www.archetypeai.io)
* Python 3.08 or higher.
