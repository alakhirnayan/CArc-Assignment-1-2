# Computer Architecture — Programming Assignments

Al-Akhir Nayan · PSID 2371302

| Assignment | Report | Code and README |
|---|---|---|
| 1. Pentium M branch predictor | [BranchPredictionReport.pdf](branch-prediction/BranchPredictionReport.pdf) | [cbp2-infrastructure-v2/](branch-prediction/cbp2-infrastructure-v2/) |
| 2. Tomasulo algorithm with multiple issue | [TomasuloReport.pdf](o3-simulator/TomasuloReport.pdf) | [tomasulo-python/](o3-simulator/tomasulo-python/) |

Each report is also included as a `.docx`. Run either command block below from
the repository root.

## Assignment 1: branch predictor

The predictor is the `pm_predictor` class in `src/my_predictor.h`: a 4096-entry
bimodal table plus a 512-set, 4-way tagged global predictor. Average: 5.848 MPKI
over the 20 traces.

```
cd branch-prediction/cbp2-infrastructure-v2/src
make -B CXXFLAGS='-O3 -Wall'
cd ..
csh ./run traces
```

## Assignment 2: Tomasulo simulator

A Python simulator with issue width 1–4, ROB, RAT, reservation stations, a
load/store queue with store forwarding and memory-order replay, and a 1-bit
predictor with an 8-entry BTB. It needs Python 3 and no packages.

```
cd o3-simulator/tomasulo-python/code
python3 main.py tests/03_loop_branch.txt -w 2    # one program, issue width 2
python3 run_tests.py                             # all 14 programs at widths 1-4 (56 runs)
python3 -m unittest -v test_memory_rules          # memory-rule regression checks
```

The test inputs are in `code/tests/`, and the output of every test at every
issue width is in `results/`.

AI use: I used an AI assistant (Claude) to help with the code and the reports,
as permitted for these assignments.
