import logging
import sys
import time
import cmd
from datetime import datetime
import socket
from pydnp3 import opendnp3, openpal, asiopal, asiodnp3
#from pydnp3 import openpal, asiopal, asiodnp3
FILTERS = opendnp3.levels.NORMAL

# DNP3 outstation running in PWDS *************
HOST = "PowerWolrdDS_Server_IP"

LOCAL = "0.0.0.0"
PORT = 20000
# HOST_frontend = '10.110.215.24'  # PyDNP3 server
# PORT_frontend = 65432        # Port to listen on (non-privileged ports are > 1023
data_to_send=""
conn = None
completions = ["TRIP_PULSE_ON", "CLOSE_PULSE_ON"]

stdout_stream = logging.StreamHandler(sys.stdout)
stdout_stream.setFormatter(logging.Formatter('%(asctime)s\t%(name)s\t%(levelname)s\t%(message)s'))

_log = logging.getLogger(__name__)
_log.addHandler(stdout_stream)
_log.setLevel(logging.WARNING)


class MyMaster:
    """
        Interface for all master application callback info except for measurement values.
        DNP3 spec section 5.1.6.1:
            The Application Layer provides the following services for the DNP3 User Layer in a master:
                - Formats requests directed to one or more outstations.
                - Notifies the DNP3 User Layer when new data or information arrives from an outstation.
        DNP spec section 5.1.6.3:
            The Application Layer requires specific services from the layers beneath it.
                - Partitioning of fragments into smaller portions for transport reliability.
                - Knowledge of which device(s) were the source of received messages.
                - Transmission of messages to specific devices or to all devices.
                - Message integrity (i.e., error-free reception and transmission of messages).
                - Knowledge of the time when messages arrive.
                - Either precise times of transmission or the ability to set time values
                  into outgoing messages.
    """
    def __init__(self,
                 outstation,
                 log_handler=asiodnp3.ConsoleLogger().Create(),
                 listener=asiodnp3.PrintingChannelListener().Create(),
                 soe_handler=asiodnp3.PrintingSOEHandler().Create(),
                 master_application=asiodnp3.DefaultMasterApplication().Create(),
                 stack_config=None):

        _log.debug('Creating a DNP3Manager.')
        self.outstation = outstation
        self.log_handler = log_handler
        self.manager = asiodnp3.DNP3Manager(1, self.log_handler)

        _log.debug('Creating the DNP3 channel, a TCP client.')
        self.retry = asiopal.ChannelRetry().Default()
        self.listener = listener
        self.channel = self.manager.AddTCPClient("tcpclient",
                                        FILTERS,
                                        self.retry,
                                        HOST,
                                        LOCAL,
                                        PORT,
                                        self.listener)

        _log.debug('Configuring the DNP3 stack.')
        self.stack_config = stack_config
        if not self.stack_config:
            self.stack_config = asiodnp3.MasterStackConfig()
            self.stack_config.master.responseTimeout = openpal.TimeDuration().Seconds(2)
            self.stack_config.link.RemoteAddr = self.outstation

        _log.debug('Adding the master to the channel.')
        self.soe_handler = soe_handler
        self.master_application = master_application
        self.master = self.channel.AddMaster("master",
                                   asiodnp3.PrintingSOEHandler().Create(),
                                   self.master_application,
                                   self.stack_config)

        _log.debug('Configuring some scans (periodic reads).')
        # # Set up a "slow scan", an infrequent integrity poll that requests events and static data for all classes.
        # self.slow_scan = self.master.AddClassScan(opendnp3.ClassField().AllClasses(),
        #                                           openpal.TimeDuration().Minutes(30),
        #                                           opendnp3.TaskConfig().Default())
        # Set up a "fast scan" but never auto-fire it (TimeDuration.Max()) -- it only runs when
        # explicitly requested via do_scan_fast's fast_scan.Demand(), so the CLI stays silent
        # until you actually ask for something instead of printing every few seconds on its own.
        self.fast_scan = self.master.AddClassScan(opendnp3.ClassField(opendnp3.ClassField.CLASS_0),
                                                  openpal.TimeDuration().Max(),
                                                  opendnp3.TaskConfig().Default())

        self.channel.SetLogFilters(openpal.LogFilters(opendnp3.levels.ALL_COMMS))
        self.master.SetLogFilters(openpal.LogFilters(opendnp3.levels.ALL_COMMS))

        _log.debug('Enabling the master. At this point, traffic will start to flow between the Master and Outstations.')
        self.master.Enable()
        time.sleep(5)

    def send_direct_operate_command(self, command, index, callback=asiodnp3.PrintingCommandCallback.Get(),
                                    config=opendnp3.TaskConfig().Default()):
        """
            Direct operate a single command
        :param command: command to operate
        :param index: index of the command
        :param callback: callback that will be invoked upon completion or failure
        :param config: optional configuration that controls normal callbacks and allows the user to be specified for SA
        """
        # global conn
        self.master.DirectOperate(command, index, callback, config)
        time.sleep(1)
        # conn.sendall(str.encode(data_to_send))

    def send_direct_operate_command_set(self, command_set, callback=asiodnp3.PrintingCommandCallback.Get(),
                                        config=opendnp3.TaskConfig().Default()):
        """
            Direct operate a set of commands
        :param command_set: set of command headers
        :param callback: callback that will be invoked upon completion or failure
        :param config: optional configuration that controls normal callbacks and allows the user to be specified for SA
        """
        # global conn
        self.master.DirectOperate(command_set, callback, config)
        time.sleep(1)
        # conn.sendall(str.encode(data_to_send))

    def send_select_and_operate_command(self, command, index, callback=asiodnp3.PrintingCommandCallback.Get(),
                                        config=opendnp3.TaskConfig().Default()):
        """
            Select and operate a single command
        :param command: command to operate
        :param index: index of the command
        :param callback: callback that will be invoked upon completion or failure
        :param config: optional configuration that controls normal callbacks and allows the user to be specified for SA
        """
        # global conn
        self.master.SelectAndOperate(command, index, callback, config)
        time.sleep(1)
        # conn.sendall(str.encode(data_to_send))

    def send_select_and_operate_command_set(self, command_set, callback=asiodnp3.PrintingCommandCallback.Get(),
                                            config=opendnp3.TaskConfig().Default()):
        """
            Select and operate a set of commands
        :param command_set: set of command headers
        :param callback: callback that will be invoked upon completion or failure
        :param config: optional configuration that controls normal callbacks and allows the user to be specified for SA
        """
        # global conn
        self.master.SelectAndOperate(command_set, callback, config)
        time.sleep(1)
        # conn.sendall(str.encode(data_to_send))

    def shutdown(self):
        del self.fast_scan
        del self.master
        del self.channel
        self.manager.Shutdown()


class MyLogger(openpal.ILogHandler):
    """
        Override ILogHandler in this manner to implement application-specific logging behavior.
    """

    def __init__(self):
        super(MyLogger, self).__init__()

    def Log(self, entry):
        flag = opendnp3.LogFlagToString(entry.filters.GetBitfield())
        filters = entry.filters.GetBitfield()
        location = entry.location.rsplit('/')[-1] if entry.location else ''
        message = entry.message
        _log.debug('LOG\t\t{:<10}\tfilters={:<5}\tlocation={:<25}\tentry={}'.format(flag, filters, location, message))


class AppChannelListener(asiodnp3.IChannelListener):
    """
        Override IChannelListener in this manner to implement application-specific channel behavior.
    """

    def __init__(self):
        super(AppChannelListener, self).__init__()

    def OnStateChange(self, state):
        _log.debug('In AppChannelListener.OnStateChange: state={}'.format(opendnp3.ChannelStateToString(state)))


class SOEHandler(opendnp3.ISOEHandler):
    """
        Override ISOEHandler in this manner to implement application-specific sequence-of-events behavior.
        This is an interface for SequenceOfEvents (SOE) callbacks from the Master stack to the application layer.
    """

    def __init__(self):
        super(SOEHandler, self).__init__()

    def Process(self, info, values):
        """
         Process measurement data.

        :param info: HeaderInfo
        :param values: A collection of values received from the Outstation (various data types are possible).
        """
        visitor_class_types = {
            opendnp3.ICollectionIndexedBinary: VisitorIndexedBinary,
            opendnp3.ICollectionIndexedDoubleBitBinary: VisitorIndexedDoubleBitBinary,
            opendnp3.ICollectionIndexedCounter: VisitorIndexedCounter,
            opendnp3.ICollectionIndexedFrozenCounter: VisitorIndexedFrozenCounter,
            opendnp3.ICollectionIndexedAnalog: VisitorIndexedAnalog,
            opendnp3.ICollectionIndexedBinaryOutputStatus: VisitorIndexedBinaryOutputStatus,
            opendnp3.ICollectionIndexedAnalogOutputStatus: VisitorIndexedAnalogOutputStatus,
            opendnp3.ICollectionIndexedTimeAndInterval: VisitorIndexedTimeAndInterval
        }
        visitor_class = visitor_class_types[type(values)]
        visitor = visitor_class()
        values.Foreach(visitor)
        for index, value in visitor.index_and_value:
            log_string = 'SOEHandler.Process {0}\theaderIndex={1}\tdata_type={2}\tindex={3}\tvalue={4}'
            _log.debug(log_string.format(info.gv, info.headerIndex, type(values).__name__, index, value))
            print('TEST *************************************')

    def Start(self):
        _log.debug('In SOEHandler.Start')

    def End(self):
        _log.debug('In SOEHandler.End')


class MasterApplication(opendnp3.IMasterApplication):
    def __init__(self):
        super(MasterApplication, self).__init__()

    # Overridden method
    def AssignClassDuringStartup(self):
        _log.debug('In MasterApplication.AssignClassDuringStartup')
        return False

    # Overridden method
    def OnClose(self):
        _log.debug('In MasterApplication.OnClose')

    # Overridden method
    def OnOpen(self):
        _log.debug('In MasterApplication.OnOpen')

    # Overridden method
    def OnReceiveIIN(self, iin):
        _log.debug('In MasterApplication.OnReceiveIIN')

    # Overridden method
    def OnTaskComplete(self, info):
        _log.debug('In MasterApplication.OnTaskComplete')

    # Overridden method
    def OnTaskStart(self, type, id):
        _log.debug('In MasterApplication.OnTaskStart')


class Action:
    def __init__(self, args):
        self.outstation = int(args[0])
        self.type = args[1]
        if self.type == "scan":
            self.scan_class = args[2]
            self.scan_interval = int(args[3])
            self.action = None
            self.target = None
        else:
            self.scan_class = None
            self.scan_interval = None
            self.action = args[2]
            self.target = int(args[3])


class MasterCmd(cmd.Cmd):
    """
        Create a DNP3Manager that acts as the Master in a DNP3 Master/Outstation interaction.
        Accept command-line input that sends commands and data to the Outstation,
        using the line-oriented command interpreter framework from the 'cmd' Python Standard Library.
    """

    def __init__(self, outstation):
        cmd.Cmd.__init__(self)
        self.prompt = 'master_'+str(outstation)+'> '   # Used by the Cmd framework, displayed when issuing a command-line prompt.
        self.application = MyMaster(log_handler=MyLogger(),
                                    listener=AppChannelListener(),
                                    soe_handler=SOEHandler(),
                                    master_application=MasterApplication(),
                                    outstation=outstation)

    def startup(self):
        """Display the command-line interface's menu and issue a prompt."""
        print('Welcome to the DNP3 master request command line. Supported commands include:')
        self.do_menu('')
        self.cmdloop('Please enter a command.')
        exit()

    def do_menu(self, line):
        """Display a menu of command-line options. Command syntax is: menu"""
        print('\tchan_log_all\tSet the channel log level to ALL_COMMS.')
        print('\tchan_log_normal\tSet the channel log level to NORMAL.')
        print('\tdisable_unsol\tPerform the function DISABLE_UNSOLICITED.')
        print('\thelp\t\tDisplay command-line help.')
        print('\tmast_log_all\tSet the master log level to ALL_COMMS.')
        print('\tmast_log_normal\tSet the master log level to NORMAL.')
        print('\tmenu\t\tDisplay this menu.')
        print('\to0\t\tSend a DirectOperate command.')
        print('\to1\t\tSend a DirectOperate LATCH_ON command.')
        print('\to2\t\tSend a DirectOperate analog value.')
        print('\to3\t\tSend a DirectOperate CommandSet.')
        print('\tquit')
        print('\trestart\t\tRequest an outstation cold restart.')
        print('\ts0\t\tSend a SelectAndOperate command.')
        print('\ts1\t\tSend a SelectAndOperate LATCH_ON command.')
        print('\ts2\t\tSend a SelectAndOperate CommandSet.')
        print('\tscan_all\tRead data from the outstation (ScanAllObjects).')
        print('\tscan_fast\tDemand immediate execution of the fast (every 1 mins) Class 1 scan.')
        print('\tscan_range\tPerform an ad-hoc scan (ScanRange) of GroupVariation 1.2, range 0..3.')
        print('\tscan_slow\tDemand immediate execution of the slow (every 30 mins) All-Classes scan.')
        print('\twrite_time\tWrite a TimeAndInterval to the outstation.')

    def do_chan_log_all(self, line):
        """Set the channel log level to ALL_COMMS. Command syntax is: chan_log_all"""
        self.application.channel.SetLogFilters(openpal.LogFilters(opendnp3.levels.ALL_COMMS))
        print('Channel log filtering level is now: {0}'.format(opendnp3.levels.ALL_COMMS))

    def do_chan_log_normal(self, line):
        """Set the channel log level to NORMAL. Command syntax is: chan_log_normal"""
        self.application.channel.SetLogFilters(openpal.LogFilters(opendnp3.levels.NORMAL))
        print('Channel log filtering level is now: {0}'.format(opendnp3.levels.NORMAL))

    def do_disable_unsol(self, line):
        """Perform the function DISABLE_UNSOLICITED. Command syntax is: disable_unsol"""
        headers = [opendnp3.Header().AllObjects(60, 2),
                   opendnp3.Header().AllObjects(60, 3),
                   opendnp3.Header().AllObjects(60, 4)]
        self.application.master.PerformFunction("disable unsolicited",
                                                opendnp3.FunctionCode.DISABLE_UNSOLICITED,
                                                headers,
                                                opendnp3.TaskConfig().Default())

    def do_mast_log_all(self, line):
        """Set the master log level to ALL_COMMS. Command syntax is: mast_log_all"""
        self.application.master.SetLogFilters(openpal.LogFilters(opendnp3.levels.ALL_COMMS))
        _log.debug('Master log filtering level is now: {0}'.format(opendnp3.levels.ALL_COMMS))

    def do_mast_log_normal(self, line):
        """Set the master log level to NORMAL. Command syntax is: mast_log_normal"""
        self.application.master.SetLogFilters(openpal.LogFilters(opendnp3.levels.NORMAL))
        _log.debug('Master log filtering level is now: {0}'.format(opendnp3.levels.NORMAL))

    def do_o0(self, line):
        command = line.split()
        target = int(command[0])
        action = command[1].upper()
        self.application.send_direct_operate_command(opendnp3.ControlRelayOutputBlock(getattr(opendnp3.ControlCode, action)),
                                                     target,
                                                     command_callback)

    def complete_o0(self, text, line, bigidx, endidx):
        mline = line.split()[2]
        offs = len(mline) - len(text)
        return [s[offs:] for s in completions if s.lower().startswith(mline.lower())]

    def do_o1(self, line):
        command = line.split()
        target = int(command[0])
        """Send a DirectOperate BinaryOutput (group 12) index 5 LATCH_ON to the Outstation. Command syntax is: o1"""
        self.application.send_direct_operate_command(opendnp3.ControlRelayOutputBlock(opendnp3.ControlCode.LATCH_ON), #LATCH_ON = 1
                                                     target) #5

    def do_o3(self, line):
        command = line.split()
        target = int(command[0])
        """Send a DirectOperate BinaryOutput (group 12) index 5 LATCH_OFF to the Outstation. Command syntax is: o3"""
        self.application.send_direct_operate_command(opendnp3.ControlRelayOutputBlock(opendnp3.ControlCode.LATCH_OFF), #LATCH_OFF = 0
                                                     target) #5

    def do_o2(self, line):
        command = line.split()
        target = int(command[0])
        action = float(command[1]) #.upper()
        self.application.send_direct_operate_command(opendnp3.AnalogOutputFloat32(action),
                                                     target,
                                                     command_callback)
  #  def do_o2(self, line):
  #      """Send a DirectOperate AnalogOutput (group 41) index 10 value 7 to the Outstation. Command syntax is: o2"""
  #      self.application.send_direct_operate_command(opendnp3.AnalogOutputInt32(7),
  #                                                   10,
  #                                                   command_callback)


## to set up the o2 command, do_o2(opendnp3.AnalogOutputFloat32(155), 4, command_callback) 
## do_o2([4, 155])
## do_o2([4 155])
## o2(4 155)
## correct syntax: o2 4 155 o2 4 200 o2 4 180 o2 4 250 o2 4 150 o2 4 126

## o1 1 1, o2 47 8, o3 1 0, o3 0 0
## o1 worked the other way around when the output had value:129:0
## o3 sent in the required command to open the line and generator
## o1 connects the object, o3 disconnects the object

##    def do_o3(self, line):
##        """Send a DirectOperate BinaryOutput (group 12) CommandSet to the Outstation. Command syntax is: o3"""
##        self.application.send_direct_operate_command_set(opendnp3.CommandSet(
##            [
##                opendnp3.WithIndex(opendnp3.ControlRelayOutputBlock(opendnp3.ControlCode.LATCH_ON), 0),
##                opendnp3.WithIndex(opendnp3.ControlRelayOutputBlock(opendnp3.ControlCode.LATCH_OFF), 1)
##            ]),
##            command_callback
##        )

        # This could also have been in multiple steps, as follows:
        # command_set = opendnp3.CommandSet()
        # command_set.Add([
        #     opendnp3.WithIndex(opendnp3.ControlRelayOutputBlock(opendnp3.ControlCode.LATCH_ON), 0),
        #     opendnp3.WithIndex(opendnp3.ControlRelayOutputBlock(opendnp3.ControlCode.LATCH_OFF), 1)
        # ])
        # self.application.send_direct_operate_command_set(command_set, command_callback)

    def do_restart(self, line):
        """Request that the Outstation perform a cold restart. Command syntax is: restart"""
        self.application.master.Restart(opendnp3.RestartType.COLD, restart_callback)

    def do_s0(self, line):
        command = line.split()
        target = int(command[0])
        action = command[1].upper()
        self.application.send_select_and_operate_command(opendnp3.ControlRelayOutputBlock(getattr(opendnp3.ControlCode, action)),
                                                         target,
                                                         command_callback)

    def do_s1(self, line):
        """Send a SelectAndOperate BinaryOutput (group 12) index 8 LATCH_ON to the Outstation. Command syntax is: s1"""
        self.application.send_select_and_operate_command(opendnp3.ControlRelayOutputBlock(opendnp3.ControlCode.LATCH_ON),
                                                         8,
                                                         command_callback)

    def do_s2(self, line):
        """Send a SelectAndOperate BinaryOutput (group 12) CommandSet to the Outstation. Command syntax is: s2"""
        self.application.send_select_and_operate_command_set(opendnp3.CommandSet(
            [
                opendnp3.WithIndex(opendnp3.ControlRelayOutputBlock(opendnp3.ControlCode.LATCH_ON), 0)
            ]),
            command_callback
        )

    def do_scan_all(self, line):
        """Call ScanAllObjects. Command syntax is: scan_all"""
        self.application.master.ScanAllObjects(opendnp3.GroupVariationID(2, 1), opendnp3.TaskConfig().Default())

    def do_scan_fast(self, line):
        """Demand an immediate fast scan. Command syntax is: scan_fast"""
        self.application.fast_scan.Demand()

    def do_scan_range(self, line):
        """Do an ad-hoc scan of a range of points (group 1, variation 2, indexes 0-3). Command syntax is: scan_range"""
        self.application.master.ScanRange(opendnp3.GroupVariationID(1, 2), 0, 3, opendnp3.TaskConfig().Default())

    def do_scan_slow(self, line):
        """Demand an immediate slow scan. Command syntax is: scan_slow"""
        self.application.slow_scan.Demand()

    def do_write_time(self, line):
        """Write a TimeAndInterval to the Outstation. Command syntax is: write_time"""
        millis_since_epoch = int((datetime.now() - datetime.utcfromtimestamp(0)).total_seconds() * 1000.0)
        self.application.master.Write(opendnp3.TimeAndInterval(opendnp3.DNPTime(millis_since_epoch),
                                                               100,
                                                               opendnp3.IntervalUnits.Seconds),
                                      0,                            # index
                                      opendnp3.TaskConfig().Default())

    def do_quit(self, line):
        """Quit the command-line interface. Command syntax is: quit"""
        self.application.shutdown()
        exit()


def collection_callback(result=None):
    """
    :type result: opendnp3.CommandPointResult
    """
    global data_to_send
    data_to_send = "Header: "+str(result.headerIndex)+" Index:  "+ str(result.index) +" State:  "+ opendnp3.CommandPointStateToString(result.state)+" Status: "+opendnp3.CommandStatusToString(result.status)
    print("Header: {0} | Index:  {1} | State:  {2} | Status: {3}".format(
        result.headerIndex,
        result.index,
        opendnp3.CommandPointStateToString(result.state),
        opendnp3.CommandStatusToString(result.status)
    ))


def command_callback(result=None):
    """
    :type result: opendnp3.ICommandTaskResult
    """
    global data_to_send
    data_to_send = "Received command result with summary: {}".format(opendnp3.TaskCompletionToString(result.summary))
    print("Received command result with summary: {}".format(opendnp3.TaskCompletionToString(result.summary)))
    result.ForeachItem(collection_callback)


def restart_callback(result=opendnp3.RestartOperationResult()):
    global data_to_send
    if result.summary == opendnp3.TaskCompletion.SUCCESS:
        data_to_send = "Restart success -> Restart Time: " + str(result.restartTime.GetMilliseconds())
        print("Restart success | Restart Time: {}".format(result.restartTime.GetMilliseconds()))
    else:
        print("Restart fail | Failure: {}".format(opendnp3.TaskCompletionToString(result.summary)))


def main():
    """The Master has been started from the command line. Execute ad-hoc tests if desired."""
    # global conn
    # app = MyMaster()
    global HOST
    args = sys.argv
    print(args)
    outstation = int(args[1])
    HOST = str(args[2])
    cmd_interface = MasterCmd(outstation)
    _log.debug('Initialization complete. In command loop.')
    time.sleep(2)
    # s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # s.bind((HOST_frontend, PORT_frontend))
    # s.listen()
    # received_req = False
    # conn, addr = s.accept()
    # if received_req == False:
    #     print('Connected by', addr)
    #     data = conn.recv(1024)
    #     if data:
    #         received_req = True
    #cmd_interface.startup()

    # Instead of starting the command interface here, we could always
    # just trigger sending commands directly from changes to the SQL database.
    cmd_interface.startup()
    _log.debug('Exiting.')


if __name__ == '__main__':
    main()
