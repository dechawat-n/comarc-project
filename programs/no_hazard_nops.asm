# ใส่ NOP คั่น 2 ตัวระหว่างคำสั่งที่ขึ้นต่อกัน -> ได้ผลถูกแม้ไม่มี forwarding
ADDI R1 R0 10
ADDI R2 R0 20
NOP
NOP
ADD R3 R1 R2
HALT
