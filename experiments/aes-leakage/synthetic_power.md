# Synthetic power and false-positive tables

Synthetic data from `synth_run()`; NOT gem5 results. `delta` is the latency rise (cycles) of a set whose table line was touched, `noise` the per-probe standard deviation (cycles); every touched line is visible (visibility 1.0).

## Power of the preregistered decision rule

| mode | delta | N | reps | mean bytes sig. p_xor_k (of 16) | mean bytes sig. last round (of 16) | frac round1 supported | frac last round supported |
|---|---|---|---|---|---|---|---|
| round1 | 40 | 250 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 40 | 500 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 40 | 1000 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 40 | 2000 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 40 | 4000 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 10 | 250 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 10 | 500 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 10 | 1000 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 10 | 2000 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 10 | 4000 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 4 | 250 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 4 | 500 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 4 | 1000 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 4 | 2000 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| round1 | 4 | 4000 | 6 | 16.0 | 0.0 | 1.00 | 0.00 |
| full | 40 | 250 | 6 | 16.0 | 0.2 | 1.00 | 0.17 |
| full | 40 | 500 | 6 | 16.0 | 0.3 | 1.00 | 0.33 |
| full | 40 | 1000 | 6 | 16.0 | 1.5 | 1.00 | 1.00 |
| full | 40 | 2000 | 6 | 16.0 | 3.2 | 1.00 | 1.00 |
| full | 40 | 4000 | 6 | 16.0 | 11.2 | 1.00 | 1.00 |
| full | 10 | 250 | 6 | 2.0 | 0.0 | 1.00 | 0.00 |
| full | 10 | 500 | 6 | 6.8 | 0.0 | 1.00 | 0.00 |
| full | 10 | 1000 | 6 | 15.2 | 0.0 | 1.00 | 0.00 |
| full | 10 | 2000 | 6 | 16.0 | 0.2 | 1.00 | 0.17 |
| full | 10 | 4000 | 6 | 16.0 | 0.2 | 1.00 | 0.17 |
| full | 4 | 250 | 6 | 0.2 | 0.0 | 0.17 | 0.00 |
| full | 4 | 500 | 6 | 0.3 | 0.0 | 0.33 | 0.00 |
| full | 4 | 1000 | 6 | 1.2 | 0.0 | 0.83 | 0.00 |
| full | 4 | 2000 | 6 | 6.0 | 0.0 | 1.00 | 0.00 |
| full | 4 | 4000 | 6 | 13.8 | 0.2 | 1.00 | 0.17 |

## False positives on data with no data dependence

| mode | N | reps | runs with any decision true | runs with any hypothesis significant |
|---|---|---|---|---|
| round1 | 1000 | 200 | 8 | 13 |
| full | 1000 | 200 | 7 | 8 |
