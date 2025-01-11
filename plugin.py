#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Name: Solax Inverter MODBUS plugin
# Version: 0.1.1
# Author: Martin Saidl
#

"""
<plugin key="SolaxMODBUS" name="Solax Inverter MODBUS plugin" author="Martin Saidl" version="0.1.1" wikilink="https://github.com/saidlm/Domoticz-Solax-Inverter-plugin">
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

    # Global section
    # ==============

    __SETTINGS = {
        'address': '5.8.8.8',
        'port': '502',
        'updateInterval': 10,
        'unitId': 1,
        'maxPower': 8000,
        'evCharger': False,
        }


    commInProgress = False
    lastEVEnergy = 0

    # Inverter section
    # ================

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
        [21, "Total Grid Energy (tariff)", 250, 1, 0, {}, 1],
        # Switches and other info
        [30, "Battery Capacity", 243, 6, 0, {}, 1],
        [31, "Inverter Temperature", 80, 5, 0, {}, 1],
        [32, "Battery Temperature", 80, 5, 0, {}, 1],
        [33, "Run Mode", 243, 19, 0, {}, 1],
        [34, "Grid Status", 244, 73, 0, {}, 1],
        [39, "Tariff", 244, 73, 0, {}, 1],
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

    # EV Charger section
    # ==================

    __EV_UNITS = [
        # id, name, type, subtype, switchtype, options, used
        # Power devices
        [100, "EV Charger Power", 248, 1, 0, {}, 1],
        # Energy devices
        [110, "EV Charger Energy", 243, 29, 0, {}, 1],
        # Switches 
        [120, "EV Charger  State", 243, 19, 0, {}, 1],
        [121, "EV Charger run Mode", 244, 73, 18, {"LevelActions": "|||", "LevelNames": "Stop|Fast|Eco|Green", "LevelOffHidden": "false", "SelectorStyle": "0" }, 1],
        # Temperature, Current etc
        [130, "EV Charger Temperature", 80, 5, 0, {}, 1],
        #[131, "EV Charger Max Current", 242, 1, 0, {'ValueStep':'0.1', 'ValueMin':'0', 'ValueMax':'32', 'ValueUnit':'A'}, 1],

    ]

    __EV_STATE = ("Avaiable", "Preparing", "Charging", "Finishing", "Faulted", "Unavaiable", "Reserved", "Suspended EV", "Suspended EVSE", "Update", "Card Activation")


    # Plugin Code
    # ===========
    
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
                self.__SETTINGS['unitId'] = int(Parameters["Mode2"])
            else: 
                self.__SETTINGS['unitId'] = 1
        except:
            self.__SETTINGS['unitId'] = 1

        # Read Inverter parameters
        Domoticz.Debug("Reading configuration information from inverter.")

        self.commInProgress = True

        while True:
            holdingRegisters = self.getHoldingRegisters(0, 374, 50)
            if holdingRegisters:
                break
            Domoticz.Debug("There is issue to read Inverter configuration. Will ty it again after 10s.")
            time.sleep(10)

        decoder = BinaryPayloadDecoder.fromRegisters(holdingRegisters, byteorder=Endian.BIG, wordorder=Endian.LITTLE)
        self.commInProgress = False
        
        # Inverter type - max power
        decoder.reset()
        decoder.skip_bytes(0x00ba * 2)
        self.__SETTINGS['maxPower'] = decoder.decode_16bit_uint()

        # EV Charger check
        decoder.reset()
        decoder.skip_bytes(0x013e * 2)
        val = decoder.decode_16bit_uint()
        
        Domoticz.Debug("External devices ModBus info: {}.".format(val))

        if val in [1, 4, 6]:
            self.__SETTINGS['evCharger'] = True
            Domoticz.Debug("EV Charger is connected.")
        else:
            self.__SETTINGS['evCharger'] = False
            Domoticz.Debug("EV Charger is NOT connected.")

        # Create Inverter devices
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
        
        # Create EV Charger devices
        if self.__SETTINGS['evCharger']:
            for unit in self.__EV_UNITS:
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

        # Change devices' options
        Domoticz.Debug("Maximum inverter power is set to: {} Watt(s)".format(self.__SETTINGS['maxPower']))
        Devices[60].Update(nValue=0, sValue="0", Options={'ValueStep':'100','ValueMin':'-' + str(self.__SETTINGS['maxPower']), 'ValueMax':str(self.__SETTINGS['maxPower']), 'ValueUnit':'W'})
        Devices[63].Update(nValue=0, sValue="0", Options={'ValueStep':'100','ValueMin':'-' + str(self.__SETTINGS['maxPower']), 'ValueMax':str(self.__SETTINGS['maxPower']), 'ValueUnit':'W'})

        # Heartbeat interval setup
        Domoticz.Debug("Update interval is set to: {} second(s)".format(self.__SETTINGS['updateInterval']))
        Domoticz.Heartbeat(int(self.__SETTINGS['updateInterval']))

        self.updateDevices()
    
    def onStop(self):
        Domoticz.Debug("onStop called --> NoOp")

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat")
        
        self.updateDevices()

    def onCommand(self, Unit, Command, Level):
        Domoticz.Debug("onCommand")

        Command = Command.strip()
        action, sep, params = Command.partition(' ')
        action = action.capitalize()       

        # Remote Control Targer Power
        if Unit == 60:
            if -(self.__SETTINGS['maxPower']) <= Level <= self.__SETTINGS['maxPower']:
                self.__RC_SETTINGS['PowerTarget'] = Level
        # Remote Control Target Energy
        elif Unit == 61:
            if -12000 <= Level <= 12000:
                self.__RC_SETTINGS['EnergyTarget'] = Level
        # Remote Control Target SoC
        elif Unit == 62:
            if 10 <= Level <= 100:
                self.__RC_SETTINGS['SOCTarget'] = Level
        # Remote Control Charge Power
        elif Unit == 63:
            if -(self.__SETTINGS['maxPower']) <= Level <= self.__SETTINGS['maxPower']:
                self.__RC_SETTINGS['ChargerPower'] = Level
        # Remote Control Duration Time
        elif Unit == 64:
            if 0 <= Level <= 6000:
                self.__RC_SETTINGS['DurationTime'] = Level
        # Remote Control TimoOut
        elif Unit == 65:    
            if 0 <= Level <= 6000:
                self.__RC_SETTINGS['TimeOut'] = Level
        # Remote Control Mode
        elif Unit == 66:
            if Level in [0, 10, 20, 30, 40]: 
                self.__RC_SETTINGS['Mode'] = Level
        # Remote Control Trigger
        elif Unit == 67:
            self.startRemoteControl()
            time.sleep(3)
            self.updateDevices()
            return
        # EV Charger Run Mode
        elif Unit == 121:
            if Level in [0, 10, 20, 30]: 
                val = Level/10
                self.updateInverter(0x100d, val)
                time.sleep(2)
                self.updateDevices()
            return
        # Tariff switch
        elif Unit == 39:
            if action == 'On':
                UpdateDevice(39,1,"On")
            else:
                UpdateDevice(39,0,"Off")
        
        self.updateLocalDevices()
    
    def updateInverter(self, register, value):
        while self.commInProgress:
            time.sleep(1)

        self.commInProgress = True

        Domoticz.Debug("Updating Inverter registers.")
        
        payload = int(value)
        result = self.setRegister(register, payload)
        if result:
            Domoticz.Debug("Done.")
        else:
            Domoticz.Debug("Failed!")

        self.commInProgress = False

    def startRemoteControl(self):
        while self.commInProgress:
            time.sleep(1)

        self.commInProgress = True

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
        result = self.setMultipleRegisters(0x007c, payload)
        if result:
            Domoticz.Debug("Done.")
        else:
            Domoticz.Debug("Failed!")
        
        self.commInProgress = False

    def updateDevices(self):
        while self.commInProgress:
            time.sleep(1)

        self.commInProgress = True

        # Inverter data
        Domoticz.Debug("Updating devices from Inverter Input Registers.")
        inputRegisters = self.getInputRegisters(0, 290, 50)
        if inputRegisters:
            Domoticz.Debug("Done.")
            self.updateInverterModBusDevices(inputRegisters)
        else:
            Domoticz.Debug("Failed!")
        
        # EV Charger data
        Domoticz.Debug("Updating devices from EV Charger Input Registers.")
        if self.__SETTINGS['evCharger']:
            time.sleep(2)
            inputRegisters = self.getInputRegisters(0x1000, 30, 30)
            if inputRegisters:
                Domoticz.Debug("Done.")
                self.updateEVChargerModBusDevicesInput(inputRegisters)
            else:
                Domoticz.Debug("Failed!")

        Domoticz.Debug("Updating devices from EV Charger Holding Registers.")
        if self.__SETTINGS['evCharger']:
            time.sleep(5)
            holdingRegisters = self.getHoldingRegisters(0x1000, 50, 50)
            if holdingRegisters:
                Domoticz.Debug("Done.")
                self.updateEVChargerModBusDevicesHolding(holdingRegisters)
            else:
                Domoticz.Debug("Failed!")

        Domoticz.Debug("Updating devices from Local array.")
        self.updateLocalDevices()

        self.commInProgress = False

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

    # EV Charger devices
    def updateEVChargerModBusDevicesInput(self, registers):
        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE)
        
        # EV Charger Power / Energy
        decoder.reset()
        decoder.skip_bytes(0x000b * 2)
        valP = decoder.decode_16bit_uint()
        decoder.reset()
        decoder.skip_bytes(0x000f * 2)
        newEVEnergy = decoder.decode_32bit_uint() * 100

        if newEVEnergy < self.lastEVEnergy:
            self.lastEVEnergy = 0
        
        try:
            [oldP, oldE] = Devices[110].sValue.split(';')
        except:
            [oldP, oldE] = [0, 0]

        valE = float(oldE) + newEVEnergy - self.lastEVEnergy
        self.lastEVEnergy = newEVEnergy
        UpdateDevice(100,0,"{}".format(valP))
        UpdateDevice(110,0,"{};{}".format(valP, valE))

        # EV Charger state
        decoder.reset()
        decoder.skip_bytes(0x001d * 2)
        val = decoder.decode_16bit_uint()
        if 0 <= val <= 10:
            UpdateDevice(120,0,"{}".format(self.__EV_STATE[val]))
        else:
            UpdateDevice(120,0,"Unknown state")

        # EV Charger Temperature
        decoder.reset()
        decoder.skip_bytes(0x001c * 2)
        val = decoder.decode_16bit_int()
        UpdateDevice(130,0,"{}".format(val))
    
    def updateEVChargerModBusDevicesHolding(self, registers):
        decoder = BinaryPayloadDecoder.fromRegisters(registers, byteorder=Endian.BIG, wordorder=Endian.LITTLE)
        
        # EV Charger Run Mode
        decoder.reset()
        decoder.skip_bytes(0x000d * 2)
        val = decoder.decode_16bit_uint()
        UpdateDevice(121,0,"{}".format(val * 10))
    
        # EV Charger Max Current
        #decoder.reset()
        #decoder.skip_bytes(0x0028 * 2)
        #val = decoder.decode_16bit_uint()
        #UpdateDevice(131,0,"{}".format(val / 100))
    
    # Inverter devices
    def updateInverterModBusDevices(self, registers):
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
        
        try:
            [oldP1, oldE1] = Devices[13].sValue.split(';')
        except:
            [oldP1, oldE1] = [0, 0]

        try:
            [oldP2, oldE2] = Devices[14].sValue.split(';')
        except:
            [oldP2, oldE2] = [0, 0]

        try:
            [oldE2T1, oldE2T2, oldE1T1, oldE1T2, oldP1, oldP2] = Devices[21].sValue.split(';')
        except:
            [oldE2T1, oldE2T2, oldE1T1, oldE1T2, oldP1, oldP2] = [0, 0, 0, 0, 0, 0]

        UpdateDevice(13,0,"{};{}".format(valP1, valE1))
        UpdateDevice(14,0,"{};{}".format(valP2, valE2))
        UpdateDevice(20,0,"{};{};{};{};{};{}".format(valE2, 0, valE1, 0, valP2, valP1))

        if Devices[39].sValue == 'On':
            valE1 = int(oldE1T2) + valE1 - int(oldE1) 
            valE2 = int(oldE2T2) + valE2 - int(oldE2) 
            UpdateDevice(21,0,"{};{};{};{};{};{}".format(oldE2T1, valE2, oldE1T1 , valE1, valP2, valP1))
        else:
            valE1 = int(oldE1T1) + valE1 - int(oldE1) 
            valE2 = int(oldE2T1) + valE2 - int(oldE2) 
            UpdateDevice(21,0,"{};{};{};{};{};{}".format(valE2, oldE2T2, valE1, oldE1T2, valP2, valP1))


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
        Domoticz.Debug("Connecting to: {}:{}, unitID: {}".format(self.__SETTINGS['address'], self.__SETTINGS['port'], self.__SETTINGS['unitId']))
        (cycles, res) = divmod(length, step)
        
        try:
            client = ModbusTcpClient(host=self.__SETTINGS['address'], port=self.__SETTINGS['port'], timeout=30, retries=5)
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
                result = client.read_input_registers(address=(start + cycle * step), count=step2, slave=self.__SETTINGS['unitId'])
                registers = registers + result.registers
            except:
                #Domoticz.Debug(result) 
                Domoticz.Debug("Unable to read input registers.")
                client.close()
                return False
            cycle = cycle + 1

        client.close()
        return(registers)

    def getHoldingRegisters(self, start=0, length=100, step=10):
        Domoticz.Debug("Connecting to: {}:{}, unitID: {}".format(self.__SETTINGS['address'], self.__SETTINGS['port'], self.__SETTINGS['unitId']))
        (cycles, res) = divmod(length, step)
        
        try:
            client = ModbusTcpClient(host=self.__SETTINGS['address'], port=self.__SETTINGS['port'], timeout=30, retries=5)
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
                result = client.read_holding_registers(address=(start + cycle * step), count=step2, slave=self.__SETTINGS['unitId'])
                registers = registers + result.registers
            except:
                #Domoticz.Debug(result) 
                Domoticz.Debug("Unable to read holding registers.")
                client.close()
                return False
            cycle = cycle + 1

        client.close()
        return(registers)
    
    def setRegister(self, start, payload):
        Domoticz.Debug("Connecting to: {}:{}, unitID: {}".format(self.__SETTINGS['address'], self.__SETTINGS['port'], self.__SETTINGS['unitId']))
        
        try:
            client = ModbusTcpClient(host=self.__SETTINGS['address'], port=self.__SETTINGS['port'], timeout=30, retries=5)
            client.connect()
        except:
            Domoticz.Debug("Connection timeout.")
            client.close()
            return False
        
        try:
            result = client.write_register(address=start, value=payload, slave=self.__SETTINGS['unitId'])
        except:
            #Domoticz.Debug(result) 
            Domoticz.Debug("Unable to write holding register.")
            client.close()
            return False

        client.close()
        return(True)
    
    def setMultipleRegisters(self, start, payload):
        Domoticz.Debug("Connecting to: {}:{}, unitID: {}".format(self.__SETTINGS['address'], self.__SETTINGS['port'], self.__SETTINGS['unitId']))
        
        try:
            client = ModbusTcpClient(host=self.__SETTINGS['address'], port=self.__SETTINGS['port'], timeout=30, retries=5)
            client.connect()
        except:
            Domoticz.Debug("Connection timeout.")
            client.close()
            return False
        
        try:
            result = client.write_registers(address=start, values=payload, slave=self.__SETTINGS['unitId'])
        except:
            #Domoticz.Debug(result) 
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
