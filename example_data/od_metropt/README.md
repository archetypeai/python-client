# OD example data (metro train air compressor)

Input for `examples/agents/agent_od.py`: three weeks of the air-production unit of one
Porto metro train, from 2020-07-01 to 2020-07-21. The file has no labels. The
operator's maintenance reports list one air leak in it, on 2020-07-15 from 14:30 to
19:00.

| file | content |
|---|---|
| `metropt_compressor_2020-07.csv.gz` | 147,518 rows, one every 10 seconds, about 17 days of data: a `timestamp` column (epoch seconds), then 7 channels |

The train is out of service at times, so the file has 46 gaps longer than 10 seconds.
A window that crosses a gap is marked invalid.

| channel | what it measures |
|---|---|
| `TP2` | pressure at the compressor (bar) |
| `TP3` | pressure at the pneumatic panel (bar) |
| `H1` | pressure drop when the cyclonic separator filter discharges (bar) |
| `DV_pressure` | pressure drop when the air-dryer towers discharge (bar) |
| `Reservoirs` | pressure downstream of the reservoirs (bar) |
| `Oil_temperature` | the compressor's oil temperature (°C) |
| `Motor_current` | current of one motor phase (A) |

## Source and attribution

Derived from the **MetroPT-3 Dataset**:

> Davari, N., Veloso, B., Ribeiro, R., & Gama, J. (2021). *MetroPT-3 Dataset* [Dataset].
> UCI Machine Learning Repository. https://doi.org/10.24432/C5VW3R

- Source: [archive.ics.uci.edu/dataset/791/metropt+3+dataset](https://archive.ics.uci.edu/dataset/791/metropt+3+dataset)
- Licence: [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
  This file keeps that licence. The client's own licence does not apply to it.

The dataset's creators and their institutions are not involved in this example and do
not endorse it.

**Changes made:** the raw samples are snapped to a 10-second grid. Holes of up to
50 seconds are filled with the last value, and longer gaps are left as gaps. Stretches
where every channel stayed unchanged for 30 minutes or more (the logger froze) are
removed. Only the 7 analog channels are kept. Timestamps are seconds since 1970, on the
dataset's own clock. The file is gzipped.
