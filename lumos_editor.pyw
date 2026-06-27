import os
import sys
from functools import partial

from PyQt5.Qsci import QsciScintilla
from PyQt5.QtCore import (
    QByteArray,
    QDir,
    QEvent,
    QFileSystemWatcher,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QActionGroup,
    QApplication,
    QCheckBox,
    QDesktopWidget,
    QDialog,
    QFileDialog,
    QFileSystemModel,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSizeGrip,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabBar,
    QTabWidget,
    QToolButton,
    QTreeView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src import (
    AIChat,
    AudioViewer,
    CommandPalette,
    ConfigManager,
    EditorTab,
    FileTreeDelegate,
    FileTreeView,
    FindReplaceDialog,
    ImageViewer,
    PluginDialog,
    PluginManager,
    SearchWorker,
    SourceControlTab,
    SplitTab,
    Terminal,
    VideoViewer,
    WelcomeScreen,
)
from src.theme_manager import theme

RADIUS = 8
SHADOW_PADDING = 20


class BorderOverlay(QWidget):
    def __init__(self, parent=None, radius=8):
        super().__init__(parent)
        self.radius = radius
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(f"{theme.color13}"), 1)
        painter.setPen(pen)
        main_window = self.window()
        if not (main_window and main_window.isMaximized()):
            rect_for_drawing = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            painter.drawRoundedRect(rect_for_drawing, self.radius, self.radius)


class CustomSizeGrip(QSizeGrip):
    def __init__(self, parent=None, color=QColor(f"{theme.color23}")):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(14, 14)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)
        dot = 2
        spacing = 3
        w = self.width()
        h = self.height()
        for col in range(3):
            for row in range(3 - col):
                x = int(w - (col + 1) * (dot + spacing))
                y = int(h - (row + 1) * (dot + spacing))
                painter.drawRect(x, y, dot, dot)
        painter.end()


class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._drag_pos = None
        self._window_pos = None
        self.setFixedHeight(40)
        self.setObjectName("TitleBar")
        self.setStyleSheet(f"background: {theme.color2};")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 8, 4)
        layout.setSpacing(8)
        self.icon_label = QLabel()
        icon = QIcon("resources:/lumos-icon.png")
        pix = icon.pixmap(QSize(16, 16))
        self.icon_label.setPixmap(pix)
        self.icon_label.setStyleSheet(f"background: {theme.color2};")
        self.icon_label.setFixedSize(18, 18)
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        self.title = QLabel("Lumos Editor")
        self.title.setFont(QFont("Segoe UI", 10))
        self.title.setStyleSheet(f"color: {theme.color30}; background: {theme.color2};")
        self.title.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        layout.addWidget(self.title, 0, Qt.AlignVCenter)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.menu_container = QWidget()
        self.menu_layout = QHBoxLayout(self.menu_container)
        self.menu_layout.setContentsMargins(0, 0, 0, 0)
        self.menu_layout.setSpacing(4)
        self.menu_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.menu_container, 1)
        btn_size = QSize(34, 28)
        self.min_btn = QToolButton()
        self.min_btn.setIcon(QIcon("resources:/minimize-window-icon.png"))
        self.min_btn.setIconSize(QSize(16, 16))
        self.min_btn.setToolTip("Minimize")
        self.min_btn.setFixedSize(btn_size)
        self.min_btn.setObjectName("WindowButton")
        self.max_btn = QToolButton()
        self.max_btn.setIcon(QIcon("resources:/restore-window-icon.png"))
        self.max_btn.setIconSize(QSize(16, 16))
        self.max_btn.setToolTip("Maximize")
        self.max_btn.setFixedSize(btn_size)
        self.max_btn.setObjectName("WindowButton")
        self.close_btn = QToolButton()
        self.close_btn.setIcon(QIcon("resources:/close-window-icon.png"))
        self.close_btn.setIconSize(QSize(16, 16))
        self.close_btn.setToolTip("Close")
        self.close_btn.setFixedSize(btn_size)
        self.close_btn.setObjectName("WindowButton")
        for b in (self.min_btn, self.max_btn, self.close_btn):
            b.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self.min_btn, 0, Qt.AlignVCenter)
        layout.addWidget(self.max_btn, 0, Qt.AlignVCenter)
        layout.addWidget(self.close_btn, 0, Qt.AlignVCenter)
        self.min_btn.clicked.connect(self.on_min)
        self.max_btn.clicked.connect(self.on_max)
        self.close_btn.clicked.connect(self.on_close)
        self.setCursor(Qt.ArrowCursor)
        self.setStyleSheet(
            f"""
        QToolButton#WindowButton {{
            background: {theme.color2};
            color: {theme.color26};
            border: none;
            border-radius: 4px;
        }}
        QToolButton#WindowButton:hover {{
            background: rgba(255,255,255,0.04);
            color: {theme.color31};
        }}
        QWidget#TitleBar {{ 
            background: {theme.color2}; 
            border-top-left-radius: {RADIUS}px; 
            border-top-right-radius: {RADIUS}px; 
            border-bottom-left-radius: 0px; 
            border-bottom-right-radius: 0px;
        }}"""
        )
        self.installEventFilter(self)

    def set_menu_bar(self, menubar):
        while self.menu_layout.count():
            item = self.menu_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        menubar.installEventFilter(self)
        menubar.setParent(self.menu_container)
        menubar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        menubar.setStyleSheet(
            f"""
            QMenuBar {{
                background: {theme.color2};
                color: {theme.color28};
            }}
            QMenuBar::item {{
                background: transparent;
                padding: 4px 10px;
            }}
            QMenuBar::item:selected {{
                background: {theme.color10};
            }}
        """
        )
        self.menu_layout.addWidget(menubar)
        for child in menubar.findChildren(QToolButton):
            child.setIcon(QIcon("resources:/chevron-right-window.png"))
            child.setIconSize(QSize(16, 16))
            child.setStyleSheet(
                f"""
                QToolButton {{
                    background: {theme.color2};
                    border: none;
                    border-radius: 4px;
                }}
                QToolButton:hover {{
                    background: {theme.color10};
                }}
            """
            )
            child.setToolTip("Menu")

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            if (
                event.buttons() == Qt.LeftButton
                and self.underMouse()
                and self._drag_pos is not None
            ):
                delta = event.globalPos() - self._drag_pos
                self.window().move(self._window_pos + delta)
        elif event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton and self.underMouse():
                self._drag_pos = event.globalPos()
                self._window_pos = self.window().pos()
        elif event.type() == QEvent.MouseButtonDblClick:
            if event.button() == Qt.LeftButton and self.underMouse():
                self.on_max()
        return super().eventFilter(obj, event)

    def on_min(self):
        if self.parent:
            self.parent.showMinimized()

    def on_max(self):
        if not self.parent:
            return
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.max_btn.setToolTip("Maximize")
        else:
            self.parent.showMaximized()
            self.max_btn.setToolTip("Restore")

    def on_close(self):
        if self.parent:
            self.parent.close()


class MainWindow(QWidget):
    project_dir_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        QDir.addSearchPath(
            "resources",
            os.path.join(os.path.dirname(__file__), f".{os.sep}resources"),
        )
        self.setWindowIcon(QIcon("resources:/lumos-icon.png"))
        self.plugin_manager = PluginManager(self, self.config_manager)
        self.resize(1218, 730)
        self.setMinimumSize(812, 630)
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        self.wrap_mode = self.config_manager.get("wrap_mode", False)
        self.current_theme = self.config_manager.get("theme", "default")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(
            SHADOW_PADDING, SHADOW_PADDING, SHADOW_PADDING, SHADOW_PADDING
        )
        self.container = QWidget()
        self.container.setObjectName("container")
        self.main_layout.addWidget(self.container)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.bg_inner = f"{theme.color6}"
        self.container.setStyleSheet(
            f"QWidget#container {{ background:{self.bg_inner}; border-radius: {RADIUS}px;}}"
        )
        self.shadow_effect = QGraphicsDropShadowEffect(self)
        self.shadow_effect.setBlurRadius(25)
        self.shadow_effect.setColor(QColor(0, 0, 0, 180))
        self.shadow_effect.setOffset(0, 8)
        self.container.setGraphicsEffect(self.shadow_effect)
        self.border_overlay = BorderOverlay(self, radius=RADIUS)
        self.border_overlay.raise_()
        self.titlebar = TitleBar(self)
        self.central_widget = QWidget()
        self.central_widget.setStyleSheet("background: transparent;")
        self.status_bar = QStatusBar()
        self.container_layout.addWidget(self.titlebar)
        self.container_layout.addWidget(self.central_widget, 1)
        self.container_layout.addWidget(self.status_bar)
        self.status_bar.setStyleSheet(
            f"""
            QStatusBar {{
                background: {theme.color2};
                color: {theme.color23};
                font-size: 18px;
                border-top: 1px solid {theme.color1};
                padding: 2px 4px;
            }}
            QStatusBar QLabel {{
                color: {theme.color23};
                font-size: 16px; 
                text-align: right;
                padding-left: 4px;
            }}
            QStatusBar {{
                background: {theme.color2};
                color: {theme.color23};
                font-size: 18px;
                border-top: 1px solid {theme.color1};
                padding: 2px 4px;
                border-bottom-left-radius: {RADIUS}px;
                border-bottom-right-radius: {RADIUS}px;
            }}
        """
        )
        self.status_position = QLabel()
        self.status_file = QLabel()
        self.status_folder = QLabel()
        label_style = f"color: {theme.color27}; background: transparent;"
        self.status_position.setStyleSheet(label_style)
        self.status_file.setStyleSheet(label_style)
        self.status_folder.setStyleSheet(label_style)
        self.status_bar.addPermanentWidget(self.status_position)
        self.status_bar.addPermanentWidget(self.status_file)
        self.status_bar.addPermanentWidget(self.status_folder)
        self.status_bar.setSizeGripEnabled(False)
        self.size_grip = CustomSizeGrip(
            self.status_bar, color=QColor(f"{theme.color23}")
        )
        self.status_bar.addPermanentWidget(self.size_grip)
        self.size_grip.setVisible(not self.isMaximized())
        layout = QHBoxLayout(self.central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.left_container = QWidget()
        left_layout = QVBoxLayout(self.left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        explorer_header = QWidget()
        explorer_header.setFixedHeight(35)
        explorer_header.setStyleSheet(
            f"background: {theme.color2}; border-bottom: 1px solid {theme.color1};"
        )
        header_layout = QHBoxLayout(explorer_header)
        header_layout.setContentsMargins(10, 0, 4, 0)
        header_layout.setSpacing(10)
        tab_style = f"""
            QPushButton {{
                color: {theme.color23}; font-size: 11px; font-weight: bold;
                letter-spacing: 0.5px; background: transparent; border: none; padding: 4px;
            }}
            QPushButton:hover {{ color: {theme.color27}; }}
            QPushButton:checked {{ color: {theme.color31}; border-bottom: 2px solid {theme.color38}; }}
        """
        self.btn_nav_explorer = QPushButton("EXPLORER")
        self.btn_nav_explorer.setCheckable(True)
        self.btn_nav_explorer.setChecked(True)
        self.btn_nav_explorer.setStyleSheet(tab_style)
        self.btn_nav_search = QPushButton("SEARCH")
        self.btn_nav_search.setCheckable(True)
        self.btn_nav_search.setStyleSheet(tab_style)
        header_layout.addWidget(self.btn_nav_explorer)
        header_layout.addWidget(self.btn_nav_search)
        header_layout.addStretch()
        self.toggle_tree = QPushButton()
        self.toggle_tree.setIcon(QIcon("resources:/close-icon.png"))
        self.toggle_tree.setFixedSize(24, 24)
        self.toggle_tree.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: none;
                padding: 4px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {theme.color9};
            }}
            QPushButton:pressed {{
                background: {theme.color12};
            }}
        """
        )
        self.toggle_tree.clicked.connect(self.toggle_left_panel)
        header_layout.addWidget(self.toggle_tree)
        left_layout.addWidget(explorer_header)
        self.folder_section = QWidget()
        folder_layout = QHBoxLayout(self.folder_section)
        folder_layout.setContentsMargins(10, 4, 4, 4)
        folder_name = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
        self.folder_label = QLabel(folder_name.upper())
        self.folder_label.setStyleSheet(
            f"""
            QLabel {{
                color: {theme.color29};
                font-size: 11px;
                font-weight: 500;
            }}
        """
        )
        folder_layout.addWidget(self.folder_label)
        folder_layout.addStretch()
        left_layout.addWidget(self.folder_section)
        self.left_stack = QStackedWidget()
        left_layout.addWidget(self.left_stack)
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        splitter.addWidget(self.left_container)
        self.right_splitter = QSplitter(Qt.Vertical)
        self.right_splitter.setChildrenCollapsible(False)
        self.tabs = QTabWidget()
        self.tabs.setTabBar(QTabBar())
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.setMovable(True)
        self.tabs.setElideMode(Qt.ElideRight)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.setStyleSheet(
            f"""
            QTabWidget::pane {{
                border: none;
            }}
            QTabBar::tab {{
                background: {theme.color2};
                color: {theme.color27};
                padding: 6px 12px;
                border: none;
                min-width: 100px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {theme.color6};
                border-bottom: 2px solid {theme.color38};
            }}
            QTabBar::tab:hover {{
                background: {theme.color9};
            }}
            QTabBar::tab:last {{
                margin-right: 0px;
            }}
            QTabBar::close-button {{
                image: url(resources:/close-icon.png);
                margin: 2px;
            }}
            QTabWidget {{
                background: {theme.color6};
                border: none;
            }}
            QTabBar {{
                background: {theme.color6};
                border: none;
                alignment: left;
            }}
            QTabBar::scroller {{ 
                width: 24px;
            }}
            QTabBar QToolButton {{
                background: {theme.color2};
                border: none;
                margin: 0;
                padding: 0;
                border-radius: 0px;
            }}
            QTabBar QToolButton::right-arrow {{
                image: url(resources:/chevron-right.png);
                width: 16px;
                height: 16px;
            }}
            QTabBar QToolButton::left-arrow {{
                image: url(resources:/chevron-left.png);
                width: 16px;
                height: 16px;
            }}
            QTabBar QToolButton:hover {{
                background: {theme.color9};
            }}
            QTabBar::tab:first {{
                margin-left: 0px;
            }}
            QTabBar::tab:!selected {{
                margin-top: 2px;
            }}
        """
        )
        self.right_splitter.addWidget(self.tabs)
        splitter.addWidget(self.right_splitter)
        self.terminal_overlay = Terminal(self)
        self.terminal_overlay.hide()
        self.terminal_overlay.closed.connect(self.hide_integrated_terminal)
        self.right_splitter.addWidget(self.terminal_overlay)
        self.splitter = splitter
        self.tree_width = 130
        self.splitter.splitterMoved.connect(self.on_splitter_moved)
        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath("")
        self.current_project_dir = None
        self.fs_watcher = QFileSystemWatcher()
        self.fs_watcher.directoryChanged.connect(self.on_directory_changed)
        self.left_container.hide()
        self.folder_section.hide()
        self.splitter.setSizes([0, self.width()])
        self.file_tree = FileTreeView(self, self.plugin_manager)
        self.fs_model.setReadOnly(False)
        self.file_tree.setFocusPolicy(Qt.NoFocus)
        self.file_tree.setModel(self.fs_model)
        self.file_tree.setRootIndex(self.fs_model.index(""))
        self.file_tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.file_tree.setIndentation(12)
        self.file_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.file_tree.setDragEnabled(True)
        self.file_tree.setAcceptDrops(True)
        self.file_tree.setDropIndicatorShown(True)
        self.file_tree.setDragDropMode(QAbstractItemView.DragDrop)
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setAnimated(False)
        self.file_tree.setUniformRowHeights(True)
        self.file_tree.setColumnHidden(1, True)
        self.file_tree.setColumnHidden(2, True)
        self.file_tree.setColumnHidden(3, True)
        self.file_tree.clicked.connect(self.on_file_tree_clicked)
        self.fs_model.setFilter(
            QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files | QDir.Drives
        )
        self.file_tree.setIconSize(QSize(16, 16))
        self.tree_delegate = FileTreeDelegate(self.file_tree, self.plugin_manager)
        self.file_tree.setItemDelegate(self.tree_delegate)
        self.left_stack.addWidget(self.file_tree)
        self.setup_search_panel()
        self.left_stack.addWidget(self.search_panel)
        self.btn_nav_explorer.clicked.connect(lambda: self.switch_left_panel(0))
        self.btn_nav_search.clicked.connect(lambda: self.switch_left_panel(1))
        self.file_tree.setStyleSheet(
            f"""
            QTreeView {{
                background-color: {theme.color2};
                border: none;
                color: {theme.color27};
                selection-background-color: transparent;
                padding-left: 5px;
            }}
            QTreeView::item {{
                padding: 4px;
                border-radius: 4px;
                margin: 1px 4px;
            }}
            QTreeView::item:hover {{
                background: {theme.color9};
            }}
            QTreeView::item:selected {{
                background: {theme.color9};
                color: {theme.color31};
            }}
            QTreeView::branch {{
                background: transparent;
                border-image: none;
                padding-left: 2px;
            }}
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {{
                image: url(resources:/chevron-right.png);
                padding: 0px;
            }}
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings {{
                image: url(resources:/chevron-down.png);
                padding: 0px;
            }}
            QTreeView::branch:selected {{
                background: {theme.color9};
            }}
        """
        )
        self.setObjectName("MainWindow")
        self.setStyleSheet(
            f"""
            QWidget#MainWindow {{
                background-color: transparent;
                color: {theme.color27};
            }}
            QToolTip {{
                background-color: {theme.color2};
                color: {theme.color27};
                border-radius: 4px;
                padding: 4px;
            }}
            QMenuBar {{
                background-color: {theme.color2};
                color: {theme.color27};
                border: none;
            }}
            QMenuBar::item {{
                background: transparent;
                padding: 4px 8px;
            }}
            QMenuBar::item:selected {{
                background-color: {theme.color9};
            }}
            QMenuBar::item:pressed {{
                background-color: {theme.color12};
            }}
            QMenu {{
                background-color: {theme.color2};
                color: {theme.color27};
                border: 1px solid {theme.color12};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 20px;
                border-radius: 0px;
            }}
            QMenu::item:selected {{
                background-color: {theme.color9};
            }}
            QMenu::separator {{
                height: 1px;
                background: {theme.color12};
                margin: 4px 0px;
            }}
            QScrollBar {{
                border: none;
                background: {theme.color6};
                margin: 0px;
                padding: 0px;
            }}
            QScrollBar:vertical {{
                width: 12px;
            }}
            QScrollBar:horizontal {{
                height: 12px;
            }}
            QScrollBar::handle {{
                background: {theme.color15};
                border-radius: 6px;
                min-height: 20px;
                min-width: 20px;
            }}
            QScrollBar::handle:hover {{
                background: {theme.color17};
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                width: 0px;
                height: 0px;
                background: none;
            }}
            QScrollBar::add-page, QScrollBar::sub-page {{
                background: none;
            }}
            QSplitterHandle, QSplitter::handle {{
                background-color: {QColor(theme.color2).lighter(120).name() if theme.is_dark else QColor(theme.color2).darker(120).name()};
                border: none; 
                image: none;
            }}
            QSplitter::handle:horizontal {{
                width: 1px;
            }}
            QSplitter::handle:vertical {{
                height: 1px;
            }}
            QTabBar::tear {{
                width: 0px;
                border: none;
                image: none;
            }}
            """
        )
        self.recent_files = []
        self.load_recent_files()
        self.create_menu_bar()
        self.welcome_screen = WelcomeScreen()
        self.active_tab_widget = self.welcome_screen
        self.tabs.addTab(self.welcome_screen, self.welcome_screen.tabname)
        self.clipboard_path = None
        self.clipboard_operation = None
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_path_exists)
        self.check_timer.start(5000)
        self.find_replace_dialog = None
        self.cache = {}
        QTimer.singleShot(0, self.update_overlay_geometry)
        self.cmd_palette_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        self.cmd_palette_shortcut.activated.connect(self.show_command_palette)
        self.project_dir_changed.connect(self.sync_terminal_directory)

        self.session_restored = False
        self._wait_plugins_timer = QTimer(self)
        self._wait_plugins_timer.timeout.connect(self._check_plugins_and_restore)
        self._wait_plugins_timer.start(50)

    def _check_plugins_and_restore(self):
        if getattr(self, "session_restored", False):
            return
        if getattr(self.plugin_manager, "plugins_loaded", True):
            self.session_restored = True
            self._wait_plugins_timer.stop()
            self.restore_session()

    def sync_terminal_directory(self, folder):
        if (
            folder
            and hasattr(self, "terminal_overlay")
            and self.terminal_overlay.is_running()
        ):
            self.terminal_overlay.push(
                f'cd "{folder}"\r' + "clear\r" if sys.platform != "win32" else "cls\r"
            )

    def _check_plugins_and_restore(self):
        if getattr(self.plugin_manager, "plugins_loaded", True):
            self._wait_plugins_timer.stop()
            self.restore_session()

    def eventFilter(self, obj, event):
        return super().eventFilter(obj, event)

    def open_integrated_terminal(self, from_plugin=False):
        if not hasattr(self, "terminal_overlay"):
            return
        if self.terminal_overlay.isVisible() and not from_plugin:
            self.hide_integrated_terminal()
        else:
            self.terminal_overlay.show()
            total_height = self.right_splitter.height()
            term_height = int(total_height * 0.35)
            self.right_splitter.setSizes([total_height - term_height, term_height])
            if not self.terminal_overlay.is_running():
                self.terminal_overlay.start()
                self.terminal_overlay.push(
                    f'cd "{self.current_project_dir or os.path.expanduser("~")}"\r'
                    + "clear\r"
                    if sys.platform != "win32"
                    else "cls\r"
                )
            self.terminal_overlay.input_field.setFocus()

    def hide_integrated_terminal(self):
        if hasattr(self, "terminal_overlay"):
            self.terminal_overlay.hide()
            editor = self.get_current_editor()
            if editor:
                editor.setFocus()

    def tint_pixmap(self, pixmap, color):
        result = QPixmap(pixmap.size())
        result.fill(Qt.transparent)
        painter = QPainter(result)
        painter.drawPixmap(0, 0, pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(result.rect(), QColor(color))
        painter.end()
        return result

    def _setup_editor_markers(self, tab):
        if not hasattr(tab, "editor") or not tab.editor:
            return

        ratio = self.devicePixelRatioF()

        logical_size = 12
        physical_size = int(logical_size * ratio)

        down_pixmap = QPixmap("resources:/chevron-down.png").scaled(
            physical_size,
            physical_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        right_pixmap = QPixmap("resources:/chevron-right.png").scaled(
            physical_size,
            physical_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        down_pixmap.setDevicePixelRatio(ratio)
        right_pixmap.setDevicePixelRatio(ratio)

        self.down_icon = self.tint_pixmap(
            down_pixmap,
            tab.get_margin_fore_color(),
        )

        self.right_icon = self.tint_pixmap(
            right_pixmap,
            tab.get_margin_fore_color(),
        )

        self.down_icon.setDevicePixelRatio(ratio)
        self.right_icon.setDevicePixelRatio(ratio)

        tab.editor.markerDefine(
            self.down_icon,
            QsciScintilla.SC_MARKNUM_FOLDEROPEN,
        )

        tab.editor.markerDefine(
            self.right_icon,
            QsciScintilla.SC_MARKNUM_FOLDER,
        )

    def save_session(self):
        session_state = {
            "geometry": self.saveGeometry().toBase64().data().decode("utf-8"),
            "splitter": self.splitter.saveState().toBase64().data().decode("utf-8"),
            "project_dir": self.current_project_dir,
            "tabs": [],
            "active_tab_index": self.tabs.currentIndex(),
            "is_maximized": self.isMaximized(),
        }
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, SplitTab) and tab.mode != "diff":
                session_state["tabs"].append(
                    {
                        "type": "split",
                        "left": getattr(tab.left_editor_tab, "filepath", None),
                        "right": getattr(tab.right_editor_tab, "filepath", None),
                        "mode": getattr(tab, "mode", None),
                    }
                )
            elif hasattr(tab, "filepath") and tab.filepath:
                session_state["tabs"].append({"type": "normal", "path": tab.filepath})
            else:
                session_state["tabs"].append({"type": type(tab).__name__})
        self.config_manager.set("last_session", session_state)

    def restore_session(self):
        session_state = self.config_manager.get("last_session", None)
        if not session_state:
            return
        if "geometry" in session_state:
            geom_data = QByteArray.fromBase64(session_state["geometry"].encode("utf-8"))
            self.restoreGeometry(geom_data)
        if session_state.get("is_maximized", False):
            self.showMaximized()
        if session_state.get("project_dir"):
            self.load_folder(session_state["project_dir"])
        if "splitter" in session_state:
            splitter_data = QByteArray.fromBase64(
                session_state["splitter"].encode("utf-8")
            )
            self.splitter.restoreState(splitter_data)
            sizes = self.splitter.sizes()
            if sizes[0] > 0 and sizes[0] < 50:
                self.tree_width = 130
                sizes[0] = 130
                self.splitter.setSizes(sizes)
            elif sizes[0] >= 50:
                self.tree_width = sizes[0]
                self.splitter.setSizes(sizes)
            elif sizes[0] == 0:
                self.tree_width = 130
                sizes[0] = 130
                self.splitter.setSizes(sizes)
        tabs_state = session_state.get("tabs", [])
        if tabs_state:
            for tab_info in tabs_state:
                t_type = tab_info.get("type")
                if t_type == "normal" and tab_info.get("path"):
                    if os.path.exists(tab_info["path"]):
                        self.open_specific_file(tab_info["path"])
                elif (
                    t_type == "split" and tab_info.get("left") and tab_info.get("right")
                ):
                    left = tab_info["left"]
                    right = tab_info["right"]
                    mode = tab_info.get("mode")
                    if os.path.exists(left) and os.path.exists(right):
                        self.open_specific_file(left)
                        self.open_in_split_view(right, mode)
                elif t_type == "AIChat":
                    self.show_ai_chat()
                elif t_type == "SourceControlTab":
                    self.show_source_control()
            active_index = session_state.get("active_tab_index", 0)
            if 0 <= active_index < self.tabs.count():
                self.tabs.setCurrentIndex(active_index)

    def menuBar(self):
        if not hasattr(self, "_menubar"):
            self._menubar = QMenuBar(self)
        return self._menubar

    def update_overlay_geometry(self):
        is_max = self.isMaximized()
        if is_max:
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.container.setStyleSheet(
                f"QWidget#container {{ background:{self.bg_inner}; border-radius: 0px; }}"
            )
            self.border_overlay.hide()
            self.shadow_effect.setEnabled(False)
        else:
            self.main_layout.setContentsMargins(
                SHADOW_PADDING, SHADOW_PADDING, SHADOW_PADDING, SHADOW_PADDING
            )
            self.container.setStyleSheet(
                f"QWidget#container {{ background:{self.bg_inner}; border-radius: {RADIUS}px; }}"
            )
            self.border_overlay.show()
            self.shadow_effect.setEnabled(True)
            QTimer.singleShot(0, self._sync_border_geometry)
        self.size_grip.setVisible(not is_max)

    def _sync_border_geometry(self):
        if not self.isMaximized():
            self.border_overlay.setGeometry(self.container.geometry())

    def resizeEvent(self, event):
        if self.left_container.isVisible():
            total = self.splitter.sizes()[0] + self.splitter.sizes()[1]
            self.splitter.setSizes([self.tree_width, total - self.tree_width])
        self.update_mask()
        self.update_overlay_geometry()
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.update_overlay_geometry)

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            QTimer.singleShot(0, self.update_overlay_geometry)
        return super().changeEvent(event)

    def update_mask(self):
        pass

    def get_available_themes(self):
        themes_dir = os.path.join(os.path.dirname(__file__), "themes")
        themes = {}
        if not os.path.exists(themes_dir):
            return themes
        for theme_name in os.listdir(themes_dir):
            theme_path = os.path.join(themes_dir, theme_name)
            if os.path.isdir(theme_path) and os.path.exists(
                os.path.join(theme_path, "theme.json")
            ):
                themes[theme_name] = theme_name
        return themes

    def change_theme(self, theme_name):
        if self.current_theme != theme_name:
            self.config_manager.set("theme", theme_name)
            self.request_restart()

    def load_recent_files(self):
        self.recent_files = self.config_manager.get("recent_files", [])

    def open_in_split_view(self, filepath, mode=None):
        current_tab = self.tabs.currentWidget()
        current_index = self.tabs.currentIndex()
        if not isinstance(
            current_tab, (EditorTab, AIChat, ImageViewer, AudioViewer, VideoViewer)
        ) or isinstance(current_tab, SplitTab):
            QMessageBox.information(
                self,
                "Cannot split view",
                "Split view can only be opened from a regular editor tab, image viewer tab, audio viewer tab, video viewer tab, or AI chat tab.",
            )
            return
        right_tab = self.open_specific_file(filepath, in_split=True)
        if right_tab is None:
            return
        self.tabs.removeTab(current_index)
        split_view = SplitTab(current_tab, right_tab, mode=mode)
        self.tabs.insertTab(
            current_index,
            split_view,
            f"{current_tab.tabname} | {right_tab.tabname}",
        )
        self.tabs.setCurrentIndex(current_index)

    def save_recent_files(self):
        self.config_manager.set("recent_files", self.recent_files)

    def add_to_recent_files(self, file_path):
        abs_path = os.path.abspath(file_path)
        if abs_path in self.recent_files:
            self.recent_files.remove(abs_path)
        self.recent_files.insert(0, abs_path)
        self.recent_files = self.recent_files[:10]

    def update_recent_files_menu(self):
        self.recent_files_menu.clear()
        if not self.recent_files:
            action = QAction("No Recent Files", self)
            action.setEnabled(False)
            self.recent_files_menu.addAction(action)
        else:
            for file_path in self.recent_files:
                action = QAction(os.path.basename(file_path), self)
                action.setData(file_path)
                action.triggered.connect(partial(self.open_specific_file, file_path))
                self.recent_files_menu.addAction(action)

    def show_status_message(self, msg, timeout=2000):
        self.status_bar.showMessage(msg, timeout)

    def show_left_panel_logic(self):
        if not self.current_project_dir:
            self.open_folder()
            if not self.current_project_dir:
                return
            self.left_container.show()
            total = self.splitter.sizes()[0] + self.splitter.sizes()[1]
            self.splitter.setSizes([self.tree_width, total - self.tree_width])
        else:
            if not self.left_container.isVisible():
                self.left_container.show()
                total = self.splitter.sizes()[0] + self.splitter.sizes()[1]
                self.splitter.setSizes([self.tree_width, total - self.tree_width])

    def toggle_left_panel(self):
        if not self.current_project_dir:
            self.show_left_panel_logic()
            return
        if self.left_container.isVisible():
            self.tree_width = self.splitter.sizes()[0]
            self.left_container.hide()
            self.splitter.setSizes([0, self.width()])
        else:
            self.left_container.show()
            total = self.splitter.sizes()[0] + self.splitter.sizes()[1]
            self.splitter.setSizes([self.tree_width, total - self.tree_width])

    def toggle_file_tree(self):
        if self.left_container.isVisible() and self.left_stack.currentIndex() == 0:
            self.toggle_left_panel()
        else:
            if not self.left_container.isVisible():
                self.toggle_left_panel()
            self.switch_left_panel(0)

    def on_splitter_moved(self, _, __):
        if self.left_container.isVisible():
            self.tree_width = self.splitter.sizes()[0]

    def create_menu_bar(self):
        menubar = self.menuBar()
        self.titlebar.set_menu_bar(menubar)
        menubar.setStyleSheet(
            f"""
            QMenuBar {{
                background-color: {theme.color2};
                border: none;
                padding: 2px;
                min-height: 28px;
            }}
            QMenuBar::item {{
                background: transparent;
                padding: 4px 8px;
                margin: 0;
                border-radius: 4px;
            }}
            QMenuBar::item:selected {{
                background: {theme.color9};
            }}
            QMenuBar::item:pressed {{
                background: {theme.color12};
            }}
            QMenu {{
                background-color: {theme.color2};
                color: {theme.color27};
                border: 1px solid {theme.color9};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 20px;
            }}
            QMenu::item:selected {{
                background-color: {theme.color9};
            }}
            QMenu::separator {{
                height: 1px;
                background: {theme.color9};
                margin: 4px 0px;
            }}
        """
        )
        self.menus = {}
        file_menu = menubar.addMenu("File")
        self.menus["File"] = file_menu
        file_menu.addAction("New...", self.new_file, QKeySequence.New)
        file_menu.addSeparator()
        file_menu.addAction("Open...", self.open_file, QKeySequence.Open)
        file_menu.addAction(
            "Open in Split View...",
            self.open_in_split_view_,
            QKeySequence("Ctrl+Shift+O"),
        )
        file_menu.addAction("Open Folder...", self.open_folder, QKeySequence("Ctrl+K"))
        file_menu.addSeparator()
        self.recent_files_menu = file_menu.addMenu("Recent Files")
        self.recent_files_menu.aboutToShow.connect(self.update_recent_files_menu)
        file_menu.addSeparator()
        file_menu.addAction("Save", self.save_file, QKeySequence.Save)
        file_menu.addAction(
            "Save As...", self.save_file_as, QKeySequence("Ctrl+Shift+S")
        )
        file_menu.addSeparator()
        file_menu.addAction(
            "Close Folder", self.close_folder, QKeySequence("Ctrl+Shift+K")
        )
        file_menu.addSeparator()
        file_menu.addAction("Restart", self.request_restart, QKeySequence("Ctrl+R"))
        file_menu.addAction("Exit", self.close, QKeySequence("Ctrl+Q"))
        edit_menu = menubar.addMenu("Edit")
        self.menus["Edit"] = edit_menu
        edit_menu.addAction("Undo", self.undo, QKeySequence.Undo)
        edit_menu.addAction("Redo", self.redo, QKeySequence.Redo)
        edit_menu.addSeparator()
        edit_menu.addAction("Cut", self.cut, QKeySequence.Cut)
        edit_menu.addAction("Copy", self.copy, QKeySequence.Copy)
        edit_menu.addAction("Paste", self.paste, QKeySequence.Paste)
        edit_menu.addSeparator()
        edit_menu.addAction("Select All", self.select_all, QKeySequence.SelectAll)
        edit_menu.addSeparator()
        edit_menu.addAction("Find", self.show_find_dialog, QKeySequence("Ctrl+F"))
        edit_menu.addAction("Replace", self.show_replace_dialog, QKeySequence("Ctrl+H"))
        edit_menu.addAction(
            "Find in File", self.show_find_dialog, QKeySequence("Ctrl+F")
        )
        edit_menu.addAction(
            "Replace in File", self.show_replace_dialog, QKeySequence("Ctrl+H")
        )
        edit_menu.addSeparator()
        edit_menu.addAction(
            "Find in Project", self.show_project_search, QKeySequence("Ctrl+Shift+F")
        )
        edit_menu.addAction(
            "Replace in Project",
            self.show_project_replace,
            QKeySequence("Ctrl+Shift+H"),
        )
        edit_menu.addSeparator()
        edit_menu.addAction(
            "Toggle Wrap Mode", self.toggle_wrap_mode, QKeySequence("Ctrl+W")
        )
        view_menu = menubar.addMenu("View")
        self.menus["View"] = view_menu
        view_menu.addAction(
            "Toggle Explorer Panel", self.toggle_file_tree, QKeySequence("Ctrl+B")
        )
        view_menu.addSeparator()
        self.preview_action = view_menu.addAction(
            "Toggle Markdown Preview", self.toggle_preview, QKeySequence("Ctrl+P")
        )
        self.view_menu = view_menu
        view_menu.addSeparator()
        self.toggle_terminal_action = view_menu.addAction(
            "Toggle Integrated Terminal",
            self.open_integrated_terminal,
            QKeySequence("Ctrl+`"),
        )
        themes_menu = menubar.addMenu("Themes")
        self.menus["Themes"] = themes_menu
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        available_themes = self.get_available_themes()
        if not available_themes:
            no_themes_action = QAction("No themes found", self)
            no_themes_action.setEnabled(False)
            themes_menu.addAction(no_themes_action)
        else:
            for theme_name in sorted(available_themes.keys()):
                action_text = theme_name.replace("-", " ").title()
                action = QAction(action_text, self, checkable=True)
                if theme_name == self.current_theme:
                    action.setChecked(True)
                action.triggered.connect(partial(self.change_theme, theme_name))
                theme_group.addAction(action)
                themes_menu.addAction(action)
        tools_menu = menubar.addMenu("Tools")
        self.menus["Tools"] = tools_menu
        ai_chat_action = QAction("Open AI Chat", self)
        ai_chat_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        ai_chat_action.triggered.connect(self.show_ai_chat)
        tools_menu.addAction(ai_chat_action)
        tools_menu.addSeparator()
        source_control_action = QAction("Open Source Control", self)
        source_control_action.setShortcut(QKeySequence("Ctrl+Shift+G"))
        source_control_action.triggered.connect(self.show_source_control)
        tools_menu.addAction(source_control_action)
        plugins_menu = menubar.addMenu("Plugins")
        self.menus["Plugins"] = plugins_menu
        self.toggle_plugins_action = QAction("Enable Plugins", self, checkable=True)
        is_enabled = self.config_manager.get("plugins_enabled", True)
        self.toggle_plugins_action.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.toggle_plugins_action.setChecked(is_enabled)
        self.toggle_plugins_action.triggered.connect(self.on_toggle_plugins)
        plugins_menu.addAction(self.toggle_plugins_action)
        manage_plugins_action = QAction("Manage Individual Plugins...", self)
        manage_plugins_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        manage_plugins_action.triggered.connect(self.open_plugin_manager_dialog)
        plugins_menu.addAction(manage_plugins_action)
        try:
            self.plugin_manager.apply_menu_actions(self.menus)
        except:
            pass

    def show_ai_chat(self):
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), AIChat):
                self.tabs.setCurrentIndex(i)
                return
        ai_chat_tab = AIChat(self)
        self.tabs.addTab(ai_chat_tab, "AI Chat")
        self.tabs.setCurrentWidget(ai_chat_tab)
        ai_chat_tab.input_text.setFocus()

    def toggle_wrap_mode(self):
        self.wrap_mode = not self.wrap_mode
        self.config_manager.set("wrap_mode", self.wrap_mode)
        self.request_restart()

    def open_plugin_manager_dialog(self):
        dialog = PluginDialog(self.plugin_manager, self.config_manager, self)
        if dialog.exec_() == QDialog.Accepted:
            self.request_restart()

    def on_toggle_plugins(self, checked):
        self.config_manager.set("plugins_enabled", checked)
        if checked:
            self.plugin_manager.reload_plugins()
            self.request_restart()
        else:
            self.plugin_manager.unload_plugins()
            self.request_restart()

    def load_folder(self, folder):
        if folder and os.path.exists(folder):
            self.close_folder()
            if self.fs_watcher.directories():
                self.fs_watcher.removePaths(self.fs_watcher.directories())
            if self.fs_watcher.files():
                self.fs_watcher.removePaths(self.fs_watcher.files())
            self.current_project_dir = folder
            self.fs_model.setRootPath(folder)
            root_index = self.fs_model.index(folder)
            self.file_tree.setRootIndex(root_index)
            self.folder_label.setText(os.path.basename(folder).upper())
            self.titlebar.title.setText(f"Lumos Editor - {os.path.basename(folder)}")
            self.fs_watcher.addPath(folder)
            self.folder_section.show()
            self.left_container.show()
            self.splitter.setSizes([self.tree_width, self.width() - self.tree_width])
            self.show_status_message(f"Folder - {folder}")
            self.project_dir_changed.emit(folder)
            try:
                self.plugin_manager.trigger_hook("folder_opened", folder_path=folder)
            except Exception:
                pass
            self.switch_left_panel(0)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Open Folder",
            (
                os.path.dirname(os.path.abspath(__file__))
                if not self.current_project_dir
                else self.current_project_dir
            ),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if folder:
            self.load_folder(folder)

    def on_directory_changed(self, path):
        self.fs_model.setRootPath(self.current_project_dir)
        if path not in self.fs_watcher.directories():
            self.fs_watcher.addPath(path)

    def update_folder_title(self):
        folder_name = os.path.basename(self.current_project_dir)
        self.folder_label.setText(folder_name.upper())
        self.titlebar.title.setText(f"Lumos Editor - {folder_name}")

    def select_all(self):
        editor = self.get_current_editor()
        if editor:
            editor.selectAll()

    def get_current_editor(self):
        current_tab = self.tabs.currentWidget()
        if isinstance(current_tab, SplitTab):
            active_child_tab = current_tab.get_active_editor_tab()
            return active_child_tab.editor if active_child_tab else None
        elif hasattr(current_tab, "editor"):
            return current_tab.editor
        return None

    def undo(self):
        editor = self.get_current_editor()
        if editor:
            editor.undo()

    def redo(self):
        editor = self.get_current_editor()
        if editor:
            editor.redo()

    def cut(self):
        editor = self.get_current_editor()
        if editor:
            editor.cut()

    def copy(self):
        editor = self.get_current_editor()
        if editor:
            editor.copy()

    def paste(self):
        editor = self.get_current_editor()
        if editor:
            editor.paste()

    def new_file(self):
        tab = EditorTab(
            main_window=self,
            plugin_manager=self.plugin_manager,
            wrap_mode=self.wrap_mode,
        )
        self._setup_editor_markers(tab)
        index = self.tabs.addTab(tab, "Untitled")
        self.tabs.setCurrentIndex(index)
        tab.editor.setFocus()

    def open_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*.*)")
        if fname:
            self.open_specific_file(fname)

    def open_in_split_view_(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*.*)")
        if fname:
            self.open_in_split_view(fname)

    def on_file_tree_clicked(self, index):
        path = self.fs_model.filePath(index)
        if os.path.isfile(path):
            self.open_specific_file(path)
        else:
            self.show_status_message(f"Folder - {path}")

    def open_specific_file(self, path, in_split=False):
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Error", f"File not found:\n{path}")
            if path in self.recent_files:
                self.recent_files.remove(path)
            return None
        abs_path = os.path.abspath(path)
        if not in_split:
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                if (
                    hasattr(tab, "filepath")
                    and tab.filepath
                    and os.path.abspath(tab.filepath) == abs_path
                ):
                    self.tabs.setCurrentIndex(i)
                    return tab
        try:
            image_extensions = [
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".bmp",
                ".ico",
                ".webp",
                ".tiff",
                ".tif",
                ".svg",
                ".psd",
                ".raw",
                ".heif",
                ".heic",
            ]
            video_extensions = [".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv", ".m4v"]
            audio_extensions = [".mp3", ".wav", ".ogg", ".m4a"]
            file_ext = os.path.splitext(path)[1].lower()
            if file_ext in image_extensions:
                tab = ImageViewer(filepath=abs_path)
            elif file_ext in video_extensions:
                tab = VideoViewer(filepath=abs_path)
            elif file_ext in audio_extensions:
                tab = AudioViewer(filepath=abs_path)
            else:
                tab = EditorTab(
                    filepath=abs_path,
                    main_window=self,
                    wrap_mode=self.wrap_mode,
                    plugin_manager=self.plugin_manager,
                )
                self._setup_editor_markers(tab)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if not in_split:
                        self.cache[abs_path] = content
                    tab.editor.setText(content)
                    tab.save()
                except (UnicodeDecodeError, IOError):
                    QMessageBox.warning(
                        self,
                        "Warning",
                        f"Could not read file as text: {os.path.basename(path)}",
                    )
                    return None
            if in_split:
                return tab
            index = self.tabs.addTab(tab, tab.tabname)
            self.tabs.setCurrentIndex(index)
            if not isinstance(tab, (ImageViewer, AudioViewer, VideoViewer)):
                self.add_to_recent_files(abs_path)
            try:
                if hasattr(self, "plugin_manager") and self.plugin_manager:
                    self.plugin_manager.trigger_hook(
                        "file_opened", filepath=abs_path, tab=tab
                    )
            except Exception:
                pass
            return tab
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file: {str(e)}")
            return None

    def save_file(self):
        current = self.tabs.currentWidget()
        if isinstance(
            current,
            (
                WelcomeScreen,
                ImageViewer,
                AudioViewer,
                VideoViewer,
                AIChat,
                SourceControlTab,
            ),
        ):
            return False
        is_checking_content_equal = False
        if isinstance(current, SplitTab):
            target_tab = current.get_active_editor_tab()
            if hasattr(current, "check_view_mode"):
                view_mode = current.check_view_mode(target_tab)
                if view_mode == "disk":
                    reply = QMessageBox.warning(
                        self,
                        "Warning: Saving Disk View",
                        "You are editing the 'On Disk' view (Right side).\n"
                        "Saving now will overwrite the file with the content of this panel.\n\n"
                        "Do you want to proceed?",
                        QMessageBox.Yes | QMessageBox.No,
                    )
                    if reply == QMessageBox.No:
                        return False
                    else:
                        is_checking_content_equal = True
                elif view_mode == "memory":
                    is_checking_content_equal = True
            editor = getattr(target_tab, "editor", None)
        else:
            target_tab = current
            editor = getattr(current, "editor", None)
        if editor is None:
            editor = self.get_current_editor()
        if not getattr(target_tab, "filepath", None):
            self.save_file_as()
            if not getattr(target_tab, "filepath", None):
                return False
            self.close_tab(self.tabs.currentIndex())
        path = target_tab.filepath
        content_to_save = editor.text()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content_on_disk = f.read()
            else:
                content_on_disk = None
            if (
                path in self.cache
                and content_on_disk is not None
                and content_on_disk != self.cache.get(path, "")
                and not is_checking_content_equal
            ):
                reply = QMessageBox.question(
                    self,
                    "File Conflict Detected",
                    f"This file '{os.path.basename(path)}' has been modified by another program.\n\n"
                    "Do you want to compare the two files or overwrite the file on disk with your changes?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                )
                if reply == QMessageBox.Cancel:
                    return False
                if reply == QMessageBox.Yes:
                    self.open_in_split_view(path, "diff")
                    return False
            with open(path, "w", encoding="utf-8") as f:
                f.write(content_to_save)
            self.cache[path] = content_to_save
            if is_checking_content_equal:
                self.close_file_tab(path)
                return True
            target_tab.save()
            self.show_status_message(f"File saved: {path}")
            return True
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save file: {str(e)}")
            return False

    def save_file_as(self):
        current_tab_widget = self.tabs.currentWidget()
        if isinstance(
            current_tab_widget,
            (
                WelcomeScreen,
                ImageViewer,
                AudioViewer,
                VideoViewer,
                AIChat,
                SourceControlTab,
            ),
        ):
            return
        target_tab = None
        if isinstance(current_tab_widget, SplitTab):
            target_tab = current_tab_widget.get_active_editor_tab()
        elif isinstance(current_tab_widget, EditorTab):
            target_tab = current_tab_widget
        if not target_tab or not hasattr(target_tab, "editor"):
            return
        fname, _ = QFileDialog.getSaveFileName(self, "Save File", "", "All Files (*.*)")
        if fname:
            target_tab.filepath = fname
            name = os.path.basename(fname)
            target_tab.tabname = name
            new_tab_text = ""
            if isinstance(current_tab_widget, SplitTab):
                new_tab_text = f"{current_tab_widget.left_editor_tab.tabname} | {current_tab_widget.right_editor_tab.tabname}"
            else:
                new_tab_text = name
            self.tabs.setTabText(self.tabs.currentIndex(), new_tab_text)
            if self.save_file():
                self.add_to_recent_files(fname)
        else:
            return

    def close_tab(self, index):
        tab_to_close = self.tabs.widget(index)
        tabs_to_check = []
        if isinstance(tab_to_close, SplitTab):
            tabs_to_check.extend(tab_to_close.get_child_editors())
        else:
            tabs_to_check.append(tab_to_close)
        for tab in tabs_to_check:
            if isinstance(tab, AIChat):
                tab._save_current_session()
                if getattr(tab, "worker", None) and tab.worker.isRunning():
                    tab.worker.quit()
                    tab.worker.wait()
            if hasattr(tab, "stop_analysis_loop"):
                tab.stop_analysis_loop()
            if hasattr(tab, "is_modified") and tab.is_modified:
                self.tabs.setCurrentIndex(index)
                if isinstance(tab_to_close, SplitTab):
                    tab_to_close._set_active_editor(tab)
                reply = QMessageBox.question(
                    self,
                    "Save Changes",
                    f"This file '{os.path.basename(tab.filepath or 'Untitled')}' has unsaved changes. Save before closing?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                )
                if reply == QMessageBox.Save:
                    self.save_file()
                    if tab.is_modified:
                        return False
                elif reply == QMessageBox.Cancel:
                    return False
            if (
                hasattr(tab, "filepath")
                and tab.filepath
                and hasattr(self, "plugin_manager")
            ):
                try:
                    self.plugin_manager.trigger_hook(
                        "file_closed",
                        filepath=tab.filepath,
                        tab=tab,
                    )
                except Exception:
                    pass
        tab_to_close.deleteLater()
        self.tabs.removeTab(index)
        filepaths_to_remove = set()
        for tab in tabs_to_check:
            if hasattr(tab, "filepath") and tab.filepath:
                filepaths_to_remove.add(os.path.abspath(tab.filepath))
        for fp in filepaths_to_remove:
            self.cache.pop(fp, None)
        if self.tabs.count() == 0:
            welcome_tab = WelcomeScreen()
            self.tabs.addTab(welcome_tab, "Welcome")
        return True

    def close_file_tab(self, filepath):
        abs_path = os.path.abspath(filepath)
        tabs_to_remove_indices = set()
        filepaths_to_remove = set()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            should_close = False
            if isinstance(tab, SplitTab):
                left_fp = tab.left_editor_tab.filepath
                right_fp = tab.right_editor_tab.filepath
                if (left_fp and os.path.abspath(left_fp) == abs_path) or (
                    right_fp and os.path.abspath(right_fp) == abs_path
                ):
                    should_close = True
                    try:
                        if left_fp and hasattr(self, "plugin_manager"):
                            self.plugin_manager.trigger_hook(
                                "file_closed",
                                filepath=left_fp,
                                tab=tab.left_editor_tab,
                            )
                        if right_fp and hasattr(self, "plugin_manager"):
                            self.plugin_manager.trigger_hook(
                                "file_closed",
                                filepath=right_fp,
                                tab=tab.right_editor_tab,
                            )
                    except Exception:
                        pass
            elif (
                hasattr(tab, "filepath")
                and tab.filepath
                and os.path.abspath(tab.filepath) == abs_path
            ):
                should_close = True
                try:
                    if hasattr(self, "plugin_manager"):
                        self.plugin_manager.trigger_hook(
                            "file_closed",
                            filepath=tab.filepath,
                            tab=tab,
                        )
                except Exception:
                    pass
            if should_close:
                tab.deleteLater()
                if hasattr(tab, "filepath") and tab.filepath:
                    filepaths_to_remove.add(os.path.abspath(tab.filepath))
                tabs_to_remove_indices.add(i)
        for i in sorted(list(tabs_to_remove_indices), reverse=True):
            self.tabs.removeTab(i)
        for fp in filepaths_to_remove:
            self.cache.pop(fp, None)

    def request_restart(self):
        QApplication.instance().setProperty("restart_requested", True)
        self.close()

    def closeEvent(self, event):
        is_restarting = QApplication.instance().property("restart_requested")
        self.save_recent_files()
        self.save_session()
        for i in reversed(range(self.tabs.count())):
            if not self.close_tab(i):
                event.ignore()
                if is_restarting:
                    QApplication.instance().setProperty("restart_requested", False)
                return
        event.accept()

    def show_context_menu(self, position):
        index = self.file_tree.indexAt(position)
        context_menu = QMenu()
        context_menu.setStyleSheet(
            f"""
            QMenu {{
                background-color: {theme.color2};
                color: {theme.color27};
                border: 1px solid {theme.color9};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 20px;
            }}
            QMenu::item:selected {{
                background-color: {theme.color9};
            }}
            QMenu::separator {{
                height: 1px;
                background: {theme.color9};
                margin: 4px 0px;
            }}
        """
        )
        if index.isValid():
            path = self.fs_model.filePath(index)
            is_dir = os.path.isdir(path)
            if is_dir:
                new_file_action = context_menu.addAction("New File")
                new_file_action.triggered.connect(lambda: self.create_new_file(index))
                new_folder_action = context_menu.addAction("New Folder")
                new_folder_action.triggered.connect(
                    lambda: self.create_new_folder(index)
                )
                context_menu.addSeparator()
            copy_action = context_menu.addAction("Copy")
            copy_action.triggered.connect(lambda: self.copy_item(index))
            cut_action = context_menu.addAction("Cut")
            cut_action.triggered.connect(lambda: self.cut_item(index))
            if self.clipboard_path:
                paste_action = context_menu.addAction("Paste")
                paste_action.triggered.connect(lambda: self.paste_item(index))
            context_menu.addSeparator()
            delete_action = context_menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self.delete_item(index))
            rename_action = context_menu.addAction("Rename")
            rename_action.triggered.connect(lambda: self.rename_item(index))
        else:
            new_file_action = context_menu.addAction("New File")
            new_file_action.triggered.connect(lambda: self.create_new_file(index))
            new_folder_action = context_menu.addAction("New Folder")
            new_folder_action.triggered.connect(lambda: self.create_new_folder(index))
            if self.clipboard_path:
                context_menu.addSeparator()
                paste_action = context_menu.addAction("Paste")
                paste_action.triggered.connect(lambda: self.paste_item(index))
        context_menu.exec_(self.file_tree.viewport().mapToGlobal(position))

    def check_path_exists(self):
        if self.current_project_dir and not os.path.exists(self.current_project_dir):
            QMessageBox.warning(
                self,
                "Directory Error",
                "This working directory no longer exists.\nPlease reopen a valid folder.",
            )
            self.current_project_dir = None
            self.left_container.hide()
            self.folder_section.hide()
            self.splitter.setSizes([0, self.width()])
            return False
        tabs_to_close = []
        missing_split_tabs = []
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, SplitTab):
                missing = []
                for child in tab.get_child_editors():
                    if getattr(child, "filepath", None) and not os.path.exists(
                        child.filepath
                    ):
                        missing.append(os.path.basename(child.filepath))
                if missing:
                    missing_split_tabs.append(", ".join(missing))
                    tabs_to_close.append(i)
            elif hasattr(tab, "filepath") and tab.filepath:
                if not os.path.exists(tab.filepath):
                    QMessageBox.warning(
                        self,
                        "File Error",
                        f"This file '{os.path.basename(tab.filepath)}' no longer exists.",
                    )
                    tabs_to_close.append(i)
        if missing_split_tabs:
            QMessageBox.warning(
                self,
                "File Error",
                "One or more files in this split view no longer exist:\n"
                + "\n".join(missing_split_tabs),
            )
        for i in reversed(tabs_to_close):
            tab = self.tabs.widget(i)
            if hasattr(tab, "filepath") and tab.filepath:
                self.cache.pop(os.path.abspath(tab.filepath), None)
            self.tabs.removeTab(i)
            tab.deleteLater()
        return True

    def create_new_file(self, index):
        if not self.check_path_exists():
            return
        if index.isValid():
            path = self.fs_model.filePath(index)
            if not os.path.isdir(path):
                path = os.path.dirname(path)
        else:
            path = self.current_project_dir
        self.show_status_message(f"Folder - {path}")
        file_name, ok = QInputDialog.getText(
            self, "New File", "Enter file name:", QLineEdit.Normal, ""
        )
        if ok and file_name:
            file_path = os.path.join(path, file_name)
            if os.path.exists(file_path):
                QMessageBox.warning(self, "Error", "File already exists!")
                return
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("")
                self.open_specific_file(file_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create file: {str(e)}")

    def create_new_folder(self, index):
        if not self.check_path_exists():
            return
        if index.isValid():
            path = self.fs_model.filePath(index)
            if not os.path.isdir(path):
                path = os.path.dirname(path)
        else:
            path = self.current_project_dir
        self.show_status_message(f"Folder - {path}")
        folder_name, ok = QInputDialog.getText(
            self, "New Folder", "Enter folder name:", QLineEdit.Normal, ""
        )
        if ok and folder_name:
            folder_path = os.path.join(path, folder_name)
            try:
                os.makedirs(folder_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create folder: {str(e)}")

    def copy_item(self, index):
        path = self.fs_model.filePath(index)
        self.show_status_message(f"Folder - {os.path.dirname(path)}")
        self.clipboard_path = path
        self.clipboard_operation = "copy"

    def cut_item(self, index):
        path = self.fs_model.filePath(index)
        self.show_status_message(f"Folder - {os.path.dirname(path)}")
        self.close_file_tab(path)
        self.clipboard_path = path
        self.clipboard_operation = "cut"

    def paste_item(self, index):
        if not self.check_path_exists():
            return
        if not self.clipboard_path:
            return
        target_path = self.current_project_dir
        if index.isValid():
            path = self.fs_model.filePath(index)
            target_path = path if os.path.isdir(path) else os.path.dirname(path)
        self.show_status_message(f"Folder - {target_path}")
        try:
            filename = os.path.basename(self.clipboard_path)
            new_path = os.path.join(target_path, filename)
            if os.path.exists(new_path):
                self.close_file_tab(new_path)
                reply = QMessageBox.question(
                    self,
                    "File exists",
                    "File already exists. Replace it?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    return
            import shutil

            if self.clipboard_operation == "copy":
                if os.path.isdir(self.clipboard_path):
                    if os.path.exists(new_path):
                        shutil.rmtree(new_path)
                    shutil.copytree(self.clipboard_path, new_path)
                else:
                    shutil.copy2(self.clipboard_path, new_path)
            else:
                self.close_file_tab(self.clipboard_path)
                if os.path.exists(new_path):
                    if os.path.isdir(new_path):
                        shutil.rmtree(new_path)
                    else:
                        os.remove(new_path)
                shutil.move(self.clipboard_path, new_path)
                self.clipboard_path = None
                self.clipboard_operation = None
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Operation failed: {str(e)}")

    def delete_item(self, index):
        if not self.check_path_exists():
            return
        path = self.fs_model.filePath(index)
        self.show_status_message(f"Folder - {os.path.dirname(path)}")
        try:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete '{os.path.basename(path)}'?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.close_file_tab(path)
                import shutil

                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not delete: {str(e)}")

    def rename_item(self, index):
        if not self.check_path_exists():
            return
        old_path = self.fs_model.filePath(index)
        self.show_status_message(f"Folder - {os.path.dirname(old_path)}")
        old_name = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(
            self, "Rename", "Enter new name:", QLineEdit.Normal, old_name
        )
        if ok and new_name and new_name != old_name:
            try:
                new_path = os.path.join(os.path.dirname(old_path), new_name)
                self.close_file_tab(old_path)
                os.rename(old_path, new_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not rename: {str(e)}")

    def on_tab_changed(self, index):
        if self.active_tab_widget:
            if hasattr(self.active_tab_widget, "stop_analysis_loop"):
                self.active_tab_widget.stop_analysis_loop()
            elif isinstance(self.active_tab_widget, SplitTab):
                if hasattr(
                    self.active_tab_widget.left_editor_tab, "stop_analysis_loop"
                ):
                    self.active_tab_widget.left_editor_tab.stop_analysis_loop()
                if hasattr(
                    self.active_tab_widget.right_editor_tab, "stop_analysis_loop"
                ):
                    self.active_tab_widget.right_editor_tab.stop_analysis_loop()
        if index == -1 or (current_widget := self.tabs.widget(index)) is None:
            self.active_tab_widget = None
            self.status_position.clear()
            self.status_file.clear()
            self.status_folder.clear()
            return
        self.active_tab_widget = current_widget
        tab = current_widget
        if isinstance(tab, SplitTab):
            active_editor_tab = tab.get_active_editor_tab()
            if active_editor_tab:
                if hasattr(active_editor_tab, "start_analysis_loop"):
                    active_editor_tab.start_analysis_loop()
                status_map = {
                    "disk": "Ready (Viewing Disk File)",
                    "memory": "Ready (Editing In-Memory)",
                    "ImageViewer": "Image Viewer",
                    "AudioViewer": "Audio Viewer",
                    "VideoViewer": "Video Viewer",
                    "AIChat": "AI Chat",
                }
                mode_msg = status_map.get(type(active_editor_tab).__name__, "Ready")
                self.show_status_message(mode_msg)
                if hasattr(active_editor_tab, "editor") and active_editor_tab.editor:
                    line, col = active_editor_tab.editor.getCursorPosition()
                    self.status_position.setText(f"Ln {line + 1}, Col {col + 1}")
                else:
                    self.status_position.clear()
                filepath = getattr(active_editor_tab, "filepath", None)
                if filepath:
                    self.status_file.setText(f"File - {os.path.basename(filepath)}")
                else:
                    self.status_file.setText("File - Untitled")
                self.status_folder.clear()
        elif isinstance(tab, EditorTab):
            tab.start_analysis_loop()
            line, col = tab.editor.getCursorPosition()
            self.show_status_message("Ready")
            self.status_position.setText(f"Ln {line + 1}, Col {col + 1}")
            if tab.filepath:
                self.status_file.setText(f"File - {os.path.basename(tab.filepath)}")
            else:
                self.status_file.setText("File - Untitled")
            self.status_folder.clear()
        elif isinstance(
            tab,
            (
                WelcomeScreen,
                ImageViewer,
                AudioViewer,
                VideoViewer,
                SourceControlTab,
                AIChat,
            ),
        ):
            status_map = {
                "WelcomeScreen": "Welcome",
                "ImageViewer": "Image Viewer",
                "AudioViewer": "Audio Viewer",
                "VideoViewer": "Video Viewer",
                "SourceControlTab": "Source Control",
                "AIChat": "AI Chat",
            }
            status_message = status_map.get(type(tab).__name__, "Ready")
            self.show_status_message(status_message)
            self.status_position.clear()
            self.status_file.clear()
            self.status_folder.clear()

    def toggle_preview(self):
        current_tab = self.tabs.currentWidget()
        target_editor = None
        if isinstance(current_tab, SplitTab):
            target_editor = current_tab.get_active_editor_tab()
        elif hasattr(current_tab, "is_markdown"):
            target_editor = current_tab
        if target_editor and getattr(target_editor, "is_markdown", False):
            target_editor.toggle_markdown_preview()

    def close_folder(self):
        if self.current_project_dir:
            closed_folder_path = self.current_project_dir
            try:
                self.plugin_manager.trigger_hook(
                    "folder_closed", folder_path=closed_folder_path
                )
            except Exception:
                pass
            if self.fs_watcher.directories():
                self.fs_watcher.removePaths(self.fs_watcher.directories())
            if self.fs_watcher.files():
                self.fs_watcher.removePaths(self.fs_watcher.files())
            self.current_project_dir = None
            self.fs_model.setRootPath("")
            self.file_tree.setRootIndex(self.fs_model.index(""))
            self.left_container.hide()
            self.folder_section.hide()
            self.splitter.setSizes([0, self.width()])
            self.titlebar.title.setText("Lumos Editor")
            self.show_status_message("Folder closed")
            self.status_folder.clear()
            self.project_dir_changed.emit("")

    def show_find_dialog(self):
        editor = self.get_current_editor()
        if not editor:
            return
        if not self.find_replace_dialog or self.find_replace_dialog.editor != editor:
            self.find_replace_dialog = FindReplaceDialog(self, editor)
        self.find_replace_dialog.replace_input.hide()
        self.find_replace_dialog.replace_label.hide()
        self.find_replace_dialog.replace_btn.hide()
        self.find_replace_dialog.replace_all_btn.hide()
        self.find_replace_dialog.show()
        self.find_replace_dialog.find_input.setFocus()

    def show_replace_dialog(self):
        editor = self.get_current_editor()
        if not editor:
            return
        if not self.find_replace_dialog or self.find_replace_dialog.editor != editor:
            self.find_replace_dialog = FindReplaceDialog(self, editor)
        self.find_replace_dialog.replace_input.show()
        self.find_replace_dialog.replace_label.show()
        self.find_replace_dialog.replace_btn.show()
        self.find_replace_dialog.replace_all_btn.show()
        self.find_replace_dialog.show()
        self.find_replace_dialog.replace_input.setFocus()

    def show_source_control(self):
        if not self.current_project_dir:
            QMessageBox.information(
                self,
                "Source Control",
                "Please open a folder first to use Source Control.",
            )
            return
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), SourceControlTab):
                self.tabs.setCurrentIndex(i)
                return
        source_control_tab = SourceControlTab(self)
        self.project_dir_changed.connect(source_control_tab.on_project_changed)
        self.tabs.addTab(source_control_tab, "Source Control")
        self.tabs.setCurrentWidget(source_control_tab)

    def show_command_palette(self):
        commands = []

        def extract_actions(menu, prefix=""):
            for action in menu.actions():
                if action.isSeparator() or not action.text():
                    continue
                clean_name = action.text().replace("&", "")
                full_name = f"{prefix}{clean_name}"
                if action.menu():
                    extract_actions(action.menu(), f"{full_name}: ")
                else:
                    shortcut_str = action.shortcut().toString()
                    commands.append(
                        {
                            "name": full_name,
                            "shortcut": shortcut_str,
                            "action": action.trigger,
                        }
                    )

        if hasattr(self, "update_recent_files_menu"):
            self.update_recent_files_menu()
        for action in self.menuBar().actions():
            if action.menu():
                extract_actions(action.menu(), f"{action.text().replace('&', '')}: ")
        palette = CommandPalette(self, commands)
        qr = palette.frameGeometry()
        cp = self.geometry().center()
        qr.moveCenter(cp)
        qr.moveTop(self.geometry().top() + int(self.height() * 0.15))
        palette.move(qr.topLeft())
        palette.exec_()

    def setup_search_panel(self):
        self.search_panel = QWidget()
        self.search_panel.setStyleSheet(f"background: {theme.color2};")
        slayout = QVBoxLayout(self.search_panel)
        slayout.setContentsMargins(15, 10, 15, 10)
        slayout.setSpacing(10)
        input_container = QWidget()
        input_layout = QVBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)
        input_style = f"""
            QLineEdit {{
                background: {theme.color13};
                color: {theme.color26};
                border: 1px solid {theme.color13};
                border-radius: 3px;
                padding: 5px 5px 5px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.color36};
                background: {theme.color13};
            }}
        """
        search_row = QHBoxLayout()
        self.btn_toggle_replace = QPushButton()
        self.btn_toggle_replace.setFixedSize(20, 24)
        self.btn_toggle_replace.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_replace.setIcon(QIcon("resources:/chevron-down.png"))
        self.btn_toggle_replace.setIconSize(QSize(12, 12))
        self.btn_toggle_replace.setStyleSheet(
            "QPushButton { border: none; background: transparent; } "
            f"QPushButton:hover {{ background: {theme.color9}; border-radius: 3px; }}"
        )
        self.btn_toggle_replace.clicked.connect(self.toggle_replace_inputs)
        self.search_proj_input = QLineEdit()
        self.search_proj_input.setPlaceholderText("Search")
        self.search_proj_input.setStyleSheet(input_style)
        self.search_proj_input.returnPressed.connect(self.do_project_search)
        self.match_case_cb = QCheckBox("Aa")
        self.match_case_cb.setToolTip("Match Case")
        self.match_case_cb.setCursor(Qt.PointingHandCursor)
        self.match_case_cb.setStyleSheet(
            f"""
            QCheckBox {{ color: {theme.color26}; font-weight: bold; font-family: monospace; }}
            QCheckBox::indicator {{ width: 0px; height: 0px; }}
            QCheckBox:checked {{ color: {theme.color36}; }}
        """
        )
        search_row.addWidget(self.btn_toggle_replace)
        search_row.addWidget(self.search_proj_input)
        search_row.addWidget(self.match_case_cb)
        self.replace_widget = QWidget()
        replace_main_layout = QVBoxLayout(self.replace_widget)
        replace_main_layout.setContentsMargins(26, 0, 0, 0)
        replace_main_layout.setSpacing(6)
        replace_input_row = QHBoxLayout()
        self.replace_proj_input = QLineEdit()
        self.replace_proj_input.setPlaceholderText("Replace with...")
        self.replace_proj_input.setStyleSheet(input_style)
        replace_input_row.addWidget(self.replace_proj_input)
        replace_btn_row = QHBoxLayout()
        replace_btn_row.setSpacing(5)
        btn_style = f"""
            QPushButton {{
                background: transparent; border: 1px solid {theme.color16};
                border-radius: 3px; color: {theme.color26}; padding: 4px 8px; font-size: 11px;
            }}
            QPushButton:hover {{ background: {theme.color36}; border-color: {theme.color36}; color: white; }}
        """
        self.btn_replace_one = QPushButton("Replace")
        self.btn_replace_one.setToolTip("Replace current match and jump to the next")
        self.btn_replace_one.setStyleSheet(btn_style)
        self.btn_replace_one.clicked.connect(self.do_replace_one)

        self.btn_replace_file = QPushButton("File")
        self.btn_replace_file.setToolTip("Replace all occurrences in the selected file")
        self.btn_replace_file.setStyleSheet(btn_style)
        self.btn_replace_file.clicked.connect(self.do_replace_in_file)

        self.btn_replace_all = QPushButton("All")
        self.btn_replace_all.setToolTip("Replace all occurrences in project")
        self.btn_replace_all.setStyleSheet(btn_style)
        self.btn_replace_all.clicked.connect(self.do_project_replace)

        replace_btn_row.addWidget(self.btn_replace_one)
        replace_btn_row.addWidget(self.btn_replace_file)
        replace_btn_row.addWidget(self.btn_replace_all)
        replace_btn_row.addStretch()
        replace_main_layout.addLayout(replace_input_row)
        replace_main_layout.addLayout(replace_btn_row)

        input_layout.addLayout(search_row)
        input_layout.addWidget(self.replace_widget)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet(f"background-color: {theme.color10};")
        self.warning_label = QLabel("Please save all files before searching")
        self.warning_label.setStyleSheet(
            f"color: {theme.color24}; font-size: 10px; font-style: italic;"
        )

        self.search_status_label = QLabel("")
        self.search_status_label.setStyleSheet(
            f"color: {theme.color24}; font-size: 11px;"
        )
        self.search_results_tree = QTreeWidget()
        self.search_results_tree.setHeaderHidden(True)
        self.search_results_tree.setStyleSheet(
            f"""
            QTreeWidget {{
                background: {theme.color2}; color: {theme.color26}; border: none; outline: none; font-size: 12px;
            }}
            QTreeWidget::item {{ padding: 3px 0px; }}
            QTreeWidget::item:hover {{ background: {theme.color8}; }}
            QTreeWidget::item:selected {{ background: {theme.color11}; color: {theme.color31}; }}
            QTreeWidget::branch:hover {{ background: {theme.color8}; }}
            QTreeWidget::branch:selected {{ background: {theme.color11}; }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{ 
                image: url(resources:/chevron-right.png); 
                padding: 4px; 
            }}
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {{ 
                image: url(resources:/chevron-down.png); 
                padding: 4px; 
            }}
            """
        )
        self.search_results_tree.itemClicked.connect(self.open_file_from_search)
        slayout.addWidget(input_container)
        slayout.addWidget(line)
        slayout.addWidget(self.warning_label)
        slayout.addWidget(self.search_status_label)
        slayout.addWidget(self.search_results_tree)
        self.search_worker = None
        self.search_result_count = 0

    def toggle_replace_inputs(self):
        is_visible = self.replace_widget.isVisible()
        self.replace_widget.setVisible(not is_visible)
        if is_visible:
            self.btn_toggle_replace.setIcon(QIcon("resources:/chevron-right.png"))
        else:
            self.btn_toggle_replace.setIcon(QIcon("resources:/chevron-down.png"))

    def check_unsaved_files_before_action(self):
        target = self if hasattr(self, "tabs") else getattr(self, "parent", None)
        if not target or not hasattr(target, "tabs"):
            return True

        unsaved_files = []
        for i in range(target.tabs.count()):
            tab_widget = target.tabs.widget(i)
            is_modified = False
            is_modified = tab_widget.is_modified

            if is_modified and hasattr(tab_widget, "filepath"):
                unsaved_files.append(os.path.basename(tab_widget.filepath))

        if unsaved_files:
            from PyQt5.QtWidgets import QMessageBox

            msg_box = QMessageBox(target if isinstance(target, QWidget) else None)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("Unsaved Changes")

            files_str = ", ".join(unsaved_files)
            msg_box.setText(f"The following file(s) have unsaved changes:\n{files_str}")
            msg_box.setInformativeText(
                "Searching or replacing now might cause conflicts or data loss.\nDo you want to proceed anyway?"
            )

            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.No)

            result = msg_box.exec_()
            if result == QMessageBox.No:
                return False

        return True

    def switch_left_panel(self, index):
        self.btn_nav_explorer.setChecked(index == 0)
        self.btn_nav_search.setChecked(index == 1)
        self.left_stack.setCurrentIndex(index)
        self.folder_section.setVisible(index == 0)
        if index == 1:
            self.search_proj_input.setFocus()

    def show_project_search(self):
        if not self.check_unsaved_files_before_action():
            return
        self.switch_left_panel(1)
        self.search_proj_input.setFocus()
        self.search_proj_input.selectAll()

    def show_project_replace(self):
        self.show_project_search()
        if not self.replace_widget.isVisible():
            self.toggle_replace_inputs()
        self.replace_proj_input.setFocus()

    def do_replace_one(self):
        current_item = self.search_results_tree.currentItem()
        if not current_item or not isinstance(current_item.data(0, Qt.UserRole), dict):
            return

        data = current_item.data(0, Qt.UserRole)
        filepath = data["path"]
        search_text = self.search_proj_input.text()
        replace_text = self.replace_proj_input.text()

        target_line = data["line"]
        target_col = data["col"]
        match_len = data["len"]

        try:
            with open(filepath, "r", encoding="utf-8") as file:
                lines = file.readlines()

            if target_line >= len(lines):
                return

            current_line_text = lines[target_line]
            actual_match = current_line_text[target_col : target_col + match_len]
            is_valid_match = (
                (actual_match == search_text)
                if self.match_case_cb.isChecked()
                else (actual_match.lower() == search_text.lower())
            )

            if is_valid_match:
                new_line_text = (
                    current_line_text[:target_col]
                    + replace_text
                    + current_line_text[target_col + match_len :]
                )
                lines[target_line] = new_line_text

                with open(filepath, "w", encoding="utf-8") as file:
                    file.writelines(lines)

                self.reload_editor_if_open(filepath)

                parent = current_item.parent()
                if parent:
                    parent.removeChild(current_item)
                    self.search_result_count -= 1
                    self.search_status_label.setText(
                        f"{self.search_result_count} results found"
                    )

                    if parent.childCount() == 0:
                        root = self.search_results_tree.invisibleRootItem()
                        root.removeChild(parent)

        except Exception as error:
            print(f"Error replacing directly in file: {error}")

    def open_file_from_search(self, item, column):
        data = item.data(0, Qt.UserRole)
        if isinstance(data, dict):
            self.open_specific_file(data["path"])
            editor = self.get_current_editor()
            if editor:
                editor.setCursorPosition(data["line"], data["col"])
                editor.setSelection(
                    data["line"], data["col"], data["line"], data["col"] + data["len"]
                )
                editor.ensureLineVisible(data["line"])
                editor.setFocus()
        elif isinstance(data, str):
            self.open_specific_file(data)

    def do_project_search(self):
        if not self.check_unsaved_files_before_action():
            return
        term = self.search_proj_input.text()
        self.search_results_tree.clear()
        self.search_result_count = 0
        if not term or not self.current_project_dir:
            self.search_status_label.setText("")
            return
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.stop()
            self.search_worker.wait()
        self.search_status_label.setText("Searching...")
        match_case = self.match_case_cb.isChecked()
        self.search_worker = SearchWorker(self.current_project_dir, term, match_case)
        self.search_worker.file_matches_found.connect(self.on_search_file_matches_found)
        self.search_worker.finished.connect(self.on_search_finished)
        self.search_worker.start()

    def on_search_file_matches_found(self, filepath, matches):
        import os
        import re

        rel_path = os.path.relpath(filepath, self.current_project_dir)
        file_node = QTreeWidgetItem(self.search_results_tree, [rel_path])
        file_node.setData(0, Qt.UserRole, filepath)
        file_node.setExpanded(True)
        file_node.setForeground(0, QColor(f"{theme.color42}"))
        term = self.search_proj_input.text()
        flags = 0 if self.match_case_cb.isChecked() else re.IGNORECASE
        abs_path = os.path.abspath(filepath)
        real_lines = []
        if abs_path in self.cache:
            real_lines = self.cache[abs_path].splitlines()
        else:
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    real_lines = f.read().splitlines()
            except Exception:
                pass
        for line_idx, line_text in matches:
            target_text = line_text
            if real_lines and line_idx < len(real_lines):
                target_text = real_lines[line_idx]
            for match in re.finditer(re.escape(term), target_text, flags):
                start_col = match.start()
                display_text = f"{line_idx + 1}:{start_col + 1}: {target_text.strip()}"
                if len(display_text) > 100:
                    display_text = display_text[:100] + "..."
                item = QTreeWidgetItem(file_node, [display_text])
                item.setData(
                    0,
                    Qt.UserRole,
                    {
                        "path": filepath,
                        "line": line_idx,
                        "col": start_col,
                        "len": len(term),
                    },
                )
                self.search_result_count += 1
        self.search_status_label.setText(f"Found {self.search_result_count} results...")

    def on_search_finished(self):
        if self.search_result_count == 0:
            self.search_status_label.setText("No results found.")
        else:
            self.search_status_label.setText(
                f"{self.search_result_count} results found."
            )

    def do_replace_in_file(self):
        current_item = self.search_results_tree.currentItem()
        if not current_item:
            return

        file_node = (
            current_item if current_item.childCount() > 0 else current_item.parent()
        )
        if not file_node or file_node.childCount() == 0:
            return

        filepath = file_node.child(0).data(0, Qt.UserRole)["path"]
        search_text = self.search_proj_input.text()
        replace_text = self.replace_proj_input.text()

        try:
            import re

            with open(filepath, "r", encoding="utf-8") as file:
                content = file.read()

            flags = 0 if self.match_case_cb.isChecked() else re.IGNORECASE
            new_content = re.sub(
                re.escape(search_text), replace_text, content, flags=flags
            )

            with open(filepath, "w", encoding="utf-8") as file:
                file.write(new_content)

            self.reload_editor_if_open(filepath)

            self.search_result_count -= file_node.childCount()
            root = self.search_results_tree.invisibleRootItem()
            root.removeChild(file_node)
            self.search_status_label.setText(
                f"{self.search_result_count} results found"
            )

        except Exception as error:
            print(f"Error replacing in file: {error}")

    def do_project_replace(self):
        root = self.search_results_tree.invisibleRootItem()
        file_count = root.childCount()

        if file_count == 0:
            return

        search_text = self.search_proj_input.text()
        replace_text = self.replace_proj_input.text()
        flags = 0 if self.match_case_cb.isChecked() else re.IGNORECASE
        import re

        for i in range(file_count - 1, -1, -1):
            file_node = root.child(i)
            if file_node.childCount() > 0:
                filepath = file_node.child(0).data(0, Qt.UserRole)["path"]
                try:
                    with open(filepath, "r", encoding="utf-8") as file:
                        content = file.read()

                    new_content = re.sub(
                        re.escape(search_text), replace_text, content, flags=flags
                    )

                    with open(filepath, "w", encoding="utf-8") as file:
                        file.write(new_content)

                    self.reload_editor_if_open(filepath)
                except Exception as error:
                    print(f"Error during project replace in {filepath}: {error}")

        self.search_results_tree.clear()
        self.search_result_count = 0
        self.search_status_label.setText("All occurrences replaced.")

    def reload_editor_if_open(self, filepath):
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if (
                hasattr(tab, "filepath")
                and tab.filepath is not None
                and os.path.abspath(tab.filepath) == os.path.abspath(filepath)
            ):
                line, col = (
                    tab.editor.getCursorPosition()
                    if hasattr(tab, "getCursorPosition")
                    else (0, 0)
                )

                try:
                    with open(filepath, "r", encoding="utf-8") as file:
                        content = file.read()
                        tab.editor.setText(content)
                        tab.editor.setCursorPosition(line, col)
                        tab.save()
                except Exception as e:
                    print(f"Error reloading file {filepath}: {e}")
                break


def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except AttributeError:
        pass

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication([])
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)
    app.setStyle("Fusion")
    app.setProperty("restart_requested", True)

    while app.property("restart_requested"):
        app.setProperty("restart_requested", False)
        try:
            from src.theme_manager import theme

            theme.reload_theme()
        except Exception as e:
            print(f"Error loading theme at startup: {e}")
        window = MainWindow()
        window.show()
        exit_code = app.exec_()
        if not app.property("restart_requested"):
            sys.exit(exit_code)


if __name__ == "__main__":
    main()
