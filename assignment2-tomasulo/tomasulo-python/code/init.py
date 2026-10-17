# Qing
# 21st May 2017
# Multi-issue version: data structures, machine state and input-file parser.

import re
from collections import deque

'''functional unit class of every opcode'''
UNIT_OF = {
    'add': 'int', 'addi': 'int', 'sub': 'int', 'beq': 'int', 'bne': 'int',
    'add.d': 'fpadd', 'sub.d': 'fpadd',
    'mult.d': 'fpmul', 'mul.d': 'fpmul',
    'ld': 'ldsd', 'sd': 'ldsd',
}
UNIT_NAMES = {
    'integer adder': 'int',
    'fp adder': 'fpadd',
    'fp multiplier': 'fpmul',
    'load/store unit': 'ldsd',
}
BTB_SIZE = 8
MEMORY_SIZE = 256   # bytes


class Instruction:
    '''one decoded instruction; pc is its index in the program (byte PC = 4*pc)'''
    def __init__(self, pc, text):
        self.pc = pc
        self.text = ' '.join(text.split())
        tokens = [t for t in re.split(r'[,\s]+', text.strip()) if t]
        self.op = tokens[0].lower()
        if self.op not in UNIT_OF:
            raise ValueError('unknown instruction: ' + text)
        self.unit = UNIT_OF[self.op]
        self.dest = self.src1 = self.src2 = None
        self.imm = 0
        args = tokens[1:]
        if self.op in ('ld', 'sd'):
            m = re.match(r'^(-?\d+)\((\w+)\)$', args[1])
            if not m:
                raise ValueError('bad address operand: ' + text)
            self.imm = int(m.group(1))
            self.src1 = reg_name(m.group(2))           # base register
            if self.op == 'ld':
                self.dest = reg_name(args[0])
            else:
                self.src2 = reg_name(args[0])          # store data
        elif self.op in ('beq', 'bne'):
            self.src1, self.src2 = reg_name(args[0]), reg_name(args[1])
            self.imm = int(args[2])                    # offset in words
        elif self.op == 'addi':
            self.dest, self.src1 = reg_name(args[0]), reg_name(args[1])
            self.imm = int(args[2])
        else:
            self.dest = reg_name(args[0])
            self.src1, self.src2 = reg_name(args[1]), reg_name(args[2])

    @property
    def is_branch(self):
        return self.op in ('beq', 'bne')

    @property
    def is_load(self):
        return self.op == 'ld'

    @property
    def is_store(self):
        return self.op == 'sd'


def reg_name(token):
    token = token.upper()
    if not re.match(r'^[RF]([0-9]|[12][0-9]|3[01])$', token):
        raise ValueError('bad register: ' + token)
    return token


class Operand:
    '''a source operand: either a value (usable from cycle `ready`) or a ROB entry to wait for'''
    def __init__(self, value=0, src=None, ready=0):
        self.value = value
        self.src = src
        self.ready = ready

    def is_ready(self, cycle):
        return self.src is None and self.ready <= cycle


class ROB_entry:
    '''one in-flight instruction; it is also the RS / ld-sd queue entry'''
    def __init__(self, seq, tag, instr):
        self.seq = seq                 # global age, smaller = older
        self.tag = tag
        self.instr = instr
        self.op1 = Operand()           # src1 (base register for ld/sd)
        self.op2 = Operand()           # src2 (store data for sd)
        self.result = None             # computed at end of EX / MEM
        self.value = None              # broadcast on the CDB
        self.addr = None               # ld/sd effective address
        self.forwarded = False         # ld got its value from a store
        self.source_seq = -1           # ld: seq of the store it forwarded from, -1 = memory
        self.fault = None              # bad address / branch target, raised at commit
        self.squashed = False
        # branch
        self.pred_next = None
        self.actual_next = None
        self.mispredicted = False
        # timing
        self.issue = None
        self.ex_start = self.ex_end = None
        self.mem_start = self.mem_end = None
        self.wb = None
        self.commit = None


class FunctionalUnit:
    def __init__(self, latency, pipelined):
        self.latency = latency
        self.pipelined = pipelined
        self.busy_until = 0            # unpipelined: last EX cycle of current op
        self.last_start = 0            # pipelined: accepts one new op per cycle
        self.current = None

    def can_start(self, cycle):
        if self.pipelined:
            return self.last_start != cycle
        return self.busy_until < cycle

    def start(self, entry, cycle):
        self.last_start = cycle
        self.busy_until = cycle + self.latency - 1
        self.current = entry
        entry.ex_start = cycle
        entry.ex_end = cycle + self.latency - 1


class Config:
    def __init__(self):
        # unit: [# of rs, cycles in EX, # of FUs]; ldsd also has cycles in MEM
        self.rs = {'int': 2, 'fpadd': 3, 'fpmul': 2, 'ldsd': 3}
        self.ex = {'int': 1, 'fpadd': 3, 'fpmul': 20, 'ldsd': 1}
        self.fus = {'int': 1, 'fpadd': 1, 'fpmul': 1, 'ldsd': 1}
        self.mem_cycles = 4
        self.rob_size = 128
        self.issue_width = 1
        self.cdb_width = 1             # the spec has one CDB
        self.commit_width = None       # defaults to the issue width


class Machine:
    '''all processor state'''
    def __init__(self, cfg, program, reg_init, mem_init):
        self.cfg = cfg
        self.program = program
        self.reg_int = [0] * 32
        self.reg_fp = [0.0] * 32
        for reg, value in reg_init.items():
            if reg == 'R0':
                continue
            if reg[0] == 'R':
                self.reg_int[int(reg[1:])] = int(value)
            else:
                self.reg_fp[int(reg[1:])] = float(value)
        self.memory = dict(mem_init)
        self.rat = {}                  # register -> ROB_entry; absent = register file
        self.rob = deque()
        self.rs = {u: [None] * cfg.rs[u] for u in ('int', 'fpadd', 'fpmul')}
        self.ld_sd_queue = []          # ROB entries of loads/stores, program order
        self.fus = {
            'int': [FunctionalUnit(cfg.ex['int'], False) for _ in range(cfg.fus['int'])],
            'fpadd': [FunctionalUnit(cfg.ex['fpadd'], True) for _ in range(cfg.fus['fpadd'])],
            'fpmul': [FunctionalUnit(cfg.ex['fpmul'], True) for _ in range(cfg.fus['fpmul'])],
            # dedicated effective-address adders
            'ldsd': [FunctionalUnit(cfg.ex['ldsd'], False) for _ in range(cfg.fus['ldsd'])],
        }
        self.mem_busy_until = 0        # memory: single-ported, non-pipelined
        self.mem_owner = None
        self.btb = [None] * BTB_SIZE   # {'pc', 'target', 'taken'} (1-bit predictor)
        self.pc = 0
        self.fetch_resume = 1          # first cycle fetch may continue after a squash
        self.next_seq = 0
        self.committed = []
        self.squashed = []
        self.branches = 0
        self.mispredictions = 0
        self.memory_violations = 0

    def reg_value(self, reg):
        if reg[0] == 'R':
            return self.reg_int[int(reg[1:])]
        return self.reg_fp[int(reg[1:])]

    def set_reg(self, reg, value):
        if reg == 'R0':
            return
        if reg[0] == 'R':
            self.reg_int[int(reg[1:])] = int(value)
        else:
            self.reg_fp[int(reg[1:])] = float(value)


# function: read input file (configuration, initial values, program)
def read_input(path):
    cfg = Config()
    program, reg_init, mem_init = [], {}, {}
    with open(path) as f:
        lines = f.read().splitlines()
    for raw in lines:
        line = raw.split('#')[0].strip()
        if not line:
            continue
        low = line.lower()
        name = next((n for n in UNIT_NAMES if low.startswith(n)), None)
        if name:
            unit = UNIT_NAMES[name]
            nums = [int(x) for x in low[len(name):].split()]
            if unit == 'ldsd':
                cfg.rs[unit], cfg.ex[unit], cfg.mem_cycles, cfg.fus[unit] = nums
            else:
                cfg.rs[unit], cfg.ex[unit], cfg.fus[unit] = nums
            continue
        m = re.match(r'^rob entries\s*=\s*(\d+)$', low)
        if m:
            cfg.rob_size = int(m.group(1))
            continue
        m = re.match(r'^issue width\s*=\s*(\d+)$', low)
        if m:
            cfg.issue_width = int(m.group(1))
            continue
        m = re.match(r'^cdb (?:width|buses)\s*=\s*(\d+)$', low)
        if m:
            cfg.cdb_width = int(m.group(1))
            continue
        m = re.match(r'^commit width\s*=\s*(\d+)$', low)
        if m:
            cfg.commit_width = int(m.group(1))
            continue
        if '=' in line:
            # R1=10, F2=30.1  or  Mem[4]=1, Mem[8]=2
            for item in line.split(','):
                name, value = [s.strip() for s in item.split('=')]
                mm = re.match(r'^mem\[(\d+)\]$', name.lower())
                if mm:
                    mem_init[int(mm.group(1))] = float(value)
                else:
                    reg_init[reg_name(name)] = float(value)
            continue
        program.append(Instruction(len(program), line))
    return cfg, program, reg_init, mem_init


# function: build machine; issue_width / cdb_width arguments override the file
def build_machine(path, issue_width=None, cdb_width=None):
    cfg, program, reg_init, mem_init = read_input(path)
    if issue_width is not None:
        cfg.issue_width = issue_width
    if cdb_width is not None:
        cfg.cdb_width = cdb_width
    if not 1 <= cfg.issue_width <= 4:
        raise ValueError('issue width must be 1-4')
    if cfg.commit_width is None:
        cfg.commit_width = cfg.issue_width
    return Machine(cfg, program, reg_init, mem_init)
