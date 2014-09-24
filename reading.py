import re
import io
import string

class PDFStreamRead:
  def __init__(self):
    self.stops = [[None]]

  def readStream(self, stream):
    with io.BytesIO(stream) as self.pdf: return self.getObject()

  def getObject(self):
    objs, obj, eol = [], [], []
    while True:
      char = self.getToken()
      if len(objs) <= 0 and char in self.stops:
        if char == ['stream']: obj[-1]['%stream'] = self.pdf.tell()
        return obj
      assert char != [None], "Incomplete or truncated object."
      if char == ['R']:
        gen = obj.pop()
        idx = obj.pop()
        obj.append((idx, gen, 'R'))
      elif char in (['['], ['<<'], ['BI']):
        eol.append([{'[':']', '<<':'>>', 'BI':'ID'}[char[0]]])
        objs.append(obj)
        obj = []
      elif len(eol) > 0 and char == eol[-1]:
        endl = eol.pop()
        if endl != [']']:
          assert len(obj)%2 == 0, "Mismatched dictionary pairs."
          objx = {}
          while len(obj) > 0:
            key = obj.pop(0)
            val = obj.pop(0)
            assert isinstance(key, str) and key[0] == '/', "Key not a name."
            objx[key[1:]] = val
        else: objx = obj
        if endl == ['ID']:
          tmps = []
          if self.pdf.read(1) not in string.whitespace: self.pdf.seek(-1, 1)
          while re.match(r'\sEI\s', ''.join(tmps[-4:])) == None:
            tmps.append(self.pdf.read(1))
          objx['%stream'] = ''.join(tmps[:-4])
        obj = objs.pop()
        obj.append(objx)
      elif isinstance(char, list) and len(char) == 1:
        tmp = [char[0]]
        while len(obj) > 0:
          if isinstance(obj[-1], tuple): break
          if isinstance(obj[-1], dict):
            if '%stream' in obj[-1] and 'Length' not in obj[-1]: break
          tmp.append(obj.pop())
        tmp.reverse()
        obj.append(tuple(tmp))
      else: obj.append(char)

  def getToken(self):
    char = self.pdf.read(1)
    while True:
      while char != '' and char in string.whitespace: char = self.pdf.read(1)
      if char == '': return [None]
      elif char == '%':
        while char not in '\r\n': char = self.pdf.read(1)
        continue
      elif char in '+-.0123456789': return self.getNumber(char)
      elif char == '(': return self.getString()
      elif char == '/': return self.getName()
      elif char in '[]': return [char]
      elif char == '<':
        char = self.pdf.read(1)
        if char in string.hexdigits: return self.getHexString(char)
        assert char == '<', "Invalid dictionary head or hex string."
        return ['<<']
      elif char == '>':
        assert self.pdf.read(1) == '>', "Invalid dictionary tail."
        return ['>>']
      else: return self.getKeyword(char)

  def getKeyword(self, char):
    obj = []
    while char not in string.whitespace and char not in '()<>[]{}/%':
      obj.append(char)
      char = self.pdf.read(1)
    assert len(obj) > 0, "Invalid keyword: '" + char + "'."
    self.pdf.seek(-1, 1)
    retval = [''.join(obj)]
    if retval == ['null']: return None
    elif retval == ['true']: return True
    elif retval == ['false']: return False
    else: return retval

  def getNumber(self, char):
    obj = [char]
    char = self.pdf.read(1)
    while char in '.0123456789':
      obj.append(char)
      char = self.pdf.read(1)
    self.pdf.seek(-1, 1)
    obj = ''.join(obj)
    cnt = obj.count('.')
    assert cnt in [0, 1], "Too many decimal points."
    if cnt == 0: return int(obj)
    else: return float(obj)

  def getName(self):
    obj = ['/']
    char = self.pdf.read(1)
    while char not in string.whitespace and char not in '()<>[]{}/%':
      obj.append(char)
      char = self.pdf.read(1)
    self.pdf.seek(-1, 1)
    return ''.join(obj)

  def getString(self):
    obj = []
    pcount = 0
    while True:
      char = self.pdf.read(1)
      if char in '\r\n':
        obj.append('\n')
        tmp = char
        char = self.pdf.read(1)
        if char not in '\r\n' or char == tmp: self.pdf.seek(-1, 1)
      elif char == '(':
        pcount += 1
        obj.append(char)
      elif char == ')':
        if pcount <= 0: break
        else:
          pcount -= 1
          obj.append(char)
      elif char == '\\':
        char = self.pdf.read(1)
        if char in 'nrtbf': obj.append(('\\' + char).decode('string_escape'))
        elif char in '\r\n':
          tmp = char
          char = self.pdf.read(1)
          if char not in '\r\n' or char == tmp: self.pdf.seek(-1, 1)
        elif char in string.digits:
          tmp = ['\\', char]
          char = self.pdf.read(1)
          if char in string.digits:
            tmp.append(char)
            char = self.pdf.read(1)
            if char in string.digits: tmp.append(char)
            else: self.pdf.seek(-1, 1)
          else: self.pdf.seek(-1, 1)
          obj.append(''.join(tmp).decode('string_escape'))
        else: obj.append(char)
      else: obj.append(char)
    return ''.join(obj)

  def getHexString(self, char):
    obj = [char]
    while char in string.hexdigits:
      obj.append(char)
      char = self.pdf.read(1)
    assert char == '>', "Invalid hex string."
    if len(obj)%2 != 0: obj.append('0')
    return ''.join(obj).decode('hex')

class PDFRead(PDFStreamRead):
  def __init__(self):
    PDFStreamRead.__init__(self)
    self.stops = [['stream'], ['endobj'], ['startxref']]

  def readPDF(self, fname):
    with open(fname, 'rb') as self.pdf:
      version = self.getVersion()
      self.pdf.seek(self.getXrefOffset())
      trailer = self.getTrailer()
      self.deepDereference(trailer)
      if 'Version' in trailer['Root']:
        trailversion = float(trailer['Root']['Version'][1:])
        if version > trailversion:
          trailer['Root']['Version'] = '/' + str(version)
      else: trailer['Root']['Version'] = '/' + str(version)
    return trailer

  def getVersion(self):
    header = self.pdf.read(8)
    assert header[:5] == '%PDF-', "Invalid header."
    return float(header[5:])

  def getXrefOffset(self):
    pdfpos = -1
    buf = 'startxref0#0%%EOF0'
    bufpos = len(buf) - 1
    xref = []
    while bufpos >= 0:
      self.pdf.seek(pdfpos, 2)
      char = self.pdf.read(1)
      if buf[bufpos] == '0':
        if char in string.whitespace: pdfpos -= 1
        else: bufpos -= 1
      elif buf[bufpos] == '#':
        if char in string.digits:
          xref.append(char)
          pdfpos -= 1
        else: bufpos -= 1
      elif buf[bufpos] == char:
        bufpos -= 1
        pdfpos -= 1
      else: assert False, "Invalid trailer."
    xref.reverse()
    return int(''.join(xref))

  def getTrailer(self):
    maxref = 0
    xrefs = []
    trailer = None
    while True:
      assert self.getToken() == ['xref'], "Invalid xref head."
      xref = []
      idx = self.getToken()
      while idx != ['trailer']:
        dat = []
        cnt = self.getToken()
        if maxref < idx + cnt: maxref = idx + cnt
        for _ in range(cnt):
          val = self.getToken()
          gen = self.getToken()
          typ = self.getToken()
          dat.append((val, gen, typ[0]))
        xref.append((idx, dat))
        idx = self.getToken()
      xrefs.append(xref)
      obj = self.getObject()[0]
      if trailer == None: trailer = obj
      if 'Prev' in obj: self.pdf.seek(obj['Prev'])
      else: break
    self.xref = [(None, None)]*maxref
    while len(xrefs) > 0:
      for idx, group in xrefs.pop():
        for offset, (val, gen, typ) in enumerate(group):
          if self.xref[idx + offset][1] > gen: continue
          if typ == 'n': self.xref[idx + offset] = (val,), gen
          else: self.xref[idx + offset] = None, gen
    return trailer

  def deepDereference(self, obj):
    objs = [obj]
    while len(objs) > 0:
      obj = objs.pop(0)
      if isinstance(obj, dict): iratr = obj
      else: iratr = range(len(obj))
      for idx in iratr:
        if isinstance(obj[idx], tuple):
          i, m, k = obj[idx]
          x, n = self.xref[i]
          assert k == 'R', "Invalid object ref."
          if m != n: obj[idx] = None
          elif isinstance(x, tuple):
            self.pdf.seek(x[0])
            self.xref[i] = self.getIndirectObject(i, m), n
            obj[idx] = self.xref[i][0]
          else:
            obj[idx] = x
            continue
        if isinstance(obj[idx], (list, dict)): objs.append(obj[idx])
      if isinstance(obj, dict) and '%stream' in obj: self.getStream(obj)

  def getIndirectObject(self, eref, egen):
    ref = self.getToken()
    gen = self.getToken()
    obj = self.getToken()
    assert (ref, gen, obj) == (eref, egen, ['obj']), "Invalid object ref."
    return self.getObject()[0]

  def getStream(self, obj):
    self.pdf.seek(obj['%stream'])
    char = self.pdf.read(1)
    if char != '\n': char = self.pdf.read(1)
    stream = self.pdf.read(obj['Length'])
    char = self.pdf.read(1)
    while char in string.whitespace: char = self.pdf.read(1)
    char += self.pdf.read(8)
    assert char == 'endstream', "Invalid stream tail."
    assert self.getToken() == ['endobj'], "Invalid object tail."
    if 'F' in obj:
      with open(obj['F'], 'rb') as fstream: stream = fstream.read()
    obj['%stream'] = stream
