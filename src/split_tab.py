from .theme_manager import theme
import difflib

from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


class SplitTab(QWidget):
    def __init__(self, left_editor_tab, right_editor_tab, parent=None, mode=None):
        super().__init__(parent)
        self.left_editor_tab = left_editor_tab
        self.right_editor_tab = right_editor_tab
        self.mode = mode
        self.active_editor = self.left_editor_tab
        self.tabname = "Split View"
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("border: none; margin: 0px; padding: 0px;")
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.left_widget = self._create_pane(self.left_editor_tab, is_disk_side=False)
        self.right_widget = self._create_pane(self.right_editor_tab, is_disk_side=True)
        splitter.addWidget(self.left_widget)
        splitter.addWidget(self.right_widget)
        self.left_widget.setMinimumWidth(250)
        self.right_widget.setMinimumWidth(250)
        main_layout.addWidget(splitter)
        for tab in (self.left_editor_tab, self.right_editor_tab):
            tab.installEventFilter(self)
            try:
                tab.editor.installEventFilter(self)
            except AttributeError:
                pass
        self._update_active_visuals()
        left_is_text = hasattr(self.left_editor_tab, "editor")
        right_is_text = hasattr(self.right_editor_tab, "editor")
        if self.mode == "diff" and left_is_text and right_is_text:
            self.setup_diff_indicators()
            self.sync_scroll()
            self.run_diff()
            self.left_editor_tab.editor.textChanged.connect(self.run_diff)
            self.right_editor_tab.editor.textChanged.connect(self.run_diff)

    def setup_diff_indicators(self):
        INDIC_FULLBOX = 16
        for tab in [self.left_editor_tab, self.right_editor_tab]:
            editor = tab.editor
            editor.SendScintilla(editor.SCI_INDICSETSTYLE, 8, INDIC_FULLBOX)
            editor.SendScintilla(editor.SCI_INDICSETFORE, 8, QColor(249, 117, 131))
            editor.SendScintilla(editor.SCI_INDICSETALPHA, 8, 45)
            editor.SendScintilla(editor.SCI_INDICSETUNDER, 8, True)
            editor.SendScintilla(editor.SCI_INDICSETSTYLE, 9, INDIC_FULLBOX)
            editor.SendScintilla(editor.SCI_INDICSETFORE, 9, QColor(133, 232, 157))
            editor.SendScintilla(editor.SCI_INDICSETALPHA, 9, 45)
            editor.SendScintilla(editor.SCI_INDICSETUNDER, 9, True)

    def sync_scroll(self):
        left_sb = self.left_editor_tab.editor.verticalScrollBar()
        right_sb = self.right_editor_tab.editor.verticalScrollBar()

        def sync_to_right(val):
            right_sb.blockSignals(True)
            right_sb.setValue(val)
            right_sb.blockSignals(False)

        def sync_to_left(val):
            left_sb.blockSignals(True)
            left_sb.setValue(val)
            left_sb.blockSignals(False)

        left_sb.valueChanged.connect(sync_to_right)
        right_sb.valueChanged.connect(sync_to_left)

    def run_diff(self):
        left_ed = self.left_editor_tab.editor
        right_ed = self.right_editor_tab.editor
        for ed in (left_ed, right_ed):
            length = ed.length()
            ed.SendScintilla(ed.SCI_SETINDICATORCURRENT, 8)
            ed.SendScintilla(ed.SCI_INDICATORCLEARRANGE, 0, length)
            ed.SendScintilla(ed.SCI_SETINDICATORCURRENT, 9)
            ed.SendScintilla(ed.SCI_INDICATORCLEARRANGE, 0, length)
        text1 = left_ed.text().splitlines(keepends=True)
        text2 = right_ed.text().splitlines(keepends=True)
        matcher = difflib.SequenceMatcher(None, text1, text2)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag in ("replace", "delete"):
                for line in range(i1, i2):
                    self.apply_indicator(left_ed, line, 8)
            if tag in ("replace", "insert"):
                for line in range(j1, j2):
                    self.apply_indicator(right_ed, line, 9)

    def apply_indicator(self, editor, line_idx, indicator_id):
        pos = editor.SendScintilla(editor.SCI_POSITIONFROMLINE, line_idx)
        length = editor.SendScintilla(editor.SCI_LINELENGTH, line_idx)
        editor.SendScintilla(editor.SCI_SETINDICATORCURRENT, indicator_id)
        editor.SendScintilla(editor.SCI_INDICATORFILLRANGE, pos, length)

    def _create_pane(self, editor_tab, is_disk_side):
        container = QWidget()
        vlayout = QVBoxLayout(container)
        vlayout.setContentsMargins(1, 1, 1, 1)
        vlayout.setSpacing(0)
        display_name = getattr(editor_tab, "tabname", "Untitled")
        if self.mode == "diff":
            display_name += " (On Disk)" if is_disk_side else " (In-Memory)"
        title_label = QLabel(display_name)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title_label.setFixedHeight(26)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_label.setStyleSheet(
            f"QLabel {{ background-color: {theme.color2}; color: {theme.color27}; padding: 4px 8px; border-bottom: 2px solid {theme.color2}; }}"
        )
        vlayout.addWidget(title_label)
        old_parent = editor_tab.parentWidget()
        if old_parent is not None and old_parent is not container:
            old_layout = old_parent.layout()
            if old_layout is not None:
                old_layout.removeWidget(editor_tab)
        editor_tab.setParent(container)
        editor_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        editor_tab.show()
        vlayout.addWidget(editor_tab, 1)
        container.title_label = title_label
        container.setLayout(vlayout)
        return container

    def check_view_mode(self, editor_tab):
        if self.mode is None:
            return None
        if editor_tab == self.right_editor_tab:
            return "disk"
        elif editor_tab == self.left_editor_tab:
            return "memory"
        return None

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.FocusIn, QEvent.MouseButtonPress):
            is_left = (obj is self.left_editor_tab) or (
                hasattr(self.left_editor_tab, "editor")
                and obj is self.left_editor_tab.editor
            )
            is_right = (obj is self.right_editor_tab) or (
                hasattr(self.right_editor_tab, "editor")
                and obj is self.right_editor_tab.editor
            )
            if is_left:
                self._set_active_editor(self.left_editor_tab)
            elif is_right:
                self._set_active_editor(self.right_editor_tab)
        return super().eventFilter(obj, event)

    def _set_active_editor(self, editor_tab):
        if self.active_editor != editor_tab:
            self.active_editor = editor_tab
            self._update_active_visuals()

    def _update_active_visuals(self):
        active = f"border-bottom: 2px solid {theme.color38};"
        inactive = f"border-bottom: 2px solid {theme.color2};"
        base = f"background-color: {theme.color2}; color: {theme.color27}; padding: 4px 8px;"
        if self.active_editor is None:
            self.left_widget.title_label.setStyleSheet(base + inactive)
            self.right_widget.title_label.setStyleSheet(base + inactive)
        elif self.active_editor == self.left_editor_tab:
            self.left_widget.title_label.setStyleSheet(base + active)
            self.right_widget.title_label.setStyleSheet(base + inactive)
        else:
            self.right_widget.title_label.setStyleSheet(base + active)
            self.left_widget.title_label.setStyleSheet(base + inactive)

    def get_active_editor_tab(self):
        return self.active_editor

    def get_child_editors(self):
        return [self.left_editor_tab, self.right_editor_tab]
