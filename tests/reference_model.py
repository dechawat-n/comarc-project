"""
reference_model.py - "Golden model" สำหรับตรวจความถูกต้อง

รันโปรแกรมทีละคำสั่งแบบ "ไม่มี pipeline" (ไม่มี hazard เพราะทำทีละคำสั่งจนจบ)
ผลสุดท้าย (register + memory + จำนวนคำสั่งที่ทำ) ต้องตรงกับ pipeline simulator เสมอ
ถ้าไม่ตรง แปลว่า forwarding / stall / flush ใน pipeline มี bug
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from registers import to_int32  # noqa: E402


def run_reference(program, max_steps=100_000):
    regs = [0] * 32
    mem = {}
    pc, executed = 0, 0
    while 0 <= pc // 4 < len(program):
        if executed >= max_steps:
            raise RuntimeError("reference model: too many steps")
        i = program[pc // 4]
        executed += 1
        a = regs[i.src1] if i.src1 is not None else 0
        b = regs[i.src2] if i.src2 is not None else 0
        next_pc = pc + 4
        op = i.opcode
        result = None
        if op == "ADD":
            result = a + b
        elif op == "SUB":
            result = a - b
        elif op == "AND":
            result = a & b
        elif op == "OR":
            result = a | b
        elif op == "ADDI":
            result = a + i.imm
        elif op == "LW":
            result = mem.get(to_int32(a + i.imm), 0)
        elif op == "SW":
            mem[to_int32(a + i.imm)] = b
        elif op in ("BEQ", "BNE"):
            if (a == b) == (op == "BEQ"):
                next_pc = pc + 4 + i.imm * 4
        elif op == "HALT":
            break
        if result is not None and i.dest not in (None, 0):
            regs[i.dest] = to_int32(result)
        pc = next_pc
    return regs, mem, executed
