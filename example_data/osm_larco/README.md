# OSM lifecycle example data (LARCO)

Input for `examples/agents/agent_osm_lifecycle.py`: washing machine vibration, 9
accelerometer channels (`back`, `side`, `top` × `x`, `y`, `z`) at 200 Hz, labeled
`fill`, `wash`, `spin` or `drain`.

| file | role | labels |
|---|---|---|
| `library/<state>__osm_larco_library.csv.gz` | training: one state per file | the state, by file name |
| `validation/osm_larco_validation.csv.gz` | scores each optimization trial | `label` column |
| `test/osm_larco_test.csv.gz` | held-out eval of the promoted blueprint | `label` column |
| `delivery/osm_larco_delivery.csv.gz` | a second unit of the same model, run through the deployed bundle | none |

Each file is a time-ordered run of 1,024-row pieces (5.12 s), each piece a single
state, so a 512-row window never spans a time jump. Values are z-scored.

To go further on the same data, both repositories below build a `data/roles/` folder
in this same layout, which the example takes as `--data_dir`:

- [LARCO quickstart](https://github.com/archetypeai/operational-state-monitoring-agent-example-larco-quickstart):
  prepares the data from the raw dataset: 19 full cycles, about 0.45 GB of role files.
- [LARCO full study](https://github.com/archetypeai/operational-state-monitoring-agent-example-larco):
  199 cycles, a 16-trial search and a comparison with a simple baseline. Its role
  files total 25 GB.

## Source and attribution

Derived from the **LARCO** dataset, "Household Laundry Appliance Resource Consumption
and Operation Dataset", by Žygimantas Jasiūnas, João Alexandre Braz Ferreira, Tiago
Julião, José Cecílio, Guilherme Carrilho da Graça and Pedro M. Ferreira:

- Dataset: Zenodo, 2026, [doi:10.5281/zenodo.19666168](https://doi.org/10.5281/zenodo.19666168)
- Paper: *Scientific Data*, 2026, [doi:10.1038/s41597-026-07361-6](https://doi.org/10.1038/s41597-026-07361-6)
- Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

The authors are not involved in this example and do not endorse it.

**Changes made:** taken from the role files of
[archetypeai/operational-state-monitoring-agent-example-larco-quickstart](https://github.com/archetypeai/operational-state-monitoring-agent-example-larco-quickstart)
(commit `b7f0f66`), which selects 19 cycles of a Becken BWM5381IX, resamples the
vibration to an exact 200 Hz grid, derives one state per second and z-scores every
channel with the training cycles' statistics. From those, these files keep 15 pieces
per state for training and 6 per state for each of validation, test and delivery,
spread across each role's cycles, and the delivery file's labels are removed. Files
keep the role-folder layout and `label` column of the repositories above.
