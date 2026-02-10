
function ajax_request(method, url, msg, callback) {
    var xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function() {
        if (xmlHttp.readyState == 4 && xmlHttp.status == 200) {
            try {
                var json_data = JSON.parse(xmlHttp.responseText);
            } catch(err) {
                console.log(err.message + " in " + xmlHttp.responseText);
                return;
            }
            //console.log(json_data);
            callback(json_data);
        }
    };
    xmlHttp.open(method, url, true); // true for asynchronous
    if (method=="POST") {
        xmlHttp.setRequestHeader("Content-type", "application/json");
        var data = JSON.stringify(msg);
        xmlHttp.send(data);
        //console.log(data);
    } else {
        xmlHttp.send()
    }
}

function set_status(status) {
    if (status==true) {
        elem_indicator.style.backgroundColor = "#66ff66";
    } else {
        elem_indicator.style.backgroundColor = "#ff5c33";
    }
    window.setTimeout(function() {elem_indicator.style.backgroundColor = "#f2f2f2";}, 600.);
}

function get_doc_float(status_field) {
    return parseFloat(document.getElementById(status_field).value);
}

function countDecimals(value) {
    if (value==null) return 0;
    if (Math.floor(value) === value) return 0;
    return value.toString().split(".")[1].length || 0; 
}

function set_doc(status_field, value){
    var spinner = document.getElementById(status_field);
    spinner.value = value;
    spinner.step = Math.pow(10.0, -countDecimals(value));
}

function set_doc_text(id, value) {
    const elem = document.getElementById(id);
    if (elem) {
        elem.textContent = value;
    }
}

function request(method, url, msg) {
    var callback = function(response){
        set_status(response.status);
    };
    ajax_request(method, url, msg, callback);
}

function get_url(url){
    request("GET", url, null);
}

function post_url(url, msg){
    request("POST", url, msg);
}

function lock(name) {
    var sel_name = elem_select.value;
    if (!name){
        name = sel_name
    }
    var resp = {"name":name};
    ajax_request("POST", "/post/lock",resp, 
        function(response){
            set_status(response.status);
            if (response.status) {
                update_element_lock((sel_name==name), name, true);
            }
        });
}

function unlock(name) {
    var sel_name = elem_select.value;
    if (!name){
        name = sel_name
    }
    var resp = {"name":name};
    ajax_request("POST", "/post/unlock",resp, 
        function(response){
            set_status(response.status);
            if (response.status) {
                update_element_lock((sel_name==name), name, false);
            }
        });
}

function activate(name) {
    var sel_name = elem_select.value;
    if (!name){
        name = sel_name
    }
    var resp = {"name":name};
    ajax_request("POST", "/post/activate",resp, 
        function(response){
            set_status(response.status);
            if (response.status) {
                update_element_active((sel_name==name), name, true)
            }
        });
}

function deactivate(name) {
    var sel_name = elem_select.value;
    if (!name){
        name = sel_name
    }
    var resp = {"name":name};
    ajax_request("POST", "/post/deactivate",resp, 
        function(response){
            set_status(response.status);
            if (response.status) {
                update_element_active((sel_name==name), name, false)
            }
        });
}

function toggle_activate(name) {
    if (!name){
        name = elem_select.value;
    }
    ajax_request("GET", "/get/status?name="+name, null, 
        function(response){
            var stat = response.data[name].active
            if (stat) {
                deactivate(name);
            } else {
                activate(name);
            }
        });
}

function toggle_lock(name) {
    if (!name){
        name = elem_select.value;
    }
    ajax_request("GET", "/get/status?name="+name, null, 
        function(response){
            var stat = response.data[name].lock
            if (stat) {
                unlock(name);
            } else {
                lock(name);
            }
        });
}

function stop() {
    post_url("/post/stop",null);
}

function plot() {
    var name = elem_select.value;
    ajax_request("GET", "/get/graph?name="+name,null, 
        function(response){
            if (response.status) {
                elem_graph.innerHTML = response.data;
            }
            set_status(response.status);
        });
}

function clear_plot() {
    var resp = {"name":elem_select.value};
    post_url("/post/trace/clear",resp);
    elem_graph.innerHTML = "";
}

function update_element_lock(selected, name, state_lock){
    var color_lock = "#f2f2f2";
    if (state_lock) {
        color_lock = "#66ff66";
    }
    if (selected) {
        document.getElementById("dot_lock").style.backgroundColor = color_lock;
    }
    document.getElementById("res_"+name+"_L").style.backgroundColor = color_lock;
}

function update_element_active(selected, name, state_active){
    var color_active = "#f2f2f2";
    if (state_active) {
        color_active = "#66ff66";
    }
    if (selected) {
        document.getElementById("dot_active").style.backgroundColor = color_active;
    }
    document.getElementById("res_"+name+"_A").style.backgroundColor = color_active;
}


function update_element_indicators(selected, name, state_active, state_lock) {
    update_element_lock(selected, name, state_lock);
    update_element_active(selected, name, state_active);
}

function update_selection() {
    //alert('changed');
    console.log('changed update_selection');
    var name = elem_select.value;
    ajax_request("GET", "/get/parameter?name="+name,null, 
        function(response){
            set_doc("par_setpoint", response.data.setpoint);
            set_doc("par_offset", response.data.offset);
            set_doc("par_P", response.data.P);
            set_doc("par_I", response.data.I);
            set_doc("par_D", response.data.D);
            set_doc("par_center", response.data.range_center);
            set_doc("par_span", response.data.range_span);
            set_doc("par_lower", response.data.limits[0]);
            set_doc("par_upper", response.data.limits[1]);
            set_doc("WM_Exposure", response.data.WM_Exposure);
            set_doc_text("WM_Reading_State", response.data.WM_Reading_State)
            update_element_indicators(true, name, response.data.active, response.data.lock);
        });
}

function update_indicator() {
    var name = elem_select.value;
    console.log("Entered update_indicator()");
    ajax_request("GET", "/get/status",null, 
        function(response){
            for (const key in response.data) {
                const value = response.data[key];
                update_element_indicators((key==name), key, value.active, value.lock);
            }
        });
}


function write_parameter() {
    var name = elem_select.value;
    console.log("Entered write_parameter()");
    ajax_request("GET", "/get/parameter?name="+name,null, 
        function(response){
            console.log("Entered set_parameter() point 1");
            response.name = name;
            console.log("Entered set_parameter() point name");
            response.data.setpoint = get_doc_float("par_setpoint");
            console.log("Entered set_parameter() point setpoint");
            response.data.offset = get_doc_float("par_offset");
            console.log("Entered set_parameter() point offset");
            response.data.P = get_doc_float("par_P");
            console.log("Entered set_parameter() point P");
            response.data.I = get_doc_float("par_I");
            console.log("Entered set_parameter() point I");
            response.data.D = get_doc_float("par_D");
            console.log("Entered set_parameter() point D");
            response.data.limits = [get_doc_float("par_lower"), get_doc_float("par_upper")];
            console.log("Entered set_parameter() point limits");
            response.data.ramp_rate = get_doc_float("ramp_rate");
            console.log("Entered set_parameter() point ramp_rate");
            response.data.range_center = get_doc_float("par_center");
            console.log("Entered set_parameter() point par_center");
            response.data.range_span = get_doc_float("par_span");
            console.log("Entered set_parameter() point par_span");
            response.data.WM_Exposure = get_doc_float("WM_Exposure");
            console.log("Entered set_parameter() point EM_Exposure");
            response.data.WM_Reading_State = get_doc_float("WM_Reading_State");
            console.log("Entered set_parameter() point WM_Reading_State");
            console.log("Entered set_parameter() point 2");
            post_url("/post/parameter",response);
            console.log(response);
        });
}

function manual_set_piezo() {
    const name = elem_select.value;  // aktuell ausgewählter Kanal
    const value = parseFloat(document.getElementById("Set_Piezo").value);

    if (isNaN(value)) {
        alert("Please enter a number.");
        return;
    }

    ajax_request("POST", "/post/unlock", { name: name }, function(response) {
        if (response.status) {
            update_element_lock((elem_select.value === name), name, false);

            ajax_request("POST", "/post/set_piezo", { name: name, piezo_value: value }, function(resp2) {
                set_status(resp2.status);
                if (!resp2.status) {
                    alert("Fehler beim Setzen des Piezo-Werts.");
                }
            });
        } else {
            alert("Unlock fehlgeschlagen – Piezo wird nicht gesetzt.");
        }
    });
}

function wmInitialize() {
    fetch('/post/wm_initialize', { method: 'POST' })
        .then(resp => resp.json())
        .then(data => alert(JSON.stringify(data)));
}

let wmInitialized = false;  // Status-Flag

function wmToggle() {
    if (!wmInitialized) {
        // Initialize
        $.post('/post/wm_initialize', {}, function(response) {
            if (response.status) {
                wmInitialized = true;
                $('#wm_button').text('Abort Calibration');
            } else {
                alert('Initialization failed: ' + JSON.stringify(response.data));
            }
        });
    } else {
        // Abort
        $.post('/post/wm_abort', {}, function(response) {
            if (response.status) {
                wmInitialized = false;
                $('#wm_button').text('WM Initialize Calibration');
            } else {
                alert('Abort failed: ' + JSON.stringify(response.data));
            }
        });
    }
}

function wmCalibrate() {
    fetch('/post/wm_calibrate', { method: 'POST' })
        .then(resp => resp.json())
        .then(data => alert(JSON.stringify(data)));
}


function update_calibration_settings() {
    const frequency = parseFloat(document.getElementById("wm_calibration_frequency").value);
    const interval = parseInt(document.getElementById("wm_calibration_interval").value);

    console.log("Updating calibration settings:", frequency, interval);

    post_url("/post/calibration_settings", {
        wm_calibration_frequency: frequency,
        wm_calibration_interval: interval
    });
}

function plot_timer(){
    var milliseconds = parseFloat(elem_timer.value);
    var btn_plot = document.getElementById("plot_timer_button");
    if (th_timer==null) {
        plot()
        th_timer = window.setInterval(plot, milliseconds);
        btn_plot.value = "Stop Plot Timer";
    } else {
        clearInterval(th_timer);
        th_timer = null;
        btn_plot.value = "Start Plot Timer";
    }
}

function updateChannelTable(data) {
    const tbody = document.querySelector("#channel_table tbody");
    tbody.innerHTML = ""; // alte Zeilen löschen

    for (const [name, value] of Object.entries(data)) {
        const tr = document.createElement("tr");

        const tdName = document.createElement("td");
        tdName.textContent = name;
        tr.appendChild(tdName);

        const tdValue = document.createElement("td");
        tdValue.textContent = value.toFixed(3); // 3 Nachkommastellen
        tr.appendChild(tdValue);

        tbody.appendChild(tr);
    }
}




function doc_ready() {
    elem_graph = document.getElementById("graph");
    elem_select = document.getElementById("selected");
    elem_timer = document.getElementById("par_timer");
    elem_indicator = document.getElementById("res_indicator");

    var select = document.querySelector('#selected');
    select.addEventListener('change', update_selection);
    update_selection();
    
    th_timer = null;

    update_indicator();
    th_indicator = window.setInterval(update_indicator, 5000.);

    ajax_request("GET", "/get/calibration_settings", null, function(response) {
        if (response.status && response.data) {
            set_doc("wm_calibration_frequency", response.data.wm_calibration_frequency);
            set_doc("wm_calibration_interval", response.data.wm_calibration_interval);
        } else {
            console.log("Error loading calibration settings");
        }
    });
}
let loggingActive = false;

function toggle_logging() {
    const name = $("#selected").val();  // aktuell gewählter Regler im Dropdown
    if (!name) {
        alert("Bitte zuerst einen Regler auswählen.");
        return;
    }

    loggingActive = !loggingActive;

    $.ajax({
        url: "/post/csv_logging",
        type: "POST",
        contentType: "application/json",
        data: JSON.stringify({ name: name, enable: loggingActive }),
        success: function(response) {
            if (response.status) {
                $("#logging_button").text(loggingActive ? "Stop Saving CSV" : "Start Saving CSV");
            } else {
                alert("Fehler: " + response.data.error);
                loggingActive = !loggingActive; // zurücksetzen falls Fehler
            }
        },
        error: function() {
            alert("Fehler beim Ansprechen des Logging-Endpunkts.");
            loggingActive = !loggingActive;
        }
    });
}

function startSSE() {
    if (!!window.EventSource) {
        var source = new EventSource("/stream/values");
        source.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                updateChannelTable(data);
                updateReferenceLockState(data.reference_lock_state);
            } catch (err) {
                console.error("Fehler beim Parsen der SSE-Daten:", err, event.data);
            }
        };
        source.onerror = function(err) {
            console.error("SSE-Connection Error:", err);
        };
    } else {
        console.warn("Browser does not support Server-Sent Events!");
    }
}

function updateChannelTable(data) {
    const tbody = document.querySelector("#channel_table tbody");
    if (!tbody) return;

    tbody.innerHTML = "";

    const freqs = data.active_values || {};
    const piezos = data.piezo_values || {};
    const freq650 = data.freq_650_value; 

    for (const [name, value] of Object.entries(freqs)) {
        const tr = document.createElement("tr");

        // Spalte: Channel
        const tdName = document.createElement("td");
        tdName.textContent = name;
        tr.appendChild(tdName);

        // Spalte: Frequency (THz)
        const tdValue = document.createElement("td");
        tdValue.textContent =
            typeof value === "number" ? value.toFixed(6) : value;
        tr.appendChild(tdValue);

        // Spalte: Piezo Voltage (V)
        const tdPiezo = document.createElement("td");
        const piezo = piezos[name];
        tdPiezo.textContent =
            typeof piezo === "number" ? piezo.toFixed(3) : "";
        tr.appendChild(tdPiezo);

        tbody.appendChild(tr);
    }

    // ✅ Neue Zeile für den 650-nm-Laser
    if (typeof freq650 === "number") {
        const tr650 = document.createElement("tr");

        const tdName650 = document.createElement("td");
        tdName650.textContent = "650 nm";
        tr650.appendChild(tdName650);

        const tdFreq650 = document.createElement("td");
        tdFreq650.textContent = freq650.toFixed(6);
        tr650.appendChild(tdFreq650);

        const tdPiezo650 = document.createElement("td");
        tdPiezo650.textContent = ""; // kein Piezo-Wert
        tr650.appendChild(tdPiezo650);

        tbody.appendChild(tr650);
    }
}
// Aktualisiert die Anzeige; hier: THz mit 6 Nachkommastellen
function updateDigitDisplay(value){
    const display = document.getElementById('digit_display');
    const thz = parseFloat(value);
    display.textContent = thz.toFixed(6);
}

// Startet SSE-Stream und aktualisiert das DigitDisplay
function startDigitSSE() {
    if (!!window.EventSource) {
        var source = new EventSource("/stream/digit");
        source.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data); // Erwartet Zahl
                updateDigitDisplay(data);
            } catch (err) {
                console.error("Fehler beim Parsen der Digit-SSE-Daten:", err, event.data);
            }
        };
        source.onerror = function(err) {
            console.error("Digit-SSE-Verbindungsfehler:", err);
        };
    } else {
        console.warn("Browser unterstützt keine Server-Sent Events!");
    }
}

function updateReferenceLockState(isLocked) {
    const indicator = document.getElementById("reference_lock_indicator");
    const text = document.getElementById("reference_lock_text");

    if (!indicator || !text) return;

    if (isLocked === true) {
        indicator.style.backgroundColor = "green";
        text.textContent = "Reference Laser Lock State: LOCKED";
    } else {
        indicator.style.backgroundColor = "red";
        text.textContent = "Reference Laser Lock State: NOT LOCKED";
    }
}


// Client Side Javascript to receive numbers.
//$(document).ready(doc_ready);
$(document).ready(function() {
    doc_ready();
    startSSE();               // dein Channel Table SSE
    startDigitSSE();   // neuer Digit Display SSE
});
