"""
registers.py - Register File simulation

แบบจำลอง Register File ของ CPU แบบ MIPS:
  - มี 32 registers: R0 .. R31
  - ทุกค่าเป็นจำนวนเต็ม 32-bit แบบ signed (two's complement)
  - R0 มีค่าเป็น 0 เสมอ (hard-wired) -> การเขียนลง R0 จะถูกเพิกเฉย

สมมติฐานสำคัญ (ใช้ตอนทำ pipeline):
  Register file "เขียนครึ่งแรกของ cycle, อ่านครึ่งหลังของ cycle"
  => ถ้า WB เขียน R3 และ ID อ่าน R3 ใน cycle เดียวกัน ID จะได้ค่าใหม่ทันที
"""

NUM_REGISTERS = 32


def to_int32(value):
    """ตัดค่าให้อยู่ในช่วง signed 32-bit (จำลอง overflow แบบ wrap-around ของฮาร์ดแวร์จริง)"""
    value &= 0xFFFFFFFF
    return value - 0x1_0000_0000 if value & 0x8000_0000 else value


class RegisterFile:
    def __init__(self, num_registers=NUM_REGISTERS):
        self.num_registers = num_registers
        self.regs = [0] * num_registers

    def _check(self, index):
        if not 0 <= index < self.num_registers:
            raise IndexError(f"Register R{index} does not exist (R0-R{self.num_registers - 1})")

    def read(self, index):
        self._check(index)
        return self.regs[index]

    def write(self, index, value):
        self._check(index)
        if index == 0:          # R0 = 0 เสมอ: เขียนไม่มีผล
            return
        self.regs[index] = to_int32(value)

    def dump(self, show_all=False):
        """คืนค่าเป็นข้อความตาราง register (ค่าเริ่มต้นแสดงเฉพาะตัวที่ไม่ใช่ 0)"""
        lines = []
        for i, v in enumerate(self.regs):
            if show_all or v != 0:
                lines.append(f"R{i:<2} = {v}")
        return "\n".join(lines) if lines else "(all registers are 0)"
