"""
test_simulator.py - Automated tests

รัน:  python3 -m unittest discover -s tests -v      (จากโฟลเดอร์ pipeline_simulator)

ตรวจ 3 ระดับ:
  1. Unit tests: parser, register file (R0, overflow), memory
  2. Program tests: ค่า register/memory สุดท้าย + จำนวน cycle/stall/flush ที่คำนวณด้วยมือ
     สูตรตรวจ cycle (เมื่อจบด้วย HALT):  C = N + 4 + stalls + 2 x (branch taken)
  3. Golden-model tests: ทุกโปรแกรม x (forwarding ON/OFF) ต้องได้ผลเท่ากับ reference model
"""

import glob
import os
import random
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cpu import CPU                                           # noqa: E402
from instructions import parse_line, parse_program, load_program_file, ParseError  # noqa: E402
from registers import RegisterFile, to_int32                 # noqa: E402
from memory import DataMemory                                 # noqa: E402
from performance import compute_metrics                       # noqa: E402
from reference_model import run_reference                     # noqa: E402

PROGRAMS = os.path.join(ROOT, "programs")


def run(name, forwarding=True):
    cpu = CPU(forwarding=forwarding)
    cpu.load_program(load_program_file(os.path.join(PROGRAMS, name)))
    cpu.run()
    return cpu


# --------------------------------------------------------------------------
class TestUnits(unittest.TestCase):
    def test_r0_is_always_zero(self):
        r = RegisterFile()
        r.write(0, 123)
        self.assertEqual(r.read(0), 0)

    def test_int32_wraparound(self):
        self.assertEqual(to_int32(2**31), -2**31)
        self.assertEqual(to_int32(-2**31 - 1), 2**31 - 1)

    def test_memory_alignment(self):
        m = DataMemory()
        with self.assertRaises(ValueError):
            m.write(3, 1)
        self.assertEqual(m.read(400), 0)

    def test_parse_formats(self):
        i = parse_line("ADD R3, R1, R2")
        self.assertEqual((i.dest, i.src1, i.src2), (3, 1, 2))
        i = parse_line("lw r5 -8(r2)  # comment")
        self.assertEqual((i.opcode, i.dest, i.src1, i.imm), ("LW", 5, 2, -8))
        i = parse_line("SW R3 4(R1)")
        self.assertEqual((i.dest, i.src1, i.src2, i.imm), (None, 1, 3, 4))
        self.assertIsNone(parse_line("   ; only comment"))

    def test_parse_errors(self):
        for bad in ["ADD R1 R2", "MUL R1 R2 R3", "LW R1 R2", "ADD R32 R1 R2", "ADDI R1 R0 x"]:
            with self.assertRaises(ParseError):
                parse_line(bad, 1)


# --------------------------------------------------------------------------
class TestPrograms(unittest.TestCase):
    def assertRegs(self, cpu, expected):
        for r, v in expected.items():
            self.assertEqual(cpu.regs.read(r), v, f"R{r}")

    def assertCycleFormula(self, cpu):
        m = compute_metrics(cpu)
        self.assertEqual(m["total_cycles"],
                         m["instructions_completed"] + 4 + m["stalls"] + 2 * m["branches_taken"])

    # 1. Basic arithmetic
    def test_arithmetic(self):
        c = run("arithmetic.asm")
        self.assertRegs(c, {1: 12, 2: 10, 3: 22, 4: 2, 5: 8, 6: 14, 7: -2, 8: -5,
                            9: 2147483647, 10: -2147483648})
        self.assertEqual(c.stats["stalls"], 0)

    # 2 + 3. Data dependency + forwarding
    def test_forwarding(self):
        c = run("forwarding.asm")
        self.assertRegs(c, {1: 5, 2: 8, 3: 13, 4: 8, 5: 8, 6: 13, 7: 5, 0: 0})
        self.assertEqual(c.stats["stalls"], 0)
        self.assertEqual(c.stats["forwards"], 7)
        self.assertEqual(c.cycle, 13)
        self.assertCycleFormula(c)

    def test_without_forwarding_values_still_correct_but_slower(self):
        on, off = run("forwarding.asm", True), run("forwarding.asm", False)
        self.assertEqual(on.regs.regs, off.regs.regs)
        self.assertEqual(off.stats["forwards"], 0)
        self.assertGreater(off.cycle, on.cycle)

    def test_no_forwarding_needs_nops(self):
        c = run("no_hazard_nops.asm", False)
        self.assertRegs(c, {3: 30})
        self.assertEqual(c.stats["stalls"], 0)

    # 4. Load-use hazard
    def test_load_use(self):
        c = run("load_use.asm")
        self.assertRegs(c, {1: 100, 2: 100, 3: 200, 4: 100})
        self.assertEqual(c.dmem.read(8), 100)
        self.assertEqual(c.stats["load_use_stalls"], 1)
        self.assertEqual(c.cycle, 11)
        self.assertCycleFormula(c)

    # 5. Pipeline stalls (หลายแบบ)
    def test_stalls(self):
        c = run("stalls.asm")
        self.assertRegs(c, {3: 7, 4: 7, 5: 0, 6: 7, 7: 14})
        self.assertEqual((c.dmem.read(8), c.dmem.read(12)), (7, 7))
        self.assertEqual(c.stats["stalls"], 3)
        self.assertEqual(c.stats["flushes"], 1)
        self.assertCycleFormula(c)

    # 6 + 7. Branch taken / not taken + flushing
    def test_branch_taken_flush(self):
        c = run("branch_taken.asm")
        self.assertRegs(c, {1: 5, 2: 5, 3: 0, 4: 0, 5: 333})
        self.assertEqual(c.stats["flushes"], 1)
        self.assertEqual(c.stats["flushed_instructions"], 2)
        self.assertCycleFormula(c)

    def test_branch_not_taken(self):
        c = run("branch_not_taken.asm")
        self.assertRegs(c, {3: 111, 4: 222, 5: 0, 6: 444})
        self.assertEqual(c.stats["branches"], 2)
        self.assertEqual(c.stats["branches_taken"], 1)
        self.assertCycleFormula(c)

    def test_loop(self):
        c = run("loop.asm")
        self.assertRegs(c, {1: 15, 2: 0})
        self.assertEqual(c.dmem.read(0), 15)
        self.assertEqual(c.stats["branches_taken"], 4)
        self.assertEqual(c.stats["flushed_instructions"], 8)
        self.assertEqual(c.cycle, 31)
        self.assertCycleFormula(c)

    # 8. Memory load/store
    def test_memory(self):
        c = run("memory.asm")
        self.assertRegs(c, {5: 22, 6: -33, 7: 11, 8: 0, 9: -11})
        self.assertEqual(c.dmem.data, {96: -33, 100: 11, 104: 22})

    # 9. Program termination
    def test_halt(self):
        c = run("halt.asm")
        self.assertRegs(c, {1: 1, 2: 0, 3: 0})
        self.assertEqual(len(c.completed), 2)
        self.assertEqual(c.cycle, 6)

    def test_spec_example_branch_past_end(self):
        c = run("example.asm")
        self.assertRegs(c, {1: 10, 2: 20, 3: 30, 4: 20, 5: 30})
        self.assertEqual(c.dmem.read(0), 30)
        self.assertEqual(c.stats["flushes"], 1)   # NOP + HALT ถูก flush, โปรแกรมจบเพราะ PC เลยท้าย

    def test_infinite_loop_guard(self):
        cpu = CPU()
        cpu.load_program(parse_program("BEQ R0 R0 -1"))
        with self.assertRaises(RuntimeError):
            cpu.run()


# --------------------------------------------------------------------------
class TestAgainstReferenceModel(unittest.TestCase):
    """ทุกโปรแกรม x ทุกโหมด ต้องให้ผลเหมือน CPU แบบไม่มี pipeline"""

    def test_all_programs(self):
        files = sorted(glob.glob(os.path.join(PROGRAMS, "*.asm")))
        self.assertGreater(len(files), 0)
        for f in files:
            prog = load_program_file(f)
            ref_regs, ref_mem, ref_count = run_reference(prog)
            for fwd in (True, False):
                with self.subTest(program=os.path.basename(f), forwarding=fwd):
                    cpu = CPU(forwarding=fwd)
                    cpu.load_program(prog)
                    cpu.run()
                    self.assertEqual(cpu.regs.regs, ref_regs)
                    self.assertEqual(cpu.dmem.data, ref_mem)
                    self.assertEqual(len(cpu.completed), ref_count)

    def test_control_stall_mode_matches_reference(self):
        """control hazard แบบ Detect-and-Stall ต้องให้ผลถูกเหมือนกัน (แค่ช้ากว่า)"""
        for f in sorted(glob.glob(os.path.join(PROGRAMS, "*.asm"))):
            prog = load_program_file(f)
            ref = run_reference(prog)
            for data in ("forwarding", "stall"):
                with self.subTest(program=os.path.basename(f), data=data):
                    cpu = CPU(data_hazard=data, control_hazard="stall")
                    cpu.load_program(prog)
                    cpu.run()
                    self.assertEqual((cpu.regs.regs, cpu.dmem.data, len(cpu.completed)), ref)
                    self.assertEqual(cpu.stats["flushes"], 0)
                    self.assertEqual(cpu.stats["control_stalls"], 2 * cpu.stats["branches"])

    def test_no_hazard_handling_gives_wrong_result(self):
        """โหมด none: ไม่มี hazard unit -> example.asm ได้ค่าผิดแบบเดียวกับขั้นที่ 3 ของการพัฒนา"""
        cpu = CPU(data_hazard="none")
        cpu.load_program(load_program_file(os.path.join(PROGRAMS, "example.asm")))
        cpu.run()
        self.assertEqual((cpu.regs.read(3), cpu.regs.read(4)), (0, -10))
        # แต่ถ้าใส่ NOP เองอย่างพอเพียง โหมด none ก็ให้ผลถูก
        cpu = CPU(data_hazard="none")
        cpu.load_program(load_program_file(os.path.join(PROGRAMS, "no_hazard_nops.asm")))
        cpu.run()
        self.assertEqual(cpu.regs.read(3), 30)

    def test_control_none_executes_two_slots_after_branch(self):
        cpu = CPU(control_hazard="none")
        cpu.load_program(load_program_file(os.path.join(PROGRAMS, "branch_taken.asm")))
        cpu.run()
        self.assertEqual((cpu.regs.read(3), cpu.regs.read(4), cpu.regs.read(5)), (111, 222, 333))

    def test_gui_server_simulate(self):
        import gui_server
        with open(os.path.join(PROGRAMS, "load_use.asm"), encoding="utf-8") as f:
            r = gui_server.simulate(f.read())
        self.assertTrue(r["ok"])
        self.assertTrue(r["reference"]["match"])
        self.assertEqual(len(r["trace"]["cycles"]), 11)
        with open(os.path.join(PROGRAMS, "example.asm"), encoding="utf-8") as f:
            r = gui_server.simulate(f.read(), "none", "predict")
        self.assertFalse(r["reference"]["match"])

    def test_random_programs(self):
        """สุ่มโปรแกรม 500 ตัว (dependency หนาแน่น, LW/SW, branch ไปข้างหน้า) เทียบกับ reference"""
        rng = random.Random(2026)
        regs = [f"R{i}" for i in range(0, 6)]          # ใช้ register น้อย -> dependency เยอะ
        for n in range(500):
            lines = [f"ADDI R{r} R0 {rng.randint(-20, 20)}" for r in range(1, 6)]
            length = rng.randint(5, 25)
            for k in range(length):
                op = rng.choice(["ADD", "SUB", "AND", "OR", "ADDI", "LW", "SW", "BEQ", "BNE", "NOP"])
                a, b, c = (rng.choice(regs) for _ in range(3))
                if op in ("ADD", "SUB", "AND", "OR"):
                    lines.append(f"{op} {a} {b} {c}")
                elif op == "ADDI":
                    lines.append(f"ADDI {a} {b} {rng.randint(-5, 5)}")
                elif op in ("LW", "SW"):
                    lines.append(f"{op} {a} {4 * rng.randint(0, 7)}(R0)")
                elif op in ("BEQ", "BNE"):
                    lines.append(f"{op} {a} {b} {rng.randint(0, 3)}")   # forward only -> จบแน่นอน
                else:
                    lines.append("NOP")
            if rng.random() < 0.8:
                lines.append("HALT")
            prog = parse_program("\n".join(lines))
            ref = run_reference(prog)
            for fwd in (True, False):
                with self.subTest(n=n, forwarding=fwd):
                    cpu = CPU(forwarding=fwd)
                    cpu.load_program(prog)
                    cpu.run()
                    self.assertEqual((cpu.regs.regs, cpu.dmem.data, len(cpu.completed)), ref,
                                     "\n".join(lines))


if __name__ == "__main__":
    unittest.main(verbosity=2)
