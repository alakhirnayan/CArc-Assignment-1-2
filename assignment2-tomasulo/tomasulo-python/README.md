# Tomasulo Algorithm Simulation (multi-issue)

Out-of-order processor simulator with a ROB, a RAT, reservation stations, a
load/store queue with speculative loads and memory-order recovery, a 1-bit
branch predictor with an 8-entry BTB, and in-order issue of 1–4 instructions
per cycle.

* Instructions: `Ld`, `Sd`, `Beq`, `Bne`, `Add`, `Addi`, `Sub`, `Add.d`, `Sub.d`, `Mult.d` (case insensitive, commas optional)
* Pipeline: ISSUE, EX, MEM, WB, COMMIT
* Everything is configured from the input file (see `code/test_case.txt`)

## How to run

Requires Python 3 (no packages).

```
cd code
python3 main.py                              # runs test_case.txt
python3 main.py tests/03_loop_branch.txt     # any input file
python3 main.py tests/03_loop_branch.txt -w 4 -s
python3 run_tests.py                         # correctness check, all tests, widths 1-4
```

Options:

| option | meaning |
|---|---|
| `-w N` | issue width 1–4 (overrides `Issue width = N` in the file; default 1) |
| `-c N` | number of CDBs (overrides `CDB width = N`; default 1) |
| `-s` | also list squashed instructions (wrong path or memory-order replay) |

## Input file

```
                # of rs         Cycles in EX    Cycles in Mem   # of FUs
Integer adder   4               1                               1
FP adder        3               4                               1
FP multiplier   2               15                              1
Load/store unit 5               1               5               1

ROB entries = 64
Issue width = 2          # optional, 1-4, default 1
CDB width = 1            # optional, default 1
Commit width = 2         # optional, default = issue width
R1=8, F20=3.0
Mem[4]=3.0, Mem[8]=2.0

Ld F2 0(R1)
Mult.d F4 F2 F20
Addi R1 R1 -4
Bne R1 R0 -4             # target = PC + 4 + offset*4
```

Text after `#` is a comment. Registers and memory start at zero.

## Files

| file | contents |
|---|---|
| `code/main.py` | command line, cycle loop |
| `code/init.py` | data structures, machine state, input parser |
| `code/issue.py` | multi-issue, renaming, branch prediction (BTB) |
| `code/exe.py` | functional units, address calculation, memory-order checks, branch resolution and squash |
| `code/mem.py` | store-to-load forwarding, speculative memory access for loads |
| `code/wb.py` | CDB broadcast |
| `code/commit.py` | in-order commit, stores write memory, faults raised at commit |
| `code/print_status.py` | output (instruction table, registers, non-zero memory) |
| `code/run_tests.py` | checks every test against an in-order reference interpreter at widths 1–4 |
| `code/tests/` | test cases |
| `results/` | simulator output for every test at widths 1–4 |
| `original_code/` | the single-issue code this work started from |
| `../Tomasulo-Simulator-Solution.pdf` (also `.docx`) | assignment report |

## Behaviour notes

* Loads follow the assignment: a load forwards from the youngest older store
  with a known matching address, otherwise it reads memory even if some older
  store addresses are still unknown. When such a store's address is computed
  and matches a load that already read memory, that load and everything after
  it are squashed and refetched (counted as a memory-order violation).
* An out-of-range address or branch target is recorded on the instruction and
  raised only if that instruction reaches commit, so wrong-path faults are
  squashed silently.
* The cycle total includes the memory write of the last committed store.

`python3 run_tests.py` runs 12 test programs at widths 1–4 (48 runs); all
match the in-order reference interpreter.
