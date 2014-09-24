from PyQt4 import QtCore, QtGui
from qtfont import QtPDFFont
import qttypes

class QtPDFStreamBuilder:
  def __init__(self):
    self.type3 = None
    self.marks = []
    istate = {}
    istate['compat'] = 0
    istate['ctm'] = QtGui.QMatrix()
    istate['fclr'] = '/DeviceGray', QtGui.QColor(QtCore.Qt.black)
    istate['bclr'] = '/DeviceGray', QtGui.QColor(QtCore.Qt.black)
    istate['tcspace'] = 0
    istate['twspace'] = 0
    istate['tscale'] = 100
    istate['tlead'] = 0
    istate['tfont'] = None, 0
    istate['tmode'] = 0
    istate['trise'] = 0
    istate['tko'] = False
    istate['lwidth'] = 1
    istate['lcap'] = 0
    istate['ljoin'] = 0
    istate['miter'] = 10
    istate['dash'] = [], 0
    istate['intent'] = '/RelativeColorimetric'
    istate['flat'] = 1
    self.state = [istate]

  def buildStream(self, par, scene, resources, stream):
    child = []
    self.scene = scene
    self.resources = resources
    while len(stream) > 0:
      cmd = stream.pop(0)
      st = self.state[-1]
      c = cmd[-1] if isinstance(cmd, tuple) else None
      if isinstance(cmd, dict): child.append(self.buildInlineImg(par, cmd, st))
      elif self.updateState(par, child, st, c, cmd): pass
      elif c == 'q': self.state.append(st.copy())
      elif c == 'Q': self.state.pop()
      elif c == 'cm': st['ctm'] = st['ctm']*QtGui.QMatrix(*cmd[:6])
      elif c == 'm': child.append(self.buildPath(par, cmd, st, stream))
      elif c == 're': child.append(self.buildPath(par, cmd, st, stream))
      elif c == 'BT': child.append(self.buildText(par, child, st, stream))
      elif c == 'Do': child.append(self.buildXObject(par, cmd[0], st))
      elif c == 'sh': child.append(self.buildShader(par, cmd[0], st))
      elif c == 'd0': self.type3 = True, cmd[0], None
      elif c == 'd1': self.type3 = False, cmd[0], list(cmd[2:6])
      elif st['compat'] > 0: pass
      else: raise Exception("Unrecognized operator '" + c + "'.")
    return child

  def buildInlineImg(self, par, img, state):
    return qttypes.QtPDFImage(par, self.scene, state, img)

  def buildXObject(self, par, img, state):
    image = self.getProp('XObject', img)
    if image['Subtype'] == '/Form':
      return qttypes.QtPDFForm(par, self.scene, state, image)
    elif image['Subtype'] == '/Image':
      return qttypes.QtPDFImage(par, self.scene, state, image)
    elif image['Subtype'] == '/PS':
      return qttypes.QtPDFPostScript(par)
    else: raise Exception("Unsupported type: '" + image['Subtype'] + "'.")

  def buildShader(self, par, img, state):
    image = self.getProp('Shading', img)
    return qttypes.QtPDFShader(par, self.scene, state)

  def buildPath(self, par, cmd, st, stream):
    pth = QtGui.QPainterPath()
    paint = None
    clip = None
    while paint == None:
      c = cmd[-1]
      if c == 'm': pth.moveTo(cmd[0],-cmd[1])
      elif c == 'l': pth.lineTo(cmd[0],-cmd[1])
      elif c == 'c': pth.cubicTo(cmd[0],-cmd[1],cmd[2],-cmd[3],cmd[4],-cmd[5])
      elif c == 'v':
        pos = pth.currentPosition()
        pth.cubicTo(pos.x(),-pos.y(),cmd[0],-cmd[1],cmd[2],-cmd[3])
      elif c == 'y': pth.cubicTo(cmd[0],-cmd[1],cmd[2],-cmd[3],cmd[2],-cmd[3])
      elif c == 'h': pth.closeSubpath()
      elif c == 're': pth.addRect(cmd[0],-cmd[1],cmd[2],-cmd[3])
      elif c == 'S': paint = True, None, None
      elif c == 's': paint = True, None, pth.closeSubpath()
      elif c == 'f': paint = False, 'nzw', pth.closeSubpath()
      elif c == 'F': paint = False, 'nzw', pth.closeSubpath()
      elif c == 'f*': paint = False, 'eo', pth.closeSubpath()
      elif c == 'B': paint = True, 'nzw', None
      elif c == 'B*': paint = True, 'eo', None
      elif c == 'b': paint = True, 'nzw', pth.closeSubpath()
      elif c == 'b*': paint = True, 'eo', pth.closeSubpath()
      elif c == 'n': paint = False, None, None
      elif c == 'W': clip = 'nzw'
      elif c == 'W*': clip = 'eo'
      elif c == 'BX': st['compat'] += 1
      elif c == 'EX': st['compat'] -= 1
      elif st['compat'] > 0: pass
      else: raise Exception("Unrecognized operator '" + c + "'.")
      if paint == None: cmd = stream.pop(0)
    if clip == None: clp = None
    elif paint[1] == None or clip == paint[1]: clp = pth
    else: clp = QtGui.QPainterPath(pth)
    if paint[1] == 'nzw': pth.setFillRule(QtCore.Qt.WindingFill)
    elif clip == 'nzw': clp.setFillRule(QtCore.Qt.WindingFill)
    stk = pth if paint[0] else None
    if paint[1] == None: pth = None
    return qttypes.QtPDFPath(par, self.scene, self.marks[:], st, stk, pth, clp)

  def buildText(self, par, child, st, stream):
    txt = []
    self.tmatrix = QtGui.QMatrix()
    self.startline = True
    cmd = stream.pop(0)
    while cmd[-1] != 'ET':
      c = cmd[-1]
      if self.buildTextPart(txt, st, c, cmd): pass
      elif self.updateState(par, child, st, c, cmd): pass
      elif st['compat'] > 0: pass
      else: raise Exception("Unrecognized operator '" + c + "'.")
      cmd = stream.pop(0)
    return qttypes.QtPDFText(par, self.scene, self.marks[:], st, txt)

  def buildTextPart(self, txt, st, c, cmd):
    if c == '"': st['twspace'], st['tcspace'] = cmd[0], cmd[1]
    elif c == 'TD': st['tlead'] = -cmd[1]
    if c == 'Tm': self.tmatrix = QtGui.QMatrix(*cmd[:6])
    elif c in ('Td','TD'):
      self.tmatrix = QtGui.QMatrix(self.tmatrix).translate(*cmd[:2])
    elif c in ('T*','"',"'"):
      self.tmatrix = QtGui.QMatrix(self.tmatrix).translate(0, st['tlead'])
    if c in ('Td','TD','Tm','T*'):
      self.startline = True
      return True
    elif c not in ('Tj','TJ',"'",'"'): return False
    mat = self.tmatrix if c in ("'", '"') or self.startline else None
    text = cmd[2] if c == '"' else cmd[0]
    if c == 'TJ':
      off = 0
      for line in text:
        if isinstance(line, str):
          txt.append(qttypes.QtPDFTextPart(self.marks[:], st, mat, off, line))
          mat = self.tmatrix
          off = 0
        else: off += line
    else: txt.append(qttypes.QtPDFTextPart(self.marks[:], st, mat, 0, text))
    self.startline = False
    return True

  def buildMark(self, par, tag, props):
    return qttypes.QtPDFMark(par, tag, props)

  def updateState(self, par, child, st, c, cmd):
    if c == 'w': st['lwidth'] = cmd[0]
    elif c == 'J': st['lcap'] = cmd[0]
    elif c == 'j': st['ljoin'] = cmd[0]
    elif c == 'M': st['miter'] = cmd[0]
    elif c == 'd': st['dash'] = cmd[0], cmd[1]
    elif c == 'ri': st['intent'] = cmd[0]
    elif c == 'i': st['flat'] = cmd[0]
    elif c == 'gs': self.applyState(cmd[0], st)
    elif c == 'Tc': st['tcspace'] = cmd[0]
    elif c == 'Tw': st['twspace'] = cmd[0]
    elif c == 'Tz': st['tscale'] = cmd[0]
    elif c == 'TL': st['tlead'] = -cmd[0]
    elif c == 'Tf': st['tfont'] = self.getFont(cmd[0]), cmd[1]
    elif c == 'Tr': st['tmode'] = cmd[0]
    elif c == 'Ts': st['trise'] = cmd[0]
    elif c == 'CS': self.setColor(st, 'fclr', cmd[0], None)
    elif c == 'cs': self.setColor(st, 'bclr', cmd[0], None)
    elif c == 'SC': self.setColor(st, 'fclr', None, cmd[:-1])
    elif c == 'SCN': self.setColor(st, 'fclr', None, cmd[:-1])
    elif c == 'sc': self.setColor(st, 'bclr', None, cmd[:-1])
    elif c == 'scn': self.setColor(st, 'bclr', None, cmd[:-1])
    elif c == 'G': self.setColor(st, 'fclr', '/DeviceGray', cmd[0])
    elif c == 'g': self.setColor(st, 'bclr', '/DeviceGray', cmd[0])
    elif c == 'RG': self.setColor(st, 'fclr', '/DeviceRGB', cmd[:-1])
    elif c == 'rg': self.setColor(st, 'bclr', '/DeviceRGB', cmd[:-1])
    elif c == 'K': self.setColor(st, 'fclr', '/DeviceCMYK', cmd[:-1])
    elif c == 'k': self.setColor(st, 'bclr', '/DeviceCMYK', cmd[:-1])
    elif c == 'MP': child.append(self.buildMark(par, cmd[0], None))
    elif c == 'DP': child.append(self.buildMark(par, cmd[0], cmd[1]))
    elif c == 'BMC': self.marks.append(self.buildMark(par, cmd[0], None))
    elif c == 'BDC': self.marks.append(self.buildMark(par, cmd[0], cmd[1]))
    elif c == 'EMC': self.marks.pop()
    elif c == 'BX': st['compat'] += 1
    elif c == 'EX': st['compat'] -= 1
    else: return False
    return True

  def applyState(self, gs, st):
    gstate = self.getProp('ExtGState', gs)
    if 'TK' in gstate: st['tko'] = gstate['TK']
    if 'LC' in gstate: st['lcap'] = gstate['LC']
    if 'FL' in gstate: st['flat'] = gstate['FL']
    if 'LJ' in gstate: st['ljoin'] = gstate['LJ']
    if 'ML' in gstate: st['miter'] = gstate['ML']
    if 'LW' in gstate: st['lwidth'] = gstate['LW']
    if 'RI' in gstate: st['intent'] = gstate['RI']
    if 'D' in gstate:
      st['dash'] = gstate['D'][0], gstate['D'][1]
    if 'Font' in gstate:
      st['tfont'] = self.getFont(gstate['Font'][0]), gstate['Font'][1]
    if 'CA' in gstate:
      a = gstate['CA']
      nc = QtGui.QColor(st['fclr'][1])
      nc.setAlphaF(a)
      st['fclr'] = st['fclr'][0], nc
    if 'ca' in gstate:
      a = gstate['ca']
      nc = QtGui.QColor(st['fclr'][1])
      nc.setAlphaF(a)
      st['bclr'] = st['bclr'][0], nc

  def getFont(self, face):
    if isinstance(face, str): face = self.getProp('Font', face)
    if '%memo' not in face: face['%memo'] = QtPDFFont(face)
    return face['%memo']

  def setColor(self, state, index, space, color):
    a = state[index][1].alphaF()
    sp = state[index][0] if space == None else space
    if color == None: col = QtGui.QColor(QtCore.Qt.black)
    elif sp == '/DeviceGray':
      col = QtGui.QColor.fromHsvF(0, 0, color, a)
    elif sp == '/DeviceRGB':
      col = QtGui.QColor.fromRgbF(color[0], color[1], color[2], a)
    elif sp == '/DeviceCMYK':
      col = QtGui.QColor.fromCmykF(color[0], color[1], color[2], color[3], a)
    elif sp == '/CalGray':
      col = QtGui.QColor(QtCore.Qt.black)
    elif sp == '/CalRGB':
      col = QtGui.QColor(QtCore.Qt.black)
    elif sp == '/Lab':
      col = QtGui.QColor(QtCore.Qt.black)
    elif sp == '/ICCBased':
      col = QtGui.QColor(QtCore.Qt.black)
    elif sp == '/Indexed':
      col = QtGui.QColor(QtCore.Qt.black)
    elif sp == '/Pattern':
      col = QtGui.QColor(QtCore.Qt.black)
    elif sp == '/Separation':
      col = QtGui.QColor(QtCore.Qt.black)
    elif sp == '/DeviceN':
      col = QtGui.QColor(QtCore.Qt.black)
    else: col = QtGui.QColor(QtCore.Qt.black)
    state[index] = sp, col

  def getProp(self, prop, name):
    if prop not in self.resources:
      raise Exception(prop + " does not exist in properties set.")
    elif name[0] != '/' or name[1:] not in self.resources[prop]:
      raise Exception("Invalid " + prop + " '" + name + "'.")
    return self.resources[prop][name[1:]]
