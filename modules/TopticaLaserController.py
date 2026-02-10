from toptica.lasersdk.dlcpro.v2_2_0 import DLCpro, NetworkConnection
import datetime
import math

############################## Voltage Limits for Testing the Controller

#class TopticaLaserController:
    #def __init__(self, IP='192.168.0.9', command_line_port=1998):
      #  self.error_timers = {}
      #  self.error_interval = 1800 
      #  self.IP = IP
     #   try:
     #       with DLCpro(NetworkConnection(IP)) as dlc:
     #           print(dlc.uptime_txt.get())
     #           self.dlc = dlc
     #   except Exception as e:
     #       self._log_error("connection", f"DLC Pro Connection error: {e}")

    #def _log_error(self, key, message):
      #  now = datetime.datetime.now()
      #  last_time = self.error_timers.get(key, None)

    #    if last_time is None or (now - last_time).total_seconds() > self.error_interval:
     #       print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] ❌ {message}")
    #        self.error_timers[key] = now

   # def SetPiezoVoltage(self, value):
         #   try:
         #       if PiezoVoltageMin < value < PiezoVoltageMax:
         #           self.dlc.laser1.dl.pc.enable.set(True)
         #           self.dlc.laser1.dl.pc.set_voltage.set(value)
         #       else:
         #           self._log_error("voltage_limit", "DLC Pro Voltage Limit exceeded")
         #   except Exception as e:
         #       self._log_error("set_piezo", f"DLC PRO: Error setting Piezo voltage: {e}")
         #   return value
    
   #     def GetPiezoVoltage(self):
        ##    try:
    #            with DLCpro(NetworkConnection(self.IP)) as dlc:
     #               value = dlc.laser1.dl.pc.voltage_act.get()
      #              return value
       #             print(value)
        #    except Exception as e:
         #       self._log_error("get_piezo", f"DLC PRO: Error getting Piezo voltage: {e}")
          #      return -1

def GetPiezoVoltage():
    try:
        PiezoVoltage = dlc.laser1.dl.pc.voltage_set.get()
        return PiezoVoltage
    except Exception as e:
        print(e)

def SetPiezoVoltage(value, LaserController, AnalogOut = None):
    PiezoVoltageMin = 0
    PiezoVoltageMax = 100
    #t_cycle = 0.125
    #PiezoVoltage_dt = 2 ### volts / second
    #print("PID Output Value: ", value)
    step_limit_abs = 1
    try:
        VoltageActual = LaserController.laser1.dl.pc.voltage_set.get()
        #print("Voltage Actual",  VoltageActual)
        #LaserController.laser1.dl.pc.enable.set(True)
        voltage_step = value - VoltageActual
        #print("voltage_step", voltage_step)
        #step_limit_abs = PiezoVoltage_dt*t_cycle
        #print("step_limit_abs", step_limit_abs)
        dt_Bool = abs(voltage_step) > (step_limit_abs)
        if dt_Bool:
            sign_value_limit = voltage_step/abs(voltage_step)
            step_limit = step_limit_abs*sign_value_limit
         #   print("setp_limit", step_limit)
            set_value = VoltageActual+step_limit
          #  print("SetVoltage", SetVoltage)
        else:
            set_value = value
        if PiezoVoltageMin < set_value < PiezoVoltageMax:
            LaserController.laser1.dl.pc.voltage_set.set(set_value)
            return set_value
        if set_value < PiezoVoltageMin:
            #LaserController.laser1.dl.pc.enable.set(True)
            LaserController.laser1.dl.pc.voltage_set.set(PiezoVoltageMin)
            return PiezoVoltageMin
        if set_value > PiezoVoltageMax:
            #LaserController.laser1.dl.pc.enable.set(True)
            LaserController.laser1.dl.pc.voltage_set.set(PiezoVoltageMax)
            return PiezoVoltageMax
    except Exception as e:
        print(e)

def SetDACVoltage(OutputVoltage): #### The DAC Analog Output is calculated as U_out = U_set * 0.5 + 5; this function gives the input value for a desired output voltage
    SetDACVoltage = (OutputVoltage - 5)*2
    return SetDACVoltage



def SetPiezoVoltageDL110(value, LaserController, DACAnalogOut):
    #PiezoVoltage in HV Mode: U_piezo = 15*U_DAC + Offset
    #PiezoVoltage in HV Mode: U_piezo = 10*U_DAC + Offset 

    # Laser Controller input needs to be between -5 and 5 volts, DAC cannot output negative voltages; therefor between 0 nd 5 Volts
    DACVoltageMin = 0  ####### hardcode limits
    DACVoltageMax = 5
    #t_cycle = 0.125
    #PiezoVoltage_dt = 2 ### volts / second
    #DACVoltage_dt = PiezoVoltage_dt/15
    #print("PID Output Value: ", value)
    
    try:
        if DACVoltageMin <= value <= DACVoltageMax:
            set_value = value
            #DACVoltage = SetDACVoltage(value) #### calculate SetVoltage for the DAC
            #LaserController.aout(DACAnalogOut, DACVoltage)
            #print(value)
        if value <= DACVoltageMin:
            set_value = DACVoltageMin
            #DACVoltage = SetDACVoltage(DACVoltageMin)
            #LaserController.aout(DACAnalogOut, DACVoltage)
            #print("Min Voltage reached, requested Voltage:  ", value)
        if value >= DACVoltageMax:
            set_value = DACVoltageMax
            #DACVoltage = SetDACVoltage(DACVoltageMax)
            #LaserController.aout(DACAnalogOut, DACVoltage)
            #print("Max Voltage reached,  requested Voltage:  ", value)
        DACVoltage = SetDACVoltage(set_value)
        LaserController.aout(DACAnalogOut, DACVoltage)
        return set_value
        
    except Exception as e:
        print(e)


    
    