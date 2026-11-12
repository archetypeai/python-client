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

## Client Name
Every request the client sends to the platform carries an `X-Atai-Client` header, `sdk` by default. Tools built on the client pass their own name instead:
```python
client = ArchetypeAI(api_key, client="agent_skills")
```
The platform recognizes `agent_skills`, `sdk`, `console` and `playground`, and records any other value as `other`.

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
2. Create a project and copy the canonical `mga` blueprint into it.
3. Package the blueprint and deploy the package as `batch`.
4. Run a session on the video and wait for it to finish.
5. Print the results, then delete everything the quick start created.

By default it uses `example_data/mga_quick_start_ac_capacitor.mp4`. Pass `--filename` to use your own video.
```bash
python -m examples.quickstart --api_key=<YOUR_API_KEY>
```

### The Agent Lifecycle
An agent goes through four phases inside a project: develop, build, deploy and run.

#### Develop
Create a project, then create a blueprint in it.
- A **project** groups the blueprints of one agent effort and everything derived from them.
- A **blueprint** defines the agent. Copy a platform blueprint, such as `mga`, into your project to use it.

To fit a blueprint to your own data, optimize it and promote the best trial to a new blueprint.
Then evaluate that blueprint on held-out data. The lifecycle examples below show each step.
```python
from archetypeai import ArchetypeAI

client = ArchetypeAI(api_key)
project = client.projects.create("Pump line 3")
blueprint = client.agents.blueprints.copy("mga", project_id=project["id"], blueprint_key="mga-pump-line-3")
```

#### Build
Build a package from a blueprint. A **package** is an immutable build of a blueprint for a
target. Every model slot is resolved at build time, so a package always runs the same models.
The `platform` target is the only one available.
```python
package = client.agents.packages.create(blueprint["id"])
package = client.agents.packages.wait_until_ready(package["id"])
```

#### Deploy
Deploy the package. A **deployment** places a package as `batch` or `serving`. Only a package
in a project can be deployed. One package can have many deployments.
```python
batch = client.agents.deployments.create(package["id"], kind="batch")
batch = client.agents.deployments.wait_until_ready(batch["id"])

serving = client.agents.deployments.create(package["id"], kind="serving")
serving = client.agents.deployments.wait_until_ready(serving["id"])
```

#### Run
Run sessions on a deployment. A **session** is one run of the agent.
```python
# A batch session processes its input files and finishes.
session = client.agents.sessions.create(batch["id"], source=["file_..."])
session = client.agents.sessions.wait_until_done(session["id"])
results = client.agents.sessions.get_results(session["id"])

# A serving session takes no input files and answers queries once it is `running`.
# It never finishes, so wait for it with wait_until_running, not wait_until_done.
session = client.agents.sessions.create(serving["id"])
session = client.agents.sessions.wait_until_running(session["id"])

# The request and the answer's `response` take whatever shape the blueprint defines.
answer = client.agents.sessions.query(session["id"], {"query": "...", "events": [...]})
```
`query` sends the request again, with a backoff, while the agent is busy or still starting.

Delete in reverse order, because each resource blocks deleting the one it runs on:
1. Cancel and delete the sessions.
2. Stop and delete the deployment.
3. Delete the package, then the blueprint, then the empty project.

### Run a Demo Agent
`examples/agents/agent_osm.py`, `agent_red.py` and `agent_ad.py` run the platform demo blueprints
`playground-osm-drilling`, `playground-red` and `playground-ad` on the sample files in
`example_data/`. Each one is the platform `osm`, `red` or `ad` blueprint with a head the platform
fit for demos. `agent_mga.py` and `agent_tva.py` run the canonical `mga` and `tva` blueprints.

Each example copies its blueprint into a project named `Python client examples`. It packages,
deploys and runs the copy. It deletes the session, deployment and package afterwards, and keeps
the project and the copy for the next run.
```bash
python -m examples.agents.agent_osm --api_key=<YOUR_API_KEY>
```

`agent_osm_serving.py` deploys the OSM demo blueprint as `serving` and queries it with
slices of the sample sensor log:
```bash
python -m examples.agents.agent_osm_serving --api_key=<YOUR_API_KEY>
```

`agent_od.py` runs the canonical `od` blueprint (Label-Free Anomaly Discovery) as `batch`. It
scores every window of a file against the file's other windows, so it needs no labels, no
reference data and no fitted head. The default input is three weeks of a metro train's air
compressor from MetroPT-3, in `example_data/od_metropt/`. The example copies `od` with
one-hour windows (`--window_size=360` rows at 10 seconds). Each output row is one window,
with its `anomaly_score` and `predicted_label`. A score over 1.5 is labeled `anomaly`. `od`
has no serving deployment yet.
```bash
python -m examples.agents.agent_od --api_key=<YOUR_API_KEY>
```

### Lens Examples (Deprecated)
The lens API is deprecated and the agents API replaces it. `client.lens` still works but raises a `FutureWarning`. The `lens_*` examples will be removed together with the lens API.

### Develop, Build, Deploy and Run an OSM Agent
Takes an Operational State Monitoring (OSM) agent through its full lifecycle on labeled data:
- **Develop:** upload the data. Copy the `osm` blueprint into a project and optimize it: each
  trial fits a classifier on the training data and is scored on the validation data. Promote
  the best trial to a blueprint of your own, then evaluate that blueprint on held-out test data.
- **Build:** package the promoted blueprint.
- **Deploy:** deploy the package as `batch`, and later as `serving`.
- **Run:** run a batch session on new, unlabeled data. Then query the serving deployment with
  the first rows of that data, sent inline.

By default it uses `example_data/osm_larco/`, a small sample of washing machine vibration
labeled `fill`, `wash`, `spin` and `drain`. It takes about 7 minutes.
```bash
python -m examples.agents.agent_osm_lifecycle --api_key=<YOUR_API_KEY>
```

Options:
- `--data_dir`: the data to use (see below). Defaults to `example_data/osm_larco`.
- `--k_neighbors`: the classifier sizes to try, one trial each. Defaults to `5 31`.
- `--rows_per_query` and `--num_queries`: the delivery rows in each serving query, and how
  many queries to send. Default to `1024` and `3`.
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

### Develop, Build, Deploy and Run an AD Agent
Takes an Anomaly Discovery (AD) agent through its full lifecycle on your data:
- **Develop:** upload the data. Copy the `ad` blueprint into a project and optimize it: each
  trial fits an anomaly detector on normal data and is scored on labeled validation data.
  Promote the best trial to a blueprint of your own, then evaluate that blueprint on held-out
  test data.
- **Build:** package the promoted blueprint.
- **Deploy:** deploy the package as `batch`, and later as `serving`.
- **Run:** run a batch session on new, unlabeled data. Then query the serving deployment with
  the first rows of that data, sent inline.

By default it uses `example_data/ad_tep/`, a sample of the Tennessee Eastman chemical
process: 33 process variables sampled every 3 minutes, with six kinds of process fault.
```bash
python -m examples.agents.agent_ad_lifecycle --api_key=<YOUR_API_KEY>
```

Options:
- `--data_dir`: the data to use (see below). Defaults to `example_data/ad_tep`.
- `--n_neighbors`: the detector sizes to try, one trial each. Defaults to `5 10`.
- `--window_size` and `--step_size`: the window length and the distance between window
  starts, in samples. Default to `48` and `8`. Size the window to your sampling rate.
- `--threshold`: the anomaly score over which a window is flagged. Defaults to `1.215`.
  Lower flags more windows; higher raises fewer false alarms.
- `--rows_per_query` and `--num_queries`: the delivery rows in each serving query, and how
  many queries to send. Default to `96` and `3`.
- `--max_run_time_sec`: how long to wait on each step before giving up. Waits forever by default.
- `--api_endpoint`: the API endpoint, as for every example.

To use your own data, give `--data_dir` a folder with one subfolder per role. Files are CSV
(or gzipped CSV) with the timestamp first, then the sensor columns:

| folder | content | labels |
|---|---|---|
| `library/` | training data, normal operation only | none: every row is `normal` |
| `validation/` | scores each optimization trial | a `label` column, `normal` or `anomaly` |
| `test/` | held-out data the promoted blueprint is evaluated on | a `label` column, `normal` or `anomaly` |
| `delivery/` | new data the deployed agent runs on | none |

Each window takes the label of its last row. Validation and test data must hold both
labels. Keep the sampling rate regular: the agent marks a window with an irregular
sampling rate as invalid and makes no prediction for it. Optimizations and evals count
an invalid window as a miss, which lowers the score.

To join several recordings in one file, leave a time gap between them, so that no window
mixes two recordings. Each gap costs about `window_size / step_size` invalid windows. To
avoid that cost, give each recording its own file.

For more on preparing AD data, see the anomaly discovery skills in
[archetypeai/agent-skills](https://github.com/archetypeai/agent-skills).

### Develop, Build, Deploy and Run a RED Agent
Takes a Rare Event Detection (RED) agent through its full lifecycle on your data:
- **Develop:** upload the data. Copy the `red` blueprint into a project and optimize it: each
  trial averages the windows of each training class into one prototype, and is scored on
  labeled validation data. Promote the best trial to a blueprint of your own, then evaluate
  that blueprint on held-out test data.
- **Build:** package the promoted blueprint.
- **Deploy:** deploy the package as `batch`, and later as `serving`.
- **Run:** run a batch session on new, unlabeled data. Then query the serving deployment with
  the first rows of that data, sent inline.

By default it uses `example_data/red_pump/`, a sample of a water pump's sensor data:
10 channels sampled once a minute, with four breakdowns. The dataset declares no licence;
see its README for the attribution.
```bash
python -m examples.agents.agent_red_lifecycle --api_key=<YOUR_API_KEY>
```

Options:
- `--data_dir`: the data to use (see below). Defaults to `example_data/red_pump`.
- `--background`: the class that means no event happened. Defaults to `normal`.
- `--metrics`: the distances to the class prototypes to try, one trial each. Defaults to
  `cosine l1`. The others are `l2` and `dot`.
- `--window_size` and `--step_size`: the window length and the distance between window
  starts, in samples. Default to `64` and `1`. Size the window to your events: an event
  shorter than half a window is hard to detect.
- `--rows_per_query` and `--num_queries`: the delivery rows in each serving query, and how
  many queries to send. Default to `96` and `3`.
- `--max_run_time_sec`: how long to wait on each step before giving up. Waits forever by default.
- `--api_endpoint`: the API endpoint, as for every example.

The optimization ranks trials by `foreground_macro_f1`, the F1 over the event classes
alone. Events are rare, so accuracy and `macro_f1` mostly score the background.

To use your own data, give `--data_dir` a folder with one subfolder per role. Files are CSV
(or gzipped CSV) with the timestamp first, then the sensor columns:

| folder | content | labels |
|---|---|---|
| `library/` | training data, one class per file, named `<class>__<name>.csv`: the background and each event | by file name |
| `validation/` | scores each optimization trial | a `label` column, one of the classes |
| `test/` | held-out data the promoted blueprint is evaluated on | a `label` column, one of the classes |
| `delivery/` | new data the deployed agent runs on | none |

Each window takes the label of its last row. Validation and test data must hold the
background and at least one event. Keep the sampling rate regular and leave no gap
inside a file: the agent marks a window with an irregular sampling rate as invalid and
makes no prediction for it. Optimizations and evals count an invalid window as a miss,
which lowers the score. Keep each row in one role only.

For more on preparing RED data, see the rare event detection skills in
[archetypeai/agent-skills](https://github.com/archetypeai/agent-skills).

## Unit Tests
You can run the unit tests for the python client by running the following in your terminal:
```bash
pip install -e '.[test]'
ATAI_API_KEY="your api key" ATAI_API_ENDPOINT="your api endpoint" python -m pytest .
```

## Requirements
* An Archetype AI developer key (request one at https://www.archetypeai.io)
* Python 3.10 or higher.
