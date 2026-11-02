# Data dependency + forwarding (ไม่มี stall เลย)
ADDI R1 R0 5
ADDI R2 R1 3      # R1: EX/MEM -> EX
ADD  R3 R1 R2     # R1: MEM/WB -> EX, R2: EX/MEM -> EX
SUB  R4 R3 R1     # R3: EX/MEM -> EX
AND  R5 R3 R4     # R3: MEM/WB, R4: EX/MEM
OR   R6 R5 R1
ADDI R0 R0 99     # เขียน R0 -> ต้องไม่มีผล และห้าม forward
ADD  R7 R0 R1     # R7 ต้องเป็น 5
HALT
# Expected: R1=5 R2=8 R3=13 R4=8 R5=8 R6=13 R7=5
