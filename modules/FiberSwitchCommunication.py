import serial
import time
import serial.tools.list_ports


class FiberSwitch:
    def __init__(self, port, baudrate):
        def FindPorts():
            USBports = serial.tools.list_ports.comports()
            for USBPort in USBports:
                print(USBPort.description)
                if "Arduino" in USBPort.description or "CH340" in USBPort.description or "USB Serial" in USBPort.description:
                    print("Arduino found")
                    print(USBPort.device)
                    FoundPort = USBPort.device
                else: 
                    print("No Device found")
            return FoundPort
        self.baudrate = baudrate
        self.port = "COM4"#FindPorts()
        print("Switch Port:  ", self.port)
        try:
            self.ser = serial.Serial(self.port, baudrate, timeout=1)
            self.ser.setDTR(False)       # Deaktiviert Reset
            time.sleep(0.5)
            self.ser.flushInput()
            self.ser.setDTR(True)        # Jetzt aktivieren (aber kein Reset mehr)
            time.sleep(0.5)

            print("Fiber Switch connection set up.")
            # Begrüßungsnachricht vom Arduino lesen
            while self.ser.in_waiting:
                print("Arduino:", self.ser.readline().decode(errors="ignore").strip())

        except serial.SerialException as e:
            print("Connection error:", e)
            self.ser = None

    def SendCommand(self, cmd):
        if self.ser is None or not self.ser.is_open:
            print("Verbindung nicht offen.")
            return

        if cmd not in ['A', 'B', 'C', 'D']:
            print("Invalid Command:", cmd)
            return
        
        try:
            self.ser.write(cmd.encode())
            #print(cmd)
            self.ser.flush()
        except serial.SerialException as e:
            print(f" USB Connection lost: {e}")
            # Verbindung als ungültig markieren
            self.ser = None

        except Exception as e:
            print(f" unexpected error within SendCommand: {e}")

    def try_reconnect(self):

        try:
            test_ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Warte, bis der Arduino nach dem Reset bereit ist
    
            ready = False
            for _ in range(5):
                line = test_ser.readline().decode(errors="ignore").strip()
                if line:
                    print(f"    ↪ Antwort: {line}")
                if "Bereit" in line or "Befehl" in line:
                    ready = True
                    break
    
            if ready:
                print(f"✅ Verbindung wiederhergestellt mit {self.port}.")
                self.ser = test_ser
                return True
            else:
                test_ser.close()
                print(f"⚠️ Keine gültige Antwort vom Arduino auf {self.port}.")
                return False
    
        except Exception as e:
            #print(f"❌ Fehler bei Wiederverbindung mit {self.port}: {e}")
            return False   
    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Verbindung geschlossen.")
