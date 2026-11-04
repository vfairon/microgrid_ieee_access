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

## 6. Commands at the `master_10>` prompt
```
scan_all                  # read everything (breakers + voltages + line loading)
o1 0 LATCH_ON              # close breaker 0
o3 0 TRIP_PULSE_ON          # open breaker 0
quit                       # NOT ctrl-c, that crashes it
```
outstation terminal logs `COMMAND: breaker 0 received CLOSE (...)` when it gets one, so you can see it land without decoding raw DNP3 hex

## 7. Replicate the paper's attack
why: paper's first real attack (after phishing gets them in) = disconnect a breaker to cause instability/blackout. closest match we have = `CB8` (STEAM mains breaker), index `5` — it's normally closed, so opening it actually changes something (unlike the emergency-tie breakers which are already open by default, standby-only)

how:
```
o0 5 TRIP_PULSE_ON
```
(not `o3` — that one ignores the action word, only `o0 <idx> <ACTION>` actually reads it)

how to see it worked (3 ways, pick whichever):
- outstation's own terminal logs `COMMAND: breaker 5 received OPEN (...)` the instant it lands
- right after sending it, master prints `Status: SUCCESS` + `[5] : 0 : 1 : 0` (value `0` = open, that's the proof)
- `scan_all` → first block of `[0]`..`[20]` lines = Binary Input, index 5 there = current breaker state (ignore all the other blocks, they're mostly empty placeholders)

to undo: `o0 5 LATCH_ON`

## Notes to self
- `ping` works now (`iputils-ping` in the image), `ip route` should show a default route automatically (DefaultRoute service), if a docker node only has loopback something's wrong with its link in the xml
