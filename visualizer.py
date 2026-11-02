"""
visualizer.py - สร้างหน้าเว็บ (HTML ไฟล์เดียว) สำหรับดูการทำงานของ pipeline แบบ interactive

หลักการ: Python รัน simulation จริงทั้งหมด (cpu.py) แล้วบันทึกสถานะทุก cycle
          -> ไฟล์นี้แปลงสถานะเหล่านั้นเป็น JSON ฝังลงในหน้า HTML
          -> หน้าเว็บมีหน้าที่ "แสดงผล" อย่างเดียว ไม่ได้คำนวณ pipeline เอง

เปิดไฟล์ HTML ด้วยเบราว์เซอร์ได้เลย ไม่ต้องใช้อินเทอร์เน็ตหรือติดตั้งอะไรเพิ่ม
"""

import html
import json
import math
import os

from display import STAGES
from performance import compute_metrics


def build_data(cpu, title):
    cycles = []
    for r in cpu.history:
        cycles.append({
            "cycle": r["cycle"],
            "cells": {s: r[s] for s in STAGES},
            "seq": r["seq"],
            "stall": r["stall"],
            "flush": r["flush"],
            "flushed": r["flushed"],
            "bubble_kind": r["bubble_kind"],
            "fetch_pc": r.get("fetch_pc"),
            "control_stall": r.get("control_stall", False),
            "latches": r.get("latches"),
            "activity": r.get("activity"),
            "notes": r["notes"],
            "pc": r["pc"],
            "regs": r["regs"],
            "mem": [[a, v] for a, v in sorted(r["mem"].items())],
        })
    metrics = {k: (None if isinstance(v, float) and math.isnan(v) else v)
               for k, v in compute_metrics(cpu).items()}
    return {
        "title": title,
        "forwarding": cpu.hazard.forwarding,
        "data_mode": cpu.hazard.mode,
        "control_mode": cpu.control,
        "finished": cpu.finished,
        "program": [{"pc": 4 * i, "text": inst.text} for i, inst in enumerate(cpu.imem.instructions)],
        "instances": [{"seq": s, "text": t, "pc": pc} for s, (t, pc) in sorted(cpu.instances.items())],
        "cycles": cycles,
        "metrics": metrics,
    }


def export_html(cpu, path, title):
    data = json.dumps(build_data(cpu, title), ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.replace("__TITLE__", html.escape(title)).replace("__DATA__", data)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return os.path.abspath(path)


TEMPLATE = r"""<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pipeline Visualizer – __TITLE__</title>
<style>
:root{
  --bg:#f4f5f7; --panel:#ffffff; --ink:#1c2230; --muted:#6b7280; --line:#e2e5ea; --soft:#f0f2f5;
  --IF:#2563eb; --ID:#7c3aed; --EX:#ea580c; --MEM:#16a34a; --WB:#0f766e;
  --stall:#d97706; --flush:#dc2626; --fwd:#2563eb; --raw:#9333ea; --chg:#fde68a; --onc:#ffffff;
}
@media (prefers-color-scheme: dark){
  :root{ --bg:#0e1116; --panel:#161a22; --ink:#e5e8ee; --muted:#98a1b0; --line:#272d38; --soft:#1d222c;
    --IF:#60a5fa; --ID:#a78bfa; --EX:#fb923c; --MEM:#4ade80; --WB:#2dd4bf;
    --stall:#fbbf24; --flush:#f87171; --fwd:#60a5fa; --raw:#c084fc; --chg:#5b4a10; --onc:#0e1116; }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans Thai","Thonburi",sans-serif}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.wrap{max-width:1240px;margin:0 auto;padding:16px}
header{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:12px}
h1{font-size:20px;margin:0}
h2{font-size:14px;margin:0 0 10px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
h2 small{text-transform:none;letter-spacing:0;font-weight:400}
.chip{display:inline-block;padding:2px 10px;border-radius:99px;background:var(--soft);border:1px solid var(--line);
  font-size:12px;margin-left:6px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:14px}
.controls{position:sticky;top:0;z-index:10;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
button{font:inherit;border:1px solid var(--line);background:var(--soft);color:var(--ink);border-radius:8px;
  padding:6px 12px;cursor:pointer;min-width:40px}
button:hover{border-color:var(--muted)}
button.primary{background:var(--IF);border-color:var(--IF);color:var(--onc);min-width:90px}
.cyc{font-size:16px;font-weight:700;min-width:120px;text-align:center}
input[type=range]{flex:1;min-width:140px;accent-color:var(--IF)}
.speed{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:12px}
.hint{color:var(--muted);font-size:12px;width:100%}

/* --- 5 stage boxes --- */
.stages{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:22px;position:relative}
.stage{border:2px solid var(--c);border-radius:10px;padding:10px 10px 12px;min-height:96px;position:relative;background:var(--panel)}
.stage:not(:last-child)::after{content:"▶";position:absolute;right:-18px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:12px}
.stage .nm{font-weight:800;color:var(--c);font-size:15px}
.stage .ds{color:var(--muted);font-size:11px}
.stage .in{margin-top:8px;font-size:14px;font-weight:600;word-break:break-word}
.stage.empty .in{color:var(--muted);font-weight:400}
.stage.bubble{border-style:dashed}
.stage.bubble .in{color:var(--stall)}
.stage.bubble.fl .in{color:var(--flush)}
.stage .tags{position:absolute;top:8px;right:8px;display:flex;gap:4px}
.tag{font-size:10px;font-weight:700;padding:1px 6px;border-radius:99px;color:var(--onc)}
.tag.stall{background:var(--stall)} .tag.flush{background:var(--flush)} .tag.fwd{background:var(--fwd)}
.tag.taken{background:var(--flush)} .tag.nt{background:var(--MEM)}
.stage.dead .in{text-decoration:line-through;opacity:.6}

/* --- events --- */
.events{list-style:none;margin:12px 0 0;padding:0;display:grid;gap:6px}
.events li{padding:6px 10px;border-radius:8px;border-left:4px solid var(--k);background:var(--soft);font-size:13px}
.events .ico{display:inline-block;width:20px;font-weight:700;color:var(--k)}
.events .th{color:var(--muted);font-size:12px;margin-left:6px}
.noev{color:var(--muted);font-size:13px;margin-top:12px}

/* --- pipeline diagram --- */
.gridwrap{overflow:auto;max-height:520px;border:1px solid var(--line);border-radius:8px}
table.pd{border-collapse:separate;border-spacing:0;font-size:12px}
table.pd th,table.pd td{padding:0;text-align:center;border-bottom:1px solid var(--line)}
table.pd thead th{position:sticky;top:0;background:var(--panel);z-index:2;min-width:38px;height:28px;cursor:pointer;color:var(--muted)}
table.pd th.lbl,table.pd td.lbl{position:sticky;left:0;background:var(--panel);z-index:1;text-align:left;
  padding:0 12px;white-space:nowrap;min-width:150px;border-right:1px solid var(--line)}
table.pd thead th.lbl{z-index:3}
table.pd td.c{height:28px;min-width:38px;cursor:pointer}
table.pd td.c span{display:inline-block;min-width:32px;padding:2px 0;border-radius:5px;color:var(--onc);font-weight:700;font-size:11px}
table.pd .cur{background:color-mix(in srgb,var(--IF) 10%,transparent)}
table.pd thead th.cur{color:var(--IF);font-weight:800}
td.c span.st{background:repeating-linear-gradient(45deg,var(--stall) 0 4px,color-mix(in srgb,var(--stall) 70%,#000) 4px 8px)}
td.c span.fl{background:var(--flush);text-decoration:line-through}
tr.flushed td.lbl{color:var(--flush);text-decoration:line-through}
tr.hl td.lbl{font-weight:800}

/* --- program / regs / mem --- */
.cols{display:grid;grid-template-columns:1.1fr 1.5fr .8fr;gap:14px}
.prog{font-size:13px}
.prog div{display:flex;align-items:center;gap:8px;padding:3px 6px;border-radius:6px}
.prog .addr{color:var(--muted);width:44px}
.prog .txt{flex:1}
.prog .badges span{font-size:10px;font-weight:700;color:var(--onc);padding:1px 5px;border-radius:4px;margin-left:3px}
.prog div.pcrow{background:var(--soft)}
.regs{display:grid;grid-template-columns:repeat(4,1fr);gap:4px}
.reg{display:flex;justify-content:space-between;padding:3px 8px;border-radius:6px;background:var(--soft);font-size:12px;transition:background .3s}
.reg .rn{color:var(--muted)}
.reg.zero .rv{color:var(--muted)}
.reg.chg{background:var(--chg);font-weight:700}
.mem div{display:flex;justify-content:space-between;padding:3px 8px;border-radius:6px;background:var(--soft);margin-bottom:4px;font-size:12px}
.mem div.chg{background:var(--chg);font-weight:700}
.muted{color:var(--muted)}

/* --- stats + legend --- */
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:8px}
.stat{background:var(--soft);border-radius:8px;padding:8px 10px}
.stat .v{font-size:20px;font-weight:800}
.stat .k{font-size:12px;color:var(--muted)}
.legend{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--muted)}
.legend span.sw{display:inline-block;width:26px;height:14px;border-radius:4px;vertical-align:middle;margin-right:5px}

@media (max-width:900px){
  .cols{grid-template-columns:1fr}
  .stages{grid-template-columns:repeat(5,minmax(110px,1fr));overflow-x:auto;gap:14px}
  .stage:not(:last-child)::after{right:-12px}
}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>CPU Pipeline Visualizer <span class="muted mono" id="ttl"></span></h1>
    <div id="chips"></div>
  </header>

  <div class="panel controls">
    <button id="bFirst" title="ไป cycle แรก (Home)">⏮</button>
    <button id="bPrev"  title="ย้อน 1 cycle (←)">◀</button>
    <button id="bPlay"  class="primary" title="เล่น/หยุด (Space)">▶ Play</button>
    <button id="bNext"  title="ไป 1 cycle (→)">▶</button>
    <button id="bLast"  title="ไป cycle สุดท้าย (End)">⏭</button>
    <div class="cyc" id="cyc"></div>
    <input type="range" id="slider" min="1" value="1">
    <div class="speed">ช้า<input type="range" id="speed" min="150" max="1500" step="50" value="800" style="flex:0;width:90px;direction:rtl">เร็ว</div>
    <div class="hint">ใช้แป้น ← → เพื่อเดินทีละ cycle, Space = เล่น/หยุด · คลิกที่ตาราง Pipeline Diagram เพื่อกระโดดไป cycle นั้น</div>
  </div>

  <div class="panel">
    <h2>Pipeline ใน cycle นี้</h2>
    <div class="stages" id="stages"></div>
    <div id="events"></div>
  </div>

  <div class="panel">
    <h2>Pipeline Diagram <small>(แถว = คำสั่งแต่ละตัว, คอลัมน์ = clock cycle)</small></h2>
    <div class="gridwrap" id="gridwrap"></div>
    <div class="legend" style="margin-top:10px" id="legend"></div>
  </div>

  <div class="cols">
    <div class="panel"><h2>Program <small>(PC ถัดไป = <span id="pcv" class="mono"></span>)</small></h2><div class="prog mono" id="prog"></div></div>
    <div class="panel"><h2>Registers <small>(สีเหลือง = เพิ่งถูกเขียนใน cycle นี้)</small></h2><div class="regs mono" id="regs"></div></div>
    <div class="panel"><h2>Data Memory</h2><div class="mem mono" id="mem"></div></div>
  </div>

  <div class="panel">
    <h2>Performance <small>(ค่าเมื่อรันจบ)</small></h2>
    <div class="stats" id="stats"></div>
  </div>
</div>

<script>
const D = __DATA__;
const STAGES = ["IF","ID","EX","MEM","WB"];
const DESC = {IF:"ดึงคำสั่ง (Fetch)", ID:"ถอดรหัส + อ่าน register", EX:"คำนวณ ALU / branch", MEM:"อ่าน/เขียน memory", WB:"เขียนผลกลับ register"};
const N = D.cycles.length;
const inst = Object.fromEntries(D.instances.map(i => [i.seq, i]));
const $ = id => document.getElementById(id);
let cur = 0, timer = null;

// ---------- static parts ----------
$("ttl").textContent = "· " + D.title;
const m = D.metrics;
$("chips").innerHTML =
  `<span class="chip">Forwarding: <b>${D.forwarding ? "ON" : "OFF"}</b></span>` +
  `<span class="chip">Branch: predict not-taken, resolve at EX</span>` +
  `<span class="chip">${m.total_cycles} cycles · CPI ${m.cpi == null ? "-" : m.cpi.toFixed(2)}</span>`;
$("slider").max = N;

function kindOf(note){
  if (note.startsWith("STALL")) return ["⏸","var(--stall)","หยุดรอ (stall): ใส่ bubble เข้า EX, คง IF/ID และ PC ไว้"];
  if (note.includes("TAKEN ->")) return ["↪","var(--flush)","branch taken: ทิ้งคำสั่งใน IF และ ID ที่ fetch มาผิดทาง"];
  if (note.includes("NOT TAKEN")) return ["→","var(--MEM)","เดาว่าไม่ taken ถูกต้อง ไม่เสีย cycle"];
  if (note.startsWith("FWD")) return ["⇢","var(--fwd)","ส่งค่าตรงจาก pipeline register เข้า ALU (ไม่ต้องรอ WB)"];
  if (note.startsWith("RAW")) return ["!","var(--raw)","ตรวจเจอ data dependency กับคำสั่งที่ยังไม่เขียนผล"];
  if (note.startsWith("WB")) return ["✎","var(--WB)","เขียนผลลง register"];
  if (note.startsWith("MEM")) return ["✎","var(--MEM)","SW เขียนลง data memory"];
  return ["•","var(--muted)",""];
}
const esc = s => String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

// ---------- pipeline diagram (built once) ----------
(function buildGrid(){
  // where[seq][cycleIndex] = {stage, st:stall?, fl:flushed?}
  const where = {};
  D.cycles.forEach((c, ci) => {
    STAGES.forEach(s => {
      const q = c.seq[s];
      if (q == null) return;
      (where[q] ||= {})[ci] = {
        stage: s,
        st: c.stall && (s === "IF" || s === "ID"),
        fl: c.flush && c.flushed.includes(q)
      };
    });
  });
  const flushedSet = new Set(D.cycles.flatMap(c => c.flushed));
  let h = '<table class="pd"><thead><tr><th class="lbl">Instruction</th>';
  for (let i = 0; i < N; i++) h += `<th data-c="${i}">${i + 1}</th>`;
  h += "</tr></thead><tbody>";
  D.instances.forEach(it => {
    const w = where[it.seq] || {};
    h += `<tr data-s="${it.seq}" class="${flushedSet.has(it.seq) ? "flushed" : ""}"><td class="lbl mono">${esc(it.text)}</td>`;
    for (let i = 0; i < N; i++) {
      const x = w[i];
      if (!x) { h += `<td class="c" data-c="${i}"></td>`; continue; }
      const cls = x.fl ? "fl" : x.st ? "st" : "";
      const bg = cls ? "" : `style="background:var(--${x.stage})"`;
      const t = x.fl ? `${x.stage}✗` : x.stage;
      h += `<td class="c" data-c="${i}"><span class="${cls}" ${bg}>${t}</span></td>`;
    }
    h += "</tr>";
  });
  $("gridwrap").innerHTML = h + "</tbody></table>";
  $("gridwrap").addEventListener("click", e => {
    const td = e.target.closest("[data-c]");
    if (td) { stop(); show(+td.dataset.c); }
  });
  $("legend").innerHTML = STAGES.map(s => `<span><span class="sw" style="background:var(--${s})"></span>${s}</span>`).join("") +
    `<span><span class="sw" style="background:repeating-linear-gradient(45deg,var(--stall) 0 4px,#8a5a00 4px 8px)"></span>stall (ค้างอยู่ stage เดิม)</span>` +
    `<span><span class="sw" style="background:var(--flush)"></span>flushed ✗ (ถูกทิ้งเพราะ branch taken)</span>`;
})();

// ---------- render one cycle ----------
function show(i){
  cur = Math.max(0, Math.min(N - 1, i));
  const c = D.cycles[cur], prev = cur > 0 ? D.cycles[cur - 1] : null;
  $("cyc").textContent = `Cycle ${c.cycle} / ${N}`;
  $("slider").value = cur + 1;

  // stage boxes
  const fwdTo = c.notes.some(n => n.startsWith("FWD"));
  const brNote = c.notes.find(n => n.startsWith("BRANCH"));
  $("stages").innerHTML = STAGES.map(s => {
    const q = c.seq[s], txt = q != null ? inst[q].text : null, cell = c.cells[s];
    let cls = "stage", tags = "";
    if (txt == null) cls += cell === "bubble" ? " bubble" : " empty";
    const bk = (c.bubble_kind || {})[s];
    if (cell === "bubble" && bk === "flush") cls += " fl";
    if (c.stall && (s === "IF" || s === "ID") && txt) tags += '<span class="tag stall">STALL</span>';
    if (c.flush && (s === "IF" || s === "ID") && txt) { tags += '<span class="tag flush">FLUSH</span>'; cls += " dead"; }
    if (s === "EX" && fwdTo) tags += '<span class="tag fwd">FWD</span>';
    if (s === "EX" && brNote) tags += brNote.includes("NOT TAKEN") ? '<span class="tag nt">NOT TAKEN</span>' : '<span class="tag taken">TAKEN</span>';
    const body = txt != null ? esc(txt) : (cell === "bubble" ? `bubble <small>(จาก ${bk})</small>` : "ว่าง");
    return `<div class="${cls}" style="--c:var(--${s})"><div class="tags">${tags}</div>
      <div class="nm">${s}</div><div class="ds">${DESC[s]}</div><div class="in mono">${body}</div></div>`;
  }).join("");

  // events
  $("events").innerHTML = c.notes.length
    ? '<ul class="events">' + c.notes.map(n => {
        const [ico, col, th] = kindOf(n);
        return `<li style="--k:${col}"><span class="ico">${ico}</span><span class="mono">${esc(n)}</span>${th ? `<span class="th">— ${th}</span>` : ""}</li>`;
      }).join("") + "</ul>"
    : '<div class="noev">ไม่มี hazard หรือ event พิเศษใน cycle นี้ ทุก stage ขยับไปข้างหน้าตามปกติ</div>';

  // diagram highlight
  document.querySelectorAll("table.pd .cur").forEach(e => e.classList.remove("cur"));
  document.querySelectorAll(`table.pd [data-c="${cur}"]`).forEach(e => e.classList.add("cur"));
  const th = document.querySelector(`table.pd thead th[data-c="${cur}"]`);
  if (th) {
    const gw = $("gridwrap"), left = th.offsetLeft - 160;
    if (left < gw.scrollLeft || th.offsetLeft + 40 > gw.scrollLeft + gw.clientWidth) gw.scrollLeft = Math.max(0, left - 80);
  }
  const active = new Set(STAGES.map(s => c.seq[s]).filter(q => q != null));
  document.querySelectorAll("table.pd tbody tr").forEach(tr => tr.classList.toggle("hl", active.has(+tr.dataset.s)));

  // program listing with stage badges
  const badges = {};
  STAGES.forEach(s => { const q = c.seq[s]; if (q != null) (badges[inst[q].pc] ||= []).push(s); });
  const fetchPc = c.seq.IF != null ? inst[c.seq.IF].pc : null;
  $("prog").innerHTML = D.program.map(p => {
    const b = (badges[p.pc] || []).map(s => `<span style="background:var(--${s})">${s}</span>`).join("");
    return `<div class="${p.pc === fetchPc ? "pcrow" : ""}"><span class="addr">${p.pc}</span><span class="txt">${esc(p.text)}</span><span class="badges">${b}</span></div>`;
  }).join("");
  $("pcv").textContent = c.pc;

  // registers
  const pr = prev ? prev.regs : new Array(32).fill(0);
  $("regs").innerHTML = c.regs.map((v, r) =>
    `<div class="reg ${v === 0 ? "zero" : ""} ${v !== pr[r] ? "chg" : ""}"><span class="rn">R${r}</span><span class="rv">${v}</span></div>`).join("");

  // memory
  const pm = Object.fromEntries(prev ? prev.mem : []);
  $("mem").innerHTML = c.mem.length
    ? c.mem.map(([a, v]) => `<div class="${pm[a] !== v ? "chg" : ""}"><span>Mem[${a}]</span><b>${v}</b></div>`).join("")
    : '<span class="muted">ยังไม่มีการเขียน memory</span>';
}

// ---------- stats ----------
const fmt = (v, d = 2) => v == null ? "-" : (typeof v === "number" && !Number.isInteger(v) ? v.toFixed(d) : v);
$("stats").innerHTML = [
  ["Total cycles", m.total_cycles], ["Instructions completed", m.instructions_completed],
  ["CPI", fmt(m.cpi, 3)], ["IPC", fmt(m.ipc, 3)],
  ["Pipeline efficiency", fmt(m.efficiency, 1) + "%"], ["Speedup vs non-pipelined", fmt(m.speedup) + "×"],
  ["Data hazards", m.data_hazards], ["Forwarding operations", m.forwards],
  ["Stalls", `${m.stalls} <small class="muted">(load-use ${m.load_use_stalls})</small>`],
  ["Control hazards", m.control_hazards], ["Branch flushes", `${m.branch_flushes} <small class="muted">(${m.flushed_instructions} instr.)</small>`],
  ["Lost cycles", m.lost_cycles],
].map(([k, v]) => `<div class="stat"><div class="v">${v}</div><div class="k">${k}</div></div>`).join("");

// ---------- controls ----------
function stop(){ if (timer) { clearInterval(timer); timer = null; } $("bPlay").textContent = "▶ Play"; }
function play(){
  if (timer) return stop();
  if (cur >= N - 1) show(0);
  $("bPlay").textContent = "⏸ Pause";
  timer = setInterval(() => { if (cur >= N - 1) stop(); else show(cur + 1); }, +$("speed").value);
}
$("bFirst").onclick = () => { stop(); show(0); };
$("bPrev").onclick  = () => { stop(); show(cur - 1); };
$("bNext").onclick  = () => { stop(); show(cur + 1); };
$("bLast").onclick  = () => { stop(); show(N - 1); };
$("bPlay").onclick  = play;
$("slider").oninput = e => { stop(); show(+e.target.value - 1); };
$("speed").oninput  = () => { if (timer) { stop(); play(); } };
document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  if (e.key === "ArrowRight") { stop(); show(cur + 1); }
  else if (e.key === "ArrowLeft") { stop(); show(cur - 1); }
  else if (e.key === " ") { e.preventDefault(); play(); }
  else if (e.key === "Home") { stop(); show(0); }
  else if (e.key === "End") { stop(); show(N - 1); }
});
show(0);
</script>
</body>
</html>
"""
