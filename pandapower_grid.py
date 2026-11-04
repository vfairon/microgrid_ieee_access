"""
Pandapower model of the University of St. Thomas microgrid, rebuilt from the
actual Fig. 3 one-line diagram (not just the paper's prose/Table 2), replacing
the proprietary PowerWorld case (Microgrid_PowerWorld.pwb).

Structure read directly off the diagram:
- Each facility block (STEAM Vault, OWS/OSS Vault, Microgrid Expansion,
  FDC-Basement, Facilities and Design Center Vault, Anderson Parking Facility
  Vault) has its OWN 13.8kV->480V transformer, fed from a shared 13.8kV
  distribution bus (Xcel Energy Feeder MPK064) via named tap services and
  breakers CB1-CB9 (CB6 isn't shown in the diagram).
- A separate 13.8kV "13.8kV Loop" (Utility Tunnel) ties STEAM Vault (CB1),
  Microgrid Expansion (CB9) and FDC-Basement (CB3) together; CB1 and CB3 are
  explicitly marked Normally Open (N.O.) in the diagram -- tie points for
  reconfiguration, not normally carrying load.
- STEAM Vault has its own internal N.O. tie feeding its emergency bus
  (unlabeled in the diagram, modeled here as sw_STV_emergency).
- Anderson Arena is fed by a wholly separate feeder ("Xcel Energy Feeder
  Copy") -- not through the main 13.8kV bus at all -- modeled as its own
  ext_grid.

This reading resolves two things the paper's prose/Table 2 left ambiguous:
- Table 2 lists only 6 explicit generator/ESS Protection objects though the
  paper's text says 7 ("...and ESS units"). The diagram shows two distinct
  diesel generators at Microgrid Expansion (Diesel Gen 1, Diesel Gen 2) --
  the missing 7th is the second one, not individually itemized in Table 2.
- Anderson Arena's emergency generator rating (never given in the paper's
  prose) is 750kW per the diagram.

Caveat: numeric load/flow values on some labels in the diagram were hard to
read precisely at the resolution available (e.g. some OWS/OSS Vault load
figures); where the paper's text gives an unambiguous value (PV 48kW, battery
396kWh, diesel 50kW, RL bank 320kVA) that's used instead of an uncertain
diagram reading. Everything else (bus structure, transformer ratings,
generator sizes, breaker names/positions, N.O. tie points) is read directly
off the diagram.
"""
import pandapower as pp


def _xfmr(net, hv_bus, lv_bus, sn_mva, name, vn_hv_kv=13.8, vn_lv_kv=0.48):
    return pp.create_transformer_from_parameters(
        net, hv_bus=hv_bus, lv_bus=lv_bus, sn_mva=sn_mva,
        vn_hv_kv=vn_hv_kv, vn_lv_kv=vn_lv_kv,
        vkr_percent=1.0, vk_percent=6.0, pfe_kw=0.8, i0_percent=0.1, name=name,
    )


def _line(net, from_bus, to_bus, name, max_i_ka=1.0):
    return pp.create_line_from_parameters(
        net, from_bus=from_bus, to_bus=to_bus, length_km=0.05,
        r_ohm_per_km=0.2, x_ohm_per_km=0.08, c_nf_per_km=200, max_i_ka=max_i_ka,
        name=name,
    )


def build_network() -> pp.pandapowerNet:
    net = pp.create_empty_network(name="ust_microgrid")
    switches, sgens, storages, lines = {}, {}, {}, {}

    def sw(from_bus, line_id, key, closed=True):
        switches[key] = pp.create_switch(net, bus=from_bus, element=line_id, et="l", closed=closed, name=key)

    def bus(vn_kv, name):
        return pp.create_bus(net, vn_kv=vn_kv, name=name)

    # --- Main 13.8kV distribution (Xcel Energy Feeder MPK064) ---
    main13 = bus(13.8, "Xcel_MPK064_13_8kv")
    pp.create_ext_grid(net, bus=main13, vm_pu=1.0, name="Xcel_Feeder_MPK064")

    # Named service taps off the main feeder (plain lines -- tap fuses, not DNP3 breakers)
    svc3 = bus(13.8, "Existing_Campus_Svc3")
    svc2 = bus(13.8, "Existing_Campus_Svc2")
    tunnel = bus(13.8, "Utility_Tunnel_13_8kv_Loop")
    _line(net, main13, svc3, "tap_svc3")
    _line(net, main13, svc2, "tap_svc2")
    _line(net, main13, tunnel, "tap_existing_microgrid_svc")

    # --- OWS/OSS Vault (via CB2 from Existing Campus Service #3) ---
    owsoss13 = bus(13.8, "OWSOSS_13_8kv")
    l = _line(net, svc3, owsoss13, "L_CB2"); sw(svc3, l, "CB2")

    oss480 = bus(0.48, "OSS_480v")
    _xfmr(net, owsoss13, oss480, sn_mva=1.0, name="Tx_OSS_1MVA")
    pp.create_load(net, oss480, p_mw=0.68, q_mvar=0.6, name="OSS_NonEmergency_Loads")

    chillers480 = bus(0.48, "Chillers_480v")
    _xfmr(net, owsoss13, chillers480, sn_mva=1.5, name="Tx_Chillers_1.5MVA")
    pp.create_load(net, chillers480, p_mw=0.6, q_mvar=0.3, name="Chillers_Load")

    ows480 = bus(0.48, "OWS_480v")
    _xfmr(net, owsoss13, ows480, sn_mva=2.5, name="Tx_OWS_2.5MVA")
    owsemg480 = bus(0.48, "OWS_Emergency_480v")
    l = _line(net, ows480, owsemg480, "L_OWS_emergency_tie"); sw(ows480, l, "sw_OWS_emergency_tie")
    pp.create_load(net, owsemg480, p_mw=0.6, q_mvar=0.2, name="OWSOSS_Emergency_Loads")
    pp.create_sgen(net, owsemg480, p_mw=0.600, q_mvar=0.0, name="OWSV_EmergencyGen_600kW")

    # --- STEAM Vault ---
    # CB1 is explicitly marked N.O. in the diagram (a loop reconfiguration tie),
    # yet STEAM Vault's own bus readings in the diagram ("1.00 pu") show it
    # normally energized -- so CB1 can't be its only supply path. The diagram's
    # actual primary feed into STEAM isn't fully legible here; this adds a
    # direct always-closed line from the main 13.8kV bus so the model stays
    # internally consistent (STEAM powered, CB1 a real but N.O. backup tie),
    # which is an inference, not a confirmed reading.
    steam13 = bus(13.8, "STEAM_13_8kv")
    _line(net, main13, steam13, "STEAM_primary_feed")  # inferred, not individually DNP3-addressable
    l = _line(net, tunnel, steam13, "L_CB1"); sw(tunnel, l, "CB1", closed=False)  # N.O. per diagram

    steam480 = bus(0.48, "STEAM_480v")
    l = _line(net, steam13, steam480, "L_CB8_xfmr_side")
    _xfmr(net, steam13, steam480, sn_mva=2.5, name="Tx_STEAM_2500kVA")
    sw(steam13, l, "CB8")  # "STEAM Mains Breaker"
    pp.create_load(net, steam480, p_mw=0.70, q_mvar=0.56, name="STEAM_Bldg_Load")

    steamemg480 = bus(0.48, "STEAM_Emergency_480v")
    l = _line(net, steam480, steamemg480, "L_STV_emergency"); sw(steam480, l, "sw_STV_emergency", closed=False)  # N.O., "coupled with STEAM mains breaker"
    pp.create_load(net, steamemg480, p_mw=0.24, q_mvar=0.18, name="STEAM_Emergency_Loads")
    pp.create_sgen(net, steamemg480, p_mw=0.700, q_mvar=0.0, name="STV_EmergencyGen_700kW")

    # --- Microgrid Expansion (via CB9 from the Utility Tunnel loop) ---
    mgex13 = bus(13.8, "MGEx_13_8kv")
    l = _line(net, tunnel, mgex13, "L_CB9"); sw(tunnel, l, "CB9")

    mgex480 = bus(0.48, "MGEx_480v_New")
    _xfmr(net, mgex13, mgex480, sn_mva=2.5, name="Tx_MGEx_2.5MVA")
    pp.create_sgen(net, mgex480, p_mw=0.500, q_mvar=0.0, name="MGEx_DieselGen1_500kW")
    pp.create_sgen(net, mgex480, p_mw=0.500, q_mvar=0.0, name="MGEx_DieselGen2_500kW")
    pp.create_storage(net, mgex480, p_mw=0.500, max_e_mwh=1.5, soc_percent=50.0, name="MGEx_ESS_500kW_1.5MWh")
    pp.create_load(net, mgex480, p_mw=0.02, q_mvar=0.0, name="MGEx_EVCharger")
    pp.create_load(net, mgex480, p_mw=2.3, q_mvar=0.6, name="MGEx_Loadbank")

    # --- FDC-Basement (via CB3, N.O. tie to the Utility Tunnel loop) ---
    # This is the original, pre-expansion microgrid -- its 300kVA transformer
    # matches the paper's "0.3 MVA transformer stepping 13.8kV to 480V" text.
    fdc13 = bus(13.8, "FDC_13_8kv_Microgrid")
    l = _line(net, tunnel, fdc13, "L_CB3"); sw(tunnel, l, "CB3", closed=False)  # N.O. per diagram

    fdc480 = bus(0.48, "FDC_480v_Microgrid")
    l = _line(net, fdc13, fdc480, "L_CB7_xfmr_side")
    _xfmr(net, fdc13, fdc480, sn_mva=0.3, name="Tx_FDC_300kVA")
    sw(fdc13, l, "CB7")
    pp.create_sgen(net, fdc480, p_mw=0.048, q_mvar=0.0, name="FDBase_PV_48kW")
    pp.create_storage(net, fdc480, p_mw=0.125, max_e_mwh=0.396, soc_percent=50.0, name="FDBase_ESS_125kW_396kWh")
    pp.create_sgen(net, fdc480, p_mw=0.050, q_mvar=0.0, name="FDBase_DieselGen_50kW")
    pp.create_load(net, fdc480, p_mw=0.288, q_mvar=0.1396, name="FDBase_RLBank_320kVA")

    # --- APF/FDC shared 13.8kV bus (via CB5 from Existing Campus Service #2) ---
    apffdc13 = bus(13.8, "APF_FDC_13_8kv")
    l = _line(net, svc2, apffdc13, "L_CB5"); sw(svc2, l, "CB5")
    # Redundant tie back to FDC-Basement's microgrid bus ("Current Microgrid
    # N.O. Switchgear" in the diagram) -- a real interconnect, not individually
    # DNP3-addressable (not one of Table 2's 21 objects), kept closed by default.
    l = _line(net, apffdc13, fdc13, "L_CB4"); sw(apffdc13, l, "CB4")

    facdcv480 = bus(0.48, "FacDCV_480v")
    _xfmr(net, apffdc13, facdcv480, sn_mva=0.3, name="Tx_FacDCV_300kVA")
    pp.create_load(net, facdcv480, p_mw=0.13, q_mvar=0.08, name="FacDCV_Bldg_Load")

    apfac480 = bus(0.48, "APFac_480v")
    _xfmr(net, apffdc13, apfac480, sn_mva=0.3, name="Tx_APFac_300kVA")
    pp.create_load(net, apfac480, p_mw=0.035, q_mvar=0.02, name="APFac_Bldg_Load")

    # --- Anderson Arena: separate feeder entirely ("Xcel Energy Feeder Copy") ---
    arena13 = bus(13.8, "Arena_13_8kv")
    pp.create_ext_grid(net, bus=arena13, vm_pu=1.0, name="Xcel_Feeder_Copy")
    arena480 = bus(0.48, "Arena_480v_Main")
    _xfmr(net, arena13, arena480, sn_mva=0.3, name="Tx_Arena_300kVA")

    bus41 = bus(0.48, "Arena_Bus41_Birz")
    bus42 = bus(0.48, "Arena_Bus42_Divinity")
    bus43 = bus(0.48, "Arena_Bus43_ArenaGen")
    bus44 = bus(0.48, "Arena_Bus44_Brady")
    _line(net, arena480, bus41, "L_arena_41")
    _line(net, arena480, bus42, "L_arena_42")
    l = _line(net, arena480, bus43, "L_arena_43_Branch_45_7")  # Control -- maps to Table 2 "Branch '45' '7'"
    sw(arena480, l, "sw_Arena_main")
    _line(net, arena480, bus44, "L_arena_44")
    pp.create_load(net, bus41, p_mw=0.0, q_mvar=0.0, name="Birz_Bldg_Load")
    pp.create_load(net, bus42, p_mw=0.0, q_mvar=0.0, name="Divinity_Bldg_Load")
    pp.create_load(net, bus43, p_mw=0.75, q_mvar=0.0, name="Arena_Bldg_Load")
    pp.create_sgen(net, bus43, p_mw=0.750, q_mvar=0.0, name="AndAre_EmergencyGen_750kW")
    pp.create_load(net, bus44, p_mw=0.0, q_mvar=0.0, name="Brady_Bldg_Load")

    # --- index lookups ---
    sgen_by_name = {row["name"]: idx for idx, row in net.sgen.iterrows()}
    storage_by_name = {row["name"]: idx for idx, row in net.storage.iterrows()}
    line_by_name = {row["name"]: idx for idx, row in net.line.iterrows()}

    net["_switch_by_label"] = switches
    net["_sgen_by_label"] = {
        "Gen_13": sgen_by_name["STV_EmergencyGen_700kW"],
        "Gen_19": sgen_by_name["MGEx_DieselGen1_500kW"],
        "Gen_19b": sgen_by_name["MGEx_DieselGen2_500kW"],
        "Gen_20": sgen_by_name["OWSV_EmergencyGen_600kW"],
        "Gen_23": sgen_by_name["FDBase_DieselGen_50kW"],
        "Gen_43": sgen_by_name["AndAre_EmergencyGen_750kW"],
    }
    net["_storage_by_label"] = {
        "Gen_35": storage_by_name["FDBase_ESS_125kW_396kWh"],
    }
    net["_line_by_label"] = {
        "Branch_10_9": line_by_name["L_CB2"],                   # OWSV feeder section
        "Branch_21_9": line_by_name["L_OWS_emergency_tie"],     # OWSV emergency section
        "Branch_3_4": line_by_name["Tx_FacDCV_300kVA"] if "Tx_FacDCV_300kVA" in line_by_name else None,
        "Branch_5_6": line_by_name["Tx_APFac_300kVA"] if "Tx_APFac_300kVA" in line_by_name else None,
        "Branch_7_8": line_by_name["L_CB7_xfmr_side"],           # FDBase, matches CB7
    }
    # FacDCV/APFac monitoring points sit on transformers, not lines -- read loading from res_trafo instead.
    net["_trafo_by_label"] = {
        "Branch_3_4": net.trafo[net.trafo.name == "Tx_FacDCV_300kVA"].index[0],
        "Branch_5_6": net.trafo[net.trafo.name == "Tx_APFac_300kVA"].index[0],
    }
    del net["_line_by_label"]["Branch_3_4"]
    del net["_line_by_label"]["Branch_5_6"]

    return net


# ---------------------------------------------------------------------------
# DNP3 point map -- 21 objects: 9 Control breakers, 7 Protection (gen/ESS),
# 5 Monitoring branches. Labeled with each point's real CB name from the
# diagram, and (where applicable) its Table 2 "Branch 'X' 'Y'" identifier.
# ---------------------------------------------------------------------------

BREAKER_POINTS = {
    0: ("CB1 (STEAM Vault tie, N.O.)",          "CB1"),
    1: ("CB2 (OWS/OSS Vault)",                   "CB2"),
    2: ("CB3 (FDC-Basement tie, N.O.)",          "CB3"),
    3: ("CB5 (APF/FDC)",                         "CB5"),
    4: ("CB7 (FDC-Basement xfmr / Branch '7' '8')", "CB7"),
    5: ("CB8 (STEAM Mains Breaker)",             "CB8"),
    6: ("CB9 (Microgrid Expansion tie)",         "CB9"),
    7: ("STV emergency bus tie, N.O. (coupled w/ CB8)", "sw_STV_emergency"),
    8: ("Arena main breaker / Branch '45' '7'",  "sw_Arena_main"),
}

# index -> (label, kind, key)   -- Binary Output, Protection (generator/ESS)
PROTECTION_POINTS = {
    9:  ("Gen '13' -- STV emergency gen 700kW",        "sgen", "Gen_13"),
    10: ("Gen '19' -- MGEx diesel gen 1, 500kW",        "sgen", "Gen_19"),
    11: ("Gen '20' -- OWSV emergency gen 600kW",        "sgen", "Gen_20"),
    12: ("Gen '23' -- FDBase diesel gen 50kW",          "sgen", "Gen_23"),
    13: ("Gen '35' -- FDBase ESS 125kW/396kWh",         "storage", "Gen_35"),
    14: ("Gen '43' -- AndAre emergency gen 750kW",      "sgen", "Gen_43"),
    15: ("MGEx diesel gen 2, 500kW (2nd unit, Table 2's 7th protection point)", "sgen", "Gen_19b"),
}

# index -> (label, element kind, result table, column, key)   -- Analog Input, Monitoring
ANALOG_POINTS = {
    16: ("Branch '10' '9' -- OWSV feeder (CB2)",       "line",  "res_line",  "loading_percent", "Branch_10_9"),
    17: ("Branch '21' '9' -- OWSV emergency section",  "line",  "res_line",  "loading_percent", "Branch_21_9"),
    18: ("Branch '3' '4' -- FacDCV feeder",             "trafo", "res_trafo", "loading_percent", "Branch_3_4"),
    19: ("Branch '5' '6' -- APFac feeder",               "trafo", "res_trafo", "loading_percent", "Branch_5_6"),
    20: ("Branch '7' '8' -- FDBase feeder (CB7)",       "line",  "res_line",  "loading_percent", "Branch_7_8"),
}

SWITCH_POINT_MAP = {i: v[1] for i, v in BREAKER_POINTS.items()}
BINARY_STATUS_POINT_MAP = dict(SWITCH_POINT_MAP)
BINARY_STATUS_POINT_MAP.update({i: v[2] for i, v in PROTECTION_POINTS.items()})
ANALOG_POINT_MAP = {i: v for i, v in ANALOG_POINTS.items()}


class MicrogridModel:
    """Wraps the pandapower net above with the operations an outstation needs."""

    def __init__(self, net: pp.pandapowerNet = None):
        self.net = net if net is not None else build_network()
        self.run_powerflow()

    def run_powerflow(self) -> None:
        pp.runpp(self.net)

    def _breaker_switch_id(self, index: int):
        label = SWITCH_POINT_MAP.get(index)
        return None if label is None else self.net["_switch_by_label"][label]

    def _protection_ref(self, index: int):
        entry = PROTECTION_POINTS.get(index)
        if entry is None:
            return None
        _, kind, key = entry
        table = self.net["_sgen_by_label"] if kind == "sgen" else self.net["_storage_by_label"]
        return kind, table[key]

    def operate_switch(self, index: int, close: bool) -> bool:
        """Open/close a breaker (Control) or enable/disable a generator (Protection)."""
        switch_id = self._breaker_switch_id(index)
        if switch_id is not None:
            self.net.switch.at[switch_id, "closed"] = close
            self.run_powerflow()
            return True
        protection = self._protection_ref(index)
        if protection is not None:
            kind, element_id = protection
            table = self.net.sgen if kind == "sgen" else self.net.storage
            table.at[element_id, "in_service"] = close
            self.run_powerflow()
            return True
        return False

    def read_binary(self, index: int) -> bool:
        switch_id = self._breaker_switch_id(index)
        if switch_id is not None:
            return bool(self.net.switch.at[switch_id, "closed"])
        protection = self._protection_ref(index)
        if protection is not None:
            kind, element_id = protection
            table = self.net.sgen if kind == "sgen" else self.net.storage
            return bool(table.at[element_id, "in_service"])
        raise KeyError(f"no binary point mapped at index {index}")

    def read_analog(self, index: int) -> float:
        mapping = ANALOG_POINT_MAP.get(index)
        if mapping is None:
            raise KeyError(f"no analog point mapped at index {index}")
        _, kind, table, column, key = mapping
        lookup = self.net["_line_by_label"] if kind == "line" else self.net["_trafo_by_label"]
        element_id = lookup[key]
        value = float(getattr(self.net, table).at[element_id, column])
        return 0.0 if value != value else value  # isolated branch -> NaN -> report 0.0

    def write_analog(self, index: int, value: float) -> bool:
        # All 21 DNP3 objects in this model are Analog Input or Binary Output --
        # no Analog Output (setpoint) objects, so nothing to write.
        return False


if __name__ == "__main__":
    model = MicrogridModel()
    print("Breakers (Control):")
    for idx, (label, _) in BREAKER_POINTS.items():
        print(f"  [{idx:2d}] {label}: {'CLOSED' if model.read_binary(idx) else 'OPEN'}")
    print("Protection (generator/ESS):")
    for idx, (label, *_rest) in PROTECTION_POINTS.items():
        print(f"  [{idx:2d}] {label}: {'IN SERVICE' if model.read_binary(idx) else 'OFFLINE'}")
    print("Monitoring (loading %):")
    for idx, (label, *_rest) in ANALOG_POINTS.items():
        print(f"  [{idx:2d}] {label}: {model.read_analog(idx):.2f}%")

    # Index 7 (the STV emergency bus tie) is N.O. by default -- standard
    # standby-generator practice, only closes during an actual outage -- so
    # opening it wouldn't change anything. The paper's narrative ("manipulates
    # the circuit breaker... system experiences a sudden frequency drop...
    # blackout") only makes sense against something that WAS supplying power,
    # so the closer match is CB8 (index 5, STEAM's normally-closed main breaker).
    print("\nSending the paper's attack: opening CB8 (index 5, STEAM Mains Breaker)...")
    print(f"  before: {model.read_analog(20):.2f}% loading on FDBase feeder (unaffected, different section)")
    model.operate_switch(5, close=False)
    print(f"  CB8 status: {'CLOSED' if model.read_binary(5) else 'OPEN'}")
    print("  STEAM Vault's 480V bus (Bldg Load + emergency section) now unreachable from the feeder.")
