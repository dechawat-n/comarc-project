"""
gui_server.py - Interactive Web GUI (แนวเดียวกับ UMich EECS 370 pipeline simulator)

รัน:  python3 gui_server.py        หรือ   python3 main.py --gui
แล้วเบราว์เซอร์จะเปิด http://localhost:8370 ให้อัตโนมัติ (กด Ctrl+C ใน Terminal เพื่อปิด)

สถาปัตยกรรม:
  เบราว์เซอร์ (gui/index.html)  --POST /api/simulate {source, data, control}-->  Python (ไฟล์นี้)
                                <-- JSON: สถานะทุก cycle (latch, activity, registers, memory)
  - การจำลอง pipeline ทั้งหมดทำโดย cpu.py ตัวเดิม; หน้าเว็บมีหน้าที่ "แสดงผล" เท่านั้น
  - ใช้แค่ Python standard library (http.server) ไม่ต้องติดตั้งอะไรเพิ่ม
  - เปิดให้เข้าถึงเฉพาะเครื่องตัวเอง (127.0.0.1)
"""

import glob
import json
import os
import sys
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from cpu import CPU, CONTROL_MODES                 # noqa: E402
from hazard import DATA_MODES                      # noqa: E402
from instructions import parse_program, ParseError  # noqa: E402
from reference_model import run_reference          # noqa: E402
from visualizer import build_data                  # noqa: E402

GUI_CYCLE_LIMIT = 1000      # หน้าเว็บแสดงได้สูงสุดกี่ cycle (กันโปรแกรมวนไม่รู้จบ)
INDEX = os.path.join(ROOT, "gui", "index.html")


def simulate(source, data_mode="forwarding", control_mode="predict", limit=GUI_CYCLE_LIMIT):
    if data_mode not in DATA_MODES or control_mode not in CONTROL_MODES:
        raise ValueError("unknown hazard mode")
    program = parse_program(source)
    if not program:
        raise ParseError("Program is empty")
    cpu = CPU(data_hazard=data_mode, control_hazard=control_mode)
    cpu.load_program(program)
    warning = None
    while not cpu.finished:
        if cpu.cycle >= limit:
            warning = (f"หยุดแสดงที่ {limit} cycles: โปรแกรมอาจวนไม่รู้จบ "
                       "(มักเกิดเมื่อเลือก None แล้ว hazard ทำให้ค่าตัวนับ loop ผิด)")
            break
        cpu.step()
    data = build_data(cpu, "program")

    # เทียบกับ reference model (CPU ที่ไม่มี pipeline) -> บอกได้ว่า hazard ทำให้ผลผิดไหม
    ref = {"match": None, "diff": []}
    try:
        ref_regs, ref_mem, _ = run_reference(program, max_steps=200_000)
        if cpu.finished:
            diff = [f"R{i}: pipeline={a}, ควรเป็น {b}" for i, (a, b) in enumerate(zip(cpu.regs.regs, ref_regs)) if a != b]
            for addr in sorted(set(ref_mem) | set(cpu.dmem.data)):
                a, b = cpu.dmem.data.get(addr, 0), ref_mem.get(addr, 0)
                if a != b:
                    diff.append(f"Mem[{addr}]: pipeline={a}, ควรเป็น {b}")
            ref = {"match": not diff, "diff": diff}
    except RuntimeError:
        ref = {"match": None, "diff": ["reference model: โปรแกรมนี้วนไม่รู้จบแม้รันแบบไม่มี pipeline"]}
    return {"ok": True, "trace": data, "reference": ref, "warning": warning}


def list_programs():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "programs", "*.asm"))):
        with open(f, encoding="utf-8") as fh:
            out.append({"name": os.path.basename(f), "source": fh.read()})
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            with open(INDEX, "rb") as f:
                self._send(200, f.read(), "text/html; charset=utf-8")
        elif self.path == "/api/programs":
            self._send(200, list_programs())
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/api/simulate":
            return self._send(404, {"ok": False, "error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            self._send(200, simulate(req.get("source", ""), req.get("data", "forwarding"),
                                     req.get("control", "predict")))
        except (ParseError, ValueError) as e:
            self._send(200, {"ok": False, "error": str(e)})
        except Exception as e:                      # แสดง error ให้ผู้ใช้เห็นแทนที่ server จะล่ม
            self._send(200, {"ok": False, "error": f"{type(e).__name__}: {e}"})

    def log_message(self, *args):                  # ไม่พิมพ์ log ทุก request ลง terminal
        pass


def main(port=8370, open_browser=True):
    server = None
    for p in range(port, port + 20):               # ถ้า port ถูกใช้อยู่ ลอง port ถัดไป
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            break
        except OSError:
            continue
    if server is None:
        print("Error: no free port found")
        return 1
    url = f"http://localhost:{server.server_address[1]}/"
    print(f"Pipeline Simulator GUI running at {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main(open_browser="--no-open" not in sys.argv))
