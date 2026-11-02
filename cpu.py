"""
cpu.py - CPU simulation and control logic

ลำดับการทำงานใน 1 clock cycle (เมธอด step):
  1. WB  ก่อน  -> จำลอง "register file เขียนครึ่งแรกของ cycle"
  2. MEM
  3. EX        -> forwarding unit เลือก operand, ALU คำนวณ, ตัดสิน branch
  4. Branch    -> จัดการ control hazard ตาม policy ที่เลือก
  5. ID        -> hazard detection unit ตัดสินใจ stall; อ่าน register หลัง WB เขียนแล้ว
  6. IF        -> (ถ้า stall: ไม่ fetch, PC คงเดิม)
  7. Commit: เอา latch ใหม่ทั้งหมดไปแทนของเก่าพร้อมกัน (= clock edge)

Control hazard policy (เลือกได้, ค่าเริ่มต้น = "predict"):
  "predict" : Predict Not-Taken, resolve ที่ EX   (ดีไซน์หลักของโปรเจกต์)
              - IF fetch คำสั่งถัดไปตามลำดับเสมอ (เดาว่าไม่ taken)
              - not taken -> เดาถูก ไม่เสีย cycle
              - taken     -> เดาผิด: คำสั่งใน IF และ ID ถูก flush (กลายเป็น bubble) => เสีย 2 cycles
              - flush มีความสำคัญเหนือ stall (คำสั่งที่จะ stall อยู่บน wrong path อยู่แล้ว)
  "stall"   : Detect and Stall - เมื่อมี branch อยู่ใน ID หรือ EX จะไม่ fetch คำสั่งใหม่
              จนกว่า branch จะรู้ผล => เสีย 2 cycles ทุก branch (ไม่มีการ flush)
  "none"    : ไม่จัดการ - 2 คำสั่งหลัง branch ทำงานเสมอ (เหมือน delay slot 2 ช่อง)
              ผู้ใช้ต้องใส่ NOP 2 ตัวหลัง branch เอง ไม่งั้นผลผิด
"""

from registers import RegisterFile
from memory import InstructionMemory, DataMemory
from pipeline import Pipeline, IF_ID, ID_EX
from hazard import HazardUnit

MAX_CYCLES = 10_000     # กันโปรแกรมวนไม่รู้จบ
BRANCH_PENALTY = 2      # จำนวน slot ที่ถูก flush เมื่อ branch taken (resolve ที่ EX)
CONTROL_MODES = ("predict", "stall", "none")


def cell(latch_or_inst, bubble=""):
    """ข้อความในช่องตาราง: ชื่อคำสั่ง / 'bubble' / '-'"""
    inst = getattr(latch_or_inst, "inst", latch_or_inst)
    bubble = getattr(latch_or_inst, "bubble", bubble)
    if inst is not None:
        return inst.short()
    return "bubble" if bubble else "-"


def _latch_snapshot(p):
    """ค่าใน pipeline register ทั้ง 4 ใบ (ไว้แสดงบน datapath ใน GUI)"""
    def t(inst):
        return inst.text if inst is not None else None

    a, b, c, d = p.if_id, p.id_ex, p.ex_mem, p.mem_wb
    return {
        "IF/ID": {"inst": t(a.inst), "bubble": a.bubble, "pc4": a.pc + 4 if a.inst else None},
        "ID/EX": {"inst": t(b.inst), "bubble": b.bubble,
                  "op": b.inst.opcode if b.inst else None,
                  "pc4": b.pc + 4 if b.inst else None,
                  "rs": b.inst.src1 if b.inst else None, "valA": b.val1 if b.inst else None,
                  "rt": b.inst.src2 if b.inst else None, "valB": b.val2 if b.inst else None,
                  "imm": b.inst.imm if b.inst else None,
                  "dest": b.inst.dest if b.inst else None},
        "EX/MEM": {"inst": t(c.inst), "bubble": c.bubble,
                   "op": c.inst.opcode if c.inst else None,
                   "target": c.branch_target if c.inst and c.inst.is_branch else None,
                   "taken": c.branch_taken if c.inst and c.inst.is_branch else None,
                   "alu": c.alu_result if c.inst else None,
                   "valB": c.store_value if c.inst else None,
                   "dest": c.inst.dest if c.inst else None},
        "MEM/WB": {"inst": t(d.inst), "bubble": d.bubble,
                   "op": d.inst.opcode if d.inst else None,
                   "value": d.value if d.inst else None,
                   "dest": d.inst.dest if d.inst else None},
    }


class CPU:
    def __init__(self, forwarding=True, data_hazard=None, control_hazard="predict"):
        if control_hazard not in CONTROL_MODES:
            raise ValueError(f"unknown control hazard mode: {control_hazard}")
        self.regs = RegisterFile()
        self.imem = InstructionMemory()
        self.dmem = DataMemory()
        self.pipeline = Pipeline(self.regs, self.imem, self.dmem)
        self.hazard = HazardUnit(forwarding, mode=data_hazard)
        self.control = control_hazard
        self.reset()

    def reset(self):
        self.regs.__init__()
        self.dmem.__init__()
        self.pipeline.reset()
        self.cycle = 0
        self.finished = False
        self.completed = []         # คำสั่งที่ผ่าน WB แล้ว
        self.history = []           # บันทึกแต่ละ cycle สำหรับตาราง
        self.instances = {}         # seq -> (ข้อความคำสั่ง, pc)  ใช้วาด pipeline diagram
        self._stalled_last_cycle = False
        # ตัวนับสำหรับ performance
        self.stats = {
            "stalls": 0, "load_use_stalls": 0, "data_hazards": 0, "forwards": 0,
            "branches": 0, "branches_taken": 0, "control_hazards": 0,
            "flushes": 0, "flushed_instructions": 0, "control_stalls": 0,
        }

    def load_program(self, program):
        self.imem.load(program)
        self.reset()

    # ------------------------------------------------------------------
    def step(self):
        """จำลอง 1 clock cycle  -> คืน record ของ cycle นั้น"""
        if self.finished:
            return None
        if self.cycle >= MAX_CYCLES:
            raise RuntimeError(f"Exceeded {MAX_CYCLES} cycles (infinite loop?)")
        p, hz, st = self.pipeline, self.hazard, self.stats
        self.cycle += 1
        notes = []

        # สิ่งที่อยู่ในแต่ละ stage ใน cycle นี้ (ไว้แสดงในตาราง)
        cells = {"ID": cell(p.if_id), "EX": cell(p.id_ex), "MEM": cell(p.ex_mem), "WB": cell(p.mem_wb)}
        seqs = {s: (l.seq if l.inst is not None else None)
                for s, l in (("ID", p.if_id), ("EX", p.id_ex), ("MEM", p.ex_mem), ("WB", p.mem_wb))}
        flushed = []
        fetch_pc = p.pc
        kinds = {s: l.bubble for s, l in (("ID", p.if_id), ("EX", p.id_ex), ("MEM", p.ex_mem), ("WB", p.mem_wb))}
        in_if = None if p.fetch_stopped else self.imem.fetch(p.pc)   # คำสั่งที่ IF จะดึงใน cycle นี้
        activity = {"wb": None, "mem": None, "fwd": ["ID/EX", "ID/EX"], "branch": None}

        # 1. WB
        done = p.stage_wb(p.mem_wb)
        if done is not None:
            self.completed.append(done)
            if done.writes_register:
                notes.append(f"WB: R{done.dest}={self.regs.read(done.dest)}")
                activity["wb"] = [done.dest, self.regs.read(done.dest)]

        # 2. MEM
        new_mem_wb = p.stage_mem(p.ex_mem)
        em = p.ex_mem
        if em.inst is not None and em.inst.is_store:
            notes.append(f"MEM: Mem[{em.alu_result}]={em.store_value}")
            activity["mem"] = ["write", em.alu_result, em.store_value]
        elif em.inst is not None and em.inst.is_load:
            activity["mem"] = ["read", em.alu_result, new_mem_wb.value]

        # 3. EX + forwarding
        op1, op2, fwd, srcs = hz.forward_operands(p.id_ex, p.ex_mem, p.mem_wb)
        new_ex_mem = p.stage_ex(p.id_ex, op1, op2)
        notes += fwd
        st["forwards"] += len(fwd)
        activity["fwd"] = srcs

        # 4. Branch resolution (control hazard)
        flush = False
        redirect = None                 # PC ใหม่ถ้า branch taken
        br = new_ex_mem.inst
        if br is not None and br.is_branch:
            st["branches"] += 1
            st["control_hazards"] += 1      # ทุก branch ทำให้ IF ไม่รู้ล่วงหน้าว่าต้อง fetch อะไร
            taken = new_ex_mem.branch_taken
            activity["branch"] = [taken, new_ex_mem.branch_target]
            if taken:
                st["branches_taken"] += 1
                redirect = new_ex_mem.branch_target
            if self.control == "predict":
                if taken:
                    flush = True
                    st["flushes"] += 1
                    victims = [f"{i.short()} ({where})" for i, where in ((p.if_id.inst, "ID"), (in_if, "IF"))
                               if i is not None]
                    st["flushed_instructions"] += len(victims)
                    notes.append(f"BRANCH {br.short()} TAKEN -> PC={redirect}; "
                                 f"FLUSH: {', '.join(victims) if victims else '(nothing)'}")
                else:
                    notes.append(f"BRANCH {br.short()} NOT TAKEN (prediction correct, no penalty)")
            elif self.control == "stall":
                notes.append(f"BRANCH {br.short()} {'TAKEN -> PC=' + str(redirect) if taken else 'NOT TAKEN'}"
                             " (resolved; fetch resumes next cycle)")
            else:   # none
                notes.append(f"BRANCH {br.short()} {'TAKEN -> PC=' + str(redirect) if taken else 'NOT TAKEN'}"
                             " -- next 2 instructions were NOT flushed (no control hazard handling)")

        stall = False
        if flush:
            # ทิ้งคำสั่ง wrong path ทั้ง 2 ตัว แล้วเริ่ม fetch ใหม่ที่ target ใน cycle ถัดไป
            new_if_id = IF_ID(bubble="flush")
            new_id_ex = ID_EX(bubble="flush")
            next_pc = redirect
            p.fetch_stopped = False           # HALT ที่ถูก fetch บน wrong path ไม่นับ
            cells["IF"] = cell(in_if)
            seqs["IF"] = p.take_seq() if in_if is not None else None   # ถูก fetch แล้วทิ้งทันที
            flushed = [x for x in (seqs["ID"], seqs["IF"]) if x is not None]
        else:
            # 5. ID + hazard detection
            if p.if_id.inst is not None and not self._stalled_last_cycle:
                raws = hz.raw_hazards(p.if_id, p.id_ex, p.ex_mem)
                if raws:                # นับ 1 ครั้งต่อคำสั่ง (ไม่นับซ้ำตอน stall หลาย cycle)
                    st["data_hazards"] += 1
                    notes += raws
            stall, reason, load_use = hz.detect_stall(p.if_id, p.id_ex, p.ex_mem)
            # control "stall": ห้าม fetch ขณะที่มี branch อยู่ใน ID (กำลังจะเข้า EX) หรือเพิ่ง resolve ใน EX
            branch_pending = (self.control == "stall" and not stall and
                              ((p.if_id.inst is not None and p.if_id.inst.is_branch) or
                               (br is not None and br.is_branch)))
            if stall:
                new_id_ex = ID_EX(bubble="stall")       # ใส่ bubble เข้า EX
                new_if_id, next_pc = p.if_id, p.pc      # คง IF/ID และ PC ไว้
                cells["IF"] = cell(in_if)
                seqs["IF"] = p.next_seq if in_if is not None else None    # ยังไม่ได้ fetch จริง (รอ)
                notes.append(reason)
                st["stalls"] += 1
                st["load_use_stalls"] += int(load_use)
            elif branch_pending:
                new_id_ex = p.stage_id(p.if_id)
                new_if_id, next_pc = IF_ID(bubble="stall"), p.pc   # ไม่ fetch: รอผล branch
                cells["IF"] = "-"
                seqs["IF"] = None
                waiting = p.if_id.inst if (p.if_id.inst is not None and p.if_id.inst.is_branch) else br
                notes.append(f"STALL (control): fetch waits for {waiting.short()} to resolve")
                st["control_stalls"] += 1
            else:
                new_id_ex = p.stage_id(p.if_id)
                # 6. IF
                new_if_id, next_pc = p.stage_if()
                cells["IF"] = cell(new_if_id)
                seqs["IF"] = new_if_id.seq if new_if_id.inst is not None else None
            if redirect is not None:            # control "stall" / "none": ไป target โดยไม่ flush
                next_pc = redirect
                if self.control == "stall":
                    p.fetch_stopped = False
        self._stalled_last_cycle = stall

        # 7. Commit (clock edge)
        p.if_id, p.id_ex, p.ex_mem, p.mem_wb = new_if_id, new_id_ex, new_ex_mem, new_mem_wb
        p.pc = next_pc

        if seqs["IF"] is not None:
            self.instances[seqs["IF"]] = (in_if.text, fetch_pc)

        record = {"cycle": self.cycle, **cells, "stall": stall, "flush": flush, "notes": notes,
                  # ข้อมูลเพิ่มสำหรับ visualizer / GUI
                  "seq": seqs, "flushed": flushed, "pc": p.pc, "fetch_pc": fetch_pc, "bubble_kind": kinds,
                  "control_stall": (not flush and not stall and cells["IF"] == "-" and
                                    any(n.startswith("STALL (control)") for n in notes)),
                  "activity": activity, "latches": _latch_snapshot(p),
                  "regs": list(self.regs.regs), "mem": dict(self.dmem.data)}
        self.history.append(record)

        if p.is_empty() and p.nothing_left_to_fetch():
            self.finished = True
        return record

    def run(self):
        while not self.finished:
            self.step()
