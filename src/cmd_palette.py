import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QWidget,
)

from .theme_manager import theme
from .themed_dialog import (
    ThemedBaseDialog,
    set_input_placeholder_color,
    themed_input_stylesheet,
)

logger = logging.getLogger(__name__)


class CommandPalette(ThemedBaseDialog):
    def __init__(self, parent=None, commands=None):
        super().__init__(
            parent,
            Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint,
            "CommandPaletteContainer",
        )
        self.setFixedSize(600, 420)
        self.commands = commands or []
        container_layout = self.content_layout
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type a command...")
        self.search_input.setStyleSheet(
            themed_input_stylesheet(
                "QLineEdit",
                background_color="transparent",
                padding="12px 16px",
                border=f"none; border-bottom: 1px solid {theme.color13}",
                focus_border=f"none; border-bottom: 1px solid {theme.color35}",
                border_radius="0px",
            )
            + "QLineEdit { font-size: 14px; }"
        )
        set_input_placeholder_color(self.search_input)
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
        logger.debug("Executing command palette action: %s", item.text())
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
