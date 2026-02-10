import socket
import time
import random
import string
import netifaces

def randomString(stringLength):
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for i in range(stringLength))

class Discovery:
    def __init__(self, bind_ip = '', port_listen=37020, port_talk=44444):
        self.bind_ip = bind_ip
        self.port_listen = port_listen
        self.port_talk = port_talk
        self.run = False
        self.sck = None
    
    def __del__(self):
        self.stop()
        
    def __setup(self):
        if self.sck is None:
            self.sck = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) # UDP
            self.sck.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            self.sck.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def __close(self):
        if self.sck is not None:
            self.sck.close()
            self.sck = None
        
    def hostname(self):
        return socket.gethostname()
    
    def list_addrs(self):
        ips = []
        for interface in netifaces.interfaces():
            addresses = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addresses:
                for link in addresses[netifaces.AF_INET]:
                    ips.append(link['addr'])
        return ips
        
    def discover(self, info='', timeout=.5):
        if self.sck is None:
            self.__setup()
            address = (self.bind_ip, self.port_talk)
            self.sck.bind(address)
            #print('Listen on %s:%i'%address)

            # Set a timeout so the socket does not block
            # indefinitely when trying to receive data.
            self.sck.settimeout(timeout)

            list_response = []
            message = bytes(info, 'utf-8')
            self.sck.sendto(message, ('<broadcast>', self.port_listen))

            self.run = True
            while self.run:
                try:
                    data, addr = self.sck.recvfrom(1024)
                    #print("respone from %s: %s"%(addr, data))
                    resp = data.decode().split(':')
                    ret_name = ''
                    ret_port = int(-1)
                    ret_info = ''
                    if len(resp)>2:
                        ret_name = resp[0]
                        ret_port = int(resp[1])
                        ret_info = resp[2]
                    list_response.append([addr, ret_name, ret_port, ret_info])
                except socket.timeout:
                    break

            self.__close()
            return list_response
        else:
            raise Exception('Socket in-use')

    def echo(self, info=''):
        if self.sck is None:
            self.__setup()
            address = (self.bind_ip, self.port_listen)
            self.sck.bind(address)
            print('Listen on %s:%i'%address)
            info = bytes(info, 'utf-8')

            self.run = True
            while self.run:
                try:
                    data, addr = self.sck.recvfrom(1024)
                    msg = info+b':'+data
                    #msg = bytes('%s%s'%(info,data.decode("utf-8")), 'utf-8')
                    self.sck.sendto(msg, addr)
                    #print('\treceived message "%s"'%(data))
                    print('\treply to %s:%i'%addr)
                    #print('\t"%s"'%msg)
                except OSError:
                    break
            self.__close()
        else:
            raise Exception('Socket in-use')

    def stop(self):
        self.run = False
        self.__close()

if __name__ == '__main__':
    duty = 'server'
    
    import sys
    if len(sys.argv)>1:
        duty = sys.argv[1]
    
    dis = Discovery()
    
    if duty=='server':
        name = dis.hostname()
        http_port = 8080
        info = '%s:%i'%(name, http_port)
        dis.echo(info=info)
    elif duty=='client':
        print('Discover')
        info = randomString(10)
        resp = dis.discover(info=info)
        for r in resp:
            ret_addr = r[0]
            ret_name = r[1]
            ret_port = r[2]
            ret_info = r[3]
            if ret_info == info:
                print('\t%s:%i %s:%i'%(*ret_addr, ret_name, ret_port))
