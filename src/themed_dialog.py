import logging

from PyQt5.QtCore import QEvent, QSize, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QIcon, QPalette
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .theme_manager import theme

logger = logging.getLogger(__name__)

DIALOG_RADIUS = 8


def themed_input_stylesheet(
    selector,
    background_color=None,
    padding="5px",
    border=None,
    focus_border=None,
    border_radius="4px",
):
    background_color = background_color or theme.color1
    border = border or f"1px solid {theme.color13}"
    focus_border = focus_border or f"1px solid {theme.color35}"
    focus_selectors = ", ".join(f"{item.strip()}:focus" for item in selector.split(","))
    return f"""
        {selector} {{
            background-color: {background_color};
            color: {theme.color27};
            border: {border};
            border-radius: {border_radius};
            padding: {padding};
            selection-background-color: {theme.color35};
            selection-color: {theme.color31};
        }}
        {focus_selectors} {{
            border: {focus_border};
        }}
    """


def set_input_placeholder_color(widget):
    palette = widget.palette()
    palette.setColor(QPalette.PlaceholderText, QColor(theme.color26))
    widget.setPalette(palette)


def themed_dialog_stylesheet(container_selector):
    return f"""
        {container_selector} {{
            background-color: {theme.color2};
            color: {theme.color27};
            border: 1px solid {theme.color13};
            border-radius: {DIALOG_RADIUS}px;
        }}
        QLabel {{
            color: {theme.color27};
            background: transparent;
        }}
        QToolButton {{
            background-color: transparent;
            color: {theme.color27};
            border: 1px solid transparent;
            border-radius: 4px;
        }}
        QToolButton:hover {{
            background-color: {theme.color9};
            border-color: {theme.color13};
        }}
        QToolButton:pressed {{
            background-color: {theme.color11};
        }}
        {themed_input_stylesheet("QLineEdit, QComboBox, QTextEdit, QListView, QTreeView")}
        QHeaderView::section {{
            background-color: {theme.color7};
            color: {theme.color27};
            border: 1px solid {theme.color13};
            padding: 4px;
        }}
        QComboBox::drop-down {{
            background-color: {theme.color7};
            border: none;
            border-left: 1px solid {theme.color13};
            width: 22px;
        }}
        QComboBox::down-arrow {{
            image: url(resources:/chevron-down.png);
            width: 12px;
            height: 12px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {theme.color2};
            color: {theme.color27};
            border: 1px solid {theme.color13};
            outline: 0;
            selection-background-color: {theme.color9};
            selection-color: {theme.color27};
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {theme.color9};
            color: {theme.color27};
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


class ThemedBaseDialog(QDialog):
    def __init__(
        self,
        parent=None,
        window_flags=None,
        object_name="ThemedDialogContainer",
    ):
        logger.debug("Creating themed dialog: class=%s", type(self).__name__)
        if window_flags is None:
            super().__init__(parent)
        else:
            super().__init__(parent, window_flags)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setStyleSheet(f"QDialog#{object_name}Root {{ background: transparent; }}")
        self.setObjectName(f"{object_name}Root")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(1, 1, 1, 1)
        outer_layout.setSpacing(0)

        self.container = QWidget(self)
        self.container.setObjectName(object_name)
        self.container.setStyleSheet(themed_dialog_stylesheet(f"QWidget#{object_name}"))
        outer_layout.addWidget(self.container)

        self.content_layout = QVBoxLayout(self.container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        if hasattr(self, "title_bar"):
            self.title_bar.setTitle(title)

    def setWindowIcon(self, icon):
        super().setWindowIcon(icon)
        if hasattr(self, "title_bar"):
            self.title_bar.setWindowIcon(icon)


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
                background: transparent;
                border-bottom: 1px solid {theme.color1};
            }}
            QToolButton#ThemedDialogCloseButton {{
                background: transparent;
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
            f"color: {theme.color30}; background: transparent;"
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
            if (
                event.type() == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton
            ):
                self._drag_position = (
                    event.globalPos() - window.frameGeometry().topLeft()
                )
                return True
            if event.type() == QEvent.MouseMove and self._drag_position is not None:
                if event.buttons() & Qt.LeftButton:
                    window.move(event.globalPos() - self._drag_position)
                    return True
            if event.type() == QEvent.MouseButtonRelease:
                self._drag_position = None
                return True
        return super().eventFilter(watched, event)


class ThemedInputDialog(ThemedBaseDialog):
    TextInput = 0
    IntInput = 1
    DoubleInput = 2

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.Dialog | Qt.FramelessWindowHint,
            "ThemedInputDialogContainer",
        )

        self._input_mode = self.TextInput
        self._label = QLabel(self.container)
        self._input_widget = None

        self._layout = self.content_layout

        self.title_bar = ThemedDialogTitleBar(self.container)
        self.title_bar.closeRequested.connect(self.reject)
        self._layout.addWidget(self.title_bar)

        content = QWidget(self.container)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 14, 16, 8)
        content_layout.setSpacing(10)
        content_layout.addWidget(self._label)
        self._content_layout = content_layout
        self._layout.addWidget(content)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self.container
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
        set_input_placeholder_color(self._input_widget)
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
        set_input_placeholder_color(self._input_widget)
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
        set_input_placeholder_color(self._input_widget)
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
        if flags != Qt.WindowFlags():
            dialog.setWindowFlags(dialog.windowFlags() | flags)
            dialog.setAttribute(Qt.WA_TranslucentBackground, True)
            dialog.setAttribute(Qt.WA_NoSystemBackground, True)
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
        if flags != Qt.WindowFlags():
            dialog.setWindowFlags(dialog.windowFlags() | flags)
            dialog.setAttribute(Qt.WA_TranslucentBackground, True)
            dialog.setAttribute(Qt.WA_NoSystemBackground, True)
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
        if flags != Qt.WindowFlags():
            dialog.setWindowFlags(dialog.windowFlags() | flags)
            dialog.setAttribute(Qt.WA_TranslucentBackground, True)
            dialog.setAttribute(Qt.WA_NoSystemBackground, True)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog._set_multiline(text)
        dialog._input_widget.setInputMethodHints(inputMethodHints)
        result = dialog.exec_()
        return dialog._input_widget.toPlainText(), result == QDialog.Accepted


class ThemedFileDialog(ThemedBaseDialog):
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
        super().__init__(
            parent,
            Qt.Dialog | Qt.FramelessWindowHint,
            "ThemedFileDialogContainer",
        )
        self.setWindowTitle(caption)
        self.setMinimumSize(740, 500)

        container_layout = self.content_layout

        self.title_bar = ThemedDialogTitleBar(self.container, caption)
        self.title_bar.closeRequested.connect(self.reject)
        container_layout.addWidget(self.title_bar)

        content_wrapper = QWidget(self.container)
        content_wrapper.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_wrapper)
        content_layout.setContentsMargins(8, 2, 8, 8)
        content_layout.setSpacing(0)

        self.file_dialog = QFileDialog(content_wrapper, caption, directory, filter)
        self.file_dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        self.file_dialog.setOptions(options | QFileDialog.DontUseNativeDialog)
        self.file_dialog.setWindowFlags(Qt.Widget)
        self.file_dialog.setStyleSheet(
            "QFileDialog { background: transparent; border: none; }"
        )
        self._apply_file_dialog_palette()

        content_layout.addWidget(self.file_dialog)
        container_layout.addWidget(content_wrapper, 1)

        self.file_dialog.accepted.connect(self.accept)
        self.file_dialog.rejected.connect(self.reject)

    def _apply_file_dialog_palette(self):
        palette = self.file_dialog.palette()
        for role, color in (
            (QPalette.Window, theme.color2),
            (QPalette.Base, theme.color2),
            (QPalette.AlternateBase, theme.color7),
            (QPalette.Text, theme.color27),
            (QPalette.WindowText, theme.color27),
            (QPalette.Button, theme.color7),
            (QPalette.ButtonText, theme.color27),
            (QPalette.Highlight, theme.color9),
            (QPalette.HighlightedText, theme.color27),
        ):
            palette.setColor(role, QColor(color))
        self.file_dialog.setPalette(palette)

        for combo_box in self.file_dialog.findChildren(QComboBox):
            combo_box.setPalette(palette)
            popup_view = combo_box.view()
            popup_view.setPalette(palette)
            popup_view.setAutoFillBackground(True)
            popup_window = popup_view.window()
            popup_window.setPalette(palette)
            popup_window.setAutoFillBackground(True)
            popup_window.setStyleSheet(
                "QFrame {"
                f"background-color: {theme.color2};"
                f"color: {theme.color27};"
                f"border: 1px solid {theme.color13};"
                "}"
            )

        for header in self.file_dialog.findChildren(QHeaderView):
            header.setPalette(palette)
            header.setStyleSheet(f"QHeaderView {{color: {theme.color27};}}")

    @classmethod
    def getOpenFileName(
        cls,
        parent=None,
        caption="",
        directory="",
        filter="",
        options=QFileDialog.Options(),
    ):
        dialog = cls(parent, caption, directory, filter, options)
        if dialog.exec_() == QDialog.Accepted:
            files = dialog.file_dialog.selectedFiles()
            return (files[0] if files else "", dialog.file_dialog.selectedNameFilter())
        return "", dialog.file_dialog.selectedNameFilter()

    @classmethod
    def getOpenFileNames(
        cls,
        parent=None,
        caption="",
        directory="",
        filter="",
        options=QFileDialog.Options(),
    ):
        dialog = cls(parent, caption, directory, filter, options)
        if dialog.exec_() == QDialog.Accepted:
            return (
                dialog.file_dialog.selectedFiles(),
                dialog.file_dialog.selectedNameFilter(),
            )
        return [], dialog.file_dialog.selectedNameFilter()

    @classmethod
    def getSaveFileName(
        cls,
        parent=None,
        caption="",
        directory="",
        filter="",
        options=QFileDialog.Options(),
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
