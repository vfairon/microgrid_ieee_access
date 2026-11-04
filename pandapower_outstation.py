"""
DNP3 outstation that exposes a pandapower microgrid model instead of PowerWorld DS.

Drop-in replacement for the PowerWorld side of the setup described in README.md:
pydnp3_master.py (unchanged) connects to whatever IP/port runs this script
instead of the PowerWorld machine. Built from the pydnp3 outstation example
(https://github.com/Kisensum/pydnp3/blob/master/examples/outstation.py), reusing
its class layout so it stays consistent with pydnp3_master.py's own style.

Requires pydnp3 (built per the Dockerfile) -- the grid logic itself lives in
pandapower_grid.py, which has no pydnp3 dependency and can be tested on its own.
"""
import logging
import sys
import time

from pydnp3 import opendnp3, openpal, asiopal, asiodnp3

from pandapower_grid import (
    MicrogridModel,
    SWITCH_POINT_MAP,
    ANALOG_POINT_MAP,
    BINARY_STATUS_POINT_MAP,
)

LOG_LEVELS = opendnp3.levels.NORMAL | opendnp3.levels.ALL_COMMS
LOCAL_IP = "0.0.0.0"
PORT = 20000

CLOSE_CODES = {opendnp3.ControlCode.LATCH_ON, opendnp3.ControlCode.CLOSE_PULSE_ON}
OPEN_CODES = {opendnp3.ControlCode.LATCH_OFF, opendnp3.ControlCode.TRIP_PULSE_ON}

stdout_stream = logging.StreamHandler(sys.stdout)
stdout_stream.setFormatter(logging.Formatter('%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s'))

_log = logging.getLogger(__name__)
_log.addHandler(stdout_stream)
_log.setLevel(logging.DEBUG)


class OutstationApplication(opendnp3.IOutstationApplication):
    """Owns the DNP3 stack and the pandapower model it exposes."""

    outstation = None

    def __init__(self, model: MicrogridModel = None):
        super(OutstationApplication, self).__init__()
        self.model = model if model is not None else MicrogridModel()

        _log.debug('Configuring the DNP3 stack.')
        self.stack_config = self.configure_stack()

        _log.debug('Configuring the outstation database.')
        self.configure_database(self.stack_config.dbConfig)

        _log.debug('Creating a DNP3Manager.')
        self.log_handler = asiodnp3.ConsoleLogger().Create()
        self.manager = asiodnp3.DNP3Manager(1, self.log_handler)

        _log.debug('Creating the DNP3 channel, a TCP server.')
        self.retry_parameters = asiopal.ChannelRetry().Default()
        self.listener = AppChannelListener()
        self.channel = self.manager.AddTCPServer("server",
                                                 LOG_LEVELS,
                                                 self.retry_parameters,
                                                 LOCAL_IP,
                                                 PORT,
                                                 self.listener)

        _log.debug('Adding the outstation to the channel.')
        self.command_handler = OutstationCommandHandler(self)
        self.outstation = self.channel.AddOutstation("outstation", self.command_handler, self, self.stack_config)
        OutstationApplication.set_outstation(self.outstation)

        _log.debug('Enabling the outstation. Traffic will now start to flow.')
        self.outstation.Enable()

        self.push_all_points()

    @staticmethod
    def configure_stack():
        # Point indices now go up to 20 (21 DNP3 objects total, per
        # pandapower_grid.py) -- must be AT LEAST 21, not the old 10, or
        # configuring/pushing points past index 9 fails outright.
        db_size = max(21, max(ANALOG_POINT_MAP, default=0) + 1, max(BINARY_STATUS_POINT_MAP, default=0) + 1)
        stack_config = asiodnp3.OutstationStackConfig(opendnp3.DatabaseSizes.AllTypes(db_size))
        stack_config.outstation.eventBufferConfig = opendnp3.EventBufferConfig().AllTypes(db_size)
        stack_config.outstation.params.allowUnsolicited = True
        stack_config.link.LocalAddr = 10
        stack_config.link.RemoteAddr = 1
        stack_config.link.KeepAliveTimeout = openpal.TimeDuration().Max()
        return stack_config

    @staticmethod
    def configure_database(db_config):
        """One analog point per ANALOG_POINT_MAP entry, one binary point per switch."""
        for index in ANALOG_POINT_MAP:
            db_config.analog[index].clazz = opendnp3.PointClass.Class2
            db_config.analog[index].svariation = opendnp3.StaticAnalogVariation.Group30Var1
            db_config.analog[index].evariation = opendnp3.EventAnalogVariation.Group32Var7
        for index in BINARY_STATUS_POINT_MAP:
            db_config.binary[index].clazz = opendnp3.PointClass.Class2
            db_config.binary[index].svariation = opendnp3.StaticBinaryVariation.Group1Var2
            db_config.binary[index].evariation = opendnp3.EventBinaryVariation.Group2Var2

    def push_all_points(self):
        """Push the model's current state into the DNP3 database (after init or any command)."""
        for index in ANALOG_POINT_MAP:
            self.apply_update(opendnp3.Analog(self.model.read_analog(index)), index)
        for index in BINARY_STATUS_POINT_MAP:
            self.apply_update(opendnp3.Binary(self.model.read_binary(index)), index)

    def apply_update(self, value, index):
        _log.debug('Recording {} measurement, index={}, value={}'.format(type(value).__name__, index, value.value))
        builder = asiodnp3.UpdateBuilder()
        builder.Update(value, index)
        update = builder.Build()
        OutstationApplication.get_outstation().Apply(update)

    def shutdown(self):
        self.manager.Shutdown()

    @classmethod
    def get_outstation(cls):
        return cls.outstation

    @classmethod
    def set_outstation(cls, outstn):
        cls.outstation = outstn

    # Overridden methods -- behavior mirrors the stock pydnp3 outstation example.
    def ColdRestartSupport(self):
        return opendnp3.RestartMode.UNSUPPORTED

    def WarmRestartSupport(self):
        return opendnp3.RestartMode.UNSUPPORTED

    def GetApplicationIIN(self):
        application_iin = opendnp3.ApplicationIIN()
        application_iin.configCorrupt = False
        application_iin.deviceTrouble = False
        application_iin.localControl = False
        application_iin.needTime = False
        return application_iin

    def SupportsAssignClass(self):
        return False

    def SupportsWriteAbsoluteTime(self):
        return False

    def SupportsWriteTimeAndInterval(self):
        return False


class OutstationCommandHandler(opendnp3.ICommandHandler):
    """Translates incoming Select/Operate commands into pandapower model changes."""

    def __init__(self, app: "OutstationApplication"):
        super(OutstationCommandHandler, self).__init__()
        self.app = app
        self.model = app.model

    def Start(self):
        _log.debug('In OutstationCommandHandler.Start')

    def End(self):
        _log.debug('In OutstationCommandHandler.End')

    def Select(self, command, index):
        """Select is a no-op dry-run: accept it if the index is one we know about."""
        if isinstance(command, opendnp3.ControlRelayOutputBlock):
            # Breakers (SWITCH_POINT_MAP) and generator/ESS protection points are both
            # commandable Binary Outputs per the paper's Table 2 -- BINARY_STATUS_POINT_MAP
            # covers both.
            known = index in BINARY_STATUS_POINT_MAP
        else:
            known = index in ANALOG_POINT_MAP
        return opendnp3.CommandStatus.SUCCESS if known else opendnp3.CommandStatus.NOT_SUPPORTED

    def Operate(self, command, index, op_type):
        if isinstance(command, opendnp3.ControlRelayOutputBlock):
            success = self._operate_breaker(command, index)
        else:
            success = self.model.write_analog(index, command.value)

        status = opendnp3.CommandStatus.SUCCESS if success else opendnp3.CommandStatus.NOT_SUPPORTED
        if success:
            self.app.push_all_points()
        return status

    def _operate_breaker(self, command, index):
        if command.functionCode in CLOSE_CODES:
            _log.info('COMMAND: breaker {} received CLOSE ({})'.format(index, command.functionCode))
            return self.model.operate_switch(index, close=True)
        if command.functionCode in OPEN_CODES:
            _log.info('COMMAND: breaker {} received OPEN ({})'.format(index, command.functionCode))
            return self.model.operate_switch(index, close=False)
        _log.debug('Unhandled ControlCode {} for index {}'.format(command.functionCode, index))
        return False


class AppChannelListener(asiodnp3.IChannelListener):
    def __init__(self):
        super(AppChannelListener, self).__init__()

    def OnStateChange(self, state):
        _log.debug('In AppChannelListener.OnStateChange: state={}'.format(state))


def main():
    app = OutstationApplication()
    _log.debug('Initialization complete. Outstation running on {}:{}. Ctrl-C to stop.'.format(LOCAL_IP, PORT))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    app.shutdown()
    _log.debug('Exiting.')


if __name__ == '__main__':
    main()
