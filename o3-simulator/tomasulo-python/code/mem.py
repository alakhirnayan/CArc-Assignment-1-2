# Qing
# 26th May 2017
# Multi-issue version.

'''
MEM stage for loads (stores write memory at commit, see commit.py)
1. a load whose address is ready looks for the youngest older store in the
   ld/sd queue with a known, matching address
    -- found: forward its data (1 cycle), or wait if that data is not ready yet
    -- not found: access memory (single port, non-pipelined, `mem_cycles`
       cycles), even if some older store addresses are still unknown
2. if one of those older stores later turns out to have the same address, the
   load and everything after it are squashed and refetched (exe.py)
3. a load leaves the ld/sd queue once it has its data
'''


def mem(m, cycle):
    # loads that got their data in an earlier cycle leave the queue
    m.ld_sd_queue = [e for e in m.ld_sd_queue
                     if not (e.instr.is_load and e.mem_end is not None and e.mem_end < cycle)]

    for i, entry in enumerate(m.ld_sd_queue):
        if not entry.instr.is_load or entry.mem_start is not None:
            continue
        if entry.addr is None or entry.ex_end >= cycle:
            continue
        match = None
        for store in reversed(m.ld_sd_queue[:i]):
            if store.instr.is_store and store.addr == entry.addr:
                match = store
                break
        if match is not None:
            # forwarding from a store takes 1 cycle
            if match.op2.is_ready(cycle):
                entry.mem_start = entry.mem_end = cycle
                entry.result = match.op2.value
                entry.forwarded = True
                entry.source_seq = match.seq
            continue
        if m.mem_busy_until < cycle:
            entry.mem_start = cycle
            entry.mem_end = cycle + m.cfg.mem_cycles - 1
            entry.result = m.memory.get(entry.addr, 0.0)
            m.mem_busy_until = entry.mem_end
            m.mem_owner = entry
