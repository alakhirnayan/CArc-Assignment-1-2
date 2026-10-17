"""Regression tests for the assignment's unresolved-store memory rule.
Run: python3 -m unittest -v test_memory_rules
"""
from pathlib import Path
import random
import tempfile
import unittest

from init import build_machine
from main import run
from run_tests import reference, nonzero

TESTS = Path(__file__).with_name('tests')


class MemoryRuleTests(unittest.TestCase):
    def simulate(self, path, width):
        m = build_machine(str(path), width)
        run(m)
        ref, trace = reference(str(path))
        self.assertEqual(m.reg_int, ref.reg_int)
        self.assertEqual(m.reg_fp, ref.reg_fp)
        self.assertEqual(nonzero(m.memory), nonzero(ref.memory))
        self.assertEqual([e.instr.pc for e in m.committed], trace)
        self.assertFalse(m.rat)
        self.assertTrue(all(not e.squashed for e in m.committed))
        return m

    def test_unknown_address_takes_priority_over_known_match(self):
        for width in range(1, 5):
            with self.subTest(width=width):
                m = self.simulate(TESTS / '12_unknown_with_match.txt', width)
                load = min((e for e in m.committed + m.squashed
                            if e.instr.is_load), key=lambda e: e.seq)
                stores = [e for e in m.committed if e.instr.is_store]
                self.assertFalse(load.forwarded)
                self.assertEqual(load.result, 2.0)
                self.assertLess(load.mem_start, stores[0].ex_end)
                self.assertGreater(load.mem_start, stores[1].ex_end)
                self.assertTrue(load.squashed)
                self.assertEqual(m.reg_fp[3], 11.0)
                self.assertEqual(m.memory_violations, 1)

    def test_bypassed_known_store_rechecks_at_commit(self):
        for width in range(1, 5):
            with self.subTest(width=width):
                m = self.simulate(TESTS / '13_bypassed_known_store.txt', width)
                load = min((e for e in m.committed + m.squashed
                            if e.instr.is_load), key=lambda e: e.seq)
                stores = [e for e in m.committed if e.instr.is_store]
                self.assertEqual(stores[0].addr, 8)
                self.assertEqual(stores[1].addr, load.addr)
                self.assertGreater(load.mem_start, stores[1].ex_end)
                self.assertLess(load.mem_start, stores[0].ex_end)
                self.assertTrue(load.squashed)
                self.assertIsNone(load.commit)
                self.assertEqual(m.memory_violations, 1)
                self.assertEqual(m.reg_fp[3:5], [11.0, 22.0])
                self.assertEqual(m.memory[12], 22.0)
                self.assertTrue(all(e.mem_start is None for e in m.squashed
                                    if e.instr.is_store))
                replay = next(e for e in m.committed if e.instr.is_load)
                self.assertGreater(replay.mem_start, stores[1].mem_end)

    def test_known_addresses_still_allow_one_cycle_forwarding(self):
        for width in range(1, 5):
            with self.subTest(width=width):
                m = self.simulate(TESTS / '04_store_load_forwarding.txt', width)
                forwarded = [e for e in m.committed if e.instr.is_load and e.forwarded]
                self.assertTrue(forwarded)
                self.assertTrue(all(e.mem_start == e.mem_end for e in forwarded))

    def test_generated_programs(self):
        # Fixed seed makes failures reproducible. Vary resource pressure and
        # dependencies while comparing state and retirement order, not timings.
        rng = random.Random(20261017)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mixed.txt'
            for case in range(30):
                lines = [
                    'Integer adder 4 %d %d' % (rng.randint(1, 6), rng.randint(1, 2)),
                    'FP adder 4 3 1', 'FP multiplier 3 5 1',
                    'Load/store unit %d 1 %d %d' %
                    (rng.randint(2, 8), rng.randint(1, 8), rng.randint(1, 2)),
                    'ROB entries = %d' % rng.randint(4, 24),
                    'CDB width = %d' % rng.randint(1, 4),
                    'F1=1, F2=2, F3=3, F4=4, F5=5, F6=6',
                    'Mem[0]=10, Mem[4]=20, Mem[8]=30, Mem[12]=40',
                ]
                for _ in range(32):
                    op = rng.randrange(6)
                    f, a, b = [rng.randint(1, 6) for _ in range(3)]
                    r = rng.randint(1, 3)
                    if op == 0:
                        line = 'Addi R%d R0 %d' % (r, 4 * rng.randrange(4))
                    elif op == 1:
                        line = 'Sd F%d 0(R%d)' % (f, r)
                    elif op == 2:
                        line = 'Ld F%d 0(R%d)' % (f, r)
                    elif op == 3:
                        line = 'Add.d F%d F%d F%d' % (f, a, b)
                    elif op == 4:
                        line = 'Mult.d F%d F%d F%d' % (f, a, b)
                    else:
                        line = 'Beq R0 R0 1'
                    lines.append(line)
                path.write_text('\n'.join(lines) + '\n')
                for width in range(1, 5):
                    with self.subTest(program=case, width=width):
                        self.simulate(path, width)


if __name__ == '__main__':
    unittest.main()
