# Load-use hazard: LW ตามด้วยคำสั่งที่ใช้ค่าทันที -> stall 1 cycle
ADDI R1 R0 100
SW   R1 8(R0)
LW   R2 8(R0)
ADD  R3 R2 R1     # load-use: ต้อง stall 1 cycle
SUB  R4 R3 R2
HALT
# Expected: R1=100 R2=100 R3=200 R4=100, Mem[8]=100
