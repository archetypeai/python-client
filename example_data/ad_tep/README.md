# AD lifecycle example data (Tennessee Eastman Process)

Input for `examples/agents/agent_ad_lifecycle.py`: 35 simulation runs of the Tennessee
Eastman chemical process, sampled every 3 minutes. Each file has a `timestamp` column
(epoch seconds), then 33 continuous process variables: `xmeas_1` to `xmeas_22`
(measurements) and `xmv_1` to `xmv_11` (controller outputs).

| file | role | labels |
|---|---|---|
| `library/normal_25h_run<NN>.csv.gz` | training: 10 fault-free 25-hour runs, one per file | all `normal` |
| `validation/ad_tep_validation.csv.gz` | scores each optimization trial: 5 fault-free 48-hour runs, then one run of each fault | `label` column |
| `test/ad_tep_test.csv.gz` | held-out eval of the promoted blueprint: 1 fault-free run, then one run of each fault | `label` column |
| `delivery/ad_tep_delivery.csv.gz` | run through the deployed bundle: 1 fault-free run, then one run of each fault | none |

The six faults are IDV 1 and 2 (step changes), IDV 5 (a step the controllers absorb),
IDV 10 (random variation), IDV 13 (a slow drift) and IDV 15 (a sticking valve, which is
hard to detect). Each faulty run is 8 hours of normal operation, then the fault: `label`
is `anomaly` from the 161st sample on.

The runs in one file are joined in the order above, with a one-day gap between them.
The agent marks a window that spans a gap as invalid and makes no prediction for it, so
a window never mixes two runs. Optimizations and evals count each invalid window as a
miss: at a window of 48 and a step of 8, each gap costs 5 windows. Every value is z-scored with the mean and standard deviation of
the library runs.

## Source and attribution

Derived from **Additional Tennessee Eastman Process Simulation Data for Anomaly
Detection Evaluation**, by Cory A. Rieth, Ben D. Amsel, Randy Tran and Maia B. Cook:

- Dataset: Harvard Dataverse, 2017, [doi:10.7910/DVN/6C3JR1](https://doi.org/10.7910/DVN/6C3JR1)
- Licence: dedicated to the public domain by its user agreement, which allows copying,
  modifying and distributing the work without permission
- Original process: J. J. Downs and E. F. Vogel, "A plant-wide industrial process control
  problem", *Computers & Chemical Engineering* 17(3), 1993, 245–255.

The authors are not involved in this example and do not endorse it.

**Changes made:** taken from the sample data of
[archetypeai/agent-skills](https://github.com/archetypeai/agent-skills), which selects
35 runs, keeps 33 of the 52 variables, adds timestamps and derives a per-row label from
the documented fault onset. From those, these files join each scored role's runs into
one file, z-score every variable and remove the delivery file's labels.
