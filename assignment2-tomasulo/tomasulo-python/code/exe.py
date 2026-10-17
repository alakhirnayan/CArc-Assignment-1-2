# Qing
# 24th May 2017
# Multi-issue version.

'''
1. start ready instructions on free functional units, oldest first
    -- an RS is released when its instruction starts EX
    -- ld/sd compute their address on the dedicated address adders
2. finish instructions whose EX ends this cycle
    -- ALU: compute the result (broadcast later in WB)
    -- ld/sd: write the address into the ld/sd queue; a store whose address is
       now known checks younger loads that already read a stale value
    -- branch: resolve, train the BTB, squash on a misprediction
3. a bad address or branch target only marks the instruction; the error is
   raised if it reaches commit, so a wrong-path fault is simply squashed
'''
from collections import deque
from init import BTB_SIZE, MEMORY_SIZE


# function: compute an ALU result
def alu(op, a, b):
    if op in ('add', 'addi'):
        return int(a + b)
    if op == 'sub':
        return int(a - b)
    if op == 'add.d':
        return a + b
    if op == 'sub.d':
        return a - b
    if op in ('mult.d', 'mul.d'):
        return a * b
    raise ValueError(op)


# function: give each ready instruction a free unit, oldest first
def dispatch(entries, units, cycle):
    started = []
    for entry in sorted(entries, key=lambda e: e.seq):
        unit = next((u for u in units if u.can_start(cycle)), None)
        if unit is None:
            break
        unit.start(entry, cycle)
        started.append(entry)
    return started


# function: squash every instruction younger than `keep_seq`, refetch at `new_pc`
def squash_after(m, keep_seq, new_pc, cycle):
    for entry in m.rob:
        if entry.seq > keep_seq:
            entry.squashed = True
            m.squashed.append(entry)
    m.rob = deque(e for e in m.rob if not e.squashed)
    # clear reservation stations, ld/sd queue, busy units
    for unit in m.rs:
        m.rs[unit] = [None if (e is not None and e.squashed) else e for e in m.rs[unit]]
    m.ld_sd_queue = [e for e in m.ld_sd_queue if not e.squashed]
    for units in m.fus.values():
        for u in units:
            if u.current is not None and u.current.squashed:
                u.busy_until = cycle
                u.current = None
    if m.mem_owner is not None and m.mem_owner.squashed:
        m.mem_busy_until = cycle
        m.mem_owner = None
    # recover the RAT from the surviving ROB entries
    m.rat = {}
    for entry in m.rob:
        if entry.instr.dest is not None and entry.instr.dest != 'R0':
            m.rat[entry.instr.dest] = entry
    # recovery takes this cycle + 1; correct fetch starts at cycle + 2
    m.pc = new_pc
    m.fetch_resume = cycle + 2


# function: a store address is known; find younger loads that read a stale value
def check_memory_order(m, store, cycle):
    stale = [e for e in m.rob
             if e.instr.is_load and e.seq > store.seq and e.mem_start is not None
             and e.addr == store.addr and e.source_seq < store.seq]
    if stale:
        load = min(stale, key=lambda e: e.seq)
        m.memory_violations += 1
        squash_after(m, load.seq - 1, load.instr.pc, cycle)


# function: resolve a branch at the end of EX
def resolve_branch(m, entry, cycle):
    instr = entry.instr
    a, b = entry.op1.value, entry.op2.value
    taken = (a == b) if instr.op == 'beq' else (a != b)
    target = instr.pc + 1 + instr.imm
    if taken and target < 0:
        # fault: stop fetching; raised at commit unless an older branch squashes it
        entry.fault = 'branch target out of range in "%s"' % instr.text
        squash_after(m, entry.seq, len(m.program), cycle)
        return
    entry.actual_next = target if taken else instr.pc + 1
    m.btb[instr.pc % BTB_SIZE] = {'pc': instr.pc, 'target': target, 'taken': taken}
    if entry.actual_next != entry.pred_next:
        entry.mispredicted = True
        m.mispredictions += 1
        squash_after(m, entry.seq, entry.actual_next, cycle)


def exe(m, cycle):
    '''start new work'''
    for unit in ('int', 'fpadd', 'fpmul'):
        ready = [e for e in m.rs[unit]
                 if e is not None and e.issue < cycle
                 and e.op1.is_ready(cycle) and e.op2.is_ready(cycle)]
        for entry in dispatch(ready, m.fus[unit], cycle):
            m.rs[unit][m.rs[unit].index(entry)] = None
    ready = [e for e in m.ld_sd_queue
             if e.ex_start is None and e.issue < cycle and e.op1.is_ready(cycle)]
    dispatch(ready, m.fus['ldsd'], cycle)

    '''finish work whose EX ends this cycle'''
    for entry in sorted(m.rob, key=lambda e: e.seq):
        if entry.squashed or entry.ex_end != cycle:
            continue
        instr = entry.instr
        if instr.unit == 'ldsd':
            addr = entry.op1.value + instr.imm
            if 0 <= addr < MEMORY_SIZE:
                entry.addr = addr
                if instr.is_store:
                    check_memory_order(m, entry, cycle)
            else:
                entry.fault = 'address %d out of range in "%s"' % (addr, instr.text)
        elif instr.is_branch:
            resolve_branch(m, entry, cycle)
        else:
            b = instr.imm if instr.op == 'addi' else entry.op2.value
            entry.result = alu(instr.op, entry.op1.value, b)
