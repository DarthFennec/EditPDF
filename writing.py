import io

class PDFStreamWrite:
  def writeStream(self, stream):
    with io.BytesIO() as pdf:
      for item in stream: self.writeVal(pdf, item, [])
      return pdf.getvalue()

  def writeVal(self, pdf, val, vals, noref=False):
    if not noref and val in vals: 
      idx = vals.index(val)
      pdf.write(str(idx + 1) + ' 0 R')
    elif val == None: pdf.write('null')
    elif isinstance(val, bool): pdf.write(str(val).lower())
    elif isinstance(val, (int, long, float)): pdf.write(str(val))
    elif isinstance(val, str):
      if val[0] == '/': pdf.write(val)
      elif self.litstr(val): pdf.write('(' + self.sformat(val) + ')')
      else: pdf.write('<' + val.encode('hex').upper() + '>')
    elif isinstance(val, tuple):
      for item in val[:-1]:
        self.writeVal(pdf, item, vals)
        pdf.write(' ')
      pdf.write(val[-1] + '\n')
    elif isinstance(val, list):
      pdf.write('[ ')
      for item in val:
        self.writeVal(pdf, item, vals)
        pdf.write(' ')
      pdf.write(']')
    elif isinstance(val, dict):
      if '%stream' in val and 'Length' not in val:
        delim = ['BI\n', 'ID\n', '\nEL']
      else: delim = ['<<\n', '>> stream\n', '\nendstream']
      stream = val['%stream'] if '%stream' in val else None
      pdf.write(delim[0])
      for item in val:
        if item[0] != '%':
          pdf.write('/' + item + ' ')
          self.writeVal(pdf, val[item], vals)
          pdf.write('\n')
      if stream != None:
        pdf.write(delim[1])
        pdf.write(stream)
        pdf.write(delim[2])
      else: pdf.write('>>')

  def litstr(self, val):
    pc, npc = 0, 0
    for char in val:
      if ' ' <= char <= '~' or char in '\n\r\t\b\f': pc += 1
      else: npc += 1
    return pc > npc

  def sformat(self, val):
    retval = []
    for char in val:
      if char in '\n\r\t\b\f': retval.append(char.encode('string_escape'))
      elif char in '()\\': retval.append('\\' + char)
      elif ' ' <= char <= '~': retval.append(char)
      else: retval.append('\\' + ('000' + oct(ord(char)))[-3:])
    return ''.join(retval)

class PDFWrite(PDFStreamWrite):
  def writePDF(self, fname, vals, trailer):
    with open(fname, 'wb') as pdf:
      xref = []
      pdf.write('%PDF-' + trailer['Root']['Version'][1:] + '\n')
      pdf.write('%\xE2\xE3\xCF\xD3\n')
      for idx, val in enumerate(vals):
        xref.append(pdf.tell())
        pdf.write(str(idx + 1) + ' 0 obj ')
        self.writeVal(pdf, val, vals, True)
        pdf.write(' endobj\n')
      sxref = pdf.tell()
      pdf.write('xref\n0 ' + str(len(xref) + 1) + '\n')
      pdf.write('0000000000 65535 f \n')
      for offset in xref: pdf.write(str(offset).zfill(10) + ' 00000 n \n')
      pdf.write('trailer\n')
      self.writeVal(pdf, trailer, vals)
      pdf.write('\nstartxref\n' + str(sxref) + '\n%%EOF')
