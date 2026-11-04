# 🔌 Integrating CORE with PowerWorld via DNP3 in a Dockerized Environment

This guide outlines the complete setup to enable communication between [CORE (Common Open Research Emulator)](https://www.nrl.navy.mil/itd/ncs/products/core) and [PowerWorld DS](https://www.powerworld.com/products/simulator) through a Dockerized DNP3 Master. This includes configuring the DNP3 Master script, building the Docker container, and launching emulated nodes that communicate over the DNP3 protocol.

---

## 🚀 Step-by-Step Instructions

### ⚡ 1. Configure PowerWorld DS

- On your **Windows machine**, open `PowerWorld Dynamic Studio` and load:

  - `Microgrid_PowerWorld.pwb` – the simulation file.
  - `Microgrid_PowerWorld.pwd` – the one-line diagram.

- Note the **IP address** of the Windows device running PowerWorld DS (you'll use it to configure the DNP3 master).

---

### 📝 2. Configure DNP3 Master Script

- Open the `pydnp3_master.py` script and replace the host IP address with the IP noted from Step 1:

  ```python
  HOST = "PowerWolrdDS_Server_IP"  # Replace this with the actual IP
  ```

---

### 🐳 3. Create and Start the Docker Container

- Use the provided `Dockerfile` to build a Docker image:

  ```bash
  docker build -t dnp3_container_image .
  ```

- Create and start a container from this image. **Give it a unique name** of your choice:

  ```bash
  docker run -dit --name <your_container_name> dnp3_container_image
  ```

> 🔖 _Note: Remember this container name for later steps._

---

### 🔐 4. Install OpenSSL Server Inside the Container

- Enter the container:

  ```bash
  docker exec -it <your_container_name> bash
  ```

- Install OpenSSL server:

  ```bash
  apt update && apt install -y openssh-server
  passwd root  # Set a password (you will use this in later scripts)
  service ssh start
  ```

---

### 🧩 5. Integrate with CORE (Common Open Research Emulator)

- Copy the `docker.py` file into the following CORE directory on your host machine:

  ```
  /opt/core/venv/lib/python3.10/site-packages/core/nodes/
  ```

> ✅ _Ensure CORE is installed and activated properly._

---

### 🛠️ 6. Update Helper Scripts

- Open `test.sh` and modify the following:

  ```bash
  TARGET_NAME="<your_container_name>"
  ```

- Open `setup_and_connect.sh` and update:

  ```bash
  CONTAINER_NAME="<your_container_name>"
  SSH_PASSWORD="1"  # Replace with the password you set for root in Step 4
  ```

---

### 🌐 7. Launch CORE with Microgrid Topology

- Start CORE and load the topology file:

  ```bash
  Microgrid_CORE.xml
  ```

---

### 🔁 8. Final Execution

- Run `test.sh` with **root privilege** to distribute scripts to containers:

  ```bash
  sudo ./test.sh
  ```

- Open any CORE container, and run:

  ```bash
  ls
  ./setup_and_connect.sh
  ```

---

## ✅ Final Outcome

Your CORE containers are now configured to communicate with PowerWorld DS over the **DNP3 protocol** via the Dockerized master. This setup enables distributed real-time testing and interaction between simulated power systems and cyber infrastructure.

---

## 📌 Notes

- Ensure your firewall allows traffic between the CORE VM and the Windows machine.
- Verify that the DNP3 master is configured to match the DNP3 outstation settings in PowerWorld.

---

## 🧪 How to test the pandapower integration

Two independent layers, test them separately:

**1. The grid model alone (no pydnp3/Docker/CORE needed)**

`pandapower_grid.py` only depends on `pandapower`, so it runs directly on the
host:

```bash
pip3 install --user pandapower   # if not already installed
python3 pandapower_grid.py
```

Expected output: initial bus voltages/line loading with both breakers closed,
then after `operate_switch(0, close=False)` the voltage of the now-isolated
feeder bus becomes `nan` (it's no longer fed) while the other bus is
unaffected — confirming the breaker→power-flow wiring actually changes grid
state instead of being a no-op.

**2. The full DNP3 master ↔ outstation path (needs the Docker build)**

`pydnp3` itself isn't pip-installable (it's built from source against an old
gcc-9/Python 3.6 toolchain, which is why the `Dockerfile` exists) — this part
can only be exercised inside the Docker image, not on a bare host:

```bash
docker build -t dnp3_container_image .
docker run -dit --name outstation_test dnp3_container_image
docker run -dit --name master_test dnp3_container_image

# terminal 1: start the outstation (replaces PowerWorld)
docker exec -it outstation_test python3 pandapower_outstation.py

# terminal 2: get the outstation's container IP, then start the master against it
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' outstation_test
docker exec -it master_test python3 pydnp3_master.py 10 <outstation_ip>
```

At the `master_0>` prompt:

```
scan_all          # read initial breaker status / bus voltages / line loading
o3 0 TRIP_PULSE_ON # open breaker 0 (feeder1)
scan_all           # breaker 0 now OPEN, feeder1 bus voltage reading reflects the outage
o1 0 LATCH_ON       # close breaker 0 again
scan_all           # feeder1 bus voltage back to normal
```

If `scan_all` reflects the breaker state change each time, the master →
outstation → pandapower → power-flow → back-to-master loop is working
end-to-end. (This Docker-based step hasn't been run in this session — the
local sandbox has no Docker daemon available — so verify it on your machine;
the grid-model logic in step 1, which doesn't need pydnp3, has been run and
confirmed above.)

---

## 📂 File Structure

```
.
├── Dockerfile
├── pydnp3_master.py
├── pandapower_grid.py
├── pandapower_outstation.py
├── docker.py
├── test.sh
├── setup_and_connect.sh
├── Microgrid_CORE.xml
├── Microgrid_PowerWorld.pwb
├── Microgrid_PowerWorld.pwd
└── README.md
```

---

## 🆓 Alternative: using pandapower instead of PowerWorld DS

PowerWorld Simulator/DS requires a paid license. `pandapower_outstation.py` +
`pandapower_grid.py` provide a free, open-source DNP3 **outstation** that plays
the same role as PowerWorld DS in the steps above, so steps 1 and 2 of the
guide (configuring PowerWorld DS and noting its IP) can be skipped entirely.

- `pandapower_grid.py` — a plain `pandapower` grid model (no pydnp3 dependency)
  with a small generic radial microgrid (`build_network()`) and a
  `MicrogridModel` wrapper exposing `operate_switch`/`read_binary`/
  `read_analog`/`write_analog`. **This is a stand-in topology, not an import of
  `Microgrid_PowerWorld.pwb`** (that file is a proprietary PowerWorld binary
  format) — adjust `build_network()` and the `*_POINT_MAP` dicts if you need it
  to match the paper's exact scenario.
- `pandapower_outstation.py` — wraps `MicrogridModel` with a `pydnp3` DNP3
  **outstation** (built from the same `pydnp3`/`opendnp3` bindings
  `pydnp3_master.py` uses as a master), listening on `0.0.0.0:20000`. Breaker
  commands (`o0/o1/o3`, `s0/s1/s2`) flip pandapower switches and re-run the
  power flow; `scan_*` commands on the master read back the resulting bus
  voltages / line loading / breaker status.

To use it: build the same Docker image (now also containing `pandapower`,
`pandapower_grid.py`, `pandapower_outstation.py`), run one container as the
outstation (`python3 pandapower_outstation.py`) in place of the Windows
PowerWorld machine, and point `pydnp3_master.py`'s `HOST` (or the `main()`
argument) at that container's IP instead of PowerWorld's. Everything else in
the guide (CORE topology, `docker.py`, `test.sh`/`setup_and_connect.sh`) is
unchanged.

See "How to test the pandapower integration" below.

# 📄 Citation

If you use this work in your research or project, please cite our paper:

**Cyber-Physical Emulation and Threat Scenario Simulation for Enhanced Microgrid Resilience**  
*Khandaker Akramul Haque, Mohamed Massaoudi, Leen Al Homoud, Katherine R. Davis, Mahmoud Kabalan, Hassan Salamy*  
**IEEE Access, 2025, Vol. 13, pp. 101455–101471**  
[https://doi.org/10.1109/ACCESS.2025.3578421](https://doi.org/10.1109/ACCESS.2025.3578421)

## BibTeX:
```bibtex
@ARTICLE{11029216,
  author={Akramul Haque, Khandaker and Massaoudi, Mohamed and Al Homoud, Leen and Davis, Katherine R. and Kabalan, Mahmoud and Salamy, Hassan},
  journal={IEEE Access}, 
  title={Cyber-Physical Emulation and Threat Scenario Simulation for Enhanced Microgrid Resilience}, 
  year={2025},
  volume={13},
  pages={101455-101471},
  doi={10.1109/ACCESS.2025.3578421}
}
```
