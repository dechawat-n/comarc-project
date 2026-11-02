# Test 1: Basic arithmetic (ADD SUB AND OR ADDI, ค่าติดลบ, overflow 32-bit)
ADDI R1 R0 12
ADDI R2 R0 10
ADD  R3 R1 R2       # 22
SUB  R4 R1 R2       # 2
AND  R5 R1 R2       # 12 & 10 = 8   (1100 & 1010 = 1000)
OR   R6 R1 R2       # 12 | 10 = 14  (1100 | 1010 = 1110)
SUB  R7 R2 R1       # -2
ADDI R8 R0 -5       # -5
ADDI R9 R0 0x7FFFFFFF
ADDI R10 R9 1       # overflow -> wrap เป็น -2147483648
HALT
# Expected: R1=12 R2=10 R3=22 R4=2 R5=8 R6=14 R7=-2 R8=-5 R9=2147483647 R10=-2147483648
