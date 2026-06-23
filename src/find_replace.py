import re

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QShortcut,
)


class FindReplaceDialog(QDialog):
    def __init__(self, parent=None, editor=None):
        super().__init__(parent)
        self.setWindowTitle("Find & Replace")
        self.setModal(False)
        self.editor = editor
        layout = QGridLayout(self)
        self.find_label = QLabel("Find:")
        self.find_input = QLineEdit()
        self.replace_label = QLabel("Replace:")
        self.replace_input = QLineEdit()
        self.case_checkbox = QCheckBox("Case sensitive")
        self.find_btn = QPushButton("Find Next")
        self.replace_btn = QPushButton("Replace")
        self.replace_all_btn = QPushButton("Replace All")
        self.close_btn = QPushButton("Close")
        layout.addWidget(self.find_label, 0, 0)
        layout.addWidget(self.find_input, 0, 1, 1, 3)
        layout.addWidget(self.replace_label, 1, 0)
        layout.addWidget(self.replace_input, 1, 1, 1, 3)
        layout.addWidget(self.case_checkbox, 2, 0)
        layout.addWidget(self.find_btn, 2, 1)
        layout.addWidget(self.replace_btn, 2, 2)
        layout.addWidget(self.replace_all_btn, 2, 3)
        layout.addWidget(self.close_btn, 3, 0, 1, 4)
        self.find_btn.clicked.connect(self.find_next)
        self.replace_btn.clicked.connect(self.replace_one)
        self.replace_all_btn.clicked.connect(self.replace_all)
        self.close_btn.clicked.connect(self.close)
        self.find_shortcut = QShortcut(QKeySequence("Return"), self)
        self.find_shortcut.activated.connect(self.find_next)
        self.replace_shortcut = QShortcut(QKeySequence("Shift+Return"), self)
        self.replace_shortcut.activated.connect(self.replace_one)
        self.replace_all_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.replace_all_shortcut.activated.connect(self.replace_all)
        self.find_input.setFocus()

    def find_next(self):
        if not self.editor:
            return
        text = self.find_input.text()
        if not text:
            return
        case_sensitive = self.case_checkbox.isChecked()
        found = self.editor.findFirst(text, False, case_sensitive, False, True, True)
        if not found:
            QMessageBox.information(self, "Find", "No more matches found.")

    def replace_one(self):
        if not self.editor:
            return
        selected = self.editor.selectedText()
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        case_sensitive = self.case_checkbox.isChecked()
        if (case_sensitive and selected == find_text) or (
            not case_sensitive and selected.lower() == find_text.lower()
        ):
            self.editor.replaceSelectedText(replace_text)
        self.find_next()

    def replace_all(self):
        if not self.editor:
            return
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        if not find_text:
            return
        content = self.editor.text()
        if self.case_checkbox.isChecked():
            new_content = content.replace(find_text, replace_text)
        else:
            new_content = re.sub(
                re.escape(find_text), replace_text, content, flags=re.IGNORECASE
            )
        self.editor.setText(new_content)
