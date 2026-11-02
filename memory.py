"""
memory.py - Instruction Memory และ Data Memory

สมมติฐานของการออกแบบ (Harvard architecture):
  - Instruction Memory กับ Data Memory "แยกกัน"
  - ดังนั้น IF (อ่านคำสั่ง) กับ MEM (LW/SW) ทำงานใน cycle เดียวกันได้
    => ไม่มี Structural Hazard ด้านหน่วยความจำในดีไซน์นี้

การระบุที่อยู่ (addressing) แบบ MIPS:
  - PC เป็น byte address, คำสั่งละ 4 bytes  -> คำสั่งที่ index i อยู่ที่ PC = 4*i
  - Data memory ใช้ byte address และต้องหาร 4 ลงตัว (word-aligned)
"""

WORD_SIZE = 4


class InstructionMemory:
    def __init__(self, instructions=None):
        self.instructions = list(instructions or [])

    def load(self, instructions):
        self.instructions = list(instructions)

    def fetch(self, pc):
        """คืนคำสั่งที่ตำแหน่ง PC หรือ None ถ้า PC ชี้เลยท้ายโปรแกรม"""
        if pc % WORD_SIZE != 0:
            raise ValueError(f"Misaligned PC: {pc}")
        index = pc // WORD_SIZE
        if 0 <= index < len(self.instructions):
            return self.instructions[index]
        return None

    def __len__(self):
        return len(self.instructions)


class DataMemory:
    def __init__(self):
        self.data = {}          # address -> value (ช่องที่ไม่เคยเขียนถือว่าเป็น 0)

    def _check(self, address):
        if address < 0 or address % WORD_SIZE != 0:
            raise ValueError(f"Invalid/misaligned data address: {address}")

    def read(self, address):
        self._check(address)
        return self.data.get(address, 0)

    def write(self, address, value):
        self._check(address)
        self.data[address] = value

    def dump(self):
        if not self.data:
            return "(data memory is empty)"
        return "\n".join(f"Mem[{a}] = {v}" for a, v in sorted(self.data.items()))
