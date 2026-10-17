# Qing
# 29th may 2017
# Multi-issue version.
'''
Commit up to `commit_width` instructions per cycle from the ROB head, in order
    -- ALU / load: the cycle after WB; write the register file, free the RAT entry
    -- branch: the cycle after it is resolved
    -- store: address and data ready and the memory port free; the store
       writes memory starting in its commit cycle (MEM column) and leaves
       the ld/sd queue
    -- an instruction with a recorded fault raises the error here
'''

# function: try to commit the ROB head; return True on success
def commit_head(m, entry, cycle):
    instr = entry.instr
    if entry.fault is not None:
        # precise exception: only an instruction that reaches commit faults
        raise RuntimeError('cycle %d: %s' % (cycle, entry.fault))
    if instr.is_branch:
        return entry.ex_end is not None and entry.ex_end < cycle
    if instr.is_store:
        if entry.addr is None or entry.ex_end >= cycle:
            return False
        if not entry.op2.is_ready(cycle) or m.mem_busy_until >= cycle:
            return False
        entry.mem_start = cycle
        entry.mem_end = cycle + m.cfg.mem_cycles - 1
        m.mem_busy_until = entry.mem_end
        m.mem_owner = entry
        m.memory[entry.addr] = entry.op2.value
        m.ld_sd_queue.remove(entry)
        return True
    if entry.wb is None or entry.wb >= cycle:
        return False
    if instr.dest is not None:
        m.set_reg(instr.dest, entry.value)
        if m.rat.get(instr.dest) is entry:
            del m.rat[instr.dest]
    return True


def commit(m, cycle):
    for _ in range(m.cfg.commit_width):
        if not m.rob or not commit_head(m, m.rob[0], cycle):
            return
        entry = m.rob.popleft()
        entry.commit = cycle
        m.committed.append(entry)
