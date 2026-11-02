# CPU Pipeline Simulator (Python)

Simulator เพื่อการศึกษาของ CPU แบบ MIPS-like ที่ใช้ **classic 5-stage pipeline** (IF → ID → EX → MEM → WB)
จำลองการทำงานแบบ cycle-by-cycle พร้อมการตรวจจับและจัดการ **data hazard (forwarding + stall)**,
**control hazard (branch + flush)** และคำนวณ **performance metrics**

ตารางทุกตารางสร้างจาก execution logic จริง ไม่มีการพิมพ์ตารางที่เตรียมไว้ล่วงหน้า
ผล register/memory สุดท้ายถูกตรวจเทียบกับ reference model (CPU ที่ไม่มี pipeline) ทุกโปรแกรม

---

## 1. โครงสร้างโปรเจกต์

```
pipeline_simulator/
├── main.py            # Entry point + CLI (เมนูโต้ตอบ / --run / --compare)
├── cpu.py             # Control logic: ลำดับการทำงานใน 1 cycle, stall, flush, ตัวนับสถิติ
├── pipeline.py        # Pipeline registers (IF/ID, ID/EX, EX/MEM, MEM/WB), ALU, ฟังก์ชันของแต่ละ stage
├── instructions.py    # Parser: ข้อความ assembly -> Instruction object
├── registers.py       # Register file 32 ตัว (R0 = 0 เสมอ), 32-bit signed
├── memory.py          # Instruction memory + Data memory (แยกกัน)
├── hazard.py          # Forwarding unit + Hazard detection unit
├── performance.py     # สูตรคำนวณ CPI, IPC, efficiency ฯลฯ
├── display.py         # จัดรูปแบบตาราง pipeline ใน terminal (มีสี, events แยกบรรทัด)
├── visualizer.py      # สร้างหน้าเว็บ visual simulator (HTML ไฟล์เดียว) จากผล simulation จริง
├── gui_server.py      # Interactive web GUI: web server เล็กๆ (standard library) ที่เรียก cpu.py
├── gui/index.html     # หน้าเว็บของ GUI: datapath diagram, editor, step/run, เลือกโหมด hazard
├── programs/          # โปรแกรมตัวอย่าง (.asm)
├── visual/            # หน้าเว็บ visualizer ที่สร้างไว้แล้วของทุกโปรแกรม (เปิดด้วยเบราว์เซอร์ได้เลย)
├── tests/             # Automated tests + reference model
└── results/           # ผลการรันตัวอย่าง, ผลเทียบประสิทธิภาพ, ผล test
```

---

## 2. สถาปัตยกรรม CPU

| ส่วนประกอบ | รายละเอียด |
|---|---|
| Registers | R0–R31, 32-bit signed (two's complement, overflow แบบ wrap-around), **R0 = 0 เสมอ** |
| Register file | **เขียนครึ่งแรกของ cycle, อ่านครึ่งหลัง** → WB กับ ID ใช้ register ตัวเดียวกันใน cycle เดียวกันได้ |
| PC | byte address, คำสั่งละ 4 bytes (คำสั่งที่ index *i* อยู่ที่ PC = 4*i*) |
| Memory | **Instruction memory กับ Data memory แยกกัน** (Harvard), data memory ใช้ byte address ที่หาร 4 ลงตัว, ช่องที่ไม่เคยเขียนมีค่า 0 |
| Pipeline registers | IF/ID, ID/EX, EX/MEM, MEM/WB (ช่องว่าง = *bubble*) |

### 2.1 หน้าที่ของแต่ละ stage

| Stage | หน้าที่ |
|---|---|
| **IF** | fetch คำสั่งที่ PC, PC ← PC + 4 (เมื่อเจอ HALT จะหยุด fetch) |
| **ID** | decode คำสั่ง, อ่าน register, **hazard detection unit** ตัดสินใจ stall |
| **EX** | ALU คำนวณ / คำนวณ address ของ LW/SW / ตัดสิน branch, **forwarding unit** เลือก operand |
| **MEM** | LW อ่าน memory, SW เขียน memory, คำสั่งอื่นส่งผลผ่านไป |
| **WB** | เขียนผลกลับ register ปลายทาง |

### 2.2 การจำลอง 1 clock cycle (`CPU.step()`)

```
1. WB    (ทำก่อน เพื่อจำลอง "เขียนครึ่งแรกของ cycle")
2. MEM
3. EX    + forwarding
4. Branch resolution → ถ้า taken: flush IF และ ID, PC ← target
5. ID    + hazard detection (stall?)  ← อ่าน register หลัง WB เขียนแล้ว
6. IF
7. Commit: แทน latch ทั้ง 4 ใบด้วยค่าใหม่พร้อมกัน (= clock edge)
```
ทุก stage คำนวณจากค่า latch **ของ cycle ก่อน** แล้วค่อย commit พร้อมกัน คำสั่งจึงขยับไปได้ครั้งละ 1 stage ต่อ cycle เหมือนฮาร์ดแวร์จริง

---

## 3. Instruction Set

| คำสั่ง | รูปแบบ | การทำงาน |
|---|---|---|
| ADD | `ADD rd rs rt` | rd ← rs + rt |
| SUB | `SUB rd rs rt` | rd ← rs − rt |
| AND | `AND rd rs rt` | rd ← rs & rt |
| OR | `OR rd rs rt` | rd ← rs \| rt |
| ADDI | `ADDI rt rs imm` | rt ← rs + imm |
| LW | `LW rt offset(rs)` | rt ← Mem[rs + offset] |
| SW | `SW rt offset(rs)` | Mem[rs + offset] ← rt |
| BEQ | `BEQ rs rt offset` | ถ้า rs == rt: PC ← PC + 4 + offset×4 |
| BNE | `BNE rs rt offset` | ถ้า rs != rt: PC ← PC + 4 + offset×4 |
| NOP | `NOP` | ไม่ทำอะไร |
| HALT | `HALT` | หยุดโปรแกรม |

Syntax: ไม่สนตัวพิมพ์เล็ก/ใหญ่, ใช้ช่องว่างหรือ comma คั่นก็ได้, comment ขึ้นต้นด้วย `#` หรือ `;`,
immediate เป็นฐาน 10 / ติดลบ / `0x..` ได้, branch offset นับเป็น **จำนวนคำสั่ง** นับจากคำสั่งถัดจาก branch (แบบ MIPS)

ภายในโปรแกรม ทุกคำสั่งถูกแปลงเป็นฟิลด์รูปแบบเดียวกันคือ `dest`, `src1`, `src2`, `imm`
(เช่น SW: `src1` = base, `src2` = ค่าที่จะเก็บ, ไม่มี `dest`) ทำให้การตรวจ hazard ใช้กฎเดียวกันได้ทุกคำสั่ง

---

## 4. Hazard Detection and Handling

### 4.1 Data hazards (RAW)

**Forwarding unit (ที่ EX)** เลือก operand ตามลำดับความสำคัญ:
1. **EX/MEM → EX** ใช้ผลของคำสั่งที่อยู่ข้างหน้า 1 ตำแหน่ง (ค่าใหม่ที่สุด จึงเช็คก่อน)
2. **MEM/WB → EX** ใช้ผลของคำสั่งที่อยู่ข้างหน้า 2 ตำแหน่ง
3. ค่าที่อ่านจาก register file ตอน ID

เงื่อนไขการ forward: producer เขียน register จริง (`dest ≠ R0`) และ `dest` ตรงกับ source ของเรา
**ห้าม forward จาก EX/MEM ถ้า producer เป็น LW** เพราะใน EX/MEM ของ LW มีแค่ address ยังไม่มีค่าข้อมูล

**Load-use hazard → stall 1 cycle (ที่ ID):** ถ้าคำสั่งใน EX เป็น LW และคำสั่งใน ID ใช้ register ที่ LW กำลังโหลด
1. ใส่ bubble เข้า ID/EX  2. คงค่า IF/ID ไว้  3. ไม่เลื่อน PC
จากนั้นใน cycle ถัดไปจะ forward ค่าจาก MEM/WB → EX

**โหมดปิด forwarding (`--no-forwarding`):** stall ทุก RAW จนกว่า producer จะถึง WB (dependency ห่าง 1 ตำแหน่ง = stall 2, ห่าง 2 ตำแหน่ง = stall 1)

dependency ที่ห่างกันตั้งแต่ 3 ตำแหน่งขึ้นไปไม่เป็น hazard เพราะ register file เขียนก่อนอ่านใน cycle เดียวกัน

### 4.2 Control hazards: **Predict Not-Taken, resolve ที่ EX**

- IF fetch คำสั่งถัดไปตามลำดับเสมอ (เดาว่า branch ไม่ taken)
- branch รู้ผลตอนจบ EX (forward operand เข้า EX ได้ จึงไม่ต้อง stall เพิ่มถ้า branch ใช้ผล ALU ของคำสั่งก่อนหน้า)
  - **Not taken** → เดาถูก ไม่เสีย cycle
  - **Taken** → **flush** คำสั่งใน IF และ ID (2 คำสั่งบน wrong path) แล้ว PC ← target → **penalty 2 cycles**
- การ flush ปลอดภัย เพราะคำสั่งที่ถูก flush ยังไม่ถึง MEM/WB จึงยังไม่ได้เปลี่ยน memory หรือ register
- ถ้า HALT ถูก fetch บน wrong path แล้วถูก flush จะเริ่ม fetch ใหม่ที่ target ตามปกติ
- flush มีความสำคัญเหนือ stall
- Trade-off: ถ้า resolve ที่ ID จะเสียเพียง 1 cycle ตอน taken แต่ต้องมี forwarding เข้า ID และต้อง stall เมื่อ branch ใช้ผลของคำสั่งก่อนหน้าทันที

### 4.3 Structural hazards

ดีไซน์นี้ **แยก instruction memory กับ data memory** ดังนั้น IF (อ่านคำสั่ง) กับ MEM (LW/SW) ทำงานใน cycle เดียวกันได้
และ register file มี 2 read ports + 1 write port (เขียนครึ่งแรก/อ่านครึ่งหลัง) ส่วนแต่ละ stage มีฮาร์ดแวร์ของตัวเอง
→ **ไม่มี structural hazard ในดีไซน์นี้** (ถ้าใช้ memory ร่วมกัน cycle ที่ LW/SW อยู่ใน MEM จะ fetch คำสั่งไม่ได้และต้อง stall)

### 4.4 การจบโปรแกรม

- เมื่อ IF เจอ `HALT` จะหยุด fetch แล้วปล่อยคำสั่งที่เหลือใน pipeline ทำจนจบ simulation จบเมื่อ HALT ออกจาก WB
- ถ้า PC ชี้เลยท้ายโปรแกรม (ไม่มี HALT หรือ branch กระโดดเลย HALT) simulation จบเมื่อ pipeline ว่าง
- มีตัวกัน infinite loop ที่ 10,000 cycles

---

## 5. การติดตั้งและการรัน

ต้องใช้ **Python 3.8 ขึ้นไป** ไม่มี external library

```bash
cd pipeline_simulator
python3 main.py                                   # เมนูโต้ตอบ
python3 main.py programs/loop.asm                 # โหลดโปรแกรมแล้วเข้าเมนู
python3 main.py programs/loop.asm --run           # รันจนจบ: ตาราง + register + memory + สถิติ
python3 main.py programs/loop.asm --run --no-forwarding
python3 main.py programs/loop.asm --compare       # เทียบ forwarding ON vs OFF
python3 main.py --gui                             # ⭐ เปิด interactive GUI (datapath แบบ UMich) ในเบราว์เซอร์
python3 main.py programs/loop.asm --html          # สร้าง visual simulator (ไฟล์ HTML) แล้วเปิดในเบราว์เซอร์
python3 main.py programs/loop.asm --run --control stall   # เลือกวิธีจัดการ control hazard
python3 main.py programs/example.asm --run --data none    # ปิด hazard unit (ผลจะผิด: ไว้สาธิต)
python3 main.py programs/loop.asm --run --no-events   # ตารางแบบย่อ (ไม่แสดง events)
python3 -m unittest discover -s tests -v          # รัน automated tests
```

เมนูโต้ตอบ:
```
 1. Load program file          5. View pipeline execution table
 2. Start / reset simulation   6. View registers and memory
 3. Step one clock cycle       7. View performance statistics
 4. Run until finished         8. Toggle forwarding
                               9. Open visual simulator in web browser
 0. Quit
```
เมื่อ step แต่ละ cycle ระบบจะแสดง PC, คำสั่งในแต่ละ stage และ events ของ cycle นั้น ได้แก่ WB, การเขียน memory, RAW, forwarding, stall, ผล branch และ flush

### Interactive GUI (`python3 main.py --gui`)

GUI แนวเดียวกับ [UMich EECS 370 pipeline simulator](https://vhosts.eecs.umich.edu/370simulators/pipeline/simulator.html)
เปิดที่ `http://localhost:8370` (กด Ctrl+C ใน Terminal เพื่อปิด) โดยใช้แค่ Python standard library

```
เบราว์เซอร์ (gui/index.html)  --POST /api/simulate {source, data, control}-->  gui_server.py -> cpu.py
                              <-- JSON: สถานะทุก cycle (latch, activity, registers, memory)
```
- **Datapath diagram:** PC, Instr Memory, Register File, Hazard Unit, forwarding mux, ALU, Data Memory และ pipeline register 4 ใบพร้อมค่าในแต่ละช่อง
  (PC+4, valA, valB, imm, dest, op, ALU result, target, taken?, write data) เส้นหนาแสดงเส้นทางที่กำลังใช้ ได้แก่ forwarding, branch → PC, write back และ memory access
- **Instruction Memory:** พิมพ์โค้ดเองหรือเลือกโปรแกรมตัวอย่าง แล้วกด Assemble ระบบจะไฮไลต์แต่ละคำสั่งด้วยสีของ stage ที่คำสั่งนั้นอยู่
- **Control:** Step ▶ / ◀ Back (ย้อนได้) / ▶▶ Run / ⏭ พร้อมคำอธิบาย event ของแต่ละ cycle
- **Pipeline Options:** เลือกวิธีจัดการ hazard (ตารางด้านล่าง) และมีช่อง **ตรวจผลกับ reference model** ที่บอกได้ทันทีว่า register หรือ memory ตัวไหนผิด เมื่อเลือก None
- Registers, Data Memory, Pipeline Diagram และ Performance

| | None | Detect and Stall | ค่าเริ่มต้น |
|---|---|---|---|
| **Data hazards** | ไม่ตรวจ ไม่แก้ (ต้องใส่ NOP เอง) | stall จน producer ถึง WB | **Forwarding** + stall load-use |
| **Control hazards** | 2 คำสั่งหลัง branch ทำงานเสมอ | หยุด fetch จน branch รู้ผล (เสีย 2 cycle ทุก branch) | **Predict not-taken + flush** |

โหมด None ใส่ไว้เพื่อสาธิตว่าทำไมต้องมี hazard unit ส่วนดีไซน์หลักของโปรเจกต์ (ที่ใช้ใน test และตารางผลทั้งหมด) คือค่าเริ่มต้น

### Visual simulator แบบไฟล์ HTML (`--html`)

`--html` (หรือเมนู 9) จะรัน simulation จนจบด้วย Python แล้วบันทึกสถานะทุก cycle ลงไฟล์ HTML ไฟล์เดียว
หน้าเว็บทำหน้าที่ **แสดงผลอย่างเดียว** ไม่ได้คำนวณ pipeline เอง และเปิดได้โดยไม่ต้องใช้อินเทอร์เน็ต
- ปุ่ม ⏮ ◀ ▶ ⏭ / Play และแถบเลื่อน (แป้น ← → = ทีละ cycle, Space = เล่น/หยุด)
- กล่อง 5 stages ของ cycle ปัจจุบัน พร้อมป้าย STALL / FLUSH / FWD / TAKEN
- รายการ events ของ cycle นั้นพร้อมคำอธิบายภาษาไทย
- **Pipeline diagram** แบบในตำรา (แถว = คำสั่ง, คอลัมน์ = cycle) แสดง stall เป็นลายทางและ flush เป็นสีแดง ✗ คลิกเพื่อกระโดดไป cycle นั้นได้
- Program listing พร้อมป้ายบอกว่าแต่ละคำสั่งอยู่ stage ไหน, registers และ memory ที่ไฮไลต์ค่าที่เพิ่งเปลี่ยน และ performance statistics

---

## 6. ตัวอย่างโปรแกรมและผลลัพธ์

| ไฟล์ | ทดสอบ (spec ข้อ 10) | ผลที่คาดไว้ |
|---|---|---|
| `arithmetic.asm` | 1. Basic arithmetic, overflow | R3=22 R4=2 R5=8 R6=14 R7=−2 R10=−2147483648 |
| `forwarding.asm` | 2–3. Data dependency, forwarding, เขียน R0 | R1=5 R2=8 R3=13 R4=8 R5=8 R6=13 R7=5 |
| `load_use.asm` | 4. Load-use hazard | R2=100 R3=200 R4=100, Mem[8]=100, stall 1 |
| `stalls.asm` | 5. Stall: LW→ADD, LW→SW, LW→BEQ | R7=14, Mem[8]=Mem[12]=7, stall 3 |
| `branch_taken.asm` | 6–7. Branch taken + flush | R3=R4=0 (ถูก flush), R5=333 |
| `branch_not_taken.asm` | 6. Not taken / BNE taken | R3=111 R4=222 R5=0 R6=444 |
| `loop.asm` | 6–7. Loop ด้วย branch ย้อนกลับ | R1=15, Mem[0]=15, flush 4 ครั้ง |
| `memory.asm` | 8. Load/store, offset ติดลบ | Mem[96]=−33 Mem[100]=11 Mem[104]=22, R9=−11 |
| `halt.asm` | 9. Termination | R1=1, R2=R3=0, 6 cycles |
| `example.asm` | โปรแกรมตัวอย่างจาก spec | R3=30 R4=20 R5=30 Mem[0]=30 |
| `no_hazard_nops.asm` | ใส่ NOP แทน forwarding | R3=30 |

ผลการรันเต็มของทุกโปรแกรมอยู่ใน `results/output_*.txt`

### ตัวอย่าง: `python3 main.py programs/load_use.asm --run`
```
Cycle | IF         | ID         | EX         | MEM        | WB         | Events
    1 | ADDI R1    | -          | -          | -          | -
    2 | SW R1      | ADDI R1    | -          | -          | -
    3 | LW R2      | SW R1      | ADDI R1    | -          | -          | RAW: SW R1 needs R1 from ADDI R1 (in EX)
    4 | ADD R3     | LW R2      | SW R1      | ADDI R1    | -          | FWD EX/MEM->EX: R1=100 (ADDI R1 -> SW R1)
    5 | SUB R4     | ADD R3     | LW R2      | SW R1      | ADDI R1    | WB: R1=100; MEM: Mem[8]=100; ...; STALL (load-use): ADD R3 waits for R2 from LW R2
    6 | SUB R4     | ADD R3     | bubble     | LW R2      | SW R1
    7 | HALT       | SUB R4     | ADD R3     | bubble     | LW R2      | WB: R2=100; FWD MEM/WB->EX: R2=100 (LW R2 -> ADD R3); ...
    8 | -          | HALT       | SUB R4     | ADD R3     | bubble     | FWD EX/MEM->EX: R3=200 (ADD R3 -> SUB R4)
    9 | -          | -          | HALT       | SUB R4     | ADD R3     | WB: R3=200
   10 | -          | -          | -          | HALT       | SUB R4     | WB: R4=100
   11 | -          | -          | -          | -          | HALT
```

### ตัวอย่าง: branch taken + flush (`branch_taken.asm`)
```
    5 | ADDI R4    | ADDI R3    | BEQ R1     | ADDI R2    | ADDI R1    | ... BRANCH BEQ R1 TAKEN -> PC=20; FLUSH: ADDI R3 (ID), ADDI R4 (IF)
    6 | ADDI R5    | bubble     | bubble     | BEQ R1     | ADDI R2    | WB: R2=5
```

---

## 7. Performance Metrics

ให้ **C** = total clock cycles, **N** = instructions completed (คำสั่งที่ผ่าน WB รวม NOP/HALT แต่ไม่รวมคำสั่งที่ถูก flush และ bubble), **k** = 5

| Metric | สูตร | ความหมาย |
|---|---|---|
| CPI | C / N | cycle เฉลี่ยต่อคำสั่ง |
| IPC | N / C | คำสั่งเฉลี่ยต่อ cycle |
| Ideal cycles | N + (k − 1) | pipeline ที่ไม่มี hazard: ใช้ k−1 cycle เติมท่อ แล้วจบ 1 คำสั่งต่อ cycle |
| Lost cycles | C − Ideal | cycle ที่เสียไปกับ stall/flush |
| Pipeline efficiency | Ideal / C × 100% | 100% = ไม่เสีย cycle จาก hazard |
| Stage utilization | N / C × 100% | สัดส่วนของช่อง stage×cycle ที่มีคำสั่งจริงทำงาน |
| Speedup | k·N / C | เทียบกับ CPU ที่ไม่ pipeline (k cycle ต่อคำสั่ง, clock เท่ากัน) |
| Data hazards | — | จำนวนคำสั่งที่ตอนอยู่ใน ID มี RAW กับคำสั่งที่ยังอยู่ใน EX/MEM (นับครั้งเดียวต่อคำสั่ง) |
| Pipeline stalls | — | จำนวน cycle ที่ใส่ bubble เพราะ stall |
| Control hazards | — | จำนวน branch ที่ execute |
| Branch flushes | — | จำนวนครั้งที่ branch taken แล้วต้อง flush (ครั้งละ 2 slot) |

เมื่อโปรแกรมจบด้วย HALT จะได้ **C = N + 4 + stalls + 2 × (branch taken)** เสมอ (มี test ตรวจสูตรนี้)

### ผลการวิเคราะห์ (forwarding ON)

| Program | N | Cycles | CPI | IPC | Stalls | Data hz | Ctrl hz | Flushes | Efficiency |
|---|---|---|---|---|---|---|---|---|---|
| arithmetic | 11 | 15 | 1.36 | 0.73 | 0 | 3 | 0 | 0 | 100.0% |
| branch_not_taken | 8 | 14 | 1.75 | 0.57 | 0 | 1 | 2 | 1 | 85.7% |
| branch_taken | 5 | 11 | 2.20 | 0.45 | 0 | 1 | 1 | 1 | 81.8% |
| example | 7 | 11 | 1.57 | 0.64 | 0 | 3 | 1 | 1 | 100.0% |
| forwarding | 9 | 13 | 1.44 | 0.69 | 0 | 5 | 0 | 0 | 100.0% |
| halt | 2 | 6 | 3.00 | 0.33 | 0 | 0 | 0 | 0 | 100.0% |
| load_use | 6 | 11 | 1.83 | 0.55 | 1 | 3 | 0 | 0 | 90.9% |
| loop | 19 | 31 | 1.63 | 0.61 | 0 | 7 | 5 | 4 | 74.2% |
| memory | 13 | 17 | 1.31 | 0.76 | 0 | 0 | 0 | 0 | 100.0% |
| stalls | 10 | 19 | 1.90 | 0.53 | 3 | 4 | 1 | 1 | 73.7% |

### Forwarding ON vs OFF

| Program | Cycles ON / OFF | CPI ON / OFF | Stalls ON / OFF |
|---|---|---|---|
| example | 11 / 15 | 1.57 / 2.14 | 0 / 4 |
| forwarding | 13 / 23 | 1.44 / 2.56 | 0 / 10 |
| load_use | 11 / 16 | 1.83 / 2.67 | 1 / 6 |
| loop | 31 / 43 | 1.63 / 2.26 | 0 / 12 |

(ตารางเต็มอยู่ใน `results/performance_comparison.txt`)

**ข้อสังเกต**
1. Forwarding ลดจำนวน cycle ได้ 27–43% โดยผลลัพธ์ยังถูกต้องเท่าเดิม
2. `loop.asm` ได้ efficiency 74% แม้เปิด forwarding เพราะ lost cycles ทั้ง 8 cycle มาจาก branch flush ทั้งหมด (predict not-taken เดาผิดทุกรอบของ loop) ต้องใช้ branch prediction ที่ดีกว่านี้จึงจะลดได้
3. โปรแกรมสั้นมี CPI > 1 แม้ efficiency 100% เพราะ 4 cycle แรกใช้เติมท่อ ถ้า N มากขึ้น CPI จะเข้าใกล้ 1
4. `example.asm` มีการ flush แต่ efficiency ยังเป็น 100% เพราะ branch กระโดดไปเลยท้ายโปรแกรม คำสั่งที่ถูก flush จึงไม่ทำให้โปรแกรมช้าลง

---

## 8. Testing

```bash
python3 -m unittest discover -s tests -v
```
มีทั้งหมด 24 tests (ผลอยู่ใน `results/test_results.txt`):
- **Unit tests:** parser (รูปแบบถูก/ผิด), R0 = 0, 32-bit overflow, memory alignment
- **Program tests:** ตรวจค่า register/memory สุดท้าย, จำนวน stall/flush/forward/cycle ของทุกโปรแกรมใน `programs/` และตรวจสูตร cycle
- **Reference model** (`tests/reference_model.py`): CPU ที่รันทีละคำสั่งแบบไม่มี pipeline
  - ทุกโปรแกรม × (forwarding ON/OFF) ต้องได้ register, memory และจำนวนคำสั่งที่ทำ **ตรงกับ reference model**
  - **Random test:** สุ่ม 500 โปรแกรมที่มี dependency หนาแน่น, LW/SW และ branch แล้วเทียบกับ reference model ทั้ง 2 โหมด
  - **Hazard modes:** control แบบ Detect-and-Stall ต้องได้ผลถูกเสมอ (และไม่มี flush); โหมด None ต้องให้ผลผิดตามที่คาดไว้; GUI server ทำงานถูกต้อง

---

## 9. Known Limitations / Simplifications

- ไม่ได้ encode คำสั่งเป็น binary 32-bit (เก็บเป็น object) และไม่จำกัดขนาด immediate (MIPS จริงใช้ 16-bit)
- รองรับเฉพาะ 11 คำสั่งตาม spec (ไม่มี J, JAL, SLT, shift, MUL)
- branch offset เป็นตัวเลขเท่านั้น (ยังไม่รองรับ label)
- ไม่มี forwarding MEM/WB → MEM ดังนั้น `LW R1` ตามด้วย `SW R1 ...` จะ stall 1 cycle (MIPS จริงบางแบบไม่ต้อง stall)
- ไม่มี branch delay slot และไม่มี dynamic branch prediction (ใช้ predict not-taken แบบ static)
- memory ทุก access ใช้ 1 cycle (ไม่มี cache/miss) และ data memory เก็บเฉพาะ word (ไม่มี LB/SB)
- ไม่มี exception/interrupt: address ที่ไม่ align ทำให้ simulation หยุดพร้อม error
