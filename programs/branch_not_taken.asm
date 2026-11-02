# BEQ not taken (ไม่เสีย cycle) แล้วตามด้วย BNE taken
ADDI R1 R0 5
ADDI R2 R0 7
BEQ  R1 R2 2      # 5 != 7 -> not taken: ทำคำสั่งถัดไปตามปกติ
ADDI R3 R0 111
ADDI R4 R0 222
BNE  R1 R2 1      # 5 != 7 -> taken: ข้าม 1 คำสั่ง
ADDI R5 R0 333    # ถูก flush
ADDI R6 R0 444
HALT
# Expected: R1=5 R2=7 R3=111 R4=222 R5=0 R6=444
