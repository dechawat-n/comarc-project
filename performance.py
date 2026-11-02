"""
performance.py - Performance metric calculations

สัญลักษณ์:
  C = Total clock cycles (จำนวน cycle ตั้งแต่ cycle 1 จนคำสั่งสุดท้ายออกจาก WB)
  N = Instructions completed (คำสั่งที่ผ่าน WB จริง รวม NOP และ HALT;
      ไม่นับคำสั่งที่ถูก flush และไม่นับ bubble)
  k = จำนวน stage = 5

สูตร:
  CPI                 = C / N
  IPC                 = N / C                    (= 1/CPI)
  Ideal cycles        = N + (k - 1)              (pipeline ไม่มี hazard เลย: เติมท่อ k-1 cycle แล้วจบ 1 คำสั่ง/cycle)
  Lost cycles         = C - Ideal cycles         (cycle ที่เสียไปกับ stall และ flush)
  Pipeline efficiency = Ideal cycles / C x 100%  (100% = ไม่เสีย cycle จาก hazard เลย)
  Stage utilization   = (N x k) / (C x k) x 100% = N / C x 100%
                        (สัดส่วน "ช่อง stage x cycle" ที่มีคำสั่งจริงทำงาน)
  Speedup vs non-pipelined = (N x k) / C
                        (สมมติ CPU แบบไม่ pipeline ใช้ k cycle ต่อคำสั่ง และ clock เท่ากัน)

ตัวนับ hazard (มาจาก cpu.stats):
  Data hazards     = จำนวนคำสั่งที่ตอนอยู่ใน ID มี RAW dependency กับคำสั่งที่ยังอยู่ใน EX/MEM
  Stalls           = จำนวน cycle ที่ pipeline ต้อง stall (ใส่ bubble เข้า EX)
  Control hazards  = จำนวน branch ที่ execute (ทุก branch ทำให้ IF ไม่รู้ PC ถัดไปล่วงหน้า)
  Branch flushes   = จำนวนครั้งที่ branch taken แล้วต้อง flush (ครั้งละ 2 slot)
"""

STAGES = 5


def compute_metrics(cpu):
    C = cpu.cycle
    N = len(cpu.completed)
    st = cpu.stats
    ideal = N + (STAGES - 1) if N else 0
    return {
        "total_cycles": C,
        "instructions_completed": N,
        "cpi": C / N if N else float("nan"),
        "ipc": N / C if C else float("nan"),
        "ideal_cycles": ideal,
        "lost_cycles": C - ideal,
        "efficiency": ideal / C * 100 if C else float("nan"),
        "utilization": N / C * 100 if C else float("nan"),
        "speedup": N * STAGES / C if C else float("nan"),
        "stalls": st["stalls"],
        "load_use_stalls": st["load_use_stalls"],
        "data_hazards": st["data_hazards"],
        "forwards": st["forwards"],
        "control_hazards": st["control_hazards"],
        "branches_taken": st["branches_taken"],
        "branch_flushes": st["flushes"],
        "flushed_instructions": st["flushed_instructions"],
        "forwarding": cpu.hazard.forwarding,
        "data_mode": cpu.hazard.mode,
        "control_mode": cpu.control,
        "control_stalls": st.get("control_stalls", 0),
        "finished": cpu.finished,
    }


def format_report(m):
    rows = [
        ("Data hazard handling", m["data_mode"], ""),
        ("Control hazard handling", m["control_mode"], ""),
        ("Total clock cycles (C)", m["total_cycles"], ""),
        ("Instructions completed (N)", m["instructions_completed"], "incl. NOP/HALT"),
        ("CPI", f"{m['cpi']:.3f}", "C / N"),
        ("IPC", f"{m['ipc']:.3f}", "N / C"),
        ("Ideal cycles", m["ideal_cycles"], "N + 4"),
        ("Lost cycles", m["lost_cycles"], "C - ideal"),
        ("Pipeline efficiency", f"{m['efficiency']:.1f}%", "ideal / C"),
        ("Stage utilization", f"{m['utilization']:.1f}%", "N / C"),
        ("Speedup vs non-pipelined", f"{m['speedup']:.2f}x", "5N / C"),
        ("Data hazards", m["data_hazards"], "RAW detected in ID"),
        ("Forwarding operations", m["forwards"], "per operand"),
        ("Pipeline stalls", m["stalls"], f"load-use: {m['load_use_stalls']}"),
        ("Control hazards", m["control_hazards"], f"taken: {m['branches_taken']}"),
        ("Branch flushes", m["branch_flushes"], f"{m['flushed_instructions']} instr. flushed"),
    ]
    if m["control_stalls"]:
        rows.append(("Control stalls", m["control_stalls"], "fetch waiting for branch"))
    w = max(len(r[0]) for r in rows)
    lines = ["=== Performance Statistics ==="]
    if not m["finished"]:
        lines.append("(simulation still running: ideal/efficiency/speedup are only meaningful after it finishes)")
    for name, val, note in rows:
        lines.append(f"{name:<{w}} : {str(val):<10} {('(' + note + ')') if note else ''}")
    return "\n".join(lines)
