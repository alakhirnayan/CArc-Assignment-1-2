# Qing
# 21st May 2017
# Multi-issue version.
#
# usage: python main.py [input_file] [-w ISSUE_WIDTH] [-c CDB_WIDTH] [-s]
#   input_file   configuration + initial values + program (default: test_case.txt)
#   -w N         issue width 1-4, overrides "Issue width = N" in the file
#   -c N         number of CDBs, overrides "CDB width = N" in the file
#   -s           also list squashed instructions (wrong path or memory-order replay)

import argparse
from init import build_machine
from issue import issue
from exe import exe
from mem import mem
from wb import wb
from commit import commit
from print_status import print_report

MAX_CYCLES = 100000


def run(m):
    '''
    Every hand-off between stages is time-stamped (an operand broadcast in
    cycle c is usable in c+1, an instruction issued in c starts EX in c+1 at
    the earliest, ...), so the call order below only decides who wins a
    shared resource inside one cycle:
      - MEM before COMMIT: a load can still forward from a store that commits
        in the same cycle, and loads get the memory port before stores.
      - ISSUE last: an RS freed at EX start or a ROB entry freed at commit can
        be reused by an instruction issued in the same cycle.
    '''
    cycle = 1
    while True:
        mem(m, cycle)
        commit(m, cycle)
        wb(m, cycle)
        exe(m, cycle)
        issue(m, cycle)
        # done when everything has committed and the last store write has finished
        if not m.rob and m.pc >= len(m.program) and m.mem_busy_until <= cycle:
            return cycle
        cycle += 1
        if cycle > MAX_CYCLES:
            raise RuntimeError('no progress after %d cycles' % MAX_CYCLES)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Multi-issue Tomasulo simulator')
    parser.add_argument('input', nargs='?', default='test_case.txt')
    parser.add_argument('-w', '--width', type=int, default=None)
    parser.add_argument('-c', '--cdb', type=int, default=None)
    parser.add_argument('-s', '--squashed', action='store_true')
    args = parser.parse_args()
    machine = build_machine(args.input, args.width, args.cdb)
    cycles = run(machine)
    print_report(machine, cycles, args.squashed)
