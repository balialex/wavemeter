import socket
import time
import os
import struct
import random
import string
import netifaces
from threading import Thread

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import InvalidToken
from cryptography.hazmat.primitives import hashes

def get_key_from_password(password):
	digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
	digest.update(bytes(password, 'utf-8'))
	return base64.urlsafe_b64encode(digest.finalize())

def randomString(stringLength):
	letters = string.ascii_letters
	return ''.join(random.choice(letters) for i in range(stringLength))
	
def key_random():
	return os.urandom(32)

def key_encode(key):
	return base64.urlsafe_b64encode(key)
	
def key_decode(key):
	return base64.urlsafe_b64decode(key)
	
def key_generate():
	return key_encode(key_random())

class Discovery:
	def __init__(self, bind_ip = '', port_listen=37020, port_talk=44444, key=None, ttl=100):
		self.bind_ip = bind_ip
		self.port_listen = port_listen
		self.port_talk = port_talk
		self.run = False
		self.sck = None
		self.th_discover = None

		if key is None:
			self.crypter = None
		else:
			if (not key) or (len(key_decode(key)) != 32):
				key = key_generate()
				print('Provided key is invalid: generate random key!')
			print('Key: ', key)
			self.crypter = Fernet(key)

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

	def send(self, address_out, message):
		message = bytes(message, 'utf-8')
		if self.crypter is not None:
			message = self.crypter.encrypt(message)
		self.sck.sendto(message, address_out)

	def recv(self):
		message, addr = self.sck.recvfrom(1024)
		try:
			if self.crypter is not None:
				message = self.crypter.decrypt(message)
			message = message.decode('utf-8')
		except InvalidToken:
			print('\treject response from %s:%i'%addr)
			addr = None; message = None;
		return addr, message
		
	def discover(self, info='', timeout=.5):
		if self.sck is None:
			self.__setup()
			address_in = (self.bind_ip, self.port_talk)
			address_out = ('<broadcast>', self.port_listen)
			
			self.sck.bind(address_in)
			print('Listen on %s:%i'%address_in)
			print('Send to %s:%i'%address_out)
			
			# Set a timeout so the socket does not block
			# indefinitely when trying to receive data.
			self.sck.settimeout(timeout)

			list_response = []
			self.send(address_out, info)

			self.run = True
			while self.run:
				try:
					addr, msg = self.recv()
					if addr is not None:
						print("respone from %s:%i: %s"%(*addr, msg))
						resp = msg.split(':')
						if len(resp)>2:
							ret_name = resp[0]
							ret_port = int(resp[1])
							ret_info = resp[2]
							if ret_info==info:
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

			self.run = True
			while self.run:
				try:
					addr, msg = self.recv()
					if addr is not None:
						resp = '%s:%s'%(info,msg)
						self.send(addr, resp)
						print('\treply to %s:%i "%s"'%(*addr,resp))
						if msg=='stop':
							self.stop()
				except OSError:
					break
			self.__close()
		else:
			raise Exception('Socket in-use')

	def stop(self):
		self.run = False
		self.__close()

	def echo_start(self, info=''):
		if self.th_discover is None:
			self.th_discover = Thread(target=self.echo, kwargs={'info': info})
			self.th_discover.start()
		else:
			raise('Echo thread is running!')

	def echo_stop(self):
		if self.th_discover is not None:
			self.stop()
			self.th_discover.join()
			self.th_discover = None
		else:
			raise('Echo thread is not running!')

if __name__ == '__main__':
	duty = 'server'
	
	import sys
	if len(sys.argv)>1:
		duty = sys.argv[1]
	
	#key = key_generate()
	#key = 'pmHtaspH83vpG9Rpa3imXZNjFqcGc0gmJrzMxw8aChs='
	key = get_key_from_password('Mg+=25')
	
	dis = Discovery(key=key)
	#dis = Discovery()
	
	if duty=='server':
		name = dis.hostname()
		http_port = 8080
		info = '%s:%i'%(name, http_port)
		dis.echo(info=info)

	elif duty=='client':
		print('Discover')
		info = randomString(10)
		#info = 'stop'
		if len(sys.argv)>2:
			info = sys.argv[2]
		resp = dis.discover(info=info)
		for r in resp:
			ret_addr = r[0]
			ret_name = r[1]
			ret_port = r[2]
			ret_info = r[3]
			print('\t%s:%i %s:%i'%(*ret_addr, ret_name, ret_port))
