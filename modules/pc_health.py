import psutil
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

class PC_health:
    def __init__(self, adr=0, **kwargs):
        self.prev_sent = psutil.net_io_counters().bytes_sent
        self.prev_recv = psutil.net_io_counters().bytes_recv
        self.prev_time = time.time()

    def get_cpu(self):
        return psutil.cpu_percent(interval=1)

    def get_ram(self):
        return psutil.virtual_memory().percent

    def get_disk(self):
        return psutil.disk_usage('/').percent

    def get_byte_sent(self):
        return self.prev_sent

    def get_byte_recv(self):
        return self.prev_recv

    def get_upload_speed(self):
        current_sent = psutil.net_io_counters().bytes_sent
        current_time = time.time()
        upload_speed = (current_sent - self.prev_sent) / (current_time - self.prev_time)  # Bytes per second
        self.prev_sent = current_sent
        self.prev_time = current_time
        return upload_speed

    def get_download_speed(self):
        current_recv = psutil.net_io_counters().bytes_recv
        current_time = time.time()
        download_speed = (current_recv - self.prev_recv) / (current_time - self.prev_time)  # Bytes per second
        self.prev_recv = current_recv
        self.prev_time = current_time
        return download_speed

def data2db(paras, data):
    bucket = "server"
    client = InfluxDBClient(url="http://10.5.78.176:8086", token="dZhmHd0XDDsWPNwZDPe17vZYBZrHy2hkivLdUfcYXP1G8FaNR2oLDQCaDgruFmCsTTvC3sgJC6K-JlF637azuA==", org="BaLi")
    write_api = client.write_api(write_options=SYNCHRONOUS)
    query_api = client.query_api()
    p = Point("server_status").tag("server", "hf_wavemeter_server").field(paras, data)
    write_api.write(bucket=bucket, record=p)
    client.close()
    
    
run = True
dev = PC_health()

while run:
    try:
        data2db("cpu", dev.get_cpu())
        data2db("ram", dev.get_ram())
        data2db("disk", dev.get_disk())
        data2db("upload", dev.get_upload_speed())
        data2db("download", dev.get_download_speed())
        time.sleep(1)
    except:
        pass
