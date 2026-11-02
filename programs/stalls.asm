# Test 5: Pipeline stalls หลายแบบ (load-use กับ ALU, กับ SW, กับ BEQ)
ADDI R1 R0 4
ADDI R2 R0 7
SW   R2 4(R1)       # Mem[8] = 7
LW   R3 4(R1)       # R3 = 7
SW   R3 12(R0)      # LW -> SW : stall 1 (ไม่มี MEM->MEM forwarding)   Mem[12] = 7
LW   R4 12(R0)      # R4 = 7
BEQ  R4 R2 1        # LW -> BEQ: stall 1 แล้ว taken (7 == 7)
ADDI R5 R0 99       # ถูก flush
LW   R6 8(R0)       # R6 = 7
ADD  R7 R6 R6       # LW -> ADD: stall 1   R7 = 14
HALT
# Expected: R3=7 R4=7 R5=0 R6=7 R7=14, Mem[8]=7 Mem[12]=7 ; stalls=3, flushes=1
