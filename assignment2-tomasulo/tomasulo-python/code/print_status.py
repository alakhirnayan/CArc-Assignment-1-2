# Qing
# 21st May 2017
# Multi-issue version: final report (instruction status, registers, memory).


def span(start, end):
    if start is None:
        return '-'
    return '%d-%d' % (start, end)


def cell(value):
    return '-' if value is None else str(value)


def fmt(value):
    if isinstance(value, float):
        return '%g' % value
    return str(value)


def print_report(m, cycles, show_squashed=False):
    cfg = m.cfg
    print('Issue width = %d, CDB width = %d, commit width = %d, ROB entries = %d'
          % (cfg.issue_width, cfg.cdb_width, cfg.commit_width, cfg.rob_size))
    print()
    print(''.ljust(26) + 'ISSUE'.ljust(8) + 'EX'.ljust(10) + 'MEM'.ljust(10)
          + 'WB'.ljust(8) + 'COMMIT')
    for e in m.committed:
        print(e.instr.text.ljust(26) + cell(e.issue).ljust(8)
              + span(e.ex_start, e.ex_end).ljust(10)
              + span(e.mem_start, e.mem_end).ljust(10)
              + cell(e.wb).ljust(8) + cell(e.commit))
    if show_squashed and m.squashed:
        print()
        print('Squashed instructions (wrong path or memory-order replay):')
        for e in m.squashed:
            print('  ' + e.instr.text.ljust(24) + 'issued in cycle %d' % e.issue)

    print()
    print('REGISTER VALUES')
    for kind, regs in (('R', m.reg_int), ('F', m.reg_fp)):
        for base in range(0, 32, 8):
            print(''.ljust(7) + ''.join(('%s%d' % (kind, i)).ljust(9) for i in range(base, base + 8)))
            print('value: ' + ''.join(fmt(regs[i]).ljust(9) for i in range(base, base + 8)))

    print()
    print('NON-ZERO MEMORY VALUES')
    print('Addresses'.ljust(12) + 'Values')
    for addr in sorted(m.memory):
        if m.memory[addr] != 0:
            print(str(addr).ljust(12) + fmt(m.memory[addr]))

    print()
    n = len(m.committed)
    print('Cycles: %d   Committed instructions: %d   IPC: %.3f'
          % (cycles, n, n / cycles if cycles else 0))
    print('Branches issued: %d   Mispredicted: %d   Memory-order violations: %d   '
          'Squashed instructions: %d'
          % (m.branches, m.mispredictions, m.memory_violations, len(m.squashed)))
