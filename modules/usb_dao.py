'''
usb-3112
https://www.mccdaq.com/
https://www.mccdaq.de/pdfs/manuals/Mcculw_WebHelp/Users_Guide/Analog_Output_Boards/USB-3100.htm

https://github.com/mccdaq
LINUX
    https://github.com/mccdaq/uldaq
WINDOWS
    https://github.com/mccdaq/mcculw

pip install mcculw

Switch digital out: AuxPort/Do#

Do0 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 1 |
Do1 | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 1 |
Do2 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 |
-------------------------------------
dec | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
-------------------------------------
#CH | 1*| 3*| 4*| 3 | 1 | 2*| 4 | 2 |

Analog out:

Ao0 -> CH1 # BD
Ao1 -> CH2
Ao2 -> CH3 # Photo
Ao3 -> CH4

'''

from mcculw.enums import BoardInfo, InfoType, ULRange, FunctionType, \
                            TrigType, ScanOptions, ErrorCode, ChannelType, \
                            DigitalInfo, InterfaceType, DigitalIODirection, \
                            DigitalPortType
from mcculw import ul
from mcculw.enums import ULRange
from mcculw.ul import ULError

# USB3112 range modes (see enums.py)
BIP10VOLTS=1
UNI10VOLTS=100

class USB_DAO:
    def __init__(self):
        self.board_num = 0
        self.channel = 0
        self.item_num = 0
        self.port_index = 0
        self.sdout = False 

        ul.release_daq_device(self.board_num)
        devices = ul.get_daq_device_inventory(InterfaceType.ANY)
        print("daq devices:  ", devices)
        for device in devices:
            try:
                print (self.board_num, devices[0])
                ul.create_daq_device(self.board_num, devices[0])
                print("Found device: %s %s"%(device.product_name, device.unique_id))
                break
            except:
                print("No Device Found")
                pass
            
        if len(devices)>0:
            #print(ul.get_config(InfoType.BOARDINFO, self.board_num, self.item_num, BoardInfo.DACRANGE))
            # hard set to bipolar
            dac_range = ULRange(BIP10VOLTS)
            print("DAC Range: ", dac_range)
            # use current setting
            #dac_range = ULRange(ul.get_config(InfoType.BOARDINFO, self.board_num, self.item_num, BoardInfo.DACRANGE))
            
            self.dac_range = dac_range
            self.port_num = ul.get_config(InfoType.BOARDINFO, self.board_num, self.item_num, BoardInfo.DINUMDEVS)
            self.port_type = DigitalPortType(ul.get_config(InfoType.DIGITALINFO, self.board_num, self.port_index, DigitalInfo.DEVTYPE))
            self.state_dout(True)
            #print(self.port_num, self.port_type, self.dac_range)
        else:
            self.board_num = -1
        
    def __del__(self):
        ul.release_daq_device(self.board_num)
        del self.board_num, self.channel, self.item_num, self.port_index, self.sdout
        
    def state_dout(self, state):
        if self.sdout != state:
            if state:
                ul.d_config_port(self.board_num, self.port_type, DigitalIODirection.OUT)
            else:
                ul.d_config_port(self.board_num, self.port_type, DigitalIODirection.IN)
    
    def dout(self, port_value):
        self.state_dout(True)
        ul.d_out(self.board_num, self.port_type, port_value)
        
    def dout_bit(self, bit_num, bit_val):
        self.state_dout(True)
        ul.d_bit_out(self.board_num, self.port_type, bit_num, bit_val)
        
    def din(self, channel=1):
        self.state_dout(False)
        value = ul.d_in(self.board_num, channel)
        return value
    
    def aout(self, channel, value):
        ul.v_out(self.board_num, channel, self.dac_range, value)
        
    def ain(self, channel):
        value = ul.v_in(self.board_num, channel, self.dac_range)
        #value = ul.v_in_32(self.board_num, channel, self.dac_range)
        return value
        
    def info(self, board_num=None, dev_num=0, ch_num=0, dev_idx=0):
        board_num = self.board_num if (board_num is None) else board_num
        ranges = []
        hard_range = ul.get_config(InfoType.BOARDINFO, board_num, dev_num, BoardInfo.RANGE)
        if hard_range < 0:
            for ai_range in ULRange:
                ranges.append(ai_range)

        print('ADRES',         ul.get_config(InfoType.BOARDINFO, board_num, 0, BoardInfo.ADRES))
        print('NUMADCHANS',    ul.get_config(InfoType.BOARDINFO, board_num, 0, BoardInfo.NUMADCHANS))
        print('ADAIMODE',      ul.get_config(InfoType.BOARDINFO, board_num, 0, BoardInfo.ADAIMODE))
        print('DACFORCESENSE', ul.get_config(InfoType.BOARDINFO, board_num, ch_num, BoardInfo.DACFORCESENSE))
        #print('DACSTARTUP',    ul.get_config(InfoType.BOARDINFO, board_num, ch_num, BoardInfo.DACSTARTUP))
        print('BOARDTYPE',     ul.get_config(InfoType.BOARDINFO, board_num, 0, BoardInfo.BOARDTYPE))
        print('DINUMDEVS',     ul.get_config(InfoType.BOARDINFO, board_num, 0, BoardInfo.DINUMDEVS))
        print('NUMDACHANS',    ul.get_config(InfoType.BOARDINFO, board_num, 0, BoardInfo.NUMDACHANS))
        print('NUMIOPORTS',    ul.get_config(InfoType.BOARDINFO, board_num, 0, BoardInfo.NUMIOPORTS))
        print('OUTMASK',       ul.get_config(InfoType.BOARDINFO, board_num, dev_idx, DigitalInfo.OUTMASK))
        print('BASEADR',       ul.get_config(InfoType.BOARDINFO, board_num, 0, DigitalInfo.BASEADR))
        #print('INITIALIZED',   ul.get_config(InfoType.BOARDINFO, board_num, dev_num, DigitalInfo.INITIALIZED))
        #print('MASK',          ul.get_config(InfoType.BOARDINFO, board_num, dev_num, DigitalInfo.MASK))
        print('CURVAL',        ul.get_config(InfoType.BOARDINFO, board_num, dev_idx, DigitalInfo.CURVAL))
        
        print('DACRES',         ul.get_config(InfoType.BOARDINFO, board_num, 0, BoardInfo.DACRES))
        print('DACSCANOPTIONS', ul.get_config(InfoType.BOARDINFO, board_num, 0, BoardInfo.DACSCANOPTIONS))
        print('DACRANGE',       ul.get_config(InfoType.BOARDINFO, board_num, 0, BoardInfo.DACRANGE))
        
        print('DEVTYPE',     ul.get_config(InfoType.DIGITALINFO, board_num, dev_idx, DigitalInfo.DEVTYPE))
        print('INMASK',      ul.get_config(InfoType.DIGITALINFO, board_num, dev_idx, DigitalInfo.INMASK))
        print('NUMBITS',     ul.get_config(InfoType.DIGITALINFO, board_num, dev_idx, DigitalInfo.NUMBITS))
        print('CONFIG',      ul.get_config(InfoType.DIGITALINFO, board_num, dev_idx, DigitalInfo.CONFIG))

        print('DACRANGE',  self.dac_range)
        #print('DOFUNCTION',  ul.get_status(board_num, FunctionType.DOFUNCTION))
        #print('DIFUNCTION',  ul.get_status(board_num, FunctionType.DIFUNCTION))
        
        return ranges
