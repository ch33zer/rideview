import sys
from itsdangerous import base64_decode
import zlib

def decode_cookie(cookie):
  try:
      compressed = False
      payload = cookie

      if payload.startswith('.'):
          compressed = True
          payload = payload[1:]

      data = payload.split(".")[0]

      data = base64_decode(data)
      if compressed:
          data = zlib.decompress(data)

      return data.decode("utf-8")
  except Exception as e:
      return "[Decoding error: are you sure this was a Flask session cookie? {}]".format(e)
if len(sys.argv) != 2:
	print("Provide filename")
	sys.exit(1)
print(decode_cookie(sys.argv[1]))