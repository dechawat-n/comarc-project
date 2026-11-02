"""
instructions.py - Instruction parsing and decoding

แปลงข้อความ assembly เช่น "ADD R3 R1 R2" ให้เป็น object Instruction

เพื่อให้ pipeline ใช้งานง่าย เราเก็บ operand ในรูปแบบเดียวกันทุกคำสั่ง:
    dest  = register ปลายทางที่จะถูกเขียน (หรือ None)
    src1  = register ต้นทางตัวที่ 1  (หรือ None)
    src2  = register ต้นทางตัวที่ 2  (หรือ None)
    imm   = ค่า immediate / offset   (หรือ 0)

ตารางรูปแบบคำสั่งที่รองรับ:
    ADD/SUB/AND/OR  rd rs rt        dest=rd, src1=rs, src2=rt
    ADDI            rt rs imm       dest=rt, src1=rs,          imm
    LW              rt imm(rs)      dest=rt, src1=rs (base),   imm
    SW              rt imm(rs)               src1=rs (base), src2=rt (ค่าที่จะเก็บ), imm
    BEQ/BNE         rs rt offset             src1=rs, src2=rt, imm=offset
    NOP, HALT       (ไม่มี operand)

หมายเหตุ: ใน MIPS จริง ADDI/LW ใช้ฟิลด์ "rt" เป็นปลายทาง แต่ใน simulator
เราเรียกรวมว่า dest เพื่อให้ hazard detection เขียนง่ายและเข้าใจง่าย

Syntax: ไม่สนตัวพิมพ์เล็ก/ใหญ่, ใช้ช่องว่างหรือ comma คั่นก็ได้,
comment ขึ้นต้นด้วย '#' หรือ ';', immediate เป็นเลขฐาน 10 / ลบ / 0x.. ได้
"""

import re

R_TYPE = {"ADD", "SUB", "AND", "OR"}
I_TYPE = {"ADDI"}
MEM_TYPE = {"LW", "SW"}
BRANCH_TYPE = {"BEQ", "BNE"}
NO_OPERAND = {"NOP", "HALT"}
ALL_OPCODES = R_TYPE | I_TYPE | MEM_TYPE | BRANCH_TYPE | NO_OPERAND

NUM_REGISTERS = 32
_MEM_OPERAND = re.compile(r"^(-?(?:0x[0-9a-f]+|\d+))\((r\d+)\)$", re.IGNORECASE)


class ParseError(Exception):
    pass


class Instruction:
    def __init__(self, opcode, dest=None, src1=None, src2=None, imm=0, text="", line_no=None):
        self.opcode = opcode
        self.dest = dest
        self.src1 = src1
        self.src2 = src2
        self.imm = imm
        self.text = text or opcode   # ข้อความต้นฉบับ (ไว้แสดงผล)
        self.line_no = line_no

    # ---- คุณสมบัติที่ hazard unit / pipeline จะถามบ่อย ----
    @property
    def is_load(self):
        return self.opcode == "LW"

    @property
    def is_store(self):
        return self.opcode == "SW"

    @property
    def is_branch(self):
        return self.opcode in BRANCH_TYPE

    @property
    def is_halt(self):
        return self.opcode == "HALT"

    @property
    def writes_register(self):
        """คำสั่งนี้เขียน register จริงไหม (เขียน R0 ไม่นับ เพราะไม่มีผล และห้าม forward)"""
        return self.dest is not None and self.dest != 0

    def source_registers(self):
        """register ที่คำสั่งนี้ต้องอ่าน (ใช้ตรวจ RAW hazard)"""
        return [r for r in (self.src1, self.src2) if r is not None]

    def short(self):
        """ชื่อย่อสำหรับตาราง pipeline เช่น 'ADD R3', 'BEQ R4'"""
        parts = self.text.split()
        return " ".join(parts[:2]).rstrip(",")

    def __repr__(self):
        return f"<{self.text}>"


def _parse_reg(token, line_no):
    t = token.upper()
    if not re.fullmatch(r"R\d+", t):
        raise ParseError(f"Line {line_no}: expected register, got '{token}'")
    n = int(t[1:])
    if n >= NUM_REGISTERS:
        raise ParseError(f"Line {line_no}: register {token} out of range (R0-R31)")
    return n


def _parse_imm(token, line_no):
    try:
        return int(token, 0)
    except ValueError:
        raise ParseError(f"Line {line_no}: expected integer immediate, got '{token}'")


def _expect(ops, n, opcode, line_no):
    if len(ops) != n:
        raise ParseError(f"Line {line_no}: {opcode} needs {n} operand(s), got {len(ops)}")


def parse_line(line, line_no=None):
    """แปลง 1 บรรทัดเป็น Instruction (คืน None ถ้าเป็นบรรทัดว่าง/comment)"""
    code = re.split(r"[#;]", line, maxsplit=1)[0].strip()
    if not code:
        return None
    tokens = code.replace(",", " ").split()
    opcode, ops = tokens[0].upper(), tokens[1:]
    text = " ".join([opcode] + [o.upper() for o in ops])

    if opcode not in ALL_OPCODES:
        raise ParseError(f"Line {line_no}: unknown instruction '{tokens[0]}'")

    if opcode in R_TYPE:
        _expect(ops, 3, opcode, line_no)
        return Instruction(opcode, dest=_parse_reg(ops[0], line_no),
                           src1=_parse_reg(ops[1], line_no),
                           src2=_parse_reg(ops[2], line_no), text=text, line_no=line_no)

    if opcode in I_TYPE:
        _expect(ops, 3, opcode, line_no)
        return Instruction(opcode, dest=_parse_reg(ops[0], line_no),
                           src1=_parse_reg(ops[1], line_no),
                           imm=_parse_imm(ops[2], line_no), text=text, line_no=line_no)

    if opcode in MEM_TYPE:
        _expect(ops, 2, opcode, line_no)
        rt = _parse_reg(ops[0], line_no)
        m = _MEM_OPERAND.match(ops[1])
        if not m:
            raise ParseError(f"Line {line_no}: expected offset(Rn), got '{ops[1]}'")
        imm, base = _parse_imm(m.group(1), line_no), _parse_reg(m.group(2), line_no)
        if opcode == "LW":
            return Instruction("LW", dest=rt, src1=base, imm=imm, text=text, line_no=line_no)
        return Instruction("SW", src1=base, src2=rt, imm=imm, text=text, line_no=line_no)

    if opcode in BRANCH_TYPE:
        _expect(ops, 3, opcode, line_no)
        return Instruction(opcode, src1=_parse_reg(ops[0], line_no),
                           src2=_parse_reg(ops[1], line_no),
                           imm=_parse_imm(ops[2], line_no), text=text, line_no=line_no)

    _expect(ops, 0, opcode, line_no)        # NOP, HALT
    return Instruction(opcode, text=text, line_no=line_no)


def parse_program(source):
    """แปลงทั้งโปรแกรม (string) เป็น list ของ Instruction"""
    program = []
    for i, line in enumerate(source.splitlines(), start=1):
        inst = parse_line(line, i)
        if inst is not None:
            program.append(inst)
    return program


def load_program_file(path):
    with open(path, encoding="utf-8") as f:
        return parse_program(f.read())
