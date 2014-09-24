import zlib

def decodeStream(data, filts):
  if not isinstance(filts, list): filts = [filts]
  for filt in filts:
    if filt == '/FlateDecode': data = zlib.decompress(data)
    else: raise Exception('Error: unsupported stream filter: ' + filt)
  return data

def encodeStream(data, filts):
  if not isinstance(filts, list): filts = [filts]
  else: filts = filts[:]
  filts.reverse()
  for filt in filts:
    if filt == '/FlateDecode': data = zlib.compress(data, 9)
    else: raise Exception('Error: unsupported stream filter: ' + filt)
  return data
