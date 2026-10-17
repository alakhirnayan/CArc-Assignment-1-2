# Qing
# 21st May 2017
# Multi-issue version.

"""
Issue up to `issue_width` instructions per cycle, in program order:
1. stop at the first instruction that has no free ROB entry / RS / ld-sd queue entry
2. read operands through the RAT, put the instruction in ROB and RS / ld-sd queue
3. rename the destination in the RAT
4. branches: predict with the BTB (1-bit predictor); a predicted-taken branch
   ends the issue group and fetch continues at the target in the next cycle
"""
from init import ROB_entry, Operand, BTB_SIZE


# function: read a source register through the RAT
def read_operand(m, reg):
    if reg is None or reg == 'R0':
        return Operand(0)
    producer = m.rat.get(reg)
    if producer is None:
        return Operand(m.reg_value(reg))
    if producer.wb is not None:
        # already broadcast: value sits in the ROB
        return Operand(producer.value, None, producer.wb + 1)
    return Operand(None, producer)


# function: find a free reservation station
def check_rs_space(station):
    for i, entry in enumerate(station):
        if entry is None:
            return i
    return -1


# function: BTB lookup, indexed by the low 3 bits of the word address
def predict(m, instr):
    entry = m.btb[instr.pc % BTB_SIZE]
    if entry is not None and entry['pc'] == instr.pc and entry['taken']:
        return entry['target']
    return instr.pc + 1


def issue(m, cycle):
    if cycle < m.fetch_resume:
        return
    for _ in range(m.cfg.issue_width):
        if m.pc >= len(m.program):
            return
        instr = m.program[m.pc]
        # structural hazards stall issue (in order)
        if len(m.rob) >= m.cfg.rob_size:
            return
        if instr.unit == 'ldsd':
            if len(m.ld_sd_queue) >= m.cfg.rs['ldsd']:
                return
        else:
            index = check_rs_space(m.rs[instr.unit])
            if index < 0:
                return

        entry = ROB_entry(m.next_seq, 'ROB%d' % (m.next_seq % m.cfg.rob_size), instr)
        m.next_seq += 1
        entry.issue = cycle
        entry.op1 = read_operand(m, instr.src1)
        entry.op2 = read_operand(m, instr.src2)
        m.rob.append(entry)
        if instr.unit == 'ldsd':
            m.ld_sd_queue.append(entry)
        else:
            m.rs[instr.unit][index] = entry
        if instr.dest is not None and instr.dest != 'R0':
            m.rat[instr.dest] = entry

        if instr.is_branch:
            m.branches += 1
            entry.pred_next = predict(m, instr)
            m.pc = entry.pred_next
            if entry.pred_next != instr.pc + 1:
                return      # predicted taken: fetch target next cycle
        else:
            m.pc += 1
