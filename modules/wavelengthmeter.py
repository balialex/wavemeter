#https://github.com/stepansnigirev/py-ws7

import ctypes
import time

ErrNoValue = 0
ErrNoSignal = -1
ErrBadSignal = -2
ErrLowSignal = -3
ErrBigSignal = -4
ErrWlmMissing = -5
ErrNotAvailable = -6
InfNothingChanged = -7
ErrNoPulse = -8
ErrDiv0 = -13
ErrOutOfRange = -14
ErrUnitNotAvailable = -15
ErrMaxErr = ErrUnitNotAvailable

cMin1 = 0
cMin2 = 1
cMax1 = 2
cMax2 = 3
cAvg1 = 4
cAvg2 = 5

cReturnWavelengthVac = 0;
cReturnWavelengthAir = 1;
cReturnFrequency = 2;
cReturnWavenumber = 3;
cReturnPhotonEnergy = 4;


# Operation Mode Constants: GetOperationState
cStop = 0
cAdjustment = 1
cMeasurement = 2

cCtrlStopAll = cStop
cCtrlStartAdjustment = cAdjustment
cCtrlStartMeasurement = cMeasurement
cCtrlStartRecord = 0x0004
cCtrlStartReplay = 0x0008
cCtrlStoreArray  = 0x0010
cCtrlLoadArray   = 0x0020

class WavelengthMeter:

    def __init__(self, dllpath="C:/Windows/System32/wlmData.dll"):
    #def __init__(self, dllpath="C:\Program Files (x86)\HighFinesse\Wavelength Meter WS Ultimate 1487\Com-Test\wlmData.dll"):
        self.dll = ctypes.WinDLL(dllpath)
        self.dll.GetExposureMode.restype = ctypes.c_bool
        self.dll.SetExposureMode.restype = ctypes.c_long
        
        self.dll.GetExposure.restype = ctypes.c_ushort
        self.dll.SetExposure.restype = ctypes.c_ushort
        
        self.dll.GetExposureNum.restype = ctypes.c_long
        self.dll.SetExposureNum.restype = ctypes.c_long

        self.dll.GetWavelength.restype = ctypes.c_double
        self.dll.GetWavelength2.restype = ctypes.c_double
        self.dll.GetWavelengthNum.restype = ctypes.c_double

        self.dll.GetFrequency.restype = ctypes.c_double
        self.dll.GetFrequency2.restype = ctypes.c_double
        self.dll.GetFrequencyNum.restype = ctypes.c_double

        self.dll.GetTemperature.restype = ctypes.c_double
        self.dll.GetPressure.restype = ctypes.c_double
        self.dll.GetDistance.restype = ctypes.c_double
        
        self.dll.GetSwitcherMode.restype = ctypes.c_long
        self.dll.SetSwitcherMode.restype = ctypes.c_long
        
        self.dll.GetSwitcherChannel.restype = ctypes.c_long
        self.dll.SetSwitcherChannel.restype = ctypes.c_long
        
        self.dll.GetWLMVersion.restype = ctypes.c_long
        self.dll.GetWLMIndex.restype = ctypes.c_long
        self.dll.GetWLMCount.restype = ctypes.c_long
        
        self.dll.GetActiveChannel.restype = ctypes.c_long
        self.dll.SetActiveChannel.restype = ctypes.c_long
        self.dll.GetChannelsCount.restype = ctypes.c_long
        
        self.dll.GetAmplitudeNum.restype = ctypes.c_long
        self.dll.GetIntensityNum.restype = ctypes.c_double
        self.dll.GetPowerNum.restype = ctypes.c_double
        
        self.dll.GetLinewidthNum.restype = ctypes.c_double
        
        self.dll.Calibration.restype = ctypes.c_long
        self.dll.GetOperationState.restype = ctypes.c_ushort
        self.dll.Operation.restype = ctypes.c_long
        self.dll.GetAutoCalMode.restype = ctypes.c_long
        self.dll.SetAutoCalMode.restype = ctypes.c_long
        
        '''
        Data_API(long)           Calibration(long Type, long Unit, double Value, long Channel) ;
        '''

    def GetExposureMode(self):
        return self.dll.GetExposureMode(ctypes.c_bool(0))

    def SetExposureMode(self, b):
        return self.dll.SetExposureMode(ctypes.c_bool(b))
    
    def GetExposure(self, num=1, ccd_arr=1):
        #return self.dll.GetExposure(ctypes.c_ushort(0))
        return self.dll.GetExposureNum(ctypes.c_long(int(num)), ctypes.c_long(int(ccd_arr)), ctypes.c_long(0))
    
    def SetExposure(self, dur, num=1, ccd_arr=1):
        #return self.dll.SetExposure(ctypes.c_ushort(int(dur)))
        return self.dll.SetExposureNum(ctypes.c_long(int(num)), ctypes.c_long(int(ccd_arr)), ctypes.c_long(int(dur)))

    def GetWavelength(self):
        return self.dll.GetWavelength(ctypes.c_double(0))

    def GetWavelength2(self):
        return self.dll.GetWavelength2(ctypes.c_double(0))

    def GetWavelengthNum(self, channel=1):
        return self.dll.GetWavelengthNum(ctypes.c_long(channel), ctypes.c_double(0))

    def GetFrequency(self):
        return self.dll.GetFrequency(ctypes.c_double(0))

    def GetFrequency2(self):
        return self.dll.GetFrequency2(ctypes.c_double(0))

    def GetFrequencyNum(self, channel=1):
        return self.dll.GetFrequencyNum(ctypes.c_long(channel), ctypes.c_double(0))

    def GetTemperature(self):
        return self.dll.GetTemperature(ctypes.c_double(0))
    
    def GetPressure(self):
        return self.dll.GetPressure(ctypes.c_double(0))

    def Calibration (self, Type, unit, value, channel):
        return self.dll.Calibration(
        ctypes.c_long(Type),
        ctypes.c_long(unit),
        ctypes.c_double(value),
        ctypes.c_long(channel))

    def SetAutoCalMode(self, value):
        return self.dll.SetAutoCalMode( ctypes.c_long(value))
    # N.A.
    def GetDistance(self):
        return self.dll.GetDistance(ctypes.c_double(0))
    
    def GetSwitcherMode(self):
        return self.dll.GetSwitcherMode(ctypes.c_long(0))

    def SetSwitcherMode(self, mode):
        return self.dll.SetSwitcherMode(ctypes.c_long(int(mode)))
    
    # N.A.
    def GetSwitcherChannel(self):
        return self.dll.GetSwitcherChannel(ctypes.c_long(0))
    
    # N.A.
    def SetSwitcherChannel(self, channel):
        return self.dll.SetSwitcherChannel(ctypes.c_long(channel))
    
    def GetWLMVersion(self, ver=0):
        return self.dll.GetWLMVersion(ctypes.c_long(int(ver)))
    
    def GetVersion(self):
        # return: type, version number, revision number, compilation number 
        return self.GetWLMVersion(0), self.GetWLMVersion(1), self.GetWLMVersion(2), self.GetWLMVersion(3)
    
    # Wavemeters internal dll handle
    def GetWLMIndex(self):
        return self.dll.GetWLMIndex(ctypes.c_long(self.GetWLMVersion(1)))
    
    # Number of WM connected
    def GetWLMCount(self):
        return self.dll.GetWLMCount(ctypes.c_long(0))
    
    def GetActiveChannel(self):
        #c_long_p = ctypes.POINTER(ctypes.c_long)
        c_long_port = ctypes.c_long(0)
        channel = self.dll.GetActiveChannel(ctypes.c_long(3), ctypes.pointer(c_long_port), ctypes.c_long(0))
        #port = c_long_p.contents
        port = c_long_port.value
        return channel, port
    
    def SetActiveChannel(self, channel=1, port=1):
        return self.dll.SetActiveChannel(ctypes.c_long(3), ctypes.c_long(int(port)), ctypes.c_long(int(channel)), ctypes.c_long(0))
    
    def GetChannelsCount(self):
        return self.dll.GetChannelsCount(ctypes.c_long(0))
    
    def GetAmplitude(self, channel=1, index=cMax1):
        return self.dll.GetAmplitudeNum(ctypes.c_long(int(channel)), ctypes.c_long(int(index)), ctypes.c_long(0))
    
    # N.A.
    def GetIntensity(self, channel=1):
        return self.dll.GetIntensityNum(ctypes.c_long(int(channel)), ctypes.c_long(0))
    
    def GetPower(self, channel=1):
        return self.dll.GetPowerNum(ctypes.c_long(int(channel)), ctypes.c_long(0))
    
    # N.A.
    def GetLinewidth(self, index=cReturnFrequency):
        return self.dll.GetLinewidthNum(ctypes.c_long(int(index)), ctypes.c_long(0))
    
    def GetOperationState(self):
        return self.dll.GetOperationState(ctypes.c_ushort(0))
    
    def Operation(self, op=cCtrlStartMeasurement):
        return self.dll.Operation(ctypes.c_ushort(int(op)))
    
    def start(self):
        return self.Operation(op=cCtrlStartMeasurement)
    
    def stop(self):
        return self.Operation(op=cCtrlStopAll)

    def switch_rear(self):
        return self.SetActiveChannel(channel=2, port=1)==0

    def switch_front(self):
        return self.SetActiveChannel(channel=1, port=1)==0
    
    @property
    def wavelength_front(self):
        return self.GetWavelength()

    @property
    def wavelength_rear(self):
        return self.GetWavelength2()

    @property
    def wavelengths(self):
        return [self.GetWavelengthNum(i+1) for i in range(8)]

    @property
    def frequency_front(self):
        return self.GetFrequency()

    @property
    def frequency_rear(self):
        return self.GetFrequency2()

    @property
    def frequencies(self):
        return [self.GetFrequencyNum(i+1) for i in range(8)]

    #@property
    #@switcher_mode.setter



class WavemeterCalibration:
    def __init__(self, wvm, lck, reference_frequency=461.312470):
        self.wvm = wvm
        self.lck = lck  
        self.reference_frequency = reference_frequency
        self.initialized = False
        self.latest_wm_value = None
        self.calibration_in_progress = False

    def initialize(self):
        try:
            self.lck.pause()
            self.calibration_in_progress = True 
            self.wvm.SetActiveChannel(channel=2, port=1)
            while self.wvm.GetActiveChannel() != (2, 1):
                time.sleep(0.1)
                print("WLM GEtActiveChannel")
            self.wvm.SetExposureMode(True)
            freq = self.wvm.GetFrequency2()
            self.latest_wm_value = freq
            self.lck.LastWMValue = freq
            self.initialized = True
            
        except Exception as e:
            print("Initialization Failed:", e)
            self.initialized = False

    def calibrate(self):
        if not self.initialized:
            print("Error: Wavemeter not initialized. Run initialize() first.")
            return
        try:
            self.calibration_in_progress = True 
            self.wvm.Calibration(Type=2, unit=2, value=self.reference_frequency, channel=2)
            self.wvm.SetActiveChannel(channel=1, port=1)
            self.wvm.SetExposureMode(False)
            time.sleep(1)
            self.lck.resume()
            print("Calibration completed successfully.")
        except Exception as e:
            print("Calibration Failed:", e)
        finally:
            self.calibration_in_progress = False 


    def abort_calibration(self):
        if self.calibration_in_progress:
            print("Calibration aborted.")
            self.calibration_in_progress = False
            self.wvm.SetActiveChannel(channel=1, port=1)
            self.wvm.SetExposureMode(False)
            time.sleep(1)
            self.lck.resume()
        else:
            print("No calibration in progress to abort.")