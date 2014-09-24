from reading import PDFRead
from qttypes import QtPDFDocument
from PyQt4 import QtCore, QtGui

class PDFEditWindow(QtCore.QObject):
  beginInsert = QtCore.pyqtSignal(object, int, int)
  endInsert = QtCore.pyqtSignal()

  def __init__(self, args):
    QtCore.QObject.__init__(self)
    self.docs = []
    self.app = QtGui.QApplication(args)

  def show(self):
    w = QtGui.QMainWindow()
    w.resize(800, 600)
    w.setWindowTitle('PDF Editor')
    objdock = QtGui.QDockWidget('Objects', w)
    propdock = QtGui.QDockWidget('Properties', w)
    self.objview = QtGui.QTreeView(objdock)
    self.propview = QtGui.QTreeView(propdock)
    self.objview.setHeaderHidden(True)
    self.propview.setHeaderHidden(True)
    self.objmodel = PDFObjectModel(self, self.objview)
    self.propmodel = PDFPropertiesModel(self, self.propview)
    self.objview.setModel(self.objmodel)
    self.propview.setModel(self.propmodel)
    objdock.setWidget(self.objview)
    propdock.setWidget(self.propview)
    w.addDockWidget(QtCore.Qt.LeftDockWidgetArea, objdock)
    w.addDockWidget(QtCore.Qt.LeftDockWidgetArea, propdock)
    self.gfx = QtGui.QGraphicsScene(w)
    self.gfxview = QtGui.QGraphicsView(self.gfx, w)
    self.initActions(w)
    self.status = w.statusBar()
    w.setCentralWidget(self.gfxview)
    w.showMaximized()
    return self.app.exec_()

  def initActions(self, w):
    self.objview.selectionModel().selectionChanged.connect(self.select)
    menu = w.menuBar()
    mfile = menu.addMenu('&File')
    aopen = mfile.addAction('&Open', lambda: self.openFile(w))
    tool = w.addToolBar('Toolbar')
    tool.addAction(aopen)

  def openFile(self, w):
    fname = QtGui.QFileDialog.getOpenFileName(w, 'Open', '.', '*.pdf')
    fname = fname.toUtf8().data()
    docxs = PDFRead().readPDF(fname)
    self.insert(None, -1, [QtPDFDocument(self, fname, docxs)])

  def insert(self, parent, index, children):
    sibs = self.docs if parent == None else parent.child
    if index < 0: index += len(sibs) + 1
    self.beginInsert.emit(parent, index, index + len(children) - 1)
    self.docs[index:index] = children
    self.endInsert.emit()

  def select(self, new, old):
    idx = new.indexes()[0].internalPointer()
    if hasattr(idx, 'props'): self.propmodel.dat = idx.props
    else: self.propmodel.dat = self.propmodel.defaultdat
    self.propview.reset()

class PDFObjectModel(QtCore.QAbstractItemModel):
  def __init__(self, win, parent=None):
    QtCore.QAbstractItemModel.__init__(self, parent)
    iRows = lambda x, y, z: self.beginInsertRows(self.modelIndex(x), y, z)
    win.beginInsert.connect(iRows)
    win.endInsert.connect(self.endInsertRows)
    self.win = win

  def index(self, row, column, parent=QtCore.QModelIndex()):
    if parent.isValid():
      par = parent.internalPointer()
      return self.createIndex(row, column, par.child[row])
    return self.createIndex(row, column, self.win.docs[row])

  def modelIndex(self, obj):
    if obj == None: return QtCore.QModelIndex()
    if obj.parent == None: row = self.win.docs.index(obj)
    else: row = obj.parent.child.index(obj)
    return self.createIndex(row, 0, obj)

  def parent(self, child):
    chi = child.internalPointer()
    return self.modelIndex(chi.parent)

  def rowCount(self, parent=QtCore.QModelIndex()):
    if parent.isValid():
      par = parent.internalPointer()
      if hasattr(par, 'child'): return len(par.child)
      return 0
    return len(self.win.docs)

  def columnCount(self, parent=QtCore.QModelIndex()):
    return 1

  def data(self, index, role=QtCore.Qt.DisplayRole):
    if role == QtCore.Qt.DisplayRole: return index.internalPointer().ident
    return QtCore.QVariant()

class PDFPropertiesModel(QtCore.QAbstractItemModel):
  def __init__(self, win, parent=None):
    QtCore.QAbstractItemModel.__init__(self, parent)
    self.win = win
    self.defaultdat = PropTree([])
    self.dat = self.defaultdat

  def index(self, row, column, parent=QtCore.QModelIndex()):
    if parent.isValid():
      par = parent.internalPointer().data[parent.row()]
      return self.createIndex(row, column, par)
    return self.createIndex(row, column, self.dat)

  def parent(self, child):
    chi = child.internalPointer()
    if chi.parent == None: return QtCore.QModelIndex()
    return self.createIndex(chi.parent.data.index(chi), 0, chi.parent)

  def rowCount(self, parent=QtCore.QModelIndex()):
    if parent.isValid():
      par = parent.internalPointer().data[parent.row()]
      if isinstance(par, PropTree): return len(par.data)
      return 0
    return len(self.dat.data)

  def columnCount(self, parent=QtCore.QModelIndex()):
    return 2

  def data(self, index, role=QtCore.Qt.DisplayRole):
    if role == QtCore.Qt.DisplayRole:
      obj = index.internalPointer()
      if index.column() == 0:
        if obj.tags != None:
          return obj.tags[index.row()]
      if index.column() == 1:
        if not isinstance(obj.data[index.row()], PropTree):
          return obj.data[index.row()]
    return QtCore.QVariant()

class PropTree:
  def __init__(self, data, parent=None):
    self.parent = parent
    if isinstance(data, dict):
      objs = zip(*sorted(data.items()))
      self.data = list(objs[1])
      self.tags = list(objs[0])
    else:
      self.data = data
      self.tags = None
    for idx in range(len(self.data)):
      if isinstance(self.data[idx], (dict, list)):
        self.data[idx] = PropTree(self.data[idx], self)

  def getData(self):
    if self.tags == None:
      data = self.data[:]
      for idx in range(len(data)):
        if isinstance(data[idx], PropTree): data[idx] = data[idx].getData()
    else:
      data = {}
      for idx in range(len(data)):
        if isinstance(self.data[idx], PropTree):
          data[self.tags[idx]] = self.data[idx].getData()
        else: data[self.tags[idx]] = self.data[idx]
    return data
