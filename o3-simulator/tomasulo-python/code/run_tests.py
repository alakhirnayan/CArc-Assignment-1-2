# Correctness check for every test case at issue widths 1-4.
#
# Each input is also executed by a plain in-order interpreter (no timing).
# The out-of-order machine must end with the same registers and memory and
# commit exactly the same instruction sequence, at every issue width.
#
# usage: python run_tests.py [input_file ...]   (default: test_case.txt tests/*.txt)

import glob
import sys
from init import build_machine
from exe import alu
from main import run


def reference(path):
    m = build_machine(path, 1)
    trace = []
    pc = 0
    while pc < len(m.program):
        instr = m.program[pc]
        trace.append(pc)
        if len(trace) > 100000:
            raise RuntimeError('reference run does not terminate')
        a = m.reg_value(instr.src1) if instr.src1 else 0
        b = m.reg_value(instr.src2) if instr.src2 else 0
        if instr.is_branch:
            taken = (a == b) if instr.op == 'beq' else (a != b)
            pc = pc + 1 + instr.imm if taken else pc + 1
            continue
        if instr.is_load:
            m.set_reg(instr.dest, m.memory.get(a + instr.imm, 0.0))
        elif instr.is_store:
            m.memory[a + instr.imm] = b
        else:
            m.set_reg(instr.dest, alu(instr.op, a, instr.imm if instr.op == 'addi' else b))
        pc += 1
    return m, trace


def nonzero(memory):
    return {a: v for a, v in memory.items() if v != 0}


def main(paths):
    failures = 0
    print('%-36s %6s %6s %6s %6s   %s' % ('test', 'w=1', 'w=2', 'w=3', 'w=4', '(cycles)'))
    for path in paths:
        ref, trace = reference(path)
        cycles = []
        for width in (1, 2, 3, 4):
            m = build_machine(path, width)
            n = run(m)
            ok = (m.reg_int == ref.reg_int and m.reg_fp == ref.reg_fp
                  and nonzero(m.memory) == nonzero(ref.memory)
                  and [e.instr.pc for e in m.committed] == trace)
            cycles.append(str(n) if ok else 'FAIL')
            failures += not ok
        print('%-36s %6s %6s %6s %6s' % ((path,) + tuple(cycles)))
    print('all tests passed' if failures == 0 else '%d failures' % failures)
    return failures


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['test_case.txt'] + sorted(glob.glob('tests/*.txt'))))
