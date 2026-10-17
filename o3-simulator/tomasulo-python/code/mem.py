# Qing
# 26th May 2017
# Multi-issue version.

'''
MEM stage for loads (stores write memory at commit, see commit.py)
1. a load whose address is ready checks the older stores in the ld/sd queue
    -- any address unresolved: access memory, even if another store matches
    -- all addresses known: forward from the youngest matching store (1 cycle),
       waiting for its data if needed; if no match exists, access memory
    -- memory access uses the single, non-pipelined port for `mem_cycles` cycles
2. stores check for stale younger loads both when their address resolves and
   when they commit; stale loads and their younger instructions are replayed
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
        older_stores = [s for s in m.ld_sd_queue[:i] if s.instr.is_store]
        unresolved = any(s.addr is None or s.ex_end >= cycle for s in older_stores)
        match = None
        if not unresolved:
            for store in reversed(older_stores):
                if store.addr == entry.addr:
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
