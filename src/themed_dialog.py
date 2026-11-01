from PyQt5.QtCore import QEvent, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .theme_manager import theme


def themed_dialog_stylesheet(dialog_selector):
    return f"""
        {dialog_selector} {{
            background-color: {theme.color2};
            color: {theme.color27};
            border: 1px solid {theme.color13};
            border-radius: 8px;
        }}
        QLabel {{
            color: {theme.color27};
            background: transparent;
        }}
        QLineEdit, QComboBox, QTextEdit, QListView, QTreeView {{
            background-color: {theme.color1};
            color: {theme.color27};
            border: 1px solid {theme.color13};
            border-radius: 4px;
            padding: 5px;
            selection-background-color: {theme.color35};
            selection-color: {theme.color31};
        }}
        QHeaderView::section {{
            background-color: {theme.color7};
            color: {theme.color27};
            border: 1px solid {theme.color13};
            padding: 4px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {theme.color2};
            color: {theme.color27};
            selection-background-color: {theme.color9};
        }}
        QCheckBox {{
            color: {theme.color27};
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            background-color: {theme.color1};
            border: 1px solid {theme.color13};
            border-radius: 3px;
        }}
        QCheckBox::indicator:hover {{
            border-color: {theme.color35};
        }}
        QCheckBox::indicator:checked {{
            background-color: {theme.color35};
            border-color: {theme.color35};
            image: url(resources:/checkmark.png);
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: {theme.color37};
            border-color: {theme.color37};
        }}
        QCheckBox::indicator:disabled {{
            background-color: {theme.color7};
            border-color: {theme.color13};
        }}
        QPushButton {{
            background-color: {theme.color7};
            color: {theme.color27};
            border: 1px solid {theme.color13};
            border-radius: 4px;
            min-width: 76px;
            padding: 6px 12px;
        }}
        QPushButton:hover {{
            background-color: {theme.color9};
        }}
        QPushButton:pressed {{
            background-color: {theme.color11};
        }}
        QPushButton:default {{
            background-color: {theme.color35};
            color: {theme.color31};
            border-color: {theme.color35};
        }}
        QPushButton:default:hover {{
            background-color: {theme.color37};
        }}
    """


class ThemedDialogTitleBar(QWidget):
    closeRequested = pyqtSignal()

    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self._drag_position = None
        self.setObjectName("ThemedDialogTitleBar")
        self.setFixedHeight(40)
        self.installEventFilter(self)
        self.setStyleSheet(
            f"""
            QWidget#ThemedDialogTitleBar {{
                background: {theme.color2};
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
            }}
            QToolButton#ThemedDialogCloseButton {{
                background: {theme.color2};
                border: none;
                border-radius: 4px;
            }}
            QToolButton#ThemedDialogCloseButton:hover {{
                background: {theme.color9};
            }}
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 8, 4)
        layout.setSpacing(8)

        self.window_icon_label = QLabel(self)
        self.window_icon_label.setFixedSize(18, 18)
        self.window_icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.window_icon_label.setPixmap(
            QIcon("resources:/lumos-icon.png").pixmap(16, 16)
        )
        layout.addWidget(self.window_icon_label, 0, Qt.AlignVCenter)

        self.title_label = QLabel(title, self)
        self.title_label.setFont(QFont("Segoe UI", 10))
        self.title_label.setStyleSheet(
            f"color: {theme.color30}; background: {theme.color2};"
        )
        self.title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.title_label, 1, Qt.AlignVCenter)

        self.close_button = QToolButton(self)
        self.close_button.setObjectName("ThemedDialogCloseButton")
        self.close_button.setIcon(QIcon("resources:/close-window-icon.png"))
        self.close_button.setIconSize(QSize(16, 16))
        self.close_button.setToolTip("Close")
        self.close_button.setFixedSize(34, 28)
        self.close_button.setFocusPolicy(Qt.NoFocus)
        self.close_button.clicked.connect(self.closeRequested)
        layout.addWidget(self.close_button, 0, Qt.AlignVCenter)

    def setTitle(self, title):
        self.title_label.setText(title)

    def setWindowIcon(self, icon):
        self.window_icon_label.setPixmap(icon.pixmap(16, 16))

    def eventFilter(self, watched, event):
        if watched is self:
            window = self.window()
            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._drag_position = event.globalPos() - window.frameGeometry().topLeft()
                return True
            if event.type() == QEvent.MouseMove and self._drag_position is not None:
                if event.buttons() & Qt.LeftButton:
                    window.move(event.globalPos() - self._drag_position)
                    return True
            if event.type() == QEvent.MouseButtonRelease:
                self._drag_position = None
                return True
        return super().eventFilter(watched, event)


class ThemedInputDialog(QDialog):
    TextInput = 0
    IntInput = 1
    DoubleInput = 2

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Dialog | Qt.FramelessWindowHint)
        self.setObjectName("ThemedInputDialog")
        self.setStyleSheet(themed_dialog_stylesheet("QDialog#ThemedInputDialog"))
        self._input_mode = self.TextInput
        self._label = QLabel(self)
        self._input_widget = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(1, 1, 1, 1)
        self._layout.setSpacing(0)
        self.title_bar = ThemedDialogTitleBar(self)
        self.title_bar.closeRequested.connect(self.reject)
        self._layout.addWidget(self.title_bar)

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 14, 16, 8)
        content_layout.setSpacing(10)
        content_layout.addWidget(self._label)
        self._content_layout = content_layout
        self._layout.addWidget(content)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(16, 4, 16, 16)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.button_box)
        self._layout.addLayout(buttons_layout)
        self.setInputMode(self.TextInput)

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        if hasattr(self, "title_bar"):
            self.title_bar.setTitle(title)

    def setWindowIcon(self, icon):
        super().setWindowIcon(icon)
        if hasattr(self, "title_bar"):
            self.title_bar.setWindowIcon(icon)

    def setLabelText(self, text):
        self._label.setText(text)

    def setInputMode(self, mode):
        self._input_mode = mode
        if self._input_widget is not None:
            self._content_layout.removeWidget(self._input_widget)
            self._input_widget.deleteLater()
        self._input_widget = QLineEdit(self)
        self._content_layout.addWidget(self._input_widget)

    def setTextValue(self, text):
        if isinstance(self._input_widget, QLineEdit):
            self._input_widget.setText(text)

    def textValue(self):
        if isinstance(self._input_widget, QLineEdit):
            return self._input_widget.text()
        return ""

    def _set_items(self, items, current=0, editable=False):
        if self._input_widget is not None:
            self._content_layout.removeWidget(self._input_widget)
            self._input_widget.deleteLater()
        self._input_widget = QComboBox(self)
        self._input_widget.addItems(items)
        self._input_widget.setEditable(editable)
        if items:
            self._input_widget.setCurrentIndex(current)
        self._content_layout.addWidget(self._input_widget)

    def _set_multiline(self, text):
        if self._input_widget is not None:
            self._content_layout.removeWidget(self._input_widget)
            self._input_widget.deleteLater()
        self._input_widget = QTextEdit(self)
        self._input_widget.setPlainText(text)
        self._input_widget.setMinimumSize(360, 120)
        self._content_layout.addWidget(self._input_widget)

    @classmethod
    def getText(
        cls,
        parent,
        title,
        label,
        echo=QLineEdit.Normal,
        text="",
        flags=Qt.WindowFlags(),
        inputMethodHints=Qt.ImhNone,
    ):
        dialog = cls(parent)
        dialog.setWindowFlags(dialog.windowFlags() | flags)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog._input_widget.setEchoMode(echo)
        dialog._input_widget.setText(text)
        dialog._input_widget.setInputMethodHints(inputMethodHints)
        result = dialog.exec_()
        return dialog.textValue(), result == QDialog.Accepted

    @classmethod
    def getItem(
        cls,
        parent,
        title,
        label,
        items,
        current=0,
        editable=True,
        flags=Qt.WindowFlags(),
        inputMethodHints=Qt.ImhNone,
    ):
        dialog = cls(parent)
        dialog.setWindowFlags(dialog.windowFlags() | flags)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog._set_items(items, current, editable)
        dialog._input_widget.setInputMethodHints(inputMethodHints)
        result = dialog.exec_()
        return dialog._input_widget.currentText(), result == QDialog.Accepted

    @classmethod
    def getMultiLineText(
        cls,
        parent,
        title,
        label,
        text="",
        flags=Qt.WindowFlags(),
        inputMethodHints=Qt.ImhNone,
    ):
        dialog = cls(parent)
        dialog.setWindowFlags(dialog.windowFlags() | flags)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog._set_multiline(text)
        dialog._input_widget.setInputMethodHints(inputMethodHints)
        result = dialog.exec_()
        return dialog._input_widget.toPlainText(), result == QDialog.Accepted


class ThemedFileDialog(QDialog):
    DontUseNativeDialog = QFileDialog.DontUseNativeDialog
    ShowDirsOnly = QFileDialog.ShowDirsOnly
    DontResolveSymlinks = QFileDialog.DontResolveSymlinks

    def __init__(
        self,
        parent=None,
        caption="",
        directory="",
        filter="",
        options=QFileDialog.Options(),
    ):
        super().__init__(parent, Qt.Dialog | Qt.FramelessWindowHint)
        self.setObjectName("ThemedFileDialog")
        self.setWindowTitle(caption)
        self.setMinimumSize(720, 480)
        self.setStyleSheet(themed_dialog_stylesheet("QDialog#ThemedFileDialog"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.title_bar = ThemedDialogTitleBar(self, caption)
        self.title_bar.closeRequested.connect(self.reject)
        layout.addWidget(self.title_bar)

        self.file_dialog = QFileDialog(None, caption, directory, filter)
        self.file_dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        self.file_dialog.setOptions(options | QFileDialog.DontUseNativeDialog)
        self.file_dialog.setWindowFlags(Qt.Widget)
        self.file_dialog.setStyleSheet(themed_dialog_stylesheet("QFileDialog"))
        layout.addWidget(self.file_dialog, 1)
        self.file_dialog.accepted.connect(self.accept)
        self.file_dialog.rejected.connect(self.reject)

    @classmethod
    def getOpenFileName(
        cls, parent=None, caption="", directory="", filter="", options=QFileDialog.Options()
    ):
        dialog = cls(parent, caption, directory, filter, options)
        if dialog.exec_() == QDialog.Accepted:
            files = dialog.file_dialog.selectedFiles()
            return (files[0] if files else "", dialog.file_dialog.selectedNameFilter())
        return "", dialog.file_dialog.selectedNameFilter()

    @classmethod
    def getOpenFileNames(
        cls, parent=None, caption="", directory="", filter="", options=QFileDialog.Options()
    ):
        dialog = cls(parent, caption, directory, filter, options)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.file_dialog.selectedFiles(), dialog.file_dialog.selectedNameFilter()
        return [], dialog.file_dialog.selectedNameFilter()

    @classmethod
    def getSaveFileName(
        cls, parent=None, caption="", directory="", filter="", options=QFileDialog.Options()
    ):
        dialog = cls(parent, caption, directory, filter, options)
        dialog.file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        if dialog.exec_() == QDialog.Accepted:
            files = dialog.file_dialog.selectedFiles()
            return (files[0] if files else "", dialog.file_dialog.selectedNameFilter())
        return "", dialog.file_dialog.selectedNameFilter()

    @classmethod
    def getExistingDirectory(
        cls, parent=None, caption="", directory="", options=QFileDialog.ShowDirsOnly
    ):
        dialog = cls(parent, caption, directory, options=options)
        dialog.file_dialog.setFileMode(QFileDialog.Directory)
        dialog.file_dialog.setOption(
            QFileDialog.ShowDirsOnly, bool(options & QFileDialog.ShowDirsOnly)
        )
        if dialog.exec_() == QDialog.Accepted:
            files = dialog.file_dialog.selectedFiles()
            return files[0] if files else ""
        return ""
