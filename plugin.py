#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Name: Solax Inverter MODBUS plugin
# Version: 0.0.2
# Author: Martin Saidl
#

"""
<plugin key="SolaxMODBUS" name="Solax Inverter MODBUS plugin" author="Martin Saidl" version="0.0.2" wikilink="https://github.com/saidlm/Domoticz-Solax-Inverter-plugin">
    <params>
        <param field="Address" label="Inverter IP Address" width="200px" required="true" default="5.8.8.8"/>
        <param field="Port" label="Port" width="40px" required="true" default="502"/>
        <param field="Mode2" label="Inverter ModBus Unit ID" width="20px" required="true" default="1"/>
        <param field="Mode1" label="Update interval (seconds)" width="20px" default="10" />
        <param field="Mode6" label="Debug" width="80px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal" default="true" />
            </options>
        </param>
    </params>
</plugin>
"""


import Domoticz
from pymodbus.client import ModbusTcpClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.constants import Endian
from datetime import datetime
import time


class BasePlugin:

    __UNITS = [
        # id, name, type, subtype, switchtype, options, used
        # Power devices
        [1, "Inverter Power", 248, 1, 0, {}, 1],
        [2, "PV1 Power", 248, 1, 0, {}, 1],
        [3, "PV2 Power", 248, 1, 0, {}, 1],
        [4, "Total PV Power", 248, 1, 0, {}, 1],
        [5, "Battery Power", 248, 1, 0, {}, 1],
        [6, "Grid Power", 248, 1, 0, {}, 1],
        [7, "Local Power Consumption", 248, 1, 0, {}, 1],
        [8, "Off-grid Power", 248, 1, 0, {}, 1],
        # Energy devices
        [10, "Total PV Energy", 243, 29, 0, {}, 1],
        [11, "To Battery Energy", 243, 29, 0, {}, 1],
        [12, "From Battery Energy", 243, 29, 0, {}, 1],
        [13, "To Grid Energy", 243, 29, 0, {}, 1],
        [14, "From Grid Energy", 243, 29, 0, {}, 1],
        [15, "Inverter Energy", 243, 29, 0, {}, 1],
        [16, "Local Energy Consumption", 243, 29, 0, {'EnergyMeterMode':'1' }, 1],
        [17, "Off-Grid Energy", 243, 29, 0, {}, 1],
        # Smart meters
        [20, "Total Grid Energy", 250, 1, 0, {}, 1],
        # Switches and other info
        [30, "Battery Capacity", 243, 6, 0, {}, 1],
        [31, "Inverter Temperature", 80, 5, 0, {}, 1],
        [32, "Battery Temperature", 80, 5, 0, {}, 1],
        [33, "Run Mode", 243, 19, 0, {}, 1],
        [34, "Grid Status", 244, 73, 0, {}, 1],
        # Remote control devices
        [50, "Actual Target Power", 243, 31, 0, {'Custom': '1;W'}, 1],
        [51, "Actual Target Energy", 243, 31, 0, {'Custom': '1;Wh'}, 1],
        [52, "Actual Target SOC", 243, 6, 0, {}, 1],
        [53, "Charge / Discharge Power", 243, 31, 0, {'Custom': '1;W'}, 1],
        [54, "Remote Control Mode", 243, 19, 0, {}, 1],
        [55, "Remote Control Timeout Active", 244, 73, 0, {}, 1],
        [56, "Remote Control Duration Time", 243, 31, 0, {'Custom': '1;s'}, 1],
        [57, "Remote Control Timeout", 243, 31, 0, {'Custom': '1;s'}, 1],
        [60, "Control - Power Target", 242, 1, 0, {'ValueStep':'100', 'ValueMin':'-8000', 'ValueMax':'8000', 'ValueUnit':'W'}, 1], 
        [61, "Control - Energy Target", 242, 1, 0, {'ValueStep':'100', 'ValueMin':'-12000', 'ValueMax':'12000', 'ValueUnit':'Wh'}, 1], 
        [62, "Control - SOC Target", 242, 1, 0, {'ValueStep':'5', 'ValueMin':'10', 'ValueMax':'100', 'ValueUnit':'%'}, 1],
        [63, "Control - Charge / Dischrge Power", 242, 1, 0, {'ValueStep':'100', 'ValueMin':'-8000', 'ValueMax':'8000', 'ValueUnit':'W'}, 1], 
        [64, "Control - Duration Time", 242, 1, 0, {'ValueStep':'1', 'ValueMin':'1', 'ValueMax':'6000', 'ValueUnit':'s'}, 1],
        [65, "Control - Remote Control Timeout", 242, 1, 0, {'ValueStep':'1', 'ValueMin':'1', 'ValueMax':'6000', 'ValueUnit':'s'}, 1],
        [66, "Control - Remote Control Mode", 244, 73, 18, {"LevelActions": "||||", "LevelNames": "Disabled|Power|Energy|SOC|Charge Only", "LevelOffHidden": "false", "SelectorStyle": "1" }, 1],
        [67, "Control - Remote Control Trigger", 244, 73, 9, {}, 1],
    ]

    __RUN_MODES = ("Waiting", "Checking", "Normal", "Fault", "Permanent Fault", "Update", "Off-grid waiting", "Off-grid", "Self Testing", "Idle", "Standby")
    __REMOTECONTROL_MODES = ("Disabled", "Power control", "Energy control", "SOC control", "Push power", "Push power - zero", "self consume", "self consume - charge only")

    __RC_SETTINGS = {
        'PowerTarget': 0,
        'EnergyTarget': 0,
        'SOCTarget': 0,
        'ChargerPower': 0,
        'DurationTime': 0,        
        'TimeOut': 0,        
        'Mode': 0,
        }

    __SETTINGS = {
        'address': '5.8.8.8',
        'port': '502',
        'updateInterval': 10,
        'unitId': 1,
        'maxPower': 8000,
        }

    def __init__(self):
        return

    def onStart(self):
        if Parameters["Mode6"] == "Debug":
            Domoticz.Debugging(1)        
        else:
            Domoticz.Debugging(0)

        Domoticz.Debug("onStart")
        DumpConfigToLog()

        # Parse configuration
        try:
            self.__SETTINGS['address'] = str(Parameters["Address"])
        except:
            self.__SETTINGS['address'] = '5.8.8.8'
        
        try:
            self.__SETTINGS['port'] = int(Parameters["Port"])
        except:
            self.__SETTINGS['port'] = 502

        try:
            if 1 <=int(Parameters["Mode1"]) <= 600:
                self.__SETTINGS['updateInterval'] = int(Parameters["Mode1"])
            else: 
                self.__SETTINGS['updateInterval'] = 10
        except:
            self.__SETTINGS['updateInterval'] = 10

        try:
            if 1 <=int(Parameters["Mode2"]) <= 255:
                self.unit_id = int(Parameters["Mode2"])
            else: 
                self.__SETTINGS['unitId'] = 1
        except:
            self.__SETTINGS['unitId'] = 1

        Domoticz.Heartbeat(int(self.__SETTINGS['updateInterval']))
        Domoticz.Debug("Update interval is set to: {} second(s)".format(str(self.__SETTINGS['updateInterval'])))

        # Create devices
        for unit in self.__UNITS:
            if unit[0] not in Devices:
                Domoticz.Device(
                    Unit=unit[0],
                    Name=unit[1],
                    Type=unit[2],
                    Subtype=unit[3],
                    Switchtype=unit[4],
                    Options=unit[5],
                    Used=unit[6],
                ).Create() 

        # Read Inverter parameters
        Domoticz.Debug("Connecting to: " + self.__SETTINGS['address'] + ":" + str(self.__SETTINGS['port']) + ", unit ID:" + str(self.__SETTINGS['unitId']))

        try:
            client = ModbusTcpClient(host = self.__SETTINGS['address'], port = self.__SETTINGS['port'], unit_id = self.__SETTINGS['unitId'])
            client.connect()
        except:
            Domoticz.Debug("Connection timeout")
            client.close()
            return

        try:
            result = client.read_holding_registers((0x00ba), 1, self.__SETTINGS['unitId'])
        except:
            Domoticz.Debug(result)
            Domoticz.Debug("Unable to read holding registers.")
            client.close()
            return
        
        decoder = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE)
        self.__SETTINGS['maxPower'] = Domoticz.Debug(decoder.decode_16bit_uint())
        
        # Change devices' option
        Devices[60].Update(nValue=0, sValue="0", Options={'ValueUnit':'W', 'ValueStep':'100','ValueMin':'-' + str(self.__SETTINGS['maxPower']), 'ValueMax':str(self.__SETTINGS['maxPower'])})

        self.updateDevices()
    
    def onStop(self):
        Domoticz.Debug("onStop called --> NoOp")

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat")
        
        self.updateDevices()

    def onCommand(self, Unit, Command, Level):
        Domoticz.Debug("onCommand")
        
        if Unit == 60:
            if -8000 <= Level <= 8000:
                self.__RC_SETTINGS['PowerTarget'] = Level
        elif Unit == 61:
            if -12000 <= Level <= 12000:
                self.__RC_SETTINGS['EnergyTarget'] = Level
        elif Unit == 62:
            if 10 <= Level <= 100:
                self.__RC_SETTINGS['SOCTarget'] = Level
        elif Unit == 63:
            if -8000 <= Level <= 8000:
                self.__RC_SETTINGS['ChargerPower'] = Level
        elif Unit == 64:
            if 0 <= Level <= 6000:
                self.__RC_SETTINGS['DurationTime'] = Level
        elif Unit == 65:
            if 0 <= Level <= 6000:
                self.__RC_SETTINGS['TimeOut'] = Level
        elif Unit == 66:
            if Level in [0, 10, 20, 30, 40]: 
                self.__RC_SETTINGS['Mode'] = Level
        elif Unit == 67:
            self.startRemoteControl()
            time.sleep(3)
            self.updateDevices()
            return
        
        self.updateLocalDevices()
    
    def startRemoteControl(self):
        Domoticz.Debug("Starting ModBus Remote Control.")
        
        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.LITTLE)
        modes = (0, 1, 2, 3, 7)
        mode = modes[int(int(self.__RC_SETTINGS['Mode'])/10)]
        
        builder.reset()
        builder.add_16bit_uint(mode)                                            # Remote Control Mode
        builder.add_16bit_uint(1)                                               # TargetSet type = SET
        builder.add_32bit_int(int(self.__RC_SETTINGS['PowerTarget']))           # Target Active Power
        builder.add_32bit_int(0)                                                # Target Reactive Power
        builder.add_16bit_uint(int(self.__RC_SETTINGS['DurationTime']))         # Time of Duration
        builder.add_16bit_uint(int(self.__RC_SETTINGS['SOCTarget']))            # Target SOC
        builder.add_32bit_uint(int(self.__RC_SETTINGS['EnergyTarget']))         # Target Energy
        builder.add_32bit_int(int(self.__RC_SETTINGS['ChargerPower']))          # Charge / Discharge Power
        builder.add_16bit_uint(int(self.__RC_SETTINGS['TimeOut']))              # Remote Control Timeout

        payload = builder.to_registers()

        try:
            self.setMultipleRegisters(0x007c, payload)
            return True
        except:
            Domoticz.Debug("Problem to write Multiple Registers via Modbus")
            return False

    def updateDevices(self):
        inputRegisters = self.getInputRegisters(0, 290, 10)
        if inputRegisters:
            Domoticz.Debug("Updating devices from Input Registers")
            self.updateModBusDevices(inputRegisters)

        Domoticz.Debug("Updating devices from Local array")
        self.updateLocalDevices()

    def updateLocalDevices(self):
        val = self.__RC_SETTINGS['PowerTarget']
        UpdateDevice(60,0,"{}".format(val))
        val = self.__RC_SETTINGS['EnergyTarget']
        UpdateDevice(61,0,"{}".format(val))
        val = self.__RC_SETTINGS['SOCTarget']
        UpdateDevice(62,0,"{}".format(val))
        val = self.__RC_SETTINGS['ChargerPower']
        UpdateDevice(63,0,"{}".format(val))
        val = self.__RC_SETTINGS['DurationTime']
        UpdateDevice(64,0,"{}".format(val))
        val = self.__RC_SETTINGS['TimeOut']
        UpdateDevice(65,0,"{}".format(val))
        val = self.__RC_SETTINGS['Mode']
        UpdateDevice(66,0,"{}".format(val))

    def updateModBusDevices(self, registers):
        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE)

        # Output Power / Energy
        decoder.reset()
        decoder.skip_bytes(0x0002 * 2)
        valP = decoder.decode_16bit_int()
        decoder.reset()
        decoder.skip_bytes(0x0052 * 2)
        valE = decoder.decode_32bit_uint() * 100
        UpdateDevice(1,0,"{}".format(valP))
        UpdateDevice(15,0,"{};{}".format(valP, valE))
        
        # PV1 Power
        decoder.reset()
        decoder.skip_bytes(0x000a * 2)
        valP1 = decoder.decode_16bit_uint()
        UpdateDevice(2,0,"{}".format(valP1))
        
        # PV2 Power
        decoder.reset()
        decoder.skip_bytes(0x000b * 2)
        valP2 = decoder.decode_16bit_uint()
        UpdateDevice(3,0,"{}".format(valP2))

        # Total PV Power / Energy
        valP = valP1 + valP2
        decoder.reset()
        decoder.skip_bytes(0x0094 * 2)
        valE = decoder.decode_32bit_uint() * 100
        UpdateDevice(4,0,"{}".format(valP))
        UpdateDevice(10,0,"{};{}".format(valP, valE))

        # Battery Power / Energy
        decoder.reset()
        decoder.skip_bytes(0x0016 * 2)
        valP = decoder.decode_16bit_int()
        decoder.reset()
        decoder.skip_bytes(0x0021 * 2)
        valE1 = decoder.decode_32bit_uint() * 100
        decoder.reset()
        decoder.skip_bytes(0x001d * 2)
        valE2 = decoder.decode_32bit_uint() * 100
        UpdateDevice(5,0,"{}".format(valP))
        if valP >= 0:
            valP1 = valP
            valP2 = 0
        elif valP < 0:
            valP1 = 0
            valP2 = abs(valP)
        UpdateDevice(11,0,"{};{}".format(valP1, valE1))
        UpdateDevice(12,0,"{};{}".format(valP2, valE2))

        # Grid Power / Energy
        decoder.reset()
        decoder.skip_bytes(0x0046 * 2)
        valP = decoder.decode_32bit_int()
        valE1 = decoder.decode_32bit_uint() * 10
        valE2 = decoder.decode_32bit_uint() * 10
        UpdateDevice(6,0,"{}".format(valP))
        if valP >= 0:
            valP1 = valP
            valP2 = 0
        elif valP < 0:
            valP1 = 0
            valP2 = abs(valP)
        UpdateDevice(13,0,"{};{}".format(valP1, valE1))
        UpdateDevice(14,0,"{};{}".format(valP2, valE2))
        UpdateDevice(20,0,"{};{};{};{};{};{}".format(valE2, 0, valE1, 0, valP2, valP1))

        # Local Power / Energy Consumption
        # Energy is calculated by Domoticz due to lack of information from inverter
        decoder.reset()
        decoder.skip_bytes(0x0046 * 2)
        valP1 = decoder.decode_32bit_int()
        decoder.reset()
        decoder.skip_bytes(0x0002 * 2)
        valP2 = decoder.decode_16bit_int()
        valP = valP2 - valP1
        if valP < 0:
            valP = 0
        UpdateDevice(7,0,"{}".format(valP))
        UpdateDevice(16,0,"{};{}".format(valP, 0))

        # Off-Grid Power / Energy
        decoder.reset()
        decoder.skip_bytes(0x004e * 2)
        valP = decoder.decode_16bit_int()
        decoder.reset()
        decoder.skip_bytes(0x008e * 2)
        valE = decoder.decode_32bit_int() * 100
        UpdateDevice(8,0,"{}".format(valP))
        UpdateDevice(17,0,"{};{}".format(valP, valE))
        
        # Battery Capacity
        decoder.reset()
        decoder.skip_bytes(0x001c * 2)
        val = decoder.decode_16bit_uint()
        UpdateDevice(30,0,"{}".format(val))

        # Inverter Temperature
        decoder.reset()
        decoder.skip_bytes(0x0008 * 2)
        val = decoder.decode_16bit_uint()
        UpdateDevice(31,0,"{}".format(val))

        # Battery Temperature
        decoder.reset()
        decoder.skip_bytes(0x0018 * 2)
        val = decoder.decode_16bit_uint()
        UpdateDevice(32,0,"{}".format(val))

        # Run Mode
        decoder.reset()
        decoder.skip_bytes(0x0009 * 2)
        val = decoder.decode_16bit_uint()
        if 0 <= val <= 10:
            UpdateDevice(33,0,"{}".format(self.__RUN_MODES[val]))
        else:
            UpdateDevice(33,0,"Unknown mode")
        
        # Grid status
        decoder.reset()
        decoder.skip_bytes(0x001a * 2)
        val = decoder.decode_16bit_uint()
        if val > 0:
            UpdateDevice(34,0,"Off")
        else:
            UpdateDevice(34,1,"On")

        # Remote control - Target Power
        decoder.reset()
        decoder.skip_bytes(0x0102 * 2)
        valP = decoder.decode_32bit_int()
        UpdateDevice(50,0,"{}".format(valP))

        # Remote control - Target Energy
        decoder.reset()
        decoder.skip_bytes(0x0112 * 2)
        valE = decoder.decode_32bit_int()
        UpdateDevice(51,0,"{}".format(valE))

        # Remote control - Target SOC
        decoder.reset()
        decoder.skip_bytes(0x011b * 2)
        val = decoder.decode_16bit_uint()
        UpdateDevice(52,0,"{}".format(val))
        
        # Remote control - Charge / Discharge Power
        decoder.reset()
        decoder.skip_bytes(0x0114 * 2)
        valP = decoder.decode_32bit_int()
        UpdateDevice(53,0,"{}".format(valP))

        # Remote Control Mode
        decoder.reset()
        decoder.skip_bytes(0x0100 * 2)
        val = decoder.decode_16bit_uint()
        if 0 <= val <= 10:
            UpdateDevice(54,0,"{}".format(self.__REMOTECONTROL_MODES[val]))
        else:
            UpdateDevice(54,0,"Unknown mode")
        
        # Remote Control Status
        decoder.reset()
        decoder.skip_bytes(0x0101 * 2)
        val = decoder.decode_16bit_uint()
        if val > 0:
            UpdateDevice(55,1,"On")
        else:
            UpdateDevice(55,0,"Off")

        # Remote control - Duration Time
        decoder.reset()
        decoder.skip_bytes(0x011a * 2)
        val = decoder.decode_16bit_uint()
        UpdateDevice(56,0,"{}".format(val))

        # Remote control - TimeOut
        decoder.reset()
        decoder.skip_bytes(0x011e * 2)
        val = decoder.decode_16bit_uint()
        UpdateDevice(57,0,"{}".format(val))

    def getInputRegisters(self, start=0, length=100, step=10):
        Domoticz.Debug("Connecting to: " + self.__SETTINGS['address'] + ":" + str(self.__SETTINGS['port']) + ", unit ID:" + str(self.__SETTINGS['unitId']))
        (cycles, res) = divmod(length, step)
        
        try:
            client = ModbusTcpClient(host = self.__SETTINGS['address'], port = self.__SETTINGS['port'], unit_id = self.__SETTINGS['unitId'])
            client.connect()
        except:
            Domoticz.Debug("Connection timeout.")
            client.close()
            return False

        cycle = 0
        step2 = step
        registers = []

        while cycle <= cycles:
            if cycle == cycles:
                if res > 0:
                    step2 = res
                else:
                    break
            try:
                result = client.read_input_registers((start + cycle * step), step2, self.__SETTINGS['unitId'])
                registers = registers + result.registers
            except:
                Domoticz.Debug(result) 
                Domoticz.Debug("Unable to read input registers.")
                client.close()
                return False
            cycle = cycle + 1

        client.close()
        return(registers)
    
    def setMultipleRegisters(self, start, payload):
        Domoticz.Debug("Connecting to: " + self.__SETTINGS['address'] + ":" + str(self.__SETTINGS['port']) + ", unit ID:" + str(self.__SETTINGS['unitId']))
        
        try:
            client = ModbusTcpClient(host = self.__SETTINGS['address'], port = self.__SETTINGS['port'], unit_id = self.__SETTINGS['unitId'])
            client.connect()
        except:
            Domoticz.Debug("Connection timeout.")
            client.close()
            return False
        
        try:
            result = client.write_registers(start, payload, self.__SETTINGS['unitId'])
        except:
            Domoticz.Debug(result) 
            Domoticz.Debug("Unable to write multiple registers.")
            client.close()
            return False

        client.close()
        return(True)

        
global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def onCommand(Unit, Command, Level, Color):
    global _plugin
    _plugin.onCommand(Unit, Command, Level)


################################################################################
# Generic helper functions
################################################################################

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug("'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: {}".format(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           {} - {}".format(x, Devices[x]))
        Domoticz.Debug("Device ID:        {}".format(Devices[x].ID))
        Domoticz.Debug("Device Name:     '{}'".format(Devices[x].Name))
        Domoticz.Debug("Device nValue:    {}".format(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '{}'".format(Devices[x].sValue))
        Domoticz.Debug("Device LastLevel: {}".format(Devices[x].LastLevel))

def UpdateDevice(Unit, nValue, sValue, TimedOut=0, MaxUpdateInterval=10, AlwaysUpdate=False):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it
    if Unit in Devices:
        # try/catch due to http://bugs.python.org/issue27400
        try:
            timeDiff = datetime.now() - datetime.strptime(Devices[Unit].LastUpdate,'%Y-%m-%d %H:%M:%S')
        except TypeError:
            timeDiff = datetime.now() - datetime(*(time.strptime(Devices[Unit].LastUpdate,'%Y-%m-%d %H:%M:%S')[0:6]))
        
        if (
            Devices[Unit].nValue != nValue
            or Devices[Unit].sValue != sValue
            or Devices[Unit].TimedOut != TimedOut
            or (timeDiff.seconds/60)%60 > MaxUpdateInterval
            or AlwaysUpdate
        ):
            Devices[Unit].Update(nValue=nValue, sValue=str(sValue), TimedOut=TimedOut)
            Domoticz.Debug(
                "Update {}: {} - {} - {}".format(
                    Devices[Unit].Name, nValue, sValue, TimedOut
                )
            )
