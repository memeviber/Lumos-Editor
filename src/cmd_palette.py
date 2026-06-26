from .theme_manager import theme

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class CommandPalette(QDialog):
    def __init__(self, parent=None, commands=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(600, 420)
        self.commands = commands or []
        main_layout = QVBoxLayout(self)
        self.container = QFrame(self)
        self.container.setObjectName("CommandContainer")
        self.container.setStyleSheet(f"""
            QFrame#CommandContainer {{
                background-color: {theme.color2};
                border-radius: 8px;
                border: 1px solid {theme.color13};
            }}
        """)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type a command...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: transparent;
                color: {theme.color27};
                padding: 12px 16px;
                border: none;
                border-bottom: 1px solid {theme.color13};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-bottom: 1px solid {theme.color35};
            }}
        """)
        container_layout.addWidget(self.search_input)
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: transparent;
                border: none;
                outline: none;
                padding: 6px;
            }}
            QListWidget::item {{
                border-radius: 4px;
                margin-bottom: 2px;
            }}
            QListWidget::item:selected {{
                background-color: {theme.color33};
            }}
        """)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        container_layout.addWidget(self.list_widget)
        main_layout.addWidget(self.container)
        self.search_input.textChanged.connect(self.filter_commands)
        self.list_widget.itemActivated.connect(self.execute_command)
        self.populate_list(self.commands)
        self.search_input.setFocus()

    def populate_list(self, cmds):
        self.list_widget.clear()
        for cmd in cmds:
            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.UserRole, cmd["action"])
            row_widget = QWidget()
            row_widget.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(12, 8, 12, 8)
            name_label = QLabel(cmd["name"])
            name_label.setStyleSheet(f"color: {theme.color27}; font-size: 13px;")
            shortcut_label = QLabel(cmd.get("shortcut", ""))
            shortcut_label.setStyleSheet(
                "color: rgba(255, 255, 255, 0.4); font-size: 12px;"
            )
            row_layout.addWidget(name_label)
            row_layout.addStretch()
            row_layout.addWidget(shortcut_label)
            item.setSizeHint(row_widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row_widget)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def filter_commands(self, text):
        filtered = [cmd for cmd in self.commands if text.lower() in cmd["name"].lower()]
        self.populate_list(filtered)

    def execute_command(self, item):
        action = item.data(Qt.UserRole)
        self.accept()
        if action:
            action()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key_Down, Qt.Key_Up):
            self.list_widget.keyPressEvent(event)
        elif event.key() == Qt.Key_Return:
            if self.list_widget.currentItem():
                self.execute_command(self.list_widget.currentItem())
        else:
            super().keyPressEvent(event)
