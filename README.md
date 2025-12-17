# Archetype AI Python Client
The official python client for the Archetype AI API.

## API Key
The Archetype AI API and python client requires an API key to upload, stream, and analyze your data.

Developers can request early access to the Archetype AI platform via: https://www.archetypeai.io

We recommend exporting your API key to the following variable: ATAI_API_KEY

For example on Linux, you can do this via:
```
echo "export ATAI_API_KEY='your api key'" >> ~/.bash_profile
source ~/.bash_profile
```

You can test this works by running the following in your terminal:
```
echo $ATAI_API_KEY
```

## API Endpoint
The Archetype AI python client can be used across all instances of the platform.

You can specify which instance of the platform you want to connect to via the *api_endpoint* parameter.

[!TIP]
You should always verify you are using the correct API key with the correct API endpoint. Using the wrong key or endpoint will result in authentication errors.

We recommend exporting your default API endpoint to the following variable: ATAI_API_ENDPOINT

For example on Linux, you can do this via:
```
echo "export ATAI_API_ENDPOINT='your default endpoint'" >> ~/.bash_profile
source ~/.bash_profile
```

You can test this works by running the following in your terminal:
```
echo $ATAI_API_ENDPOINT
```

## Installation
As a best practice, we recomend using a virtual environment such as Conda.

You can install the Archetype AI python client via pip:
```bash
pip install archetypeai
```

## Build From Source
If you want to build and install the latest example, you can do it directly from the git source code:
```bash
git clone git@github.com:archetypeai/python-client.git
cd python-client
python -m pip install .
```

## Test
You can test the Archetype AI python client is installed by running the following in your terminal:
```bash
python -c "from archetypeai import ArchetypeAI; print(f'Version: {ArchetypeAI.get_version()}')"
```

## Examples
You can find examples of how to use the python client in the examples directory.

### Quick Start
```bash
python -m examples.quickstart \
    --api_key=<YOU_API_KEY> \
    --filename=<YOUR_MP4_VIDEO_FILENAME> \
    --instruction="Analyze the video with the following focus."" \
    --focus="Describe the actions in the video."
```

## Unit Tests
You can run the unit tests for the python client by running the following in your terminal:
```bash
ATAI_API_KEY="your api key" ATAI_API_ENDPOINT="your api endpoint" python -m pytest .
```

## Requirements
* An Archetype AI developer key (request one at https://www.archetypeai.io)
* Python 3.8 or higher.
