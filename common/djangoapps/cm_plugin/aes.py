import random
import base64
from Crypto.Cipher import AES
import logging

log = logging.getLogger(__name__)

def encrypt(text, key):
    iv = ''.join(chr(random.randint(0, 0xFF)) for i in range(16))
    BS = 16  # block size
    pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
    en = AES.new(key=key, mode=AES.MODE_CFB, IV=iv, segment_size=128)
    cipher = en.encrypt(pad(text))
    return base64.urlsafe_b64encode(cipher + b'||/' + iv.encode()).decode()

def decrypt(ciph, key, byte_value):
    ciph = base64.urlsafe_b64decode(ciph)
    ciph, iv = ciph.split(b'||/')
    unpad = lambda s: s[0:-s[-1]]
    de = AES.new(key=key.encode(), mode=AES.MODE_CFB, IV=iv, segment_size=128)
    plain = de.decrypt(ciph)
    return plain.rstrip(byte_value.encode()).decode('utf-8', errors='ignore')
