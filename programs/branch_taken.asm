# BEQ taken -> flush 2 คำสั่งที่ fetch มาผิดทาง
ADDI R1 R0 5
ADDI R2 R0 5
BEQ  R1 R2 2      # 5 == 5 -> taken, target = PC+4 + 2*4 (ข้าม 2 คำสั่ง)
ADDI R3 R0 111    # ถูก flush
ADDI R4 R0 222    # ถูก flush
ADDI R5 R0 333    # branch target
HALT
# Expected: R1=5 R2=5 R3=0 R4=0 R5=333
