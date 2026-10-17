# Pentium M Branch Outcome Predictor (CBP2 infrastructure)

Implementation of the `pm_predictor` class in `src/my_predictor.h`: a hybrid of
a 4096-entry bimodal table and a 512-set, 4-way tagged global predictor. When
the global predictor hits, it overrides the bimodal prediction, as in the
Pentium M.

## Build and run

```
cd src
make -B CXXFLAGS='-O3 -Wall'   # builds without debug symbols
cd ..
csh ./run traces        # MPKI for every trace and the average
./src/predict traces/164.gzip/gzip.trace.bz2      # a single trace
```

* `run` is a csh script. If it is not executable, start it with `csh ./run traces`
  or run `chmod +x run`.
* `trace.cc` passes the trace path to `bzip2` without quoting it, so the
  trace argument must not contain spaces. Use relative paths as above, or a symlink.

Build options (add them to `CXXFLAGS` in `src/Makefile`):

| flag | effect |
|---|---|
| `-DPM_GLOBAL_WAYS=2` | 2-way global predictor instead of 4-way |
| `-DPM_ALLOCATE_ALWAYS` | allocate a global entry on every global miss, not only when the bimodal predictor was wrong |

## Files

| file | contents |
|---|---|
| `src/my_predictor.h` | `pm_predictor` (this assignment); the sample `gshare_predictor` is unchanged |
| `results_pm4.txt` | output of `./run traces` with the default (4-way) predictor |
| `results_comparison.txt` | MPKI of all predictor variants on all 20 traces |
| `../Branch-Prediction-Solution.pdf` (also `.docx`) | assignment report |
