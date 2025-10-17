# Reticulum-Network-Over-Icom-D-star-Transceivers
Allows using the Icom D-star transceiver as a data transmission device for organizing off-grid RNS networks.
# Reticulum Network Over Icom D-star Transceivers

This custom RNS (reticulum.network) interface script enables transmission and reception of LXMF packets (MTU 500 bytes) through GMSK modems in Icom transceivers compatible with the D-star standard. This allows using the transceiver as a data transmission device for organizing off-grid RNS networks.

## Supported Models
- ID-50
- ID-52
- IC-705
- IC-905
- IC-7100
- ID-5100
- IC-9700

## Configuration Requirements
1. Read your transceiver's manual for serial port connection setup
2. Enable **Fast Data** mode (3400 bit/s)
3. Configure serial port (usually Port B) for **DV Data** transmission
4. Set port speed (default 115200)
5. Disable GPS data transmission (**GPS TX**)
6. Stop all D-star message transmissions (**TX Message** / **My Call Sign**)

## Example Setup for ID-52
1. Connect transceiver to computer and identify serial port name  
   For MacOS/Linux: `ls /dev/cu.*`
2. **Menu → Set → My Station → My Call Sign → OFF**
3. **Menu → Set → My Station → TX Message → OFF**
4. **Menu → GPS → GPS TX Mode → OFF**
5. **Menu → Set → Function → USB Connect → Serialport**
6. **Menu → Set → Function → USB Serialport Function → DV Data**
7. Select **DV** modulation type on main screen

## Installation
1. Place ReticulumOverDstar.py in the interfaces folder within .reticulium root directory
2. Launch applications (e.g., Mesh Chat)
3. Verify interface activity and data transmission
4. Transceiver will automatically engage transmission

## Reticulum Configuration
Edit the `config` file in `.reticulium` root directory:

```ini
[[Reticulum over D-star]]
    type = ReticulumOverDstar
    enabled = yes
    mode = access_point  # full, gateway, access_point, roaming, boundary
    port = /dev/cu.usbserial-14430  # your port name
    speed = 9600  # serial port speed, usually 115200
    databits = 8
    parity = none
    stopbits = 1
    name = Reticulum over D-star
