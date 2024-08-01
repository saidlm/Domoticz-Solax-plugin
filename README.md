# Domoticz-Solax-plugin
It is developed to be able to monitor and control Solax inverter from Domoticz software via ModBUS over TCP/IP. Current version is read only. It means that there is no possibility to change configuration or changes behavior of the inverter. 
All the information which are collected by default version are visible on pictures below.

### Utility tab

![Utility tab](images/Domoticz-Solax_1.png)

### Temperature tab

![Temperature tab](images/Domoticz-Solax_2.png)

### Switches tab

![Switches tab](images/Domoticz-Solax_3.png)

## Prerequsities
* Running Domoticz software
* The installation of additional python3 library – pymodbus is necessary.
```
sudo pip3 install -U pymodbus
```
The current version of the plugin was tested with Domoticz version 2024.4, python 3.11.2, libpython 3.11 and pymodbus 3.6.8

## Installation
* Place the folder inside Domoticz plugin folder e.g. :
```
/home/domoticz/plugin/Solax
```
* Copy plugin.py from repository folder to the folder created in previous step.
* Restart Domoticz.
```
sudo service domoticz.sh restart
```
or
```
docker restart domoticz
```
The exact command depends on your instalation.

## Configuration
![Hardware configuration](images/Domoticz-Solax_4.png)
