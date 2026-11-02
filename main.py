"""
main.py - Program entry point (Command-Line Interface)

วิธีใช้:
  python3 main.py                              # เมนูแบบโต้ตอบ
  python3 main.py programs/loop.asm            # โหลดไฟล์แล้วเข้าเมนู
  python3 main.py programs/loop.asm --run      # รันจนจบ แสดงตาราง + ผลลัพธ์ + สถิติ
  python3 main.py programs/loop.asm --run --no-forwarding
  python3 main.py programs/loop.asm --compare  # เทียบ forwarding ON vs OFF
  python3 main.py programs/loop.asm --html     # สร้างหน้าเว็บ visualizer แล้วเปิดในเบราว์เซอร์
  python3 main.py --gui                        # เปิด interactive GUI (datapath + พิมพ์โค้ดเอง) ในเบราว์เซอร์
"""

import argparse
import os
import sys
import webbrowser

from cpu import CPU
from display import format_table, STAGES
from instructions import load_program_file, ParseError
from performance import compute_metrics, format_report
from visualizer import export_html


def show_cycle(cpu, record):
    print(f"\n=== Cycle {record['cycle']} ===   (next PC = {cpu.pipeline.pc})")
    for s in STAGES:
        print(f"  {s:<3}: {record[s]}")
    if record["notes"]:
        print("  Events:")
        for n in record["notes"]:
            print(f"   - {n}")
    if cpu.finished:
        print("\n*** Simulation finished ***")


def show_state(cpu):
    print("\n--- Registers (non-zero) ---")
    print(cpu.regs.dump())
    print("--- Data Memory ---")
    print(cpu.dmem.dump())


def show_final(cpu, events=True):
    print("\n" + format_table(cpu.history, events=events))
    show_state(cpu)
    print()
    print(format_report(compute_metrics(cpu)))


def make_html(path, forwarding=True, out=None, open_browser=True):
    """รัน simulation จนจบ แล้วสร้างไฟล์ HTML visualizer (ค่าเริ่มต้น: visual/<ชื่อโปรแกรม>.html)"""
    cpu = load(path, forwarding)
    cpu.run()
    name = os.path.splitext(os.path.basename(path))[0]
    if out is None:
        out = os.path.join("visual", name + ("" if forwarding else "_no_forwarding") + ".html")
    title = os.path.basename(path) + ("" if forwarding else " (no forwarding)")
    full = export_html(cpu, out, title)
    print(f"Visualizer saved to: {full}")
    if open_browser:
        webbrowser.open("file://" + full)
    return full


CONTROL = "predict"


def load(path, forwarding=True):
    """forwarding: True/False หรือชื่อโหมด data hazard ("forwarding" | "stall" | "none")"""
    if isinstance(forwarding, str):
        cpu = CPU(data_hazard=forwarding, control_hazard=CONTROL)
    else:
        cpu = CPU(forwarding=forwarding, control_hazard=CONTROL)
    cpu.load_program(load_program_file(path))
    return cpu


def compare(path):
    results = []
    for fwd in (True, False):
        cpu = load(path, fwd)
        cpu.run()
        results.append(compute_metrics(cpu))
    keys = [("total_cycles", "Cycles"), ("cpi", "CPI"), ("ipc", "IPC"), ("stalls", "Stalls"),
            ("branch_flushes", "Branch flushes"), ("efficiency", "Efficiency %")]
    print(f"Program: {path}")
    print(f"{'Metric':<16}{'Forwarding ON':>15}{'Forwarding OFF':>16}")
    for k, label in keys:
        a, b = results[0][k], results[1][k]
        fmt = (lambda v: f"{v:.1f}") if k == "efficiency" else (lambda v: f"{v:.3f}") if isinstance(a, float) else str
        print(f"{label:<16}{fmt(a):>15}{fmt(b):>16}")


MENU = """
========== CPU Pipeline Simulator ==========
 Program: {prog}   | Forwarding: {fwd}   | Cycle: {cyc}{done}
 1. Load program file
 2. Start / reset simulation
 3. Step one clock cycle
 4. Run until finished
 5. View pipeline execution table
 6. View registers and memory
 7. View performance statistics
 8. Toggle forwarding (resets simulation)
 9. Open visual simulator in web browser
 0. Quit
"""


def interactive(path=None, forwarding=True):
    cpu, prog = None, None
    if path:
        try:
            cpu, prog = load(path, forwarding), path
        except (OSError, ParseError) as e:
            print(f"Error: {e}")
    while True:
        print(MENU.format(prog=prog or "(none)", fwd="ON" if forwarding else "OFF",
                          cyc=cpu.cycle if cpu else "-",
                          done=" (finished)" if cpu and cpu.finished else ""))
        choice = input("Select> ").strip()
        if choice == "0":
            break
        if choice == "1":
            p = input("File path: ").strip()
            try:
                cpu, prog = load(p, forwarding), p
                print(f"Loaded {len(cpu.imem)} instructions from {p}")
            except (OSError, ParseError) as e:
                print(f"Error: {e}")
            continue
        if choice == "8":
            forwarding = not forwarding
            if prog:
                cpu = load(prog, forwarding)
            print(f"Forwarding is now {'ON' if forwarding else 'OFF'}")
            continue
        if cpu is None:
            print("Please load a program first (option 1).")
            continue
        if choice == "9":
            make_html(prog, forwarding)
            continue
        if choice == "2":
            cpu.reset()
            print("Simulation reset to cycle 0.")
        elif choice == "3":
            if cpu.finished:
                print("Simulation already finished.")
            else:
                show_cycle(cpu, cpu.step())
        elif choice == "4":
            cpu.run()
            show_final(cpu)
        elif choice == "5":
            print(format_table(cpu.history) if cpu.history else "(no cycles executed yet)")
        elif choice == "6":
            show_state(cpu)
        elif choice == "7":
            print(format_report(compute_metrics(cpu)))
        else:
            print("Invalid choice.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Educational 5-stage MIPS-like CPU pipeline simulator")
    ap.add_argument("program", nargs="?", help="assembly file (.asm)")
    ap.add_argument("--run", action="store_true", help="run to completion and print results")
    ap.add_argument("--no-forwarding", action="store_true", help="disable data forwarding")
    ap.add_argument("--compare", action="store_true", help="compare forwarding ON vs OFF")
    ap.add_argument("--html", nargs="?", const="", metavar="OUT.html",
                    help="create an interactive HTML visualizer (default: visual/<program>.html) and open it")
    ap.add_argument("--no-open", action="store_true", help="with --html/--gui: do not open the browser")
    ap.add_argument("--gui", action="store_true", help="start the interactive web GUI (http://localhost:8370)")
    ap.add_argument("--data", choices=["forwarding", "stall", "none"], help="data hazard handling mode")
    ap.add_argument("--control", choices=["predict", "stall", "none"], default="predict",
                    help="control hazard handling mode (default: predict not-taken + flush)")
    ap.add_argument("--no-events", action="store_true", help="with --run: hide event lines under each cycle")
    args = ap.parse_args(argv)
    fwd = not args.no_forwarding
    global CONTROL
    CONTROL = args.control

    if args.gui:
        import gui_server
        return gui_server.main(open_browser=not args.no_open)
    if args.data:
        fwd = args.data
    if (args.run or args.compare or args.html is not None) and not args.program:
        ap.error("--run/--compare/--html needs a program file")
    try:
        if args.html is not None:
            make_html(args.program, fwd, args.html or None, not args.no_open)
        elif args.compare:
            compare(args.program)
        elif args.run:
            cpu = load(args.program, fwd)
            cpu.run()
            show_final(cpu, events=not args.no_events)
        else:
            interactive(args.program, fwd)
    except (OSError, ParseError) as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
