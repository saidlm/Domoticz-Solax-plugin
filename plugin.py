#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Name: Solax Inverter MODBUS plugin
# Version: 0.0.1
# Author: Martin Saidl
#

"""
<plugin key="SolaxMODBUS" name="Solax Inverter MODBUS plugin" author="Martin Saidl" version="0.0.1" wikilink="https://github.com/saidlm/Domoticz-Solax-Inverter-plugin">
    <params>
        <param field="Address" label="Inverter IP Address" width="200px" required="true" default="5.8.8.8"/>
        <param field="Port" label="Port" width="40px" required="true" default="502"/>
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
from pymodbus.constants import Endian
from datetime import datetime
import time


class BasePlugin:

    __UNITS = [
        # id, name, type, subtype, options, used
        [1, "Inverter Power", 248, 1, {}, 1],
        [2, "PV1 Power", 248, 1, {}, 1],
        [3, "PV2 Power", 248, 1, {}, 1],
        [4, "Total PV Power", 248, 1, {}, 1],
        [5, "Battery Power", 248, 1, {}, 1],
        [6, "Grid Power", 248, 1, {}, 1],
        [7, "Local Power Consumption", 248, 1, {}, 1],
        [8, "Off-grid Power", 248, 1, {}, 1],
        [10, "Total PV Energy", 243, 29, {}, 1],
        [11, "To Battery Energy", 243, 29, {}, 1],
        [12, "From Battery Energy", 243, 29, {}, 1],
        [13, "To Grid Energy", 243, 29, {}, 1],
        [14, "From Grid Energy", 243, 29, {}, 1],
        [15, "Inverter Energy", 243, 29, {}, 1],
        [16, "Local Energy Consumption", 243, 29, {'EnergyMeterMode':'1' }, 1],
        [17, "Off-Grid Energy", 243, 29, {}, 1],
        [20, "Total Grid Energy", 250, 1, {}, 1],
        [30, "Battery Capacity", 243, 6, {}, 1],
        [31, "Inverter Temperature", 80, 5, {}, 1],
        [32, "Battery Temperature", 80, 5, {}, 1],
        [33, "Run Mode", 243, 19, {}, 1],
        [34, "Grid Status", 244, 73, {}, 1],
    ]

    __RUN_MODES = ("Waiting", "Checking", "Normal", "Fault", "Permanent Fault", "Update", "Off-grid waiting", "Off-grid", "Self Testing", "Idle", "Standby")
 

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
            if 1 <=int(Parameters["Mode1"]) <= 600:
                self.updateInterval = int(Parameters["Mode1"])
            else: 
                self.updateInterval = 10
        except:
            self.updateInterval = 10

        Domoticz.Heartbeat(int(self.updateInterval))
        Domoticz.Debug("Update interval is set to: {} second(s)".format(str(self.updateInterval)))

        # Create devices
        for unit in self.__UNITS:
            if unit[0] not in Devices:
                Domoticz.Device(
                    Unit=unit[0],
                    Name=unit[1],
                    Type=unit[2],
                    Subtype=unit[3],
                    Options=unit[4],
                    Used=unit[5],
                ).Create() 

    def onStop(self):
        Domoticz.Log("onStop called --> NoOp")

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat")

        attempCount = 0

        while True:
            attempCount = attempCount + 1
            if attempCount > 3:
                Domoticz.Debug("Connection has not been established.")
                return
            inputRegisters = self.getInputRegisters(0, 290, 10)
            if inputRegisters:
                break
        
        Domoticz.Debug("Successful attempt number: " + str(attempCount))

        self.updateDevices(inputRegisters)
    

    def updateDevices(self, registers):
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
        UpdateDevice(5,0,"{}".format(valP))
        if valP >= 0:
            decoder.reset()
            decoder.skip_bytes(0x0021 * 2)
            valE = decoder.decode_32bit_uint() * 100
            UpdateDevice(11,0,"{};{}".format(valP, valE))
        if valP <= 0:
            decoder.reset()
            decoder.skip_bytes(0x001d * 2)
            valE = decoder.decode_32bit_uint() * 100
            UpdateDevice(12,0,"{};{}".format(abs(valP), valE))

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
        decoder.skip_bytes(0x001a * 2)
        val = decoder.decode_16bit_uint()
        #if val > 1:
        decoder.reset()
        decoder.skip_bytes(0x004e * 2)
        valP = decoder.decode_16bit_int()
        #else:
        #    valP = 0
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
        
        # Grid Status
        decoder.reset()
        decoder.skip_bytes(0x001a * 2)
        val = decoder.decode_16bit_uint()
        if val > 1:
            UpdateDevice(34,0,"Off")
        else:
            UpdateDevice(34,1,"On")

    def getInputRegisters(self, start=0, length=100, step=10):
        Domoticz.Debug("Connecting to: " + str(Parameters["Address"]) + ":" + str(Parameters["Port"]))
        (cycles, res) = divmod(length, step)
        
        try:
            client = ModbusTcpClient(str(Parameters["Address"]), int(Parameters["Port"]))
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
            Domoticz.Debug("Start: " + str(start) + ", cycle: " + str(cycle) + "step: " + str(step) + ", step2: " + str(step2)) 
            try:
                result = client.read_input_registers((start + cycle * step), step2)
                registers = registers + result.registers
            except:
                Domoticz.Debug(result) 
                Domoticz.Debug("Unable to read input registers.")
                client.close()
                return False
            cycle = cycle + 1

        client.close()
        return(registers)

        
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
