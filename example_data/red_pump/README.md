# RED lifecycle example data (pump breakdowns)

Input for `examples/agents/agent_red_lifecycle.py`: one water pump, sampled once a
minute, with four breakdowns. Each file has a `timestamp` column (epoch seconds), then
10 sensor channels: `sensor_02` to `sensor_05`, `sensor_10` to `sensor_12`, `sensor_38`,
`sensor_41` and `sensor_42`. The classes are `normal` (the background) and
`pump_breakdown` (the rare event).

| file | role | labels |
|---|---|---|
| `library/normal__red_pump_library.csv.gz` | training: 8,192 rows of normal operation | `normal`, by file name |
| `library/pump_breakdown__red_pump_inc<NN>.csv.gz` | training: breakdowns 1 (945 rows) and 2 (3,111 rows), one per file | `pump_breakdown`, by file name |
| `validation/red_pump_validation.csv.gz` | scores each optimization trial: breakdown 3 (1,313 rows) with normal operation either side | `label` column |
| `test/red_pump_test.csv.gz` | held-out eval of the promoted blueprint: breakdown 4 (606 rows) with normal operation either side | `label` column |
| `delivery/red_pump_delivery.csv.gz` | run through the deployed bundle: breakdown 4 again, with 1,024 rows either side | none |

Breakdown rows are 15% of the validation file and 7% of the test file, so accuracy
says little: the example optimizes the F1 over the event class alone.

No row is in two of training, validation and test. The delivery file is a slice of the
test file, as an operator re-running a known incident would see it. Each file is an
exact one-minute grid with no gap. Every value is z-scored with the mean and standard
deviation of the normal rows before the validation file.

## Source and attribution

Derived from the **pump_sensor_data** dataset ("Pump sensor data for predictive
maintenance"), published on Kaggle by the user
[`nphantawee`](https://www.kaggle.com/nphantawee) on 2019-03-04:

- Dataset: [kaggle.com/datasets/nphantawee/pump-sensor-data](https://www.kaggle.com/datasets/nphantawee/pump-sensor-data)
- Provenance: the uploader describes it as the raw sensor data of a water pump looked
  after by a friend's small operations team, which failed seven times in one year.
  Credit for the underlying data belongs to that team.
- Licence: **none is declared.** The uploader selected no licence on the dataset page,
  so there is no explicit grant of commercial use.

The uploader and the operations team are not involved in this example and do not
endorse it.

**Changes made:** taken from the sample data of the RED data-prep skill in
[archetypeai/agent-skills](https://github.com/archetypeai/agent-skills), which keeps the
first 82,492 rows (the first four breakdowns) and 15 of the 52 sensor channels. From
those, the skill's `prepare.py` and `build_roles.py` map `BROKEN` and `RECOVERING` to
`pump_breakdown` and `NORMAL` to `normal`, keep the 10 channels above, interpolate
short runs of missing values, z-score every channel and cut the role files above.
These files rename the role files, leave out the delivery labels and gzip each file.
The original remains available at the Kaggle link above.
