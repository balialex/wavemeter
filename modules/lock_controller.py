import json
import time
import os
import csv
import datetime
import numpy as np
from threading import Lock, Event
from .pid_wrapper import pid_container

class config_helper(object):
    def __init__(self, file_config = 'config.json', file_config_default = 'config_default.json'):
        self.file_config = file_config
        self.file_config_default = file_config_default
        self.config = self.load_config(self.file_config)
        
    def load_config(self, cfile):
        try:
            with open(cfile,'r') as json_file:
                cdict = json.load(json_file)
                #print("Debug ", cdict)
        except IOError:
            cdict = {}
        return cdict
        
    def save_config(self, cfg, cfile):
        with open(cfile, 'w') as json_file:
            json.dump(cfg, json_file)
        
    def save(self):
        self.save_config(self.config, self.file_config)
        
    def get_config(self):
        return self.config
        
    def get_config_default(self):
                    ###################################################### Changed: implement WS Exposure and Readout Errors
        for name in cfg:
            if 'WM_Exposure' not in cfg[name]:
                cfg[name]['WM_Exposure'] = 0
            if "WM_Reading_State" not in cfg[name]:
                cfg[name]['WM_Reading_State'] = "WM Readout Working"
         ###################################################### Changed: implement WS Exposure 
        return self.load_config(self.file_config_default)
        
    def set_config(self, config):
        self.config = config
        self.save()
        
    def set_config_default(self):
        self.set_config(self.get_config_default())
    
    def set_config_as_default(self, name):
        temp_default = self.get_config_default()
        temp_default[name] = self.config[name]
        self.save_config(temp_default, self.file_config_default)
        
    def set(self, name, key, value):
        if not name in self.config:
            self.config[name] = {}
        self.config[name][key] = value
        self.save()
    
    def get(self, name, key):
        if not name in self.config:
            self.config[name] = {}
            self.save()
            
        if not key in self.config[name]:
            self.config[name][key] = 0
            self.save()
            
        return self.config[name][key]
    
    def get_all(self, s_key):
        lst = []
        for key, value in self.config.items():
            if isinstance(value, dict) and s_key in value:
                lst.append(value[s_key])
        return lst
        
    def get_global(self, key):
        return self.get('.', key)
    
    def set_global(self, key, value):
        self.set('.', key, value)
        
class Controller(config_helper):
    def __init__(self, sampling=None, **kwargs):
        super().__init__(**kwargs)
        self.pid_dict = {}
        
        sampling = self.get('.', 'sampling') if (sampling is None) else sampling;
        sampling = 1 if (sampling==0) else sampling;
        self.set('.', 'sampling', sampling)
        
        self.mutex = Lock()
        self.undersampling = False

        ###################### Pausing Mechanism Change
        self.runit = True
        self.pause_event = Event()
        self.pause_event.set()
        #######################
        self.csv_logging = False
        self.csv_dir = r"C:\Users\bali\WM-CSV-Files"
        os.makedirs(self.csv_dir, exist_ok=True)
        self.csv_files = {}

        self.latest_values = {}
        self.LastWMValue = None
        self.latest_piezo_values = {}
        self.ReferenceLockState = None
        
    def add(self, name, func_read, func_write, active=None, 
            lock_type=None, tracelen=None, 
            unit_input=None, unit_output=None, 
            accuracy_input=None, accuracy_output=None, 
            unlock_set_offset=False):
        if (name in self.pid_dict) or name == '.':
            return False
        else:
            self.undersampling = False
            
            lock =False
            ################################################################################## Set the PID parameters according to the config.json file
            self.set(name,'lock', lock)
            P = self.get(name,'P')
            I = self.get(name,'I')
            D = self.get(name,'D')
            setpoint = self.get(name,'setpoint')
            offset = self.get(name,'offset')
            limits = self.get(name,'limits')
            limits = [None, None] if (limits==0) else limits;
            self.set(name, 'limits', limits)
            center = self.get(name, 'range_center')
            center = None if (center==0) else center;
            self.set(name, 'range_center', center)

            
            span = self.get(name, 'range_span')
            span = None if (span==0) else span;
            self.set(name, 'range_span', span)
            
            active = self.get(name, 'active') if (active is None) else active;
            self.set(name, 'active', active)

            lock_type = self.get(name, 'type') if (lock_type is None) else lock_type;
            self.set(name, 'type', lock_type)
            
            tracelen = self.get(name, 'trace') if (tracelen is None) else tracelen;
            tracelen = tracelen if (tracelen > 0) else 100;
            self.set(name, 'trace',tracelen)
            
            unit_input = self.get(name, 'unit_input') if (unit_input is None) else unit_input;
            unit_input = '' if (unit_input == 0) else unit_input;
            self.set(name, 'unit_input', unit_input)
            
            unit_output = self.get(name, 'unit_output') if (unit_output is None) else unit_output;
            unit_output = '' if (unit_output == 0) else unit_output;
            self.set(name, 'unit_output', unit_output)       
            self.set(name, 'accuracy_input', accuracy_input)
            self.set(name, 'accuracy_output', accuracy_output)

            ramp_rate = self.get(name, 'ramp_rate')
            ramp_rate = None if (ramp_rate == 0) else ramp_rate
            self.set(name, 'ramp_rate', ramp_rate)
            
            
            ################################################# WM Change
            wm_exposure = self.get(name, 'WM_Exposure')
            self.set(name, 'WM_Exposure', wm_exposure)
            WM_Reading_State = self.get(name, 'WM_Reading_State')
            self.set(name, 'WM_Reading_State', WM_Reading_State)
            ################################################# WM Change
            with self.mutex:
                self.pid_dict[name] = pid_container(func_read, func_write, lock, 
                                                    offset, P, I, D, setpoint, limits, 
                                                    tracelen, unlock_set_offset)
                self.pid_dict[name].set_ramp_rate(ramp_rate)
            return True
            
    def remove(self,name):
        if name in self.pid_dict:
            with self.mutex:
                del self.pid_dict[name]
            return True
        else:
            return False
            
    def get_list(self):
        return list(self.pid_dict.keys())
        
    def set_sampling(self, sampling):
        self.set('.', 'sampling',sampling)
        self.undersampling = False
        
    def get_status(self, name=None):
        ret = {}
        if name in self.pid_dict:
            ret[name] = {'active':self.get(name,'active'), 'lock':self.get(name,'lock')}
        else:
            for name in self.pid_dict:
                ret[name] = {'active':self.get(name,'active'), 'lock':self.get(name,'lock')}
        return ret

    def set_trace(self, name, tracelen):
        if name in self.pid_dict:
            self.set(name, 'trace', tracelen)
            pid = self.pid_dict[name]
            pid.set_trace(tracelen)
            return True
        else:
            return False
        
    def clear_trace(self, name):
        if name in self.pid_dict:
            pid = self.pid_dict[name]
            pid.clear_trace()
            return True
        else:
            return False
        
    def get_label(self, name):
        lbl_in = ''
        lbl_out = ''
        if name in self.pid_dict:
            lbl_in = self.get(name, 'unit_input')
            lbl_out = self.get(name, 'unit_output')
        return lbl_in, lbl_out
        
    def get_trace(self, name):
        if name in self.pid_dict:
            pid = self.pid_dict[name]
            return pid.get_trace()
        else:
            return [], [], [], []

    def get_trace_setpoints(self, name):
        if name in self.pid_dict:
            pid = self.pid_dict[name]
            return pid.get_trace_setpoints()
        else:
            return [], []        
        
    def get_trace_last(self, name):
        if name in self.pid_dict:
            pid = self.pid_dict[name]
            return pid.get_trace_last()
        else:
            return None, None, None, None

    def lock(self, name, state):
        if name in self.pid_dict:
            if self.get(name, 'type') > 0:
                self.set(name, 'lock', state)
                pid = self.pid_dict[name]
                pid.set_lock(state)
                if not state:
                    self.set(name, 'last_output', list(pid.get_trace_last()))
                    pid.reset() #### changed 13.10.2025
                return True
            else:
                return False
        else:
            return False
        
    def activate(self, name, state):
        if name in self.pid_dict:
            self.set(name, 'active', state)
            self.undersampling = False
            return True
        else:
            return False
            
    def reset(self, name):
        if name in self.pid_dict:
            pid = self.pid_dict[name]
            pid.reset()
            return True
        else:
            return False
    
    def set_offset(self, name, offset):
        if name in self.pid_dict:
            self.set(name, 'offset', offset)
            pid = self.pid_dict[name]
            pid.set_offset(offset)
            return True
        else:
            return False
            
    def set_pid(self, name, P, I, D):
        if name in self.pid_dict:
            pid = self.pid_dict[name]
            self.set(name, 'P', P)
            self.set(name, 'I', I)
            self.set(name, 'D', D)
            pid.set_pid(P,I,D)
            return True
        else:
            return False
            
    def set_pid_dict(self, name, par_dict):
        try:
            return self.set_pid(name, par_dict['P'], par_dict['I'], par_dict['D'])
        except:
            return False
            
    def set_setpoint(self, name, sp):
        if name in self.pid_dict:
            self.set(name, 'setpoint', sp)
            pid = self.pid_dict[name]
            pid.set_setpoint(sp)
            return True
        else:
            return False
        
    def set_limits(self, name, lms):
        if name in self.pid_dict:
            pid = self.pid_dict[name]
            if pid.set_limits(lms):
                self.set(name, 'limits', lms)
                return True
            else:
                return False
        else:
            return False 


    def set_ramp_rate(self, name, ramp_rate):
        if name in self.pid_dict:
            self.set(name, 'ramp_rate', ramp_rate)
            pid = self.pid_dict[name]
            pid.set_ramp_rate(ramp_rate)
            return True
        else:
            return False
            
    
    def set_input_range(self, name, center, span):
        if name in self.pid_dict:
            if span is None or span>0:
                self.set(name, 'range_center', center)
                self.set(name, 'range_span', span)
                return True
        return False


     ########################################################## WM exposure Change   
    def set_wm_exposure(self, name, value):
        if name in self.pid_dict:
            self.set(name, 'WM_Exposure', value)
            return True
        return False
    def get_wm_exposure(self, name):
        return self.get(name, 'WM_Exposure')

    def set_wm_reading_state(self, name, value):
        if name in self.pid_dict:
            self.set(name, 'WM_Reading_State', value)
            return True
        return False
    def get_wm_reading_state(self, name):
        return self.get("WM_Reading_State")
       ########################################################## WM exposure Change


    def set_last_piezo_output(self, name, value):
        if name in self.pid_dict:
            self.set(name, 'last_piezo_voltage', value)
            return True
        return False
        
    def count(self):
        i = 0
        with self.mutex:
            for name, pid in self.pid_dict.items():
                if self.get(name,'active'):
                    i+=1
        return i
    ################################################### Function for Running PID Controller
     ##########################################################################################
    def run(self):
        starttime = time.time()
        self.runit = True
        last_out = 0
        print("Controller Running, ",starttime)
       # print ("PIDDict:  ",self.pid_dict)
        while self.runit:
            self.pause_event.wait()
            N = len(self.pid_dict)
            ActiveChannels = self.count()
            #print("ActiveChannels: ", ActiveChannels)
            if N>0:
                sampling = float(self.get('.','sampling'))
                wait_dur = sampling/N
                #print("Wait-Dur",wait_dur)
                with self.mutex:
                    for name, pid in self.pid_dict.items():
                        active = self.get(name, 'active')
                        if active:
                            pid.SingleChannelMode = (ActiveChannels == 1)
                            _, val, out = pid() ################# PID Function
                            self.latest_values[name] = val
                            #print("Controller Latest Values ", self.latest_values)
                            self.__check_input_range(name, val)#### unlock laser, when wavelength is out of specific range
                            t, y, e, o = pid.get_trace_last()
                            ################################ Save CSV new Code
                            if name in self.csv_files:
                                filename = self.csv_files[name]
                                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                with open(filename, "a", newline="") as f:
                                    writer = csv.writer(f)
                                    writer.writerow([
                                        timestamp,
                                        t,
                                        self.get(name, 'setpoint'),
                                        self.get(name, 'P'),
                                        self.get(name, 'I'),
                                        self.get(name, 'D'),
                                        self.get(name, 'WM_Exposure'),
                                        y,
                                        e,
                                        o
                                    ])
                            ##################################################
                        t_wait =  wait_dur - float(time.time()-starttime)%wait_dur
                        if t_wait<0 and not self.undersampling:
                            self.undersampling = True
                            print('Warning: sampling rate can not be achieved!', t_wait)
                            t_wait = max(0,t_wait)
                        time.sleep(t_wait)
            else:
                time.sleep(.5)
            ####################################################################################################################################################################################      
    def __in_range(self, name, val):
        center = self.get(name, 'range_center')
        span = self.get(name, 'range_span')
        if span is None or center is None:
            return True
        if (val<=center+span) and (val>=center-span):
            return True
        return False
    
    def __check_input_range(self, name, val):
        if self.get(name, 'lock') and not self.__in_range(name, val) :
            self.lock(name, False)
    def pause(self):
        self.pause_event.clear()
    def resume(self):
        self.pause_event.set()
    def stop(self):
        self.runit = False
        self.pause_event.set()
        with self.mutex:
            for name, pid in self.pid_dict.items():
                self.lock(name, False)

    def set_piezo_manual(self, name, value):
        if name not in self.pid_dict:
            return False, f"Channel '{name}' not found"
        
        limits = self.get(name, 'limits')  # z. B. [min, max] oder [None, None]
        min_limit, max_limit = limits if limits else (None, None)
    
        try:
            value = float(value)
        except ValueError:
            return False, "Invalid piezo value"
    
        # Wert an Limits anpassen
        if min_limit is not None and value < min_limit:
            value = min_limit
        if max_limit is not None and value > max_limit:
            value = max_limit
    
        pid = self.pid_dict[name]
    
        try:
            pid._pid_container__output(value)  # Piezo-Wert ausgeben
            self.latest_piezo_values[name] = value
            self.set(name, 'last_piezo_voltage', value)
            return True, f"Piezo value set successfully (adjusted to {value})"
    
        except Exception as e:
            return False, f"Error writing piezo output: {str(e)}"

    def enable_csv_logging(self, name, enable=True):
        if enable:
            if name not in self.csv_files:
                filename = os.path.join(self.csv_dir, f"data_{name}.csv")
                if not os.path.isfile(filename):
                    with open(filename, "w", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow([ "datetime","time_trace_last", "setpoint", "P", "I", "D", "WM_Exposure", "PID Input", "Error", "PID Output"])
                self.csv_files[name] = filename
            print(f"CSV-Logging activated for {name} → {self.csv_files[name]}")
        else:
            if name in self.csv_files:
                print(f"CSV-Logging deactivated for {name}")
                del self.csv_files[name]

