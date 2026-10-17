# Qing
# 29th May 2017
# Multi-issue version.

'''
1. pick finished instructions, oldest first, up to `cdb_width` per cycle
    -- ALU ops: the cycle after EX ends; loads: the cycle after MEM ends
2. broadcast: write the value into the ROB and wake up every waiting operand
   (reservation stations, ld/sd queue base registers and store data)
'''


# function: has the instruction finished and is waiting for the CDB
def waiting_for_cdb(entry, cycle):
    instr = entry.instr
    if entry.wb is not None or instr.is_branch or instr.is_store:
        return False
    if instr.is_load:
        return entry.mem_end is not None and entry.mem_end < cycle
    return entry.ex_end is not None and entry.ex_end < cycle


# function: broadcast one result
def broadcast(m, producer, cycle):
    producer.wb = cycle
    producer.value = producer.result
    for entry in m.rob:
        for op in (entry.op1, entry.op2):
            if op.src is producer:
                op.value = producer.value
                op.src = None
                op.ready = cycle + 1


def wb(m, cycle):
    finished = [e for e in m.rob if waiting_for_cdb(e, cycle)]
    for entry in sorted(finished, key=lambda e: e.seq)[:m.cfg.cdb_width]:
        broadcast(m, entry, cycle)
