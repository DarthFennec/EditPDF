from PyQt4 import QtCore, QtGui

class QtPDFFont:
  def __init__(self, fdict):
    assert fdict['Type'] == '/Font', "Not a font dictionary."
    self.qtfont = self.buildQtFont(fdict['FontDescriptor'])
    self.dwidth = fdict['FontDescriptor']['MissingWidth']
    self.fchar = fdict['FirstChar']
    self.lchar = fdict['LastChar']
    self.widths = fdict['Widths']

  def buildQtFont(self, ddict):
    assert ddict['Type'] == '/FontDescriptor', "Not a font descriptor."
    fnt = QtGui.QFont()
    fnt.setKerning(False)
    fnt.setFamily(ddict['FontFamily'])
    fnt.setWeight((ddict['FontWeight'] + 200)/12)
    nflags = ddict['Flags']
    sflags = [False]
    for _ in range(19):
      sflags.append(nflags&1 != 0)
      nflags >>= 1
    fnt.setFixedPitch(sflags[1])
    fnt.setItalic(sflags[7])
    if sflags[17]: caps = QtGui.QFont.AllUppercase
    elif sflags[18]: caps = QtGui.QFont.SmallCaps
    else: caps = QtGui.QFont.MixedCase
    fnt.setCapitalization(caps)
    if sflags[4]: style = QtGui.QFont.Decorative
    elif sflags[2]: style = QtGui.QFont.Serif
    else: style = QtGui.QFont.SansSerif
    fnt.setStyleHint(style)
    return fnt

  def paintGlyph(self, painter, pos, glyph):
    painter.drawText(pos, glyph)
    return self.getWidth(glyph)

  def setFont(self, painter):
    painter.setFont(self.qtfont)

  def getWidth(self, glyph):
    char = ord(glyph)
    if self.lchar <= char <= self.fchar:
      return self.widths[char - self.lchar]
    else: return self.dwidth

  def getGlyph(self, glyph):
    if glyph in self.glyphs: return self.glyphs[glyph]
    self.fontdata.load_char(glyph, FT_LOAD_NO_BITMAP)
    outline = self.fontdata.glyph.outline
    path = QtGui.QPainterPath()
    start = 0
    for end in outline.contours:
      points = outline.points[start:end + 1]
      tags = outline.tags[start:end + 1]
      points.append(points[0])
      tags.append(tags[0])
      segments = [[points[0]]]
      for j in range(1, len(points)):
        segments[-1].append(points[j])
        if tags[j] & 1 and j < len(points) - 1: segments.append([points[j]])
      path.moveTo(*points[0])
      for segment in segments:
        if len(segment) == 2: path.lineTo(*segment[1])
        elif len(segment) == 3:
          [(cx, cy), (px, py)] = segment[1:]
          path.quadTo(cx, cy, px, py)
        else:
          for i in range(1, len(segment) - 2):
            cx, cy = segment[i]
            px, py = segment[i + 1]
            path.quadTo(cx, cy, (cx + px)/2.0, (cy + py)/2.0)
          [(cx, cy), (px, py)] = segment[-2:]
          path.quadTo(cx, cy, px, py)
      start = end + 1
    self.glyphs[glyph] = path
    return path
