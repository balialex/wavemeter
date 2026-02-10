import pandas as pd
import os

def get_csv(data, pid_params, setpoint, offset, wm_exposure_time, wm_reading_state, csv_file='data_log.csv'):
    """
    Speichert die Messdaten zusammen mit zusätzlichen Parametern in einer CSV-Datei.
    Wenn die Datei bereits existiert, werden die neuen Daten angehängt.
    
    :param data: Liste oder Array der Messwerte
    :param pid_params: Dictionary der PID Parameter, z.B. {'P':1, 'I':0.5, 'D':0.1}
    :param setpoint: Sollwert für den Messwert
    :param offset: Offset Wert
    :param wm_exposure_time: Belichtungszeit
    :param wm_reading_state: Zustand des Lesens
    :param csv_file: Pfad zur CSV-Datei
    """
    
    # Daten in DataFrame umwandeln
    df_new = pd.DataFrame({
        'data': data,
        'P': pid_params.get('P', None),
        'I': pid_params.get('I', None),
        'D': pid_params.get('D', None),
        'setpoint': setpoint,
        'offset': offset,
        'WM_Exposure': wm_exposure_time,
        'WM_Reading_State': wm_reading_state
    })
    
    # Prüfen, ob die Datei existiert
    if os.path.exists(csv_file):
        # Anhängen, ohne die Kopfzeile erneut zu schreiben
        df_new.to_csv(csv_file, mode='a', index=False, header=False)
    else:
        # Neue Datei erstellen
        df_new.to_csv(csv_file, index=False)

    print(f"{len(data)} Datenpunkte zu '{csv_file}' hinzugefügt.")