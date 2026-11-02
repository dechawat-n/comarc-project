# Loop: sum = 5+4+3+2+1  (branch ย้อนกลับด้วย offset ติดลบ)
ADDI R1 R0 0      # sum = 0
ADDI R2 R0 5      # i = 5
ADD  R1 R1 R2     # loop: sum += i          (index 2)
ADDI R2 R2 -1     # i = i - 1               (index 3)
BNE  R2 R0 -3     # if i != 0 goto loop     (index 4) target = (4+1) + (-3) = 2
SW   R1 0(R0)     # Mem[0] = sum
HALT
# Expected: R1=15 R2=0 Mem[0]=15 ; branch taken 4 ครั้ง, not taken 1 ครั้ง
