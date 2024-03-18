# Archetype AI Python Client
The official python client for the Archetype AI API.

## API Key
The Archetype AI API and python client requires an API key to upload, stream, and analyze your data.

Developers can request early access to the Archetype AI platform via: https://www.archetypeai.io

## Installation
You can install the Archetype AI python client via:

```
git clone git@github.com:archetypeai/python-client.git
cd python-client/src
python pip install -r requirements.txt
python pip install .
```

## Examples
You can find examples of how to use the python client in the examples directory.

```
cd examples
python image_summarization.py --api_key=<YOU_API_KEY> --filename=example_image.png --query="Describe the image."
```

```
cd examples
python video_description.py --api_key=<YOU_API_KEY> --filename=example_video.mp4 --query="Describe the video."
```

## Requirements
* An Archetype AI developer key (request one at https://www.archetypeai.io)
* Python 3.7 or higher.