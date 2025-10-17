# This interface enables Reticulum communication over D-star
# compatible transceivers using Base64 encoding for ASCII-only
# data transmission. Designed for Icom D-star transceivers
# like IC-705 and ID-52.

from time import sleep
import sys
import threading
import time
import base64

# This HDLC helper class is used by the interface
# to delimit and packetize data over the physical
# medium - in this case a serial connection.
class HDLC():
    # This example interface packetizes data using
    # simplified HDLC framing, similar to PPP
    FLAG     = 0x7E
    ESC      = 0x7D
    ESC_MASK = 0x20

    @staticmethod
    def escape(data):
        data = data.replace(bytes([HDLC.ESC]), bytes([HDLC.ESC, HDLC.ESC^HDLC.ESC_MASK]))
        data = data.replace(bytes([HDLC.FLAG]), bytes([HDLC.ESC, HDLC.FLAG^HDLC.ESC_MASK]))
        return data

# Reticulum over D-star interface class
class ReticulumOverDstar(Interface):
    # All interface classes must define a default
    # IFAC size, used in IFAC setup when the user
    # has not specified a custom IFAC size.
    DEFAULT_IFAC_SIZE = 8

    # The following properties are local to this
    # particular interface implementation.
    owner    = None
    port     = None
    speed    = None
    databits = None
    parity   = None
    stopbits = None
    serial   = None

    def __init__(self, owner, configuration):
        import importlib
        if importlib.util.find_spec('serial') != None:
            import serial
        else:
            RNS.log("Using this interface requires a serial communication module to be installed.", RNS.LOG_CRITICAL)
            RNS.log("You can install one with the command: python3 -m pip install pyserial", RNS.LOG_CRITICAL)
            RNS.panic()

        # Initialize the super-class
        super().__init__()

        # Parse configuration
        ifconf    = Interface.get_config_obj(configuration)
        name      = ifconf["name"]
        self.name = name

        # Read configuration parameters
        port      = ifconf["port"] if "port" in ifconf else None
        speed     = int(ifconf["speed"]) if "speed" in ifconf else 9600
        databits  = int(ifconf["databits"]) if "databits" in ifconf else 8
        parity    = ifconf["parity"] if "parity" in ifconf else "N"
        stopbits  = int(ifconf["stopbits"]) if "stopbits" in ifconf else 1

        if port == None:
            raise ValueError(f"No port specified for {self}")

        # For Base64 encoding: 500 bytes becomes ~667 bytes after encoding
        self.HW_MTU = 700

        self.online   = False
        self.bitrate  = speed
        
        # Configure internal properties
        self.pyserial = serial
        self.serial   = None
        self.owner    = owner
        self.port     = port
        self.speed    = speed
        self.databits = databits
        self.parity   = serial.PARITY_NONE
        self.stopbits = stopbits
        self.timeout  = 100

        if parity.lower() == "e" or parity.lower() == "even":
            self.parity = serial.PARITY_EVEN

        if parity.lower() == "o" or parity.lower() == "odd":
            self.parity = serial.PARITY_ODD

        # Open serial port
        try:
            self.open_port()
        except Exception as e:
            RNS.log("Could not open serial port for interface "+str(self), RNS.LOG_ERROR)
            raise e

        if self.serial.is_open:
            self.configure_device()
        else:
            raise IOError("Could not open serial port")

    def open_port(self):
        RNS.log("Opening serial port "+self.port+" for D-star communication...", RNS.LOG_VERBOSE)
        self.serial = self.pyserial.Serial(
            port = self.port,
            baudrate = self.speed,
            bytesize = self.databits,
            parity = self.parity,
            stopbits = self.stopbits,
            xonxoff = False,
            rtscts = False,
            timeout = 0,
            inter_byte_timeout = None,
            write_timeout = None,
            dsrdtr = False,
        )

    def configure_device(self):
        sleep(0.5)
        thread = threading.Thread(target=self.read_loop)
        thread.daemon = True
        thread.start()
        self.online = True
        RNS.log("D-star serial interface "+self.port+" is now operational", RNS.LOG_VERBOSE)

    def process_incoming(self, data):
        try:
            # Decode Base64 ASCII string back to binary data
            binary_data = base64.b64decode(data)
            
            # Update received bytes counter
            self.rxb += len(binary_data)            

            # Send binary data to Transport instance
            self.owner.inbound(binary_data, self)
            
        except Exception as e:
            RNS.log(f"Error decoding Base64 data in D-star interface: {e}", RNS.LOG_ERROR)

    def process_outgoing(self, data):
        if self.online:
            try:
                # Encode binary Reticulum packet to Base64 ASCII string
                base64_data = base64.b64encode(data)
                
                # Escape and packetize the Base64 data using HDLC framing
                framed_data = bytes([HDLC.FLAG]) + HDLC.escape(base64_data) + bytes([HDLC.FLAG])

                # Write framed data to port
                written = self.serial.write(framed_data)

                # Update transmitted bytes counter
                self.txb += len(data)            
                if written != len(framed_data):
                    raise IOError("D-star interface only wrote "+str(written)+" bytes of "+str(len(framed_data)))
                    
            except Exception as e:
                RNS.log(f"Error in D-star process_outgoing: {e}", RNS.LOG_ERROR)
                raise

    def read_loop(self):
        try:
            in_frame = False
            escape = False
            data_buffer = b""
            last_read_ms = int(time.time()*1000)

            while self.serial.is_open:
                if self.serial.in_waiting:
                    byte = ord(self.serial.read(1))
                    last_read_ms = int(time.time()*1000)

                    if (in_frame and byte == HDLC.FLAG):
                        in_frame = False
                        # Process received Base64 data
                        self.process_incoming(data_buffer)
                    elif (byte == HDLC.FLAG):
                        in_frame = True
                        data_buffer = b""
                    elif (in_frame and len(data_buffer) < self.HW_MTU):
                        if (byte == HDLC.ESC):
                            escape = True
                        else:
                            if (escape):
                                if (byte == HDLC.FLAG ^ HDLC.ESC_MASK):
                                    byte = HDLC.FLAG
                                if (byte == HDLC.ESC  ^ HDLC.ESC_MASK):
                                    byte = HDLC.ESC
                                escape = False
                            data_buffer = data_buffer+bytes([byte])
                        
                else:
                    time_since_last = int(time.time()*1000) - last_read_ms
                    if len(data_buffer) > 0 and time_since_last > self.timeout:
                        data_buffer = b""
                        in_frame = False
                        escape = False
                    sleep(0.08)
                    
        except Exception as e:
            self.online = False
            RNS.log("D-star serial port error: "+str(e), RNS.LOG_ERROR)
            RNS.log("The D-star interface "+str(self)+" is now offline.", RNS.LOG_ERROR)
            
            if RNS.Reticulum.panic_on_interface_error:
                RNS.panic()

            RNS.log("Reticulum will attempt to reconnect the D-star interface periodically.", RNS.LOG_ERROR)

        self.online = False
        self.serial.close()
        self.reconnect_port()

    def reconnect_port(self):
        while not self.online:
            try:
                time.sleep(5)
                RNS.log("Attempting to reconnect D-star interface "+str(self.port)+"...", RNS.LOG_VERBOSE)
                self.open_port()
                if self.serial.is_open:
                    self.configure_device()
            except Exception as e:
                RNS.log("Error while reconnecting D-star port: "+str(e), RNS.LOG_ERROR)

        RNS.log("Reconnected D-star interface "+str(self))

    def should_ingress_limit(self):
        return False

    def __str__(self):
        return "ReticulumOverDstar["+self.name+"]"

# Register the interface class
interface_class = ReticulumOverDstar