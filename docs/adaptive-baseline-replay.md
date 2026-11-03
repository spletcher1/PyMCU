# Adaptive baseline: replay of recorded data

Written by `scripts/replay_baseline.py` on 2026-11-01, for [adaptive-baseline-plan.md](adaptive-baseline-plan.md) stage S3. Every record of every DFM below went through `BaselineTracker` with `BaselineRatePerHour: 5` and `BaselineCapCounts: 50`, and the Baseline in force was rebuilt from the updates PyMCU would have sent. Contact is the DFM's test, signal above Baseline + 20, compared with the fixed Starting baseline.

## Data

9 recordings, 65 DFMs, 780 Wells:

- `Scott/MBON02/Rep1_Training10.ProgAssay_14April25`
- `Scott/MBON02/Rep2_Training10.ProgAssay_16April25`
- `Scott/MBON09/Rep1_Training10.ProgAssay_68287_24Feb25`
- `Scott/MBON09/Rep2_Training10.ProgAssay_68287_26Feb25`
- `Scott/PAM05/Rep1_Training10.ProgAssay_68276_28April25`
- `Scott/PAM05/Rep2_Training10.ProgAssay_68276_30April25`
- `MBabap/Rep1_JChrimson68370_28Jan25`
- `MBabap/Rep2_JChrimson68370_30Jan25`
- `CantonS/FLICMCU_10_17_2026_00_17`

Sucrose Wells are the A Wells of paired chambers, Yeast Wells the B Wells, and Single Wells come from 12-chamber DFMs.

## Pass criteria

| | Criterion | Result |
|---|---|---|
| P1 | No contact run longer than 5 min on a Sucrose Well loses more than 1% of its records (209 runs on 64 Wells) | **fail** (2) |
| P2 | No Sucrose Well reaches the cap (384 Wells) | **fail** (3) |
| P3 | On drifting Yeast Wells, the Baseline in force stays within 12 counts of the reference resting level after the first 2 h (26 Wells) | **fail** (21) |

The reference resting level is the rolling 31-minute 10th percentile of a Well's per-minute Floors. A Well is a *step* Well if its reference moves more than 20 counts in 5 minutes, *drifting* if not and it moves 10 counts or more over the recording, and *flat* otherwise.

P1 failures, worst first:

| Recording | DFM | Well | WorstLongRunLost |
|---|---|---|---|
| `MBabap/Rep2_JChrimson68370_30Jan25` | 1 | 5 | 0.6292 |
| `MBabap/Rep1_JChrimson68370_28Jan25` | 1 | 5 | 0.0278 |

P3 failures, worst first:

| Recording | DFM | Well | MaxGapAfter2h |
|---|---|---|---|
| `Scott/PAM05/Rep2_Training10.ProgAssay_68276_30April25` | 2 | 12 | 27.2 |
| `MBabap/Rep2_JChrimson68370_30Jan25` | 4 | 11 | 20.4 |
| `MBabap/Rep2_JChrimson68370_30Jan25` | 6 | 10 | 20.0 |
| `MBabap/Rep2_JChrimson68370_30Jan25` | 7 | 1 | 20.0 |
| `Scott/PAM05/Rep1_Training10.ProgAssay_68276_28April25` | 5 | 4 | 19.0 |
| `Scott/MBON02/Rep2_Training10.ProgAssay_16April25` | 5 | 10 | 18.0 |
| `Scott/MBON02/Rep2_Training10.ProgAssay_16April25` | 5 | 2 | 17.0 |
| `MBabap/Rep2_JChrimson68370_30Jan25` | 4 | 3 | 17.0 |
| `Scott/MBON02/Rep2_Training10.ProgAssay_16April25` | 1 | 4 | 16.0 |
| `Scott/PAM05/Rep1_Training10.ProgAssay_68276_28April25` | 2 | 8 | 16.0 |

## Reported

Median / 90th percentile / maximum.

| Measure | Value |
|---|---|
| Updates per DFM per day | 2 / 4.98 / 7 |
| DFMs that sent no update | 21 of 65 |
| Sucrose Wells: flat / drifting / step | 368 / 1 / 15 |
| Sucrose Wells capped (up / down) | 0 / 3 |
| Sucrose Wells: largest gap, Baseline in force to reference, after 2 h | 0 / 2 / 155 |
| Sucrose Wells: share of records whose contact differs from the fixed baseline | 0 / 0 / 0.01 |
| Sucrose Wells whose Starting baseline was 10 or more above the floor | 3 |
| Yeast Wells: flat / drifting / step | 178 / 26 / 180 |
| Yeast Wells capped (up / down) | 3 / 1 |
| Yeast Wells: largest gap, Baseline in force to reference, after 2 h | 16 / 109.1 / 1016 |
| Yeast Wells: share of records whose contact differs from the fixed baseline | 0 / 0.01 / 0.55 |
| Yeast Wells whose Starting baseline was 10 or more above the floor | 1 |
| Single Wells: flat / drifting / step | 12 / 0 / 0 |
| Single Wells capped (up / down) | 0 / 0 |
| Single Wells: largest gap, Baseline in force to reference, after 2 h | 1 / 1 / 1 |
| Single Wells: share of records whose contact differs from the fixed baseline | 0 / 0 / 0 |
| Single Wells whose Starting baseline was 10 or more above the floor | 0 |

Per-Well results are in the CSV written beside the run (`--out`).
