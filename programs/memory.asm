# Test 8: Memory load/store (base + offset บวก/ลบ, อ่านช่องที่ไม่เคยเขียน = 0)
ADDI R1 R0 100      # base address
ADDI R2 R0 11
ADDI R3 R0 22
ADDI R4 R0 -33
SW   R2 0(R1)       # Mem[100] = 11
SW   R3 4(R1)       # Mem[104] = 22
SW   R4 -4(R1)      # Mem[96]  = -33
LW   R5 4(R1)       # R5 = 22
LW   R6 -4(R1)      # R6 = -33
LW   R7 0(R1)       # R7 = 11
LW   R8 200(R0)     # R8 = 0 (ไม่เคยเขียน)
ADD  R9 R5 R6       # R9 = -11
HALT
# Expected: R5=22 R6=-33 R7=11 R8=0 R9=-11, Mem[96]=-33 Mem[100]=11 Mem[104]=22
