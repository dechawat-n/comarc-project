# Test 9: Program termination - คำสั่งหลัง HALT ต้องไม่ถูก execute
ADDI R1 R0 1
HALT
ADDI R2 R0 2        # ห้ามทำงาน
ADDI R3 R0 3        # ห้ามทำงาน
# Expected: R1=1 R2=0 R3=0 ; cycles = 2 + 4 = 6
