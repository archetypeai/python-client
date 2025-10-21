# Archetype AI Python Client
The official python client for the Archetype AI API.

## API Key
The Archetype AI API and python client requires an API key to upload, stream, and analyze your data.

Developers can request early access to the Archetype AI platform via: https://www.archetypeai.io

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
python -c "from archetypeai.api_client import ArchetypeAI; print(f'Version: {ArchetypeAI.get_version()}')"
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

## Requirements
* An Archetype AI developer key (request one at https://www.archetypeai.io)
* Python 3.8 or higher.
