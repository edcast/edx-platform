import random
import base64
from Crypto.Cipher import AES
import logging

log = logging.getLogger(__name__)

def encrypt(text, key):
    # edcustom: Generate a random initialization vector (IV)
    iv = ''.join(chr(random.randint(0, 0xFF)) for i in range(16))
    BS = 16  # Block size for AES encryption
    pad = lambda s: s + (BS - len(s) % BS) * chr(BS - len(s) % BS)
    en = AES.new(key=key, mode=AES.MODE_CFB, IV=iv, segment_size=128) # edcustom: Create AES decryption object with CFB mode
    cipher = en.encrypt(pad(text))
    
    # edcustom: Concatenate the ciphertext with the IV and encode using base64
    return base64.urlsafe_b64encode(cipher + b'||/' + iv.encode()).decode()

def decrypt(ciph, key, byte_value):
    ''' 
    edcustom:    
    Removed import unicodedata and its usage as it was not being used for Unicode normalization.
    ciph = unicodedata.normalize('NFKD', ciph).encode('ascii', 'ignore')
    This line is removed because it's not necessary for base64 decoding in Python 3.
    '''
    # edcustom: Decode the ciphertext from base64
    ciph = base64.urlsafe_b64decode(ciph)
    ciph, iv = ciph.split(b'||/') # edcustom: Split the ciphertext and IV
    unpad = lambda s: s[0:-s[-1]]
    de = AES.new(key=key.encode(), mode=AES.MODE_CFB, IV=iv, segment_size=128) # edcustom: Create AES decryption object with CFB mode
    plain = de.decrypt(ciph)

    # edcustom: Strip unwanted characters from the decrypted plaintext
    return plain.rstrip(byte_value.encode()).decode('utf-8', errors='ignore')
