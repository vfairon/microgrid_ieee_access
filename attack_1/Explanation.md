# 1. The Core network must be accessible from laptop : 
This simulates the fact that our laptop has access to the machine that is connected to the internet

# 2. Payload execution on "Internet" node : 
Executes the install_ssh.sh (we can invent cute name) that will install laptop public key into ssh authorized key files
(todo : include it in img )
# 3. Connect to master from laptop : 
Ip of internet :  10.0.14.20
Ip of master : 10.0.28.2

`ssh -J root@10.0.14.20 root@10.0.28.2`

## 6. Commands at the `master_10>` prompt
```
scan_all                  # read everything (breakers + voltages + line loading)
o1 0 LATCH_ON              # close breaker 0
o3 0 TRIP_PULSE_ON          # open breaker 0
quit                       # NOT ctrl-c, that crashes it
```
outstation terminal logs `COMMAND: breaker 0 received CLOSE (...)` when it gets one, so you can see it land without decoding raw DNP3 hex