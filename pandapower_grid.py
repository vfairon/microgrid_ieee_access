"""
Pandapower stand-in for the PowerWorld case (Microgrid_PowerWorld.pwb/.pwd).

This module has NO dependency on pydnp3 so it can be built/tested on its own.
pandapower_outstation.py wraps MicrogridModel with the DNP3 outstation glue.

The topology below is a generic radial microgrid (external grid -> main bus ->
two feeder buses, each behind its own breaker, with a small DG on the second
feeder). It is NOT extracted from Microgrid_PowerWorld.pwb (that file is a
proprietary binary PowerWorld format) -- adjust build_network()/POINT_MAP to
match the real case if exact parity with the paper's scenario is needed.
"""
import pandapower as pp

# DNP3 binary-output index -> pandapower switch id (the "breakers")
SWITCH_POINT_MAP = {
    0: 0,  # breaker feeding bus 1 (load feeder)
    1: 1,  # breaker feeding bus 2 (DG feeder)
}

# DNP3 analog-input index -> (pandapower result table, column, element id)
ANALOG_POINT_MAP = {
    0: ("res_bus", "vm_pu", 0),   # slack/main bus voltage
    1: ("res_bus", "vm_pu", 1),   # feeder bus 1 voltage
    2: ("res_bus", "vm_pu", 2),   # feeder bus 2 voltage
    3: ("res_line", "loading_percent", 0),  # line to bus 1 loading
    4: ("res_line", "loading_percent", 1),  # line to bus 2 loading
}

# DNP3 binary-input index -> pandapower switch id (status readback, mirrors SWITCH_POINT_MAP)
BINARY_STATUS_POINT_MAP = SWITCH_POINT_MAP


def build_network() -> pp.pandapowerNet:
    net = pp.create_empty_network(name="microgrid")

    b_main = pp.create_bus(net, vn_kv=20.0, name="main_bus")
    b_feeder1 = pp.create_bus(net, vn_kv=20.0, name="feeder1_bus")
    b_feeder2 = pp.create_bus(net, vn_kv=20.0, name="feeder2_bus")

    pp.create_ext_grid(net, bus=b_main, vm_pu=1.0, name="grid_connection")

    pp.create_line_from_parameters(
        net, from_bus=b_main, to_bus=b_feeder1, length_km=1.0,
        r_ohm_per_km=0.1, x_ohm_per_km=0.1, c_nf_per_km=10, max_i_ka=0.4,
        name="line_to_feeder1",
    )
    pp.create_line_from_parameters(
        net, from_bus=b_main, to_bus=b_feeder2, length_km=1.0,
        r_ohm_per_km=0.1, x_ohm_per_km=0.1, c_nf_per_km=10, max_i_ka=0.4,
        name="line_to_feeder2",
    )

    pp.create_load(net, bus=b_feeder1, p_mw=0.5, q_mvar=0.1, name="load_feeder1")
    pp.create_sgen(net, bus=b_feeder2, p_mw=0.3, q_mvar=0.0, name="dg_feeder2")

    # switch 0 = breaker on the line into feeder1, switch 1 = breaker on the line into feeder2
    pp.create_switch(net, bus=b_main, element=0, et="l", closed=True, name="breaker_feeder1")
    pp.create_switch(net, bus=b_main, element=1, et="l", closed=True, name="breaker_feeder2")

    return net


class MicrogridModel:
    """Wraps a pandapower net with the operations an outstation needs."""

    def __init__(self, net: pp.pandapowerNet = None):
        self.net = net if net is not None else build_network()
        self.run_powerflow()

    def run_powerflow(self) -> None:
        pp.runpp(self.net)

    def operate_switch(self, index: int, close: bool) -> bool:
        """Open/close a breaker by its DNP3 binary-output index. Returns True on success."""
        switch_id = SWITCH_POINT_MAP.get(index)
        if switch_id is None:
            return False
        self.net.switch.at[switch_id, "closed"] = close
        self.run_powerflow()
        return True

    def read_binary(self, index: int) -> bool:
        switch_id = BINARY_STATUS_POINT_MAP.get(index)
        if switch_id is None:
            raise KeyError(f"no binary point mapped at index {index}")
        return bool(self.net.switch.at[switch_id, "closed"])

    def read_analog(self, index: int) -> float:
        mapping = ANALOG_POINT_MAP.get(index)
        if mapping is None:
            raise KeyError(f"no analog point mapped at index {index}")
        table, column, element_id = mapping
        return float(getattr(self.net, table).at[element_id, column])

    def write_analog(self, index: int, value: float) -> bool:
        """Only setpoints that make sense to write back (e.g. sgen output) are supported."""
        if index == 4:
            self.net.sgen.at[0, "p_mw"] = value
            self.run_powerflow()
            return True
        return False


if __name__ == "__main__":
    model = MicrogridModel()
    print("Initial state (both breakers closed):")
    print(" bus voltages (p.u.):", [model.read_analog(i) for i in (0, 1, 2)])
    print(" line loading (%):   ", [model.read_analog(i) for i in (3, 4)])

    print("\nOpening breaker 0 (feeder1)...")
    model.operate_switch(0, close=False)
    print(" breaker 0 status:", model.read_binary(0))
    print(" bus voltages (p.u.):", [model.read_analog(i) for i in (0, 1, 2)])
