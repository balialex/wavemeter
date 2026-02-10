import socket
import time
import os
import struct
import random
import string
import netifaces

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.hmac import HMAC

def get_key_from_password(password):
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(password)
    return base64.urlsafe_b64encode(digest.finalize())

def randomString(stringLength):
	letters = string.ascii_letters
	return ''.join(random.choice(letters) for i in range(stringLength))
	
def key_random():
	return os.urandom(16)

def key_encode(key):
	return base64.urlsafe_b64encode(key)
	
def key_decode(key):
	return base64.urlsafe_b64decode(key)
	
def key_generate():
	return key_encode(key_random())
	
class InvalidToken(Exception):
	pass
	
def hmac_hash(signing_key, data):
	h = HMAC(signing_key, hashes.SHA256(), backend=default_backend())
	h.update(data)
	return h.finalize()
	
def hmac_verify(signing_key, data):
	h = HMAC(signing_key, hashes.SHA256(), backend=default_backend())
	h.update(data[:-32])
	try:
		h.verify(data[-32:])
	except InvalidSignature:
		raise InvalidToken
		
def hmac_extract(data):
	ts, = struct.unpack(">Q", data[0:8])
	body = data[8:-32]
	hmac_token =  data[-32:]
	return ts, body, hmac_token

def hmac_generate(ts, data, signing_key):
	body = struct.pack(">Q", ts) + data
	hmac_token = hmac_hash(signing_key, body)
	return body + hmac_token
	
def timestamp():
	current_time = int(time.time())
	return current_time

class Discovery:
	def __init__(self, bind_ip = '', port_listen=37020, port_talk=44444, signing_key='', ttl=100):
		self.bind_ip = bind_ip
		self.port_listen = port_listen
		self.port_talk = port_talk
		self.run = False
		self.sck = None

		# signing key
		key = key_decode(signing_key)
		if len(key) != 16:
			if signing_key:
				print('Provided key invalid! Generate new key!')
			key = key_random()
		self.signing_key = key
		print('Key: ', key_encode(key))

		# time to live
		self.ttl = ttl

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
			address_in = (self.bind_ip, self.port_talk)
			address_out = ('<broadcast>', self.port_listen)
			
			self.sck.bind(address_in)
			print('Listen on %s:%i'%address_in)
			print('Send to %s:%i'%address_out)
			
			# Set a timeout so the socket does not block
			# indefinitely when trying to receive data.
			self.sck.settimeout(timeout)

			list_response = []

			message = hmac_generate(timestamp(),  bytes(info, 'utf-8'), self.signing_key)
			print(message)
			self.sck.sendto(message, address_out)

			self.run = True
			while self.run:
				try:
					data, addr = self.sck.recvfrom(1024)
					print("respone from %s: %s"%(addr, data))
					if self.verify(data):
						ts, msg, hmac_token = hmac_extract(data)
						if abs(ts-timestamp())<self.ttl:
							resp = msg.decode().split(':')
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
			
	def verify(self, data):
		try:
			hmac_verify(self.signing_key, data)
		except InvalidToken:
			return False
		return True

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
					print('\treceived message "%s"'%(data))
					if self.verify(data):
						ts, msg, hmac_token = hmac_extract(data)
						if abs(ts-timestamp())<self.ttl:
							resp = info+b':'+msg
							message = hmac_generate(timestamp(),  resp, self.signing_key)
							self.sck.sendto(message, addr)
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
	
	#key = key_generate()
	key = 'VL4v42Eu5hG0j2dkawwhqQ=='
	
	dis = Discovery(signing_key=key)
	
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
