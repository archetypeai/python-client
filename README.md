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

The endpoint is the platform host followed by `/api`, for example `https://platform.u1.archetypeai.app/api`. This is the default. The client adds the API path to it, for example `/api/files/...` or `/api/agents/...`.

[!IMPORTANT]
Earlier versions of the client used endpoints such as `https://api.u1.archetypeai.app/v0.5`. These endpoints do not work with this version. Update `ATAI_API_ENDPOINT` and any `api_endpoint` value to the new format.

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
Runs a Manual Generation (MGA) agent on a short procedure video:
1. Upload the video.
2. Bundle the canonical `mga` blueprint.
3. Run the bundle and wait for the agent to finish.
4. Print the results, then delete the agent run and the bundle.

By default it uses `example_data/mga_quick_start_ac_capacitor.mp4`. Pass `--filename` to use your own video.
```bash
python -m examples.quickstart --api_key=<YOUR_API_KEY>
```

### Lens Examples (Deprecated)
The lens API is deprecated and the agents API replaces it. `client.lens` still works but raises a `FutureWarning`. The `lens_*` examples will be removed together with the lens API.

### Optimize, Evaluate and Deploy an OSM Agent
Takes an Operational State Monitoring (OSM) agent through its full lifecycle on labeled data:
1. Upload the data.
2. Optimize the `osm` blueprint: each trial fits a classifier on the training data and is
   scored on the validation data.
3. Promote the best trial to a blueprint of your own.
4. Evaluate that blueprint on held-out test data.
5. Bundle it and run it on new, unlabeled data.

By default it uses `example_data/osm_larco/`, a small sample of washing machine vibration
labeled `fill`, `wash`, `spin` and `drain`. It takes about 4 minutes.
```bash
python -m examples.agents.agent_osm_lifecycle --api_key=<YOUR_API_KEY>
```

Options:
- `--data_dir`: the data to use (see below). Defaults to `example_data/osm_larco`.
- `--k_neighbors`: the classifier sizes to try, one trial each. Defaults to `5 31`.
- `--max_run_time_sec`: how long to wait on each step before giving up. Waits forever by default.
- `--api_endpoint`: the API endpoint, as for every example.

To use your own data, give `--data_dir` a folder with one subfolder per role. Files are CSV
(or gzipped CSV) with the timestamp first, then the sensor columns:

| folder | content | labels |
|---|---|---|
| `library/` | training data, one state per file, named `<state>__<name>.csv` | the state, from the file name |
| `validation/` | scores each optimization trial | a `label` column |
| `test/` | held-out data the promoted blueprint is evaluated on | a `label` column |
| `delivery/` | new data the deployed agent runs on | none |

The [LARCO quickstart](https://github.com/archetypeai/operational-state-monitoring-agent-example-larco-quickstart)
builds its data in this layout, so the example runs on its 19 full washing machine cycles
(about 0.45 GB, Git LFS required):
```bash
git clone https://github.com/archetypeai/operational-state-monitoring-agent-example-larco-quickstart.git
cd operational-state-monitoring-agent-example-larco-quickstart
git lfs pull && python prep/archive_roles.py --unpack
cd -
python -m examples.agents.agent_osm_lifecycle --api_key=<YOUR_API_KEY> \
    --data_dir=operational-state-monitoring-agent-example-larco-quickstart/data/roles
```

## Unit Tests
You can run the unit tests for the python client by running the following in your terminal:
```bash
pip install -e '.[test]'
ATAI_API_KEY="your api key" ATAI_API_ENDPOINT="your api endpoint" python -m pytest .
```

## Requirements
* An Archetype AI developer key (request one at https://www.archetypeai.io)
* Python 3.10 or higher.
