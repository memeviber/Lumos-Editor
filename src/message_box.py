from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialogButtonBox, QHBoxLayout, QLabel, QStyle, QVBoxLayout

from .theme_manager import theme
from .themed_dialog import ThemedBaseDialog, ThemedDialogTitleBar


class QMessageBox(ThemedBaseDialog):
    NoIcon = 0
    Information = 1
    Warning = 2
    Critical = 3
    Question = 4

    Ok = QDialogButtonBox.Ok
    Save = QDialogButtonBox.Save
    SaveAll = QDialogButtonBox.SaveAll
    Open = QDialogButtonBox.Open
    Yes = QDialogButtonBox.Yes
    YesToAll = QDialogButtonBox.YesToAll
    No = QDialogButtonBox.No
    NoToAll = QDialogButtonBox.NoToAll
    Abort = QDialogButtonBox.Abort
    Retry = QDialogButtonBox.Retry
    Ignore = QDialogButtonBox.Ignore
    Close = QDialogButtonBox.Close
    Cancel = QDialogButtonBox.Cancel
    Discard = QDialogButtonBox.Discard
    Help = QDialogButtonBox.Help
    Apply = QDialogButtonBox.Apply
    Reset = QDialogButtonBox.Reset
    RestoreDefaults = QDialogButtonBox.RestoreDefaults

    def __init__(self, parent=None):
        super().__init__(
            parent,
            Qt.Dialog | Qt.FramelessWindowHint,
            "ThemedMessageBoxContainer",
        )
        self._icon = self.NoIcon
        self._standard_buttons = self.Ok
        self._default_button = None

        self.setMinimumWidth(380)
        self.setMaximumWidth(560)

        self.title_bar = ThemedDialogTitleBar(self.container)
        self.title_bar.closeRequested.connect(self.reject)
        self.content_layout.addWidget(self.title_bar)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(20, 18, 20, 14)
        content_layout.setSpacing(14)
        self.message_icon_label = QLabel(self.container)
        self.message_icon_label.setFixedSize(32, 32)
        self.message_icon_label.hide()
        content_layout.addWidget(self.message_icon_label, 0, Qt.AlignTop)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)
        self.text_label = QLabel(self.container)
        self.text_label.setWordWrap(True)
        text_layout.addWidget(self.text_label)
        self.informative_label = QLabel(self.container)
        self.informative_label.setWordWrap(True)
        self.informative_label.setStyleSheet(f"color: {theme.color26};")
        self.informative_label.hide()
        text_layout.addWidget(self.informative_label)
        content_layout.addLayout(text_layout, 1)
        self.content_layout.addLayout(content_layout, 1)

        self.button_box = QDialogButtonBox(self.container)
        self.button_box.setStyleSheet(
            """
            QDialogButtonBox {
                background: transparent;
                border: none;
            }
            """
        )
        self.button_box.clicked.connect(self._on_button_clicked)
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(20, 0, 20, 18)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(self.button_box)
        self.content_layout.addLayout(buttons_layout)

        self.setStandardButtons(self._standard_buttons)

    def setWindowTitle(self, title):
        super().setWindowTitle(title)
        if hasattr(self, "title_bar"):
            self.title_bar.setTitle(title)

    def setWindowIcon(self, icon):
        super().setWindowIcon(icon)
        if hasattr(self, "title_bar"):
            self.title_bar.setWindowIcon(icon)

    def setIcon(self, icon):
        self._icon = icon
        style_icons = {
            self.Information: QStyle.SP_MessageBoxInformation,
            self.Warning: QStyle.SP_MessageBoxWarning,
            self.Critical: QStyle.SP_MessageBoxCritical,
            self.Question: QStyle.SP_MessageBoxQuestion,
        }
        standard_icon = style_icons.get(icon)
        if standard_icon is None:
            self.message_icon_label.clear()
            self.message_icon_label.hide()
            return
        self.message_icon_label.setPixmap(
            self.style().standardIcon(standard_icon).pixmap(32, 32)
        )
        self.message_icon_label.show()

    def setText(self, text):
        self.text_label.setText(text)

    def setInformativeText(self, text):
        self.informative_label.setText(text)
        self.informative_label.setVisible(bool(text))

    def setStandardButtons(self, buttons):
        self._standard_buttons = buttons
        self.button_box.setStandardButtons(buttons)
        push_buttons = self.button_box.buttons()
        default_button = next(
            (
                button
                for button in push_buttons
                if self.button_box.standardButton(button) == self._default_button
            ),
            push_buttons[0] if push_buttons else None,
        )
        for button in push_buttons:
            is_default = button is default_button
            button.setDefault(is_default)
            button.setAutoDefault(is_default)

    def setDefaultButton(self, button):
        self._default_button = button
        for push_button in self.button_box.buttons():
            is_default = self.button_box.standardButton(push_button) == button
            push_button.setDefault(is_default)
            push_button.setAutoDefault(is_default)

    def _on_button_clicked(self, button):
        self.done(int(self.button_box.standardButton(button)))

    @classmethod
    def _show_message(cls, parent, title, text, icon, buttons=None, defaultButton=None):
        box = cls(parent)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(cls.Ok if buttons is None else buttons)
        if defaultButton is not None:
            box.setDefaultButton(defaultButton)
        return box.exec_()

    @classmethod
    def information(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._show_message(
            parent, title, text, cls.Information, buttons, defaultButton
        )

    @classmethod
    def warning(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._show_message(
            parent, title, text, cls.Warning, buttons, defaultButton
        )

    @classmethod
    def critical(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._show_message(
            parent, title, text, cls.Critical, buttons, defaultButton
        )

    @classmethod
    def question(cls, parent, title, text, buttons=None, defaultButton=None):
        return cls._show_message(
            parent, title, text, cls.Question, buttons, defaultButton
        )
