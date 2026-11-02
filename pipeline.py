"""
pipeline.py - Pipeline stage management

ไฟล์นี้มี 2 ส่วน:
  1) Pipeline registers (latch) 4 ใบที่คั่นระหว่าง stage:  IF/ID, ID/EX, EX/MEM, MEM/WB
     - inst = None หมายถึง "bubble" (ช่องว่าง ไม่มีคำสั่ง); ฟิลด์ bubble บอกว่าเกิดจาก stall หรือ flush
  2) ฟังก์ชันของแต่ละ stage: รับ latch "ฝั่งซ้าย" (ค่าเก่า) แล้วคืน latch "ฝั่งขวา" ใบใหม่

หลักการสำคัญ: ทุก stage คำนวณจากค่า latch "ของ cycle ก่อน" แล้วค่อย commit
พร้อมกันตอนจบ cycle (เหมือน clock edge ในฮาร์ดแวร์) -> ทำใน cpu.py
"""

from dataclasses import dataclass
from typing import Optional

from instructions import Instruction
from registers import to_int32

WORD = 4


# --------------------------------------------------------------------------
# 1) Pipeline registers
# --------------------------------------------------------------------------
@dataclass
class IF_ID:
    inst: Optional[Instruction] = None
    pc: int = 0                     # address ของคำสั่งนี้
    bubble: str = ""                # "" | "stall" | "flush" : ป้ายบอกที่มาของ bubble (ไว้แสดงผล)
    seq: int = -1                   # หมายเลข instance ของคำสั่ง (ไว้วาด pipeline diagram)


@dataclass
class ID_EX:
    inst: Optional[Instruction] = None
    pc: int = 0
    val1: int = 0                   # ค่าที่อ่านจาก register src1 ตอน ID
    val2: int = 0                   # ค่าที่อ่านจาก register src2 ตอน ID
    bubble: str = ""                # "" | "stall" | "flush" : ป้ายบอกที่มาของ bubble (ไว้แสดงผล)
    seq: int = -1                   # หมายเลข instance ของคำสั่ง (ไว้วาด pipeline diagram)


@dataclass
class EX_MEM:
    inst: Optional[Instruction] = None
    alu_result: int = 0             # ผล ALU หรือ address ของ LW/SW
    store_value: int = 0            # ค่าที่ SW จะเขียนลง memory
    branch_taken: bool = False
    branch_target: int = 0
    bubble: str = ""                # "" | "stall" | "flush" : ป้ายบอกที่มาของ bubble (ไว้แสดงผล)
    seq: int = -1                   # หมายเลข instance ของคำสั่ง (ไว้วาด pipeline diagram)


@dataclass
class MEM_WB:
    inst: Optional[Instruction] = None
    value: int = 0                  # ค่าที่จะเขียนกลับ register (ผล ALU หรือค่าที่ LW อ่านได้)
    bubble: str = ""                # "" | "stall" | "flush" : ป้ายบอกที่มาของ bubble (ไว้แสดงผล)
    seq: int = -1                   # หมายเลข instance ของคำสั่ง (ไว้วาด pipeline diagram)


# --------------------------------------------------------------------------
# ALU
# --------------------------------------------------------------------------
def alu(opcode, a, b, imm):
    """คำนวณผลของ EX stage: คืน (result, branch_taken)"""
    if opcode == "ADD":
        return to_int32(a + b), False
    if opcode == "SUB":
        return to_int32(a - b), False
    if opcode == "AND":
        return to_int32(a & b), False
    if opcode == "OR":
        return to_int32(a | b), False
    if opcode in ("ADDI", "LW", "SW"):          # LW/SW: คำนวณ address = base + offset
        return to_int32(a + imm), False
    if opcode == "BEQ":
        return 0, a == b
    if opcode == "BNE":
        return 0, a != b
    return 0, False                              # NOP, HALT


# --------------------------------------------------------------------------
# 2) Stages
# --------------------------------------------------------------------------
class Pipeline:
    STAGES = ("IF", "ID", "EX", "MEM", "WB")

    def __init__(self, regs, imem, dmem):
        self.regs = regs
        self.imem = imem
        self.dmem = dmem
        self.reset()

    def reset(self):
        self.pc = 0
        self.if_id = IF_ID()
        self.id_ex = ID_EX()
        self.ex_mem = EX_MEM()
        self.mem_wb = MEM_WB()
        self.fetch_stopped = False      # True หลังจาก fetch เจอ HALT
        self.next_seq = 0               # ตัวนับ instance ของคำสั่งที่ถูก fetch (คำสั่งเดียวกันใน loop ได้เลขต่างกัน)

    def take_seq(self):
        seq = self.next_seq
        self.next_seq += 1
        return seq

    def is_empty(self):
        return all(l.inst is None for l in (self.if_id, self.id_ex, self.ex_mem, self.mem_wb))

    def nothing_left_to_fetch(self):
        return self.fetch_stopped or self.imem.fetch(self.pc) is None

    # ---- Stage 1: IF ----------------------------------------------------
    def stage_if(self):
        """ดึงคำสั่งที่ PC และคำนวณ PC ถัดไป -> คืน (IF_ID ใหม่, next_pc)"""
        if self.fetch_stopped:
            return IF_ID(), self.pc
        inst = self.imem.fetch(self.pc)
        if inst is None:                        # PC เลยท้ายโปรแกรม -> ส่ง bubble
            return IF_ID(), self.pc
        if inst.is_halt:
            # เจอ HALT: หยุด fetch คำสั่งใหม่ แล้วปล่อยให้คำสั่งที่อยู่ใน pipeline ทำต่อจนจบ
            self.fetch_stopped = True
            return IF_ID(inst, self.pc, seq=self.take_seq()), self.pc
        return IF_ID(inst, self.pc, seq=self.take_seq()), self.pc + WORD

    # ---- Stage 2: ID ----------------------------------------------------
    def stage_id(self, if_id):
        """ถอดรหัส + อ่านค่า register"""
        inst = if_id.inst
        if inst is None:
            return ID_EX(bubble=if_id.bubble)
        v1 = self.regs.read(inst.src1) if inst.src1 is not None else 0
        v2 = self.regs.read(inst.src2) if inst.src2 is not None else 0
        return ID_EX(inst, if_id.pc, v1, v2, seq=if_id.seq)

    # ---- Stage 3: EX ----------------------------------------------------
    def stage_ex(self, id_ex, op1, op2):
        """op1/op2 = ค่า operand ที่ใช้จริง (cpu.py เป็นคนเลือกว่าจะใช้ค่าจาก ID หรือค่าที่ forward มา)"""
        inst = id_ex.inst
        if inst is None:
            return EX_MEM(bubble=id_ex.bubble)
        result, taken = alu(inst.opcode, op1, op2, inst.imm)
        # branch target = (PC + 4) + offset*4   (แบบ MIPS)
        target = id_ex.pc + WORD + inst.imm * WORD if inst.is_branch else 0
        return EX_MEM(inst, result, store_value=op2, branch_taken=taken, branch_target=target,
                      seq=id_ex.seq)

    # ---- Stage 4: MEM ---------------------------------------------------
    def stage_mem(self, ex_mem):
        inst = ex_mem.inst
        if inst is None:
            return MEM_WB(bubble=ex_mem.bubble)
        if inst.is_load:
            return MEM_WB(inst, self.dmem.read(ex_mem.alu_result), seq=ex_mem.seq)
        if inst.is_store:
            self.dmem.write(ex_mem.alu_result, ex_mem.store_value)
        return MEM_WB(inst, ex_mem.alu_result, seq=ex_mem.seq)  # คำสั่งอื่นส่งผล ALU ผ่านไปเฉยๆ

    # ---- Stage 5: WB ----------------------------------------------------
    def stage_wb(self, mem_wb):
        """เขียนผลกลับ register  -> คืนคำสั่งที่ทำเสร็จ (หรือ None)"""
        inst = mem_wb.inst
        if inst is None:
            return None
        if inst.writes_register:
            self.regs.write(inst.dest, mem_wb.value)
        return inst
