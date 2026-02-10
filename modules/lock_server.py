import signal
#import sys
import os
import json
from threading import Thread
from flask import Flask, render_template, request, Response, url_for, redirect
from flask import stream_with_context
from flask import session, g
import csv
import datetime
from waitress import serve, task, create_server
from modules.wavelengthmeter import WavelengthMeter, WavemeterCalibration

from .lock_controller import Controller
from .plotter import parse_data, plot_data, export_plot_svg
class endpoint_action(object):
    #'application/json'
    #'text/html'
    #'text/xml'
    def __init__(self, action, mimetype='application/json', serve_json=True):
        self.action = action
        self.mimetype = mimetype
        self.serve_json = serve_json

    def __call__(self, *args):
        #djsn = request.json
        djsn = request.get_json(silent=True)
        if djsn is None:
            djsn = request.args
        #data = request.data
        #form = request.form
        #coks = request.cookies
        ret, data = self.action(djsn)
        if self.serve_json:
            msg = json.dumps({'status':ret, 'data':data})
        else:
            msg = data
        #Response(status_code=200, headers={}, status=msg)
        return Response(msg, mimetype=self.mimetype)




USERNAME = 'bali'
PASSWORD = 'balibali24'

class flask_server(Flask):
    def __init__(self, name):
        self.debug_mode = True
        super(flask_server, self).__init__(name) 
        self.add_url_rule('/login', 'login', self.login, methods=['GET', 'POST']) #### login
        self.config['SECRET_KEY'] = os.urandom(16)
        super().before_request(self.before_request)

    def before_request(self): ######### new Password function
        # Seite /login ist immer erlaubt
        if request.endpoint == 'login':
            return
        # Falls kein Login in der Session, umleiten
        if not session.get('logged_in'):
            return redirect(url_for('login')) 
            
    def login(self):  ################ define login
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            if username == USERNAME and password == PASSWORD:
                session['logged_in'] = True
                return redirect(url_for('index'))
            return Response('<h3>Login fehlgeschlagen</h3>', mimetype='text/html')
        return '''
            <form method="post">
                Benutzername: <input type="text" name="username"><br>
                Passwort: <input type="password" name="password"><br>
                <input type="submit" value="Login">
            </form>
        '''            

        
    def add_endpoint(self, endpoint=None, endpoint_name=None, handler=None, methods=None, **kwargs):
        self.add_url_rule(rule=endpoint, 
                                endpoint=endpoint_name,
                                view_func=endpoint_action(handler, **kwargs),
                                methods=methods)
        
    def start(self, host, port, debug_mode=False):
        self.debug_mode = debug_mode
        if debug_mode:
            self.run(host=host, port=port, debug=debug_mode, use_reloader=False)
        else:
            serve(self, host=host, port=port, threads=10000)

    def shutdown_server(self, signum=None, stack=None):
        if self.debug_mode:
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                raise RuntimeError('Not running with the Werkzeug Server')
            func()
        else:
            print('Terminate server PID %i'%os.getpid())
            os.kill(os.getpid(), signal.SIGTERM)
        
class web_test(object):
    def __init__(self, name=__name__):
        self.flsk = flask_server(name)
        self.flsk.add_endpoint('/', endpoint_name='index', handler=self.index)
        
    def run(self, host='127.0.0.1', port=8080, debug=True):
        self.flsk.start(host=host, port=port, debug_mode=debug)
        
    def index(self, jdata):
        form_script = ''
        for i in range(10):
            form_script += '<option value ="%s">%s</option>'%(str(i),str(i))
        html = render_template("index.html", form_script=form_script)
        return True, html
        
class web_lock(object):
    def __init__(self, name=__name__, **kwargs):
        self.cntrl = Controller(**kwargs)
        self.wvm = WavelengthMeter()
        self.flsk = flask_server(name)
        self.calibration_settings = {
    "wm_calibration_frequency": self.cntrl.get_global("wm_calibration_frequency"),
    "wm_calibration_interval": self.cntrl.get_global("wm_calibration_interval")
}
        self.flsk.add_endpoint('/', endpoint_name='index', handler=self.index, mimetype='text/html', serve_json=False)
        self.flsk.add_endpoint('/stop', endpoint_name='stop', handler=self.stop, mimetype='text/html', serve_json=False)
        
        self.flsk.add_endpoint('/get/list', endpoint_name='get_list', handler=self.get_list, methods=['GET'])
        self.flsk.add_endpoint('/get/config', endpoint_name='get_config', handler=self.get_config, methods=['GET'])
        self.flsk.add_endpoint('/get/config/default', endpoint_name='get_default_config', handler=self.get_default_config, methods=['GET'])
        self.flsk.add_endpoint('/get/parameter', endpoint_name='get_parameter', handler=self.get_parameter, methods=['GET'])
        self.flsk.add_endpoint('/get/status', endpoint_name='get_status', handler=self.get_status, methods=['GET'])
        self.flsk.add_endpoint('/get/trace/last', endpoint_name='get_trace_last', handler=self.get_trace_last, methods=['GET'])
        self.flsk.add_endpoint('/get/trace', endpoint_name='get_trace', handler=self.get_trace, methods=['GET'])
        self.flsk.add_endpoint('/get/graph', endpoint_name='get_graph', handler=self.get_plot, methods=['GET'])
        self.flsk.add_endpoint('/get/plot', endpoint_name='get_plot', handler=self.get_plot, methods=['GET'], mimetype='text/html', serve_json=False)
        self.flsk.add_endpoint('/get/calibration_settings', endpoint_name='get_calibration_settings', handler=self.get_calibration_settings, methods=['GET'])
        
        
        self.flsk.add_endpoint('/post/trace', endpoint_name='post_trace', handler=self.post_trace, methods=['POST'])
        self.flsk.add_endpoint('/post/trace/clear', endpoint_name='post_trace_clear', handler=self.post_trace_clear, methods=['POST'])
        
        self.flsk.add_endpoint('/post/parameter', endpoint_name='set_parameter', handler=self.set_parameter, methods=['POST'])
        self.flsk.add_endpoint('/post/offset', endpoint_name='post_offset', handler=self.post_offset, methods=['POST'])
        self.flsk.add_endpoint('/post/setpoint', endpoint_name='post_setpoint', handler=self.post_setpoint, methods=['POST'])
        self.flsk.add_endpoint('/post/pid', endpoint_name='post_pid', handler=self.post_pid, methods=['POST'])
        self.flsk.add_endpoint('/post/sampling', endpoint_name='post_sampling', handler=self.post_sampling, methods=['POST'])
        self.flsk.add_endpoint('/post/limits', endpoint_name='post_limits', handler=self.post_limits, methods=['POST'])
        self.flsk.add_endpoint('/post/ramp_rate', endpoint_name='post_ramp_rate', handler=self.post_ramp_rate, methods=['POST'])
        self.flsk.add_endpoint('/post/range', endpoint_name='post_range', handler=self.post_range, methods=['POST'])
        self.flsk.add_endpoint('/post/reset', endpoint_name='post_reset', handler=self.post_reset, methods=['POST'])
        
        self.flsk.add_endpoint('/post/lock', endpoint_name='post_lock', handler=self.post_lock, methods=['POST'])
        self.flsk.add_endpoint('/post/unlock', endpoint_name='post_unlock', handler=self.post_unlock, methods=['POST'])
        
        self.flsk.add_endpoint('/post/activate', endpoint_name='post_activate', handler=self.post_activate, methods=['POST'])
        self.flsk.add_endpoint('/post/deactivate', endpoint_name='post_deactivate', handler=self.post_deactivate, methods=['POST'])
        self.flsk.add_endpoint('/post/set_piezo', endpoint_name='post_set_piezo', handler=self.post_set_piezo, methods=['POST'])
        self.flsk.add_endpoint('/post/wm_initialize', endpoint_name='wm_initialize', handler=self.post_wm_initialize, methods=['POST'])
        #self.flsk.add_endpoint('/post/wm_calibrate', endpoint_name='wm_calibrate', handler=self.post_wm_calibrate, methods=['POST'])
        self.flsk.add_endpoint('/post/wm_abort', endpoint_name='wm_abort', handler=self.post_wm_abort, methods=['POST'])
        self.flsk.add_endpoint('/post/wm_calibrate', endpoint_name='wm_calibrate', handler=self.post_wm_calibrate, methods=['POST'])

        
        self.flsk.add_endpoint('/post/remove', endpoint_name='post_remove', handler=self.post_remove, methods=['POST'])
        self.flsk.add_endpoint('/post/stop', endpoint_name='post_stop', handler=self.post_stop, methods=['POST'])
        self.flsk.add_endpoint('/post/pause', endpoint_name='post_pause', handler=self.post_pause, methods=['POST'])
        self.flsk.add_endpoint('/post/resume', endpoint_name='post_resume', handler=self.post_resume, methods=['POST'])
        self.flsk.add_endpoint('/post/calibration_settings', endpoint_name='post_calibration_settings', handler=self.post_calibration_settings, methods=['POST'])

        
        self.flsk.add_endpoint('/post/csv_logging', endpoint_name='post_csv_logging',
                       handler=self.post_csv_logging, methods=['POST'])
        self.flsk.add_url_rule(
    '/stream/values',
    'stream_values',
    view_func=lambda: Response(self.sse_values()(), mimetype='text/event-stream'),
    methods=['GET']
)
        self.flsk.add_url_rule(
            '/stream/digit',
            'stream_digit',
            view_func=lambda: Response(self.sse_digit_display()(), mimetype='text/event-stream'),
            methods=['GET']
        )
        self.flsk.add_url_rule(
            '/stream/piezo',
            'stream_piezo',
            view_func=lambda: Response(self.sse_piezo_values()(), mimetype='text/event-stream'),
            methods=['GET']
        )


    def __del__(self):
        try:
            self.cntrl.stop()
            self.flsk.shutdown_server()
        except:
            pass
        
    def run(self, host='127.0.0.1', port=8080, debug=True):
        #signal.signal(signal.SIGTERM, self.flsk.shutdown_server)
        #signal.signal(signal.SIGINT, self.flsk.shutdown_server)
        #signal.signal(signal.SIGHUP, signal.SIG_IGN)
    
        ControlThread = Thread(target = self.cntrl.run)
        ControlThread.start()
        self.flsk.start(host=host, port=port, debug_mode=debug)
        ControlThread.join()
        
    def add(self, *args, **kwars):
        self.cntrl.add(*args, **kwars)

    def index(self, req_data):
        #import os
        #dirpath = os.getcwd()
        #print(dirpath)
        
        _, lst = self.get_list([])
        form_select = ''
        form_indicate = ''
        for l in lst:
            form_select += '<option value ="%s">%s</option>'%(l,l)
            form_indicate +=    '<div class="div_indicator">' + \
                                '%s'%l + \
                                '<span class="stat_indicator" style="" id="res_%s_A" '%l + \
                                'onclick="toggle_activate(%s%s%s)">A</span>'%("'",l,"'") + \
                                '<span class="stat_indicator" style="" id="res_%s_L"'%l + \
                                'onclick="toggle_lock(%s%s%s)">L</span>'%("'",l,"'") + \
                                '</div>'
        html = render_template("index.html", form_select=form_select, form_indicate=form_indicate)
        return True, html
    
    def stop(self, req_data):
        self.__del__()
        html = '<!DOCTYPE html><html><head></head><body>STOP</body></html>'
        return True, html
    def post_pause(self, req_data):
        self.cntrl.pause()
        return True, {}
    
    def post_resume(self, req_data):
        self.cntrl.resume()
        return True, {}  
        
    def post_stop(self, req_data):
        self.__del__()
        return True, {}
    
    def get_list(self, req_data):
        return True, self.cntrl.get_list()

    def get_config(self, req_data):
        return True, self.cntrl.get_config()

    def get_default_config(self, req_data):
        return True, self.cntrl.get_config_default()
    
    def get_parameter(self, req_data):
       # print("Web Server get_parameter called")
        cfg = self.cntrl.get_config()
       # print(cfg,"\n\n")
       # print(req_data,"\n\n")
        if 'name' in req_data:
            name = req_data['name']
        #    print("name :", name,"\n\n")
            if name in cfg:
         #       print (cfg[name],"\n\n")
                return True, cfg[name]
        return False, {}
    
    def set_parameter(self, req_data):
        cfg = self.cntrl.get_config()
        print("LockServer set_parameter: ")
        if 'name' in req_data and 'data' in req_data:
            name = req_data['name']
            data = req_data['data']
            if ('setpoint' in data):
                self.cntrl.set_setpoint(name, data['setpoint'])
            if ('offset' in data):
                self.cntrl.set_offset(name, data['offset'])
            if (('P' in data) and ('I' in data) and ('D' in data)):
                self.cntrl.set_pid(name, data['P'], data['I'], data['D'])
            if ('limits' in data):
                self.cntrl.set_limits(name, data['limits'])
            if ('ramp_rate' in data):
                self.cntrl.set_ramp_rate(name, data['ramp_rate'])
            if (('range_center' in data) and ('range_span' in data)):
                self.cntrl.set_input_range(name, data['range_center'], data['range_span'])
            if ('WM_Exposure' in data):
                self.cntrl.set_wm_exposure(name, data['WM_Exposure'])
                #print(name, " Debug Exposure Config:", data['WM_Exposure'])
            if ('WM_Reading_State' in data):
                self.cntrl.set(name, 'WM_Reading_State', data['WM_Reading_State'])
            return True, {}
            #if name in cfg:
            #    cfg[name] = data
            #    self.cntrl.set_config(cfg)
            #    return True, cfg
        return False, {}
    
    def get_status(self, req_data):
        name = None
        if 'name' in req_data:
            name = req_data['name']
        return True, self.cntrl.get_status(name)

    def get_trace_last(self, req_data):
        if 'name' in req_data:
            name = req_data['name']
            t, y, e, o = self.cntrl.get_trace_last(name)
            return True, {'time':t, 'trace':y, 'error':e, 'output':o}
        else:
            return False,{}

    def get_trace(self, req_data):
        if 'name' in req_data:
            name = req_data['name']
            t_list, y_list, e_list, o_list = self.cntrl.get_trace(name)
            return True, {'time':t_list, 'trace':y_list, 'error':e_list, 'output':o_list}
        else:
            return False,{}
        
    def get_plot(self, req_data):
        if 'name' in req_data:
            name = req_data['name']
            
            cfg = self.cntrl.get_config()
            if name not in cfg:
                return False,{}
            
            t_list, y_list, e_list, o_list = self.cntrl.get_trace(name)
            #setpoint = self.cntrl.get(name,'setpoint')
            #setpoint_list = [setpoint]*len(t_list)
            times, setpoints = self.cntrl.get_trace_setpoints(name)
            setpoint_tolerance = 0.000005 ### 20 MHz
            if len(t_list) != len(y_list):
                return False,{}
            
            ret = parse_data(t_list, y_list, e_list, o_list)
            if ret is None:
                return False,{}

            fig = plot_data(name, t_list[0],  cfg[name], *ret, setpoints, setpoint_tolerance)
            if fig is None:
                return False,{}
            data_svg = export_plot_svg(fig, transparent=True)
            return True, data_svg
        else:
            return False,{}
    
    def post_sampling(self, req_data):
        if 'data' in req_data:
            data = req_data['data']
            return self.cntrl.set_sampling(data), {}
        else:
            return False,{}
        
    def post_trace(self, req_data):
        if 'name' in req_data and 'data' in req_data:
            name = req_data['name']
            data = req_data['data']
            return self.cntrl.set_trace(name, data), {}
        else:
            return False,{}
        
    def post_trace_clear(self, req_data):
        if 'name' in req_data:
            name = req_data['name']
            return self.cntrl.clear_trace(name), {}
        else:
            return False,{}

    def post_offset(self, req_data):
        if 'name' in req_data and 'data' in req_data:
            name = req_data['name']
            data = req_data['data']
            return self.cntrl.set_offset(name, data), {}
        else:
            return False,{}

    def post_setpoint(self, req_data):
        if 'name' in req_data and 'data' in req_data:
            name = req_data['name']
            data = req_data['data']
            return self.cntrl.set_setpoint(name, data), {}
        else:
            return False,{}

    def post_pid(self, req_data):
        if 'name' in req_data and 'data' in req_data:
            name = req_data['name']
            data = req_data['data']
            return self.cntrl.set_pid_dict(name, data), {}
        else:
            return False,{}
        
    def post_limits(self, req_data):
        if 'name' in req_data and 'data' in req_data:
            name = req_data['name']
            data = req_data['data']
            return self.cntrl.set_limits(name, data), {}
        else:
            return False,{}
            
    def post_ramp_rate(self, req_data):
        if 'name' in req_data and 'data' in req_data:
            name = req_data['name']
            data = req_data['data']
            return self.cntrl.set_ramp_rate(name, data), {}
        else:
            return False,{}        
    def post_range(self, req_data):
        if 'name' in req_data and 'data' in req_data:
            name = req_data['name']
            data = req_data['data']
            return self.cntrl.set_input_range(name, *data), {}
        else:
            return False, {}

    def post_reset(self, req_data):
        if 'name' in req_data:
            name = req_data['name']
            return self.cntrl.reset(name), {}
        else:
            return False,{}

    def post_lock(self, req_data):
        if 'name' in req_data:
            name = req_data['name']
            return self.cntrl.lock(name,True), {}
        else:
            return False,{}

    def post_unlock(self, req_data):
        if 'name' in req_data:
            name = req_data['name']
            return self.cntrl.lock(name,False), {}
        else:
            return False,{}
    
    def post_activate(self, req_data):
        if 'name' in req_data:
            name = req_data['name']
            return self.cntrl.activate(name,True), {}
        else:
            return False,{}
    
    def post_deactivate(self, req_data):
        if 'name' in req_data:
            name = req_data['name']
            return self.cntrl.activate(name,False), {}
        else:
            return False,{}

    def post_remove(self, req_data):
        if 'name' in req_data:
            name = req_data['name']
            return self.cntrl.remove(name), {}
        else:
            return False,{}
            
    def post_calibration_settings(self, req_data):
        try:
            wavelength = float(req_data.get("wm_calibration_frequency"))
            interval = int(req_data.get("wm_calibration_interval"))
        except (TypeError, ValueError):
            return False, {"error": "Invalid data format"}
    
        self.calibration_settings["wm_calibration_frequency"] = wavelength
        self.calibration_settings["wm_calibration_interval"] = interval
        self.cntrl.set_global("wm_calibration_frequency", wavelength)
        self.cntrl.set_global("wm_calibration_interval", interval)
    
        print(f"Updated calibration settings: reference frequency={wavelength}, time interval={interval}")
        return True, {}
    
    def get_calibration_settings(self, req_data):
        return True, self.calibration_settings

    def post_csv_logging(self, req_data):
        if "name" not in req_data or "enable" not in req_data:
            return False, {"error": "name und enable erwartet"}
        name = req_data["name"]
        enable = bool(req_data["enable"])
        self.cntrl.enable_csv_logging(name, enable)
        return True, {"logging": enable}
        
    #def sse_values(self, req_data=None):
     #   def generate():
     #       while True:
     #           import time, json
     #           time.sleep(0.1)
     #           data = json.dumps(self.cntrl.latest_values)
     #           yield f"data: {data}\n\n"
     #   return generate

    def sse_values(self, req_data=None):
        def generate():
            while True:
                import time, json
                time.sleep(0.01)
                active_values = {k:v for k,v in self.cntrl.latest_values.items() if self.cntrl.get(k, 'active')}
                piezo_values = self.cntrl.latest_piezo_values
                reference_lock_state = getattr(self.cntrl, 'ReferenceLockState', False)
                freq_650_value = self.cntrl.latest_values.get("650 nm")
                data = json.dumps({
                    "active_values": active_values,
                    "piezo_values": piezo_values,
                    "reference_lock_state": reference_lock_state,
                    "freq_650_value": freq_650_value 
                })
                yield f"data: {data}\n\n"
        return generate

    def sse_digit_display(self, req_data=None):
        def generate():
            while True:
                import time, json
                time.sleep(0.5)
                
                # Prüfen, ob der Controller pausiert ist
                if getattr(self.cntrl, 'pause_event', None) and not self.cntrl.pause_event.is_set():
                    wm_value = getattr(getattr(self, 'wm_calib', None), 'latest_wm_value', None)
                else:
                    # Controller läuft → Wert aus Controller verwenden
                    wm_value = getattr(self.cntrl, 'LastWMValue', None)
                
                data = json.dumps(wm_value)
                yield f"data: {data}\n\n"
        return generate

    
    def sse_piezo_values(self, req_data=None):
        def generate():
            while True:
                import time, json
                time.sleep(0.1)
                piezo_values = self.cntrl.latest_piezo_values  # Dict mit Key:Reglername, Value:Piezo
                yield f"data: {json.dumps(piezo_values)}\n\n"
        return generate


    def post_set_piezo(self, req_data):
        if 'name' in req_data and 'piezo_value' in req_data:
            name = req_data['name']
            try:
                value = float(req_data['piezo_value'])
            except ValueError:
                return False, {"error": "Invalid piezo value"}
    
            try:
                self.cntrl.set_piezo_manual(name, value)
                return True, {}
            except AttributeError:
                return False, {"error": "Piezo setting not supported in controller"}
        else:
            return False, {"error": "name and piezo_value required"}
                
    def post_wm_abort(self, req_data):
        try:
            if hasattr(self, 'wm_calib') and self.wm_calib.initialized:
                # Prüfen, ob die Kalibrierung gerade läuft
                if getattr(self.wm_calib, 'running', False):  # neues Flag 'running'
                    self.wm_calib.abort_calibration()
                    self.wm_calib.running = False
                    return True, {"status": "aborted"}
                else:
                    return False, {"error": "Calibration not running"}
            return False, {"error": "Wavemeter not initialized"}
        except Exception as e:
            return False, {"error": str(e)}

    def post_wm_initialize(self, req_data):
        try:
            if not hasattr(self, 'wm_calib'):
                print("no attribute")
                self.wm_calib = WavemeterCalibration(self.wvm, self.cntrl)
    
            self.wm_calib.initialize()
            print("initializing")
            # Kalibrierung läuft jetzt
            self.wm_calib.running = True
    
            if self.wm_calib.initialized:
                print("initialized")
                return True, {"status": "initialized"}
            else:
                print("Initialization failed")
                return False, {"error": "Initialization failed"}
        except Exception as e:
            print("Calibration INit exceptiopn")
            return False, {"error": str(e)}
            
    def post_wm_calibrate(self, req_data):
        try:
            if not hasattr(self, 'wm_calib') or not self.wm_calib.initialized:
                return False, {"error": "Wavemeter not initialized"}
            self.wm_calib.calibrate()
            return True, {"status": "calibration_done"}
        except Exception as e:
            return False, {"error": str(e)}

 #   def post_wm_calibrate(self, req_data):
 #       try:
 #           if not hasattr(self, 'wm_calib') or not self.wm_calib.initialized:
 #               return False, {"error": "Wavemeter not initialized"}
 #           self.wm_calib.calibrate()
 #           return True, {"status": "calibration_done"}
 #       except Exception as e:
 #           return False, {"error": str(e)}