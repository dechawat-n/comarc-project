"""
display.py - แสดงผลตาราง pipeline ใน terminal

- events ของแต่ละ cycle แสดงเป็นบรรทัดแยกใต้แถวของ cycle นั้น (อ่านง่ายกว่าใส่ท้ายแถว)
- ใส่สี (ANSI) อัตโนมัติเมื่อแสดงบน terminal; ถ้า redirect ลงไฟล์จะไม่มีสี
  (ปิดสีเองได้ด้วย environment variable NO_COLOR=1)
"""

import os
import sys

STAGES = ("IF", "ID", "EX", "MEM", "WB")

_C = {"reset": "\033[0m", "dim": "\033[2m", "bold": "\033[1m", "yellow": "\033[33m",
      "red": "\033[31m", "green": "\033[32m", "blue": "\033[34m", "magenta": "\033[35m",
      "cyan": "\033[36m"}


def use_color():
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _paint(text, color, on):
    return f"{_C[color]}{text}{_C['reset']}" if on and color else text


def _event_style(note):
    """เลือกสัญลักษณ์และสีตามชนิดของ event"""
    if note.startswith("STALL"):
        return "⏸", "yellow"
    if "TAKEN ->" in note:
        return "↪", "red"
    if "NOT TAKEN" in note:
        return "→", "green"
    if note.startswith("FWD"):
        return "⇢", "blue"
    if note.startswith("RAW"):
        return "!", "magenta"
    if note.startswith(("WB", "MEM")):
        return "✎", "cyan"
    return "•", None


def format_row(record, width=10, color=False, events=True):
    cols = [f"{record['cycle']:>5}"]
    for s in STAGES:
        text = f"{record[s]:<{width}}"
        if record[s] == "bubble":
            text = _paint(text, "yellow", color)
        elif record[s] == "-":
            text = _paint(text, "dim", color)
        cols.append(text)
    lines = [" | ".join(cols)]
    if events:
        notes = record["notes"]
        for k, note in enumerate(notes):
            icon, col = _event_style(note)
            branch = "└─" if k == len(notes) - 1 else "├─"
            lines.append(_paint(f"        {branch} {icon} {note}", col, color))
    return "\n".join(lines)


def format_table(history, width=10, color=None, events=True):
    if color is None:
        color = use_color()
    header = " | ".join([f"{'Cycle':>5}"] + [f"{s:<{width}}" for s in STAGES])
    sep = "-" * len(header)
    rows = []
    for r in history:
        rows.append(format_row(r, width, color, events))
        if events and r["notes"]:
            rows.append("")          # เว้นบรรทัดหลัง cycle ที่มี event ให้อ่านง่าย
    return "\n".join([_paint(header, "bold", color), sep] + rows)
