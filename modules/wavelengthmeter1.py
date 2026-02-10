import time
from typing import List, Optional, Tuple
from .HighFinesse_dll import HFDLL


# Error codes
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

# Constants
cMin1 = 0
cMin2 = 1
cMax1 = 2
cMax2 = 3
cAvg1 = 4
cAvg2 = 5

cReturnWavelengthVac = 0
cReturnWavelengthAir = 1
cReturnFrequency = 2
cReturnWavenumber = 3
cReturnPhotonEnergy = 4

# Operation Mode Constants
cStop = 0
cAdjustment = 1
cMeasurement = 2

cCtrlStopAll = cStop
cCtrlStartAdjustment = cAdjustment
cCtrlStartMeasurement = cMeasurement
cCtrlStartRecord = 0x0004
cCtrlStartReplay = 0x0008
cCtrlStoreArray = 0x0010
cCtrlLoadArray = 0x0020



class WavelengthMeter:
    """Fixed implementation based on original working code"""

    def __init__(self, dllpath="C:/Windows/System32/wlmData.dll"):
        self.hf_dll = HFDLL()
        self._switcher_available = True  # Track switcher status
        self._current_channel = 1
        self._current_port = 1

    def _check_initialized(self):
        """Check if DLL is properly initialized"""
        if not hasattr(self, 'hf_dll') or self.hf_dll.lib is None:
            raise Exception("Wavelength meter DLL not initialized")

    def GetActiveChannel(self):
        """CORRECT implementation based on original code"""
        self._check_initialized()
        
        if not self._switcher_available:
            # Software tracking mode
            return self._current_channel, self._current_port
        
        try:
            # Use original code parameters: 3, pointer(port), 0
            port_var = ctypes.c_long(0)
            channel = self.hf_dll.GetActiveChannel(3, ctypes.byref(port_var), 0)
            port = port_var.value
            
            # Update internal state
            self._current_channel = channel
            self._current_port = port
            
            return channel, port
        except Exception as e:
            print(f"GetActiveChannel hardware error: {e}, using software tracking")
            self._switcher_available = False
            return self._current_channel, self._current_port

    def SetActiveChannel(self, channel=1, port=1):
        """CORRECT implementation based on original code"""
        self._check_initialized()
        
        print(f"SetActiveChannel called: channel={channel}, port={port}")
        
        if not self._switcher_available:
            print("Warning: Switcher mode not available, using software channel tracking")
            # Software tracking mode
            self._current_channel = channel
            self._current_port = port
            return 0
        
        try:
            # Use original code parameters: 3, port, channel, 0
            result = self.hf_dll.SetActiveChannel(3, port, channel, 0)
            print(f"Hardware SetActiveChannel result: {result}")
            
            if result != 0:
                error_msg = self.hf_dll.ResErr.get(result, f"Unknown error: {result}")
                print(f"SetActiveChannel error: {error_msg}")
                # Fall back to software tracking
                self._switcher_available = False
            
            # Update internal state
            self._current_channel = channel
            self._current_port = port
            return result
            
        except Exception as e:
            print(f"SetActiveChannel hardware exception: {e}")
            self._switcher_available = False
            # Fall back to software tracking
            self._current_channel = channel
            self._current_port = port
            return 0

    def GetExposureMode(self):
        """Get exposure mode"""
        self._check_initialized()
        try:
            return self.hf_dll.GetExposureModeNum(1, ctypes.c_bool(0))
        except Exception as e:
            print(f"GetExposureMode error: {e}")
            return False

    def SetExposureMode(self, b):
        """Set exposure mode"""
        self._check_initialized()
        try:
            return self.hf_dll.SetExposureModeNum(1, ctypes.c_bool(b))
        except Exception as e:
            print(f"SetExposureMode error: {e}")
            return -1

    def GetExposureNum(self, num=1, ccd_arr=1):
        """Get exposure value"""
        self._check_initialized()
        try:
            return self.hf_dll.GetExposureNum(num, ccd_arr, 0)
        except Exception as e:
            print(f"GetExposureNum error: {e}")
            return 0

    def SetExposureNum(self, dur, num=1, ccd_arr=1):
        """Set exposure value"""
        self._check_initialized()
        try:
            return self.hf_dll.SetExposureNum(num, ccd_arr, dur)
        except Exception as e:
            print(f"SetExposureNum error: {e}")
            return -1

    def GetWavelength(self):
        """Get wavelength from default channel"""
        self._check_initialized()
        try:
            return self.hf_dll.GetWavelength(0.0)
        except Exception as e:
            print(f"GetWavelength error: {e}")
            return 0.0

    def GetWavelength2(self):
        """Get wavelength from channel 2"""
        self._check_initialized()
        try:
            return self.hf_dll.GetWavelength2(0.0)
        except Exception as e:
            print(f"GetWavelength2 error: {e}")
            return 0.0

    def GetWavelengthNum(self, channel=1):
        """Get wavelength from specific channel"""
        self._check_initialized()
        try:
            return self.hf_dll.GetWavelengthNum(channel, 0.0)
        except Exception as e:
            print(f"GetWavelengthNum error: {e}")
            return 0.0

    def GetFrequency(self):
        """Get frequency from default channel"""
        self._check_initialized()
        try:
            return self.hf_dll.GetFrequency(0.0)
        except Exception as e:
            print(f"GetFrequency error: {e}")
            return 0.0

    def GetFrequency2(self):
        """Get frequency from channel 2"""
        self._check_initialized()
        try:
            return self.hf_dll.GetFrequency2(0.0)
        except Exception as e:
            print(f"GetFrequency2 error: {e}")
            return 0.0

    def GetFrequencyNum(self, channel=1):
        """Get frequency from specific channel"""
        self._check_initialized()
        try:
            return self.hf_dll.GetFrequencyNum(channel, 0.0)
        except Exception as e:
            print(f"GetFrequencyNum error: {e}")
            return 0.0

    def GetTemperature(self):
        """Get temperature"""
        self._check_initialized()
        try:
            return self.hf_dll.GetTemperature(0.0)
        except Exception as e:
            print(f"GetTemperature error: {e}")
            return 0.0

    def GetPressure(self):
        """Get pressure"""
        self._check_initialized()
        try:
            return self.hf_dll.GetPressure(0.0)
        except Exception as e:
            print(f"GetPressure error: {e}")
            return 0.0

    def Calibration(self, Type, unit, value, channel):
        """Perform calibration"""
        self._check_initialized()
        try:
            return self.hf_dll.Calibration(Type, unit, value, channel)
        except Exception as e:
            print(f"Calibration error: {e}")
            return -1

    def GetSwitcherMode(self):
        """Get switcher mode"""
        self._check_initialized()
        try:
            return self.hf_dll.GetSwitcherMode(0)
        except Exception as e:
            print(f"GetSwitcherMode error: {e}")
            return False

    def SetSwitcherMode(self, mode):
        """Set switcher mode"""
        self._check_initialized()
        try:
            return self.hf_dll.SetSwitcherMode(mode)
        except Exception as e:
            print(f"SetSwitcherMode error: {e}")
            return -1

    def GetSwitcherChannel(self):
        """Get switcher channel"""
        self._check_initialized()
        try:
            return self.hf_dll.GetSwitcherChannel(0)
        except Exception as e:
            print(f"GetSwitcherChannel error: {e}")
            return 1

    def SetSwitcherChannel(self, channel):
        """Set switcher channel"""
        self._check_initialized()
        try:
            return self.hf_dll.SetSwitcherChannel(channel)
        except Exception as e:
            print(f"SetSwitcherChannel error: {e}")
            return -1

    def GetWLMVersion(self, ver=0):
        """Get WLM version"""
        self._check_initialized()
        try:
            return self.hf_dll.GetWLMVersion(ver)
        except Exception as e:
            print(f"GetWLMVersion error: {e}")
            return 0

    def GetVersion(self):
        """Get complete version info"""
        return (self.GetWLMVersion(0), self.GetWLMVersion(1), 
                self.GetWLMVersion(2), self.GetWLMVersion(3))

    def GetWLMIndex(self):
        """Get WLM index"""
        self._check_initialized()
        try:
            return self.hf_dll.GetWLMIndex(self.GetWLMVersion(1))
        except Exception as e:
            print(f"GetWLMIndex error: {e}")
            return 0

    def GetWLMCount(self):
        """Get WLM count"""
        self._check_initialized()
        try:
            return self.hf_dll.GetWLMCount(0)
        except Exception as e:
            print(f"GetWLMCount error: {e}")
            return 0

    def GetChannelsCount(self):
        """Get channels count"""
        self._check_initialized()
        try:
            return self.hf_dll.GetChannelsCount(0)
        except Exception as e:
            print(f"GetChannelsCount error: {e}")
            return 1

    def GetAmplitudeNum(self, channel=1, index=cMax1):
        """Get amplitude"""
        self._check_initialized()
        try:
            return self.hf_dll.GetAmplitudeNum(channel, index, 0)
        except Exception as e:
            print(f"GetAmplitudeNum error: {e}")
            return 0

    def GetIntensityNum(self, channel=1):
        """Get intensity"""
        self._check_initialized()
        try:
            return self.hf_dll.GetIntensityNum(channel, 0)
        except Exception as e:
            print(f"GetIntensityNum error: {e}")
            return 0.0

    def GetPowerNum(self, channel=1):
        """Get power"""
        self._check_initialized()
        try:
            return self.hf_dll.GetPowerNum(channel, 0)
        except Exception as e:
            print(f"GetPowerNum error: {e}")
            return 0.0

    def GetLinewidthNum(self, index=cReturnFrequency):
        """Get linewidth"""
        self._check_initialized()
        try:
            return self.hf_dll.GetLinewidthNum(index, 0)
        except Exception as e:
            print(f"GetLinewidthNum error: {e}")
            return 0.0

    def GetOperationState(self):
        """Get operation state"""
        self._check_initialized()
        try:
            return self.hf_dll.GetOperationState(0)
        except Exception as e:
            print(f"GetOperationState error: {e}")
            return cStop

    def Operation(self, op=cCtrlStartMeasurement):
        """Control operation"""
        self._check_initialized()
        try:
            return self.hf_dll.Operation(op)
        except Exception as e:
            print(f"Operation error: {e}")
            return -1

    def start(self):
        """Start measurement"""
        return self.Operation(op=cCtrlStartMeasurement)

    def stop(self):
        """Stop measurement"""
        return self.Operation(op=cCtrlStopAll)

    def switch_rear(self):
        """Switch to rear channel"""
        return self.SetActiveChannel(channel=2, port=1) == 0

    def switch_front(self):
        """Switch to front channel"""
        return self.SetActiveChannel(channel=1, port=1) == 0

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

    @property
    def is_switcher_available(self):
        """Check if switcher hardware is available"""
        return self._switcher_available



class WavemeterCalibration:
    def __init__(self, wavemeter, lock_reference, reference_frequency: float = 461.312470):
        self.wvm = wavemeter
        self.lck = lock_reference
        self.reference_frequency = reference_frequency
        self.initialized = False
        self.latest_wm_value = None
        self.calibration_in_progress = False
        self._calibration_channel = 1  # 改为使用通道1进行校准
        self._operation_channel = 1    # 工作通道也是1

    def initialize(self) -> bool:
        """单通道校准初始化"""
        try:
            print("=== Single-channel calibration initialization ===")
            
            # 暂停锁相环
            if hasattr(self.lck, 'pause'):
                print("Pausing lock...")
                self.lck.pause()
            
            self.calibration_in_progress = True 
            
            # 确保在通道1（单通道设备）
            print("Ensuring channel 1 is active...")
            self.wvm.SetActiveChannel(channel=1, port=1)
            
            # 设置自动曝光模式
            print("Setting exposure mode to auto...")
            self.wvm.SetExposureMode(True)
            
            # 等待稳定
            print("Waiting for stabilization...")
            time.sleep(2.0)
            
            # 读取频率
            print("Reading frequency from channel 1...")
            freq = self.wvm.GetFrequency(1)
            print(f"Channel 1 frequency: {freq} THz")
            
            if freq == 0.0:
                print("⚠️ Warning: Frequency reading is 0.0 THz - check signal input")
                # 继续执行，但记录警告
            
            self.latest_wm_value = freq
            
            # 设置锁相环参考值
            if hasattr(self.lck, 'LastWMValue'):
                self.lck.LastWMValue = freq
                print(f"Lock reference set to: {freq} THz")
            
            self.initialized = True
            print("=== Single-channel initialization completed ===")
            return True
            
        except Exception as e:
            print(f"Initialization Failed: {e}")
            self.initialized = False
            self.calibration_in_progress = False
            return False

    def calibrate(self) -> bool:
        """单通道校准"""
        if not self.initialized:
            print("Error: Wavemeter not initialized")
            return False
        
        try:
            print("=== Starting single-channel calibration ===")
            self.calibration_in_progress = True
            
            # 在通道1上执行校准
            print(f"Calibrating on channel 1 with reference: {self.reference_frequency} THz")
            result = self.wvm.Calibration(
                Type=2, 
                unit=2, 
                value=self.reference_frequency, 
                channel=1
            )
            print(f"Calibration result: {result}")
            
            # 设置手动曝光模式
            print("Setting exposure mode to manual...")
            self.wvm.SetExposureMode(False)
            
            # 恢复锁相环
            if hasattr(self.lck, 'resume'):
                print("Resuming lock...")
                self.lck.resume()
            
            print("=== Calibration completed ===")
            return result == 0
            
        except Exception as e:
            print(f"Calibration Failed: {e}")
            return False
        finally:
            self.calibration_in_progress = False


    def abort_calibration(self):
        """完全复制原始 abort_calibration 方法"""
        if self.calibration_in_progress:
            print("Calibration aborted.")
            self.calibration_in_progress = False
            self.wvm.SetActiveChannel(channel=1, port=1)
            self.wvm.SetExposureMode(False)
            time.sleep(1)
            self.lck.resume()
        else:
            print("No calibration in progress to abort.")