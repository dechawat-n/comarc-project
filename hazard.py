"""
hazard.py - Hazard detection and handling

Data hazard มี 3 โหมด (เลือกได้, ค่าเริ่มต้น = "forwarding"):
  "forwarding" : forwarding + stall เฉพาะ load-use               (ดีไซน์หลักของโปรเจกต์)
  "stall"      : ไม่มี forwarding, stall ทุก RAW จน producer ถึง WB
  "none"       : ไม่ตรวจ ไม่แก้อะไรเลย -> ผู้ใช้ต้องใส่ NOP เอง ไม่งั้นผลผิด (ไว้สาธิตว่าทำไมต้องมี hazard unit)

1) Forwarding Unit (ทำงานที่ EX)
   เลือกค่า operand ให้คำสั่งใน EX จาก 3 แหล่ง เรียงตามความสำคัญ:
     a. EX/MEM  -> EX   : ผลของคำสั่งที่อยู่ข้างหน้า 1 ตำแหน่ง (ใหม่ที่สุด จึงมาก่อน)
     b. MEM/WB  -> EX   : ผลของคำสั่งที่อยู่ข้างหน้า 2 ตำแหน่ง
     c. ค่าที่อ่านจาก register file ตอน ID (ไม่มี hazard)
   เงื่อนไข forward: producer ต้องเขียน register จริง (dest != R0) และ dest == source ของเรา
   ห้าม forward จาก EX/MEM ถ้า producer เป็น LW (ค่ายังไม่ได้อ่านจาก memory) -> กรณีนี้ต้อง stall

2) Hazard Detection Unit (ทำงานที่ ID) -> ตัดสินใจ stall
   - forwarding : stall เฉพาะ load-use (LW อยู่ใน EX และคำสั่งใน ID ใช้ register ที่ LW จะโหลด)
                  stall 1 cycle แล้ว forward จาก MEM/WB -> EX
   - stall      : stall ทุก RAW ที่ producer ยังอยู่ใน EX หรือ MEM
                  (รอจน producer ถึง WB แล้วอ่านจาก register file ได้ เพราะเขียนครึ่งแรก/อ่านครึ่งหลัง)

   การ stall = (1) ใส่ bubble เข้า ID/EX  (2) คงค่า IF/ID ไว้  (3) ไม่เลื่อน PC

สมมติฐาน (ทำให้ง่ายกว่า MIPS จริง): ไม่มี forwarding MEM/WB -> MEM
  ดังนั้น "LW R1 ; SW R1 ..." จะ stall 1 cycle เหมือน load-use ทั่วไป
"""

DATA_MODES = ("forwarding", "stall", "none")


def _depends(consumer, producer):
    """คืน register ที่ consumer อ่าน และ producer เขียน (RAW) หรือ None"""
    if consumer is None or producer is None or not producer.writes_register:
        return None
    return producer.dest if producer.dest in consumer.source_registers() else None


class HazardUnit:
    def __init__(self, forwarding=True, mode=None):
        if mode is None:
            mode = "forwarding" if forwarding else "stall"
        if mode not in DATA_MODES:
            raise ValueError(f"unknown data hazard mode: {mode}")
        self.mode = mode

    @property
    def forwarding(self):
        return self.mode == "forwarding"

    # ---------------- ID stage: ตรวจ RAW + ตัดสินใจ stall ----------------
    def raw_hazards(self, if_id, id_ex, ex_mem):
        """หา RAW dependency ของคำสั่งใน ID กับคำสั่งที่ยังอยู่ใน EX / MEM -> list ของข้อความ"""
        found = []
        consumer = if_id.inst
        suffix = " -- NOT HANDLED (no hazard unit)" if self.mode == "none" else ""
        for producer, where in ((id_ex.inst, "EX"), (ex_mem.inst, "MEM")):
            reg = _depends(consumer, producer)
            if reg is not None:
                found.append(f"RAW: {consumer.short()} needs R{reg} from {producer.short()} (in {where}){suffix}")
        return found

    def detect_stall(self, if_id, id_ex, ex_mem):
        """คืน (ต้อง stall ไหม, เหตุผล, เป็น load-use ไหม)"""
        consumer = if_id.inst
        if consumer is None or self.mode == "none":
            return False, "", False
        producer = id_ex.inst
        reg = _depends(consumer, producer)
        if reg is not None and producer.is_load:
            return True, f"STALL (load-use): {consumer.short()} waits for R{reg} from {producer.short()}", True
        if self.mode == "stall":
            for producer, where in ((id_ex.inst, "EX"), (ex_mem.inst, "MEM")):
                reg = _depends(consumer, producer)
                if reg is not None:
                    return True, (f"STALL (no forwarding): {consumer.short()} waits for R{reg} "
                                  f"from {producer.short()} (in {where})"), False
        return False, "", False

    # ---------------- EX stage: Forwarding unit ----------------
    def forward_operands(self, id_ex, ex_mem, mem_wb):
        """คืน (op1, op2, ข้อความ forwarding, แหล่งที่มาของ op1/op2: "ID/EX" | "EX/MEM" | "MEM/WB")"""
        inst = id_ex.inst
        ops = [id_ex.val1, id_ex.val2]
        srcs = ["ID/EX", "ID/EX"]
        msgs = []
        if inst is None or not self.forwarding:
            return ops[0], ops[1], msgs, srcs
        for i, src in enumerate((inst.src1, inst.src2)):
            if src is None:
                continue
            p1, p2 = ex_mem.inst, mem_wb.inst
            if p1 is not None and p1.writes_register and p1.dest == src and not p1.is_load:
                ops[i], srcs[i] = ex_mem.alu_result, "EX/MEM"
                msgs.append(f"FWD EX/MEM->EX: R{src}={ops[i]} ({p1.short()} -> {inst.short()})")
            elif p2 is not None and p2.writes_register and p2.dest == src:
                ops[i], srcs[i] = mem_wb.value, "MEM/WB"
                msgs.append(f"FWD MEM/WB->EX: R{src}={ops[i]} ({p2.short()} -> {inst.short()})")
        return ops[0], ops[1], msgs, srcs
