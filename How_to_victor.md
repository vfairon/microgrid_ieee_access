# How to run this project 

## TODOS : 
1. verify pandapower_grid.py and pandapower_outstation.py to check if matches paper (**@Medhi**)
2. see how to connect laptop (or VM) to the "internet docker" of the CORE to be able to execute first attack (laptop <=>"internet docker"<=>master and execute command) **@Victor**
3. Second attack (**@Chacha**)


## 1. Install CORE

bonne merde ! 

## 2. Build the image 
with name `dnp3_container_image`
`docker build -t dnp3_container_image .`

has pydnp3 + pandapower + ssh baked in, root pw = `1`

## Use the Core : 
IDK if needed but apparently you need : `sudo iptables --policy FORWARD ACCEPT`

Then up the CORE and start the gui : 
- `sudo core-daemon`
- `core-gui`

In the GUI chose the Microgrid_CORE.xml file that has : 
- every docker has the dnp3_container_image used as docker
- routable links to the network
- ssh/ping/.. installed

## Activate ssh 
**DEPRECIATED : NOW DOCKER IMAGE STARTS IT AUTOMATICALLY**
Double click on one docker to get shell

not needed for dnp3 but if you wanna test 
- `ip a` (and copy ip)
- on another `service ssh start` first (nothing auto-starts it)
- then ssh password is `1`

or use the script instead of doing it by hand:

## 3. Architecture 
- 8 `DockerX` nodes (one per facility router: STV, OWSV, MGEx, AndAre, FDBase, FacDCV, APFac, CentralR) = **outstations**
- `DockerMaster` (9th node, linked to CentralR) = **master** (I HAD TO ADD THIS ONE MAIS OK)
- master polls PowerWorld in the real paper, here it's pandapower (`pandapower_outstation.py`) standing in

## 4. Start the outstations
on EACH of the 8 facility nodes:
```
cd /workspace && python3 pandapower_outstation.py
```

## 5. Start the master
on `DockerMaster`, get target outstation's IP first (click node in gui or `ip a` inside it)
```
cd /workspace && python3 pydnp3_master.py 10 <outstation_ip>
```
`10` = DNP3 link address, same for every outstation, fine since master only talks to one at a time (not a shared/multi-drop link)





## Only "Internet" node reachable from laptop (not the whole grid)

Create virtual ethernet cable on laptop (or VM)  and plug it into the switch connected to the internet machine. Set an ip to the laptop part on the subnet that the internet machine has (so default route possible) and add a firewall onto the Mastter that says if it is a "forwarded" coming from the internet subnet, drop (only internet machine can go past the master) : 

b.40.1 is the switch id="40"
TO RUN On laptop : 
```
sudo ip link add vlaptop type veth peer name vlaptop-br
sudo ip link set vlaptop-br master b.40.1
sudo ip link set vlaptop-br up
sudo ip addr add 10.0.14.21/24 dev vlaptop
sudo ip link set vlaptop up
```

And to cleanup : 
`sudo ip link delete vlaptop`


## Kill stale : 
```
docker rm -f $(docker ps -aq) 2>/dev/null
sudo pkill -9 vnoded
sudo pkill -9 -f "/usr/local/bin/core-daemon"
sudo rm -rf /tmp/pycore.*
for d in $(ip -br link show | awk '{print $1}' | sed 's/@.*//' | grep -E '^(p|b)\.[0-9]+\.[0-9]+$|^beth|^veth|^ctrl[0-9]'); do sudo ip link delete "$d" 2>/dev/null; done
ip -br link show | grep -E '^(p|b)\.|^beth|^veth|^ctrl[0-9]'   # should print nothing now
```