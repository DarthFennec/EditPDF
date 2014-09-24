import win
from qtstreamtypes import QtPDFStreamBuilder
from reading import PDFStreamRead
from filters import decodeStream
from PyQt4 import QtCore, QtGui

def getProp(doc, keys, default):
  for key in keys:
    if key in doc: doc = doc[key]
    else: return default
  return doc

def setPosition(obj, matrix):
  a, b = matrix.m11(), matrix.m12()
  c, d = matrix.m21(), matrix.m22()
  e, f = matrix.dx(), matrix.dy()
  x, y = e, f
  #x = (c*f - d*e)/(b*c - a*d)
  #y = (b*e - a*f)/(b*c - a*d)
  obj.setTransform(QtGui.QTransform(a, b, 0, c, d, 0, 0, 0))
  obj.setPos(x, -y)

class QtPDFDocument(QtGui.QGraphicsItem):
  def __init__(self, w, fname, ddict):
    QtGui.QGraphicsItem.__init__(self, None, w.gfx)
    self.width, self.height = 0, 0
    self.parent = None
    self.ident = fname[1 + fname.rfind('/'):]
    self.props = win.PropTree(self.getProps(ddict))
    self.child = []
    index = 0
    group, groups = ddict['Root']['Pages']['Kids'], []
    while len(group) > 0 or len(groups) > 0:
      child = group.pop(0)
      if child['Type'] == '/Page':
        self.child.append(QtPDFPage(w, self, index, child))
        index += 1
      else:
        groups.append(group)
        group = child['Kids']
      while len(group) <= 0 and len(groups) > 0: group = groups.pop()
    self.setLayout()

  def getProps(self, ddict):
    props = {}
    props['Version'] = ddict['Root']['Version']
    props['Layout'] = getProp(ddict, ['Root', 'PageLayout'], '/SinglePage')
    props['Mode'] = getProp(ddict, ['Root', 'PageMode'], '/UseNone')
    props['Language'] = getProp(ddict, ['Root', 'Lang'], '')
    return props

  def setLayout(self):
    top = 0
    self.width = 0
    for child in self.child: top = child.setLayout(top)
    self.height = top

  def boundingRect(self):
    return QtCore.QRectF(-self.width/2, 0, self.width, self.height)

  def paint(self, painter, option, widget):
    pass

class QtPDFPage(QtGui.QGraphicsItem):
  def __init__(self, w, parent, idx, ddict):
    QtGui.QGraphicsItem.__init__(self, parent, w.gfx)
    self.width, self.height, self.x, self.y = 0, 0, 0, 0
    self.getInherit(ddict, 'Resources', None)
    self.getInherit(ddict, 'MediaBox', None)
    self.getInherit(ddict, 'CropBox', ddict['MediaBox'])
    self.getInherit(ddict, 'Rotate', 0)
    self.parent = parent
    self.ident = 'Page ' + str(idx)
    self.props = win.PropTree(self.getProps(ddict))
    res = ddict['Resources']
    conts = ddict['Contents']
    if not isinstance(conts, list): conts = [conts]
    cstream = []
    for cont in conts:
      if 'F' not in cont and 'Filter' in cont:
        cstream.append(decodeStream(cont['%stream'], cont['Filter']))
      elif 'F' in cont and 'FFilter' in cont:
        cstream.append(decodeStream(cont['%stream'], cont['FFilter']))
      else: cstream.append(cont['%stream'])
    stream = PDFStreamRead().readStream(' '.join(cstream))
    child = QtPDFStreamBuilder().buildStream(self, w.gfx, res, stream)
    if len(child) > 0: self.child = child

  def getInherit(self, ddict, prop, default):
    gdict = ddict
    while 'Parent' in gdict:
      if prop in gdict:
        if ddict is not gdict: ddict[prop] = gdict[prop]
        return
      else: gdict = gdict['Parent']
    assert default != None, "Required property not provided."
    ddict[prop] = default

  def getProps(self, ddict):
    props = {}
    props['Media Box'] = ddict['MediaBox']
    props['Crop Box'] = ddict['CropBox']
    props['Bleed Box'] = getProp(ddict, ['BleedBox'], props['Crop Box'])
    props['Trim Box'] = getProp(ddict, ['TrimBox'], props['Crop Box'])
    props['Art Box'] = getProp(ddict, ['ArtBox'], props['Crop Box'])
    return props

  def setLayout(self, top):
    rect = self.props.data[self.props.tags.index('Media Box')].data
    self.width = rect[2] - rect[0]
    self.height = rect[3] - rect[1]
    if self.parent.width < self.width: self.parent.width = self.width
    self.x = -self.width/2
    self.y = top + self.height
    self.setPos(self.x, self.y)
    return self.y

  def boundingRect(self):
    return QtCore.QRectF(0, -self.height, self.width, self.height)

  def paint(self, painter, option, widget):
    painter.setPen(QtCore.Qt.black)
    painter.setBrush(QtGui.QBrush(QtCore.Qt.white))
    painter.drawRect(self.boundingRect())

class QtPDFForm(QtGui.QGraphicsItem):
  def __init__(self, par, sc, state, image):
    QtGui.QGraphicsItem.__init__(self, par, sc)
    self.parent = par
    self.ident = 'Image'
    setPosition(self, state['ctm'])

  def boundingRect(self):
    return QtCore.QRectF(0, 0, 0, 0)

  def paint(self, painter, option, widget):
    pass

class QtPDFImage(QtGui.QGraphicsItem):
  def __init__(self, par, sc, state, image):
    QtGui.QGraphicsItem.__init__(self, par, sc)
    self.parent = par
    self.ident = 'Image'
    self.img = QtGui.QPixmap()
    self.img.loadFromData(image['%stream'])
    self.targetRect = QtCore.QRectF(0, -1, 1, 1)
    self.sourceRect = QtCore.QRectF(self.img.rect())
    setPosition(self, state['ctm'])

  def boundingRect(self):
    return self.targetRect

  def paint(self, painter, option, widget):
    painter.drawPixmap(self.targetRect, self.img, self.sourceRect)

class QtPDFShader(QtGui.QGraphicsItem):
  def __init__(self, par, sc, state):
    QtGui.QGraphicsItem.__init__(self, par, sc)
    self.parent = par
    self.ident = 'Shader'
    setPosition(self, state['ctm'])

  def boundingRect(self):
    return QtCore.QRectF(0, 0, 0, 0)

  def paint(self, painter, option, widget):
    pass

class QtPDFPostScript:
  def __init__(self, par):
    self.parent = par
    self.ident = 'PostScript Object'

class QtPDFPath(QtGui.QGraphicsItem):
  def __init__(self, par, sc, marks, state, stroke, fill, clip):
    QtGui.QGraphicsItem.__init__(self, par, sc)
    self.parent = par
    self.ident = 'Path'
    setPosition(self, state['ctm'])
    if stroke != None: self.brect = stroke.boundingRect()
    elif fill != None: self.brect = fill.boundingRect()
    elif clip != None: self.brect = clip.boundingRect()
    else: self.brect = QtCore.QRectF(0, 0, 0, 0)
    self.path = fill if stroke == None else stroke
    self.setDrawInfo(state, stroke, fill)

  def setDrawInfo(self, st, stroke, fill):
    if fill == None: self.brush = QtGui.QBrush()
    else: self.brush = QtGui.QBrush(st['bclr'][1])
    if stroke == None:
      self.pen = QtGui.QPen(QtCore.Qt.NoPen)
      return
    brush = QtGui.QBrush(st['fclr'][1])
    if st['lcap'] == 0: cap = QtCore.Qt.FlatCap
    elif st['lcap'] == 1: cap = QtCore.Qt.RoundCap
    elif st['lcap'] == 2: cap = QtCore.Qt.SquareCap
    if st['ljoin'] == 0: join = QtCore.Qt.MiterJoin
    elif st['ljoin'] == 1: join = QtCore.Qt.RoundJoin
    elif st['ljoin'] == 2: join = QtCore.Qt.BevelJoin
    self.pen = QtGui.QPen(brush, st['lwidth'], QtCore.Qt.SolidLine, cap, join)
    self.pen.setMiterLimit(st['miter']/2)
    if len(st['dash'][0]) > 0:
      if len(st['dash'][0])%2 == 0: dash = st['dash'][0]
      else: dash = st['dash'][0]*2
      self.pen.setDashPattern(dash)
      self.pen.setDashOffset(st['dash'][1])

  def boundingRect(self):
    return self.brect

  def paint(self, painter, option, widget):
    if self.path != None:
      painter.setPen(self.pen)
      painter.setBrush(self.brush)
      painter.drawPath(self.path)

class QtPDFText(QtGui.QGraphicsItem):
  def __init__(self, par, sc, marks, state, lines):
    QtGui.QGraphicsItem.__init__(self, par, sc)
    self.parent = par
    self.ident = 'Text Box'
    self.lines = lines
    setPosition(self, state['ctm'])

  def boundingRect(self):
    return QtCore.QRectF(0, 0, 0, 0)

  def paint(self, painter, option, widget):
    state = {}
    for line in self.lines:
      state = line.paint(painter, state)

class QtPDFTextPart:
  def __init__(self, marks, state, linem, offset, text):
    self.text = text
    self.matrix = linem
    self.offset = offset
    self.font, self.size = state['tfont']
    self.cspace = state['tcspace']
    self.wspace = state['twspace']
    self.scale = state['tscale']
    self.rise = state['trise']
    self.fill = state['tmode'] in (0, 2, 4, 6)
    self.stroke = state['tmode'] in (1, 2, 5, 6)
    self.clip = state['tmode'] in (4, 5, 6, 7)
    self.fcolor = state['fclr'][1]
    self.bcolor = state['bclr'][1]

  def paint(self, painter, state):
    if self.matrix != None:
      a, b = self.matrix.m11(), self.matrix.m12()
      c, d = self.matrix.m21(), self.matrix.m22()
      e, f = self.matrix.dx(), self.matrix.dy()
      matr = QtGui.QTransform(a, b, 0, c, d, 0, 0, 0)
      pos = e, -f
    else:
      # do something else

class QtPDFMark:
  def __init__(self, par, tag, props):
    self.parent = par
    self.ident = 'Marked Content'
