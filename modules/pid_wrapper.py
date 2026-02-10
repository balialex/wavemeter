 #https://pypi.org/project/simple-pid/
#from simple_pid import PID

from .PID import PID
import collections
import time

class logger(object):
    def __init__(self, tracelen):
        self.trace = []
        self.setup(tracelen)
        
    def setup(self, tracelen):
        self.trace = collections.deque(self.trace, maxlen=tracelen)
        
    def get(self):
        return list(self.trace)
    
    def get_item(self, index):
        return self.trace[index]
    
    def append(self, val):
        self.trace.append(val)
        
    def clear(self):
        self.trace.clear()
        
    def size(self):
        return len(self.trace)
        

class pid_container(object):
    def __init__(self, 
                func_read, func_write, 
                lock, offset, 
                P, I, D, setpoint, limits, 
                tracelen, unlock_set_offset=False, ramp_rate  = None):
        self.last_out = None
        self.lock = lock
        self.unlock_set_offset = unlock_set_offset
        
        self.pid = PID(Kp=P, Ki=I, Kd=D, 
                       setpoint=setpoint, 
                         sample_time=None,
                       offset=offset,
                       output_limits=tuple(i for i in limits),
                       auto_mode=True,
                       proportional_on_measurement=False)

        self.func_write = func_write
        self.func_read = func_read

        self.times = logger(tracelen)
        self.trace = logger(tracelen)
        self.error = logger(tracelen)
        self.outpt = logger(tracelen)
        self.setpoints = logger(tracelen)

        ########## new ramp feature
        self.ramp_rate = ramp_rate if ramp_rate and ramp_rate > 0 else None
        self._last_ramp_time = None
        self._last_ramp_output = None
        ##############################
        
    def reset(self):
        self.pid._integral = 0
        
    def clear_trace(self):
        self.times.clear()
        self.trace.clear()
        self.error.clear()
        self.outpt.clear()
        self.setpoints.clear()
        
    def set_trace(self, tracelen):
        self.times.setup(tracelen)
        self.trace.setup(tracelen)
        self.error.setup(tracelen)
        self.outpt.setup(tracelen)
        self.setpoints.setup(tracelen)
        
    def set_offset(self, offset):
        self.pid.offset = offset

    def get_offset(self):
        return self.pid.offset
        
    def set_setpoint(self, sp):
        self.pid.setpoint = sp
        
    def set_limits(self, limits):
        return self.pid.set_limits(limits)

    def set_ramp_rate(self, ramp_rate):
        self.ramp_rate = None if (ramp_rate is None or ramp_rate == 0) else float(ramp_rate)
        return self.ramp_rate
        
    def set_pid(self, kp, ki, kd):
        self.pid.tunings = (kp,ki,kd)
    
    def get_trace(self):
        return self.times.get(), self.trace.get(), self.error.get(), self.outpt.get()
    def get_trace_setpoints(self):
        return self.times.get(), self.setpoints.get()
        
    def get_trace_last(self):
        t = None; y = None; e = None; o = None;
        if self.times.size()>0:
            t = self.times.get_item(-1)
            y = self.trace.get_item(-1)
            e = self.error.get_item(-1)
            o = self.outpt.get_item(-1)
        return t,y,e,o
        
    def set_lock(self, state):
        '''
        if not state:
            if self.last_out is not None:
                self.set_offset(self.last_out)
        '''
        self.lock = state
    
    def __measure(self):
        val = self.func_read()
        now = time.time()
        return now, val
    
    def __output(self, value): ################## communication with output device        
        if callable(self.func_write):
            self.last_out = self.func_write(value, self.last_out)

    def __apply_ramp(self, target_value):
        if self.ramp_rate is None:
            self._last_ramp_time = time.time()
            self._last_ramp_output = target_value
            return target_value
        now = time.time()

        if self._last_ramp_time is None:
            self._last_ramp_time = now
            self._last_ramp_output = target_value
            return target_value

        dt = now - self._last_ramp_time
        if dt <= 0:
            return self._last_ramp_output

        max_delta = self.ramp_rate*dt
        delta = target_value - self._last_ramp_output

        if abs(delta) > max_delta:
            new_output = self._last_ramp_output + (max_delta if delta>0 else -max_delta)
        else:
            new_output = target_value
        self._last_ramp_output = new_output
        self._last_ramp_time = now
        return new_output
    
    def __call__(self):
        now, value_in = self.__measure()
        ########################################### if locked, give output to the laser controller
        if self.lock:
            if value_in > 0: ### if under/overexposed Wm gives out negative values
                value_pid = self.pid(value_in)
                #print("Output Without Ramp:  ", value_pid)
                value_pid = self.__apply_ramp(value_pid)
                #print("Output With Ramp:  ", value_pid)
                self.__output(value_pid)
                #print("locked", "ValuePID Output:", value_pid)
        ############################################# if unlocked
        elif self.unlock_set_offset:
            self.__output(self.get_offset())
            #print("unlocked")
        value_out = self.last_out
        value_err = value_in-self.pid.setpoint
        self.times.append(now)
        self.trace.append(value_in)
        self.error.append(value_err)
        self.outpt.append(value_out)
        self.setpoints.append(self.pid.setpoint)
        ##### test pid output
        #value_pid = self.pid(value_in)
        #print("Value PID: (Output):   ",value_pid)
        #######
        return now, value_in, value_out
    
    

