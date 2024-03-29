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
python -m pip install -r requirements.txt
python -m pip install /src
```

## Examples
You can find examples of how to use the python client in the examples directory.

```
cd examples
python -m image_summarization --api_key=<YOU_API_KEY> --filename=<YOUR_IMAGE> --query="Describe the image."
```

```
cd examples
python -m video_description --api_key=<YOU_API_KEY> --filename=<YOUR_VIDEO> --query="Describe the video."
```

## Requirements
* An Archetype AI developer key (request one at https://www.archetypeai.io)
* Python 3.7 or higher.