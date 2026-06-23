from .theme_manager import theme
import collections
import functools
import os
import sys

import pyte
from PyQt5 import QtCore
from PyQt5.QtCore import QSize, Qt, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QClipboard, QColor, QFont, QFontMetrics, QPalette, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from pyte.screens import History

if sys.platform == "win32":
    try:
        from winpty import PTY
    except ImportError:
        PTY = None
else:
    import fcntl
    import pty
    import select
    import struct
    import subprocess
    import termios


def SafeSlot(*slot_args, **slot_kwargs):
    def error_managed(method):
        @pyqtSlot(*slot_args, **slot_kwargs)
        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            try:
                return method(*args, **kwargs)
            except Exception as e:
                sys.excepthook(*sys.exc_info())

        return wrapper

    return error_managed


control_keys_mapping = {
    QtCore.Qt.Key_A: b"\x01",
    QtCore.Qt.Key_B: b"\x02",
    QtCore.Qt.Key_C: b"\x03",
    QtCore.Qt.Key_D: b"\x04",
    QtCore.Qt.Key_E: b"\x05",
    QtCore.Qt.Key_F: b"\x06",
    QtCore.Qt.Key_G: b"\x07",
    QtCore.Qt.Key_H: b"\x08",
    QtCore.Qt.Key_I: b"\x09",
    QtCore.Qt.Key_J: b"\x0a",
    QtCore.Qt.Key_K: b"\x0b",
    QtCore.Qt.Key_L: b"\x0c",
    QtCore.Qt.Key_M: b"\x0d",
    QtCore.Qt.Key_N: b"\x0e",
    QtCore.Qt.Key_O: b"\x0f",
    QtCore.Qt.Key_P: b"\x10",
    QtCore.Qt.Key_Q: b"\x11",
    QtCore.Qt.Key_R: b"\x12",
    QtCore.Qt.Key_S: b"\x13",
    QtCore.Qt.Key_T: b"\x14",
    QtCore.Qt.Key_U: b"\x15",
    QtCore.Qt.Key_V: b"\x16",
    QtCore.Qt.Key_W: b"\x17",
    QtCore.Qt.Key_X: b"\x18",
    QtCore.Qt.Key_Y: b"\x19",
    QtCore.Qt.Key_Z: b"\x1a",
    QtCore.Qt.Key_Escape: b"\x1b",
    QtCore.Qt.Key_Backslash: b"\x1c",
    QtCore.Qt.Key_Underscore: b"\x1f",
}


normal_keys_mapping = {
    QtCore.Qt.Key_Return: b"\n",
    QtCore.Qt.Key_Space: b" ",
    QtCore.Qt.Key_Enter: b"\n",
    QtCore.Qt.Key_Tab: b"\t",
    QtCore.Qt.Key_Backspace: b"\x08",
    QtCore.Qt.Key_Home: b"\x47",
    QtCore.Qt.Key_End: b"\x4f",
    QtCore.Qt.Key_Left: b"\x02",
    QtCore.Qt.Key_Up: b"\x10",
    QtCore.Qt.Key_Right: b"\x06",
    QtCore.Qt.Key_Down: b"\x0e",
    QtCore.Qt.Key_PageUp: b"\x49",
    QtCore.Qt.Key_PageDown: b"\x51",
    QtCore.Qt.Key_F1: b"\x1b\x31",
    QtCore.Qt.Key_F2: b"\x1b\x32",
    QtCore.Qt.Key_F3: b"\x1b\x33",
    QtCore.Qt.Key_F4: b"\x1b\x34",
    QtCore.Qt.Key_F5: b"\x1b\x35",
    QtCore.Qt.Key_F6: b"\x1b\x36",
    QtCore.Qt.Key_F7: b"\x1b\x37",
    QtCore.Qt.Key_F8: b"\x1b\x38",
    QtCore.Qt.Key_F9: b"\x1b\x39",
    QtCore.Qt.Key_F10: b"\x1b\x30",
    QtCore.Qt.Key_F11: b"\x45",
    QtCore.Qt.Key_F12: b"\x46",
}


def QtKeyToAscii(event):
    if sys.platform == "darwin":
        if event.modifiers() == QtCore.Qt.MetaModifier:
            if event.key() == Qt.Key_Backspace:
                return control_keys_mapping.get(Qt.Key_W)
            return control_keys_mapping.get(event.key())
        elif event.modifiers() == QtCore.Qt.ControlModifier:
            if event.key() == Qt.Key_C:
                return "copy"
            elif event.key() == Qt.Key_V:
                return "paste"
            return None
        else:
            return normal_keys_mapping.get(event.key(), event.text().encode("utf8"))
    if event.modifiers() == QtCore.Qt.ControlModifier:
        return control_keys_mapping.get(event.key())
    else:
        return normal_keys_mapping.get(event.key(), event.text().encode("utf8"))


class Screen(pyte.HistoryScreen):
    def __init__(self, write_callback, cols, rows, historyLength):
        super().__init__(cols, rows, historyLength, ratio=1 / rows)
        self._write_callback = write_callback

    def write_process_input(self, data):
        try:
            self._write_callback(data)
        except Exception:
            pass

    def resize(self, lines, columns):
        lines = lines or self.lines
        columns = columns or self.columns
        if lines == self.lines and columns == self.columns:
            return
        self.dirty.clear()
        self.dirty.update(range(lines))
        self.save_cursor()
        if lines < self.lines:
            if lines <= self.cursor.y:
                nlines_to_move_up = self.lines - lines
                for i in range(nlines_to_move_up):
                    line = self.buffer[i]
                    self.history.top.append(line)
                self.cursor_position(0, 0)
                self.delete_lines(nlines_to_move_up)
                self.restore_cursor()
                self.cursor.y -= nlines_to_move_up
        else:
            self.restore_cursor()
        self.lines, self.columns = lines, columns
        self.history = History(
            self.history.top,
            self.history.bottom,
            1 / max(1, self.lines),
            self.history.size,
            self.history.position,
        )
        self.set_margins()


class Backend(QtCore.QThread):
    dataReady = pyqtSignal(bytes)
    processExited = pyqtSignal()

    def __init__(self, cmd, cols, rows):
        super().__init__()
        self.cmd = cmd
        self.cols = cols
        self.rows = rows
        self.running = True
        self.pty_win = None
        self.master_fd = None
        self.proc = None
        if sys.platform == "win32":
            self._init_windows()
        else:
            self._init_posix()

    def _init_windows(self):
        if PTY is None:
            return
        self.pty_win = PTY(self.cols, self.rows)
        cmd = self.cmd or "powershell.exe"
        if not os.path.isabs(cmd):
            import shutil

            resolved = shutil.which(cmd)
            if resolved:
                cmd = resolved
            elif cmd.lower() == "powershell.exe":
                cmd = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        try:
            self.pty_win.spawn(cmd)
        except Exception as e:
            err_msg = f"\r\n[!] Failed to spawn terminal: {cmd}\r\n[!] Error: {e}\r\n"
            QtCore.QTimer.singleShot(
                100, lambda: self.dataReady.emit(err_msg.encode("utf-8"))
            )

    def _init_posix(self):
        self.master_fd, slave_fd = pty.openpty()
        env = os.environ.copy()
        env["COLUMNS"] = str(self.cols)
        env["LINES"] = str(self.rows)
        env["TERM"] = "xterm-256color"
        env["LANG"] = env.get("LANG", "en_US.UTF-8")
        cmd = self.cmd or os.environ.get("SHELL", "bash")
        if isinstance(cmd, str):
            import shlex

            cmd = shlex.split(cmd)
        try:
            self.proc = subprocess.Popen(
                cmd,
                preexec_fn=os.setsid,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
            )
        except Exception as e:
            err_msg = f"\r\n[!] Failed to spawn terminal: {cmd}\r\n[!] Error: {e}\r\n"
            QtCore.QTimer.singleShot(
                100, lambda: self.dataReady.emit(err_msg.encode("utf-8"))
            )
        os.close(slave_fd)

    def run(self):
        import time

        if sys.platform == "win32":
            if PTY is None:
                self.dataReady.emit(
                    b"\r\n[!] ERROR: 'pywinpty' is not installed.\r\n[!] Please run 'pip install pywinpty' to enable terminal support on Windows.\r\n"
                )
                self.running = False
                self.processExited.emit()
                return
            if not self.pty_win:
                self.processExited.emit()
                return
            while self.running:
                try:
                    try:
                        out = self.pty_win.read(length=65536, blocking=False)
                    except TypeError:
                        out = self.pty_win.read(blocking=False)
                    if not out:
                        alive = True
                        if hasattr(self.pty_win, "isalive"):
                            alive = self.pty_win.isalive()
                        if not alive:
                            break
                        time.sleep(0.01)
                        continue
                    if isinstance(out, str):
                        out = out.encode("utf-8")
                    self.dataReady.emit(out)
                except EOFError:
                    break
                except Exception as e:
                    self.dataReady.emit(
                        f"\r\n[!] PTY read exception: {e}\r\n".encode("utf-8")
                    )
                    break
        else:
            while self.running:
                try:
                    r, _, _ = select.select([self.master_fd], [], [], 0.1)
                    if self.master_fd in r:
                        out = os.read(self.master_fd, 65536)
                        if not out:
                            break
                        self.dataReady.emit(out)
                    if self.proc and self.proc.poll() is not None:
                        break
                except OSError as e:
                    self.dataReady.emit(
                        f"\r\n[!] Posix read exception: {e}\r\n".encode("utf-8")
                    )
                    break
        self.running = False
        self.processExited.emit()

    def write(self, data):
        if sys.platform == "win32":
            if self.pty_win:
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                try:
                    self.pty_win.write(data)
                except Exception:
                    pass
        else:
            if self.master_fd is not None:
                if isinstance(data, str):
                    data = data.encode("utf-8")
                try:
                    os.write(self.master_fd, data)
                except OSError:
                    pass

    def resize(self, rows, cols):
        self.rows = rows
        self.cols = cols
        if sys.platform == "win32":
            if self.pty_win:
                try:
                    self.pty_win.set_size(cols, rows)
                except Exception:
                    pass
        else:
            if self.master_fd is not None:
                try:
                    winsize = struct.pack("HHHH", rows, cols, 0, 0)
                    fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
                except OSError:
                    pass

    def stop(self):
        self.running = False
        if sys.platform == "win32":
            try:
                if self.pty_win and hasattr(self.pty_win, "close"):
                    self.pty_win.close()
            except Exception:
                pass
        else:
            if self.proc:
                try:
                    self.proc.terminate()
                except OSError:
                    pass


class CommandInput(QLineEdit):
    def __init__(self, terminal_widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.term = terminal_widget
        self.history = []
        self.history_index = 0
        self.current_draft = ""

    def add_history(self, command):
        if command.strip():
            if not self.history or self.history[-1] != command:
                self.history.append(command)
        self.history_index = len(self.history)
        self.current_draft = ""

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        if modifiers == Qt.ControlModifier:
            if event.key() == Qt.Key_C and not self.hasSelectedText():
                self.term.push("\x03")
                return
            elif event.key() == Qt.Key_D:
                self.term.push("\x04")
                return
            elif event.key() == Qt.Key_L:
                self.term.push("\x0c")
                return
        if modifiers == Qt.NoModifier or modifiers == Qt.KeypadModifier:
            if event.key() == Qt.Key_Up:
                if self.history_index == len(self.history):
                    self.current_draft = self.text()
                if self.history_index > 0:
                    self.history_index -= 1
                    self.setText(self.history[self.history_index])
                return
            elif event.key() == Qt.Key_Down:
                if self.history_index < len(self.history) - 1:
                    self.history_index += 1
                    self.setText(self.history[self.history_index])
                elif self.history_index == len(self.history) - 1:
                    self.history_index += 1
                    self.setText(self.current_draft)
                return
        super().keyPressEvent(event)


class Terminal(QWidget):
    closed = pyqtSignal()

    def __init__(self, parent=None, cols=132):
        super().__init__(parent)
        self.term = _TerminalWidget(self, cols, rows=25)
        self.term.setReadOnly(True)
        self.scroll_bar = QScrollBar(Qt.Vertical, self)
        term_layout = QHBoxLayout()
        term_layout.addWidget(self.term)
        term_layout.addWidget(self.scroll_bar)
        term_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        term_layout.setContentsMargins(0, 0, 0, 0)
        term_layout.setSpacing(0)
        self.input_container = QWidget()
        self.input_container.setObjectName("InputContainer")
        self.input_container.setFixedHeight(30)
        self.input_container.setStyleSheet(
            "QWidget#InputContainer {"
            f"   background-color: {theme.color2};"
            f"   border-top: 1px solid {theme.color15};"
            "}"
        )
        input_layout = QHBoxLayout(self.input_container)
        input_layout.setContentsMargins(8, 0, 8, 0)
        input_layout.setSpacing(6)
        prompt_label = QLabel(">")
        prompt_label.setStyleSheet(
            f"color: {theme.color26}; font-family: Consolas, monospace; font-size: 13px; border: none;"
        )
        self.input_field = CommandInput(self.term)
        self.input_field.setStyleSheet(
            "QLineEdit {"
            f"   background: transparent; color: {theme.color26}; border: none;"
            "   font-family: Consolas, monospace; font-size: 13px;"
            "}"
        )
        self.input_field.returnPressed.connect(self._send_command)
        input_layout.addWidget(prompt_label)
        input_layout.addWidget(self.input_field)
        main_layout = QVBoxLayout(self)
        main_layout.addLayout(term_layout)
        main_layout.addWidget(self.input_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.MinimumExpanding)
        self.term.set_scroll_bar(self.scroll_bar)
        self.set_cmd("")

    @pyqtSlot()
    def _send_command(self):
        cmd = self.input_field.text()
        self.input_field.add_history(cmd)
        self.input_field.clear()
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.ShiftModifier:
            self.term.push(cmd + "\n")
        else:
            self.term.push(cmd + "\r")

    def minimumSizeHint(self):
        size = self.term.sizeHint()
        size.setWidth(size.width() + self.scroll_bar.width())
        return size

    def sizeHint(self):
        return self.minimumSizeHint()

    def get_rows(self):
        return self.term.rows

    def set_rows(self, rows):
        self.term.rows = rows
        self.adjustSize()
        self.updateGeometry()

    def get_cols(self):
        return self.term.cols

    def set_cols(self, cols):
        self.term.cols = cols
        self.adjustSize()
        self.updateGeometry()

    def get_bgcolor(self):
        return QColor.fromString(self.term.bg_color)

    def set_bgcolor(self, color):
        self.term.bg_color = color.name(QColor.HexRgb)

    def get_fgcolor(self):
        return QColor.fromString(self.term.fg_color)

    def set_fgcolor(self, color):
        self.term.fg_color = color.name(QColor.HexRgb)

    def get_cmd(self):
        return self.term._cmd

    def set_cmd(self, cmd):
        if not cmd:
            cmd = os.environ.get(
                "SHELL", "powershell.exe" if sys.platform == "win32" else "bash"
            )
        self.term._cmd = cmd
        if self.term.backend is None:
            self.term.clear()
            self.term.appendPlainText(f"Terminal - {repr(cmd)}")

    def is_running(self):
        return self.term.backend is not None

    @SafeSlot(bool)
    def start(self, deactivate_ctrl_d=True):
        self.term.start(deactivate_ctrl_d=deactivate_ctrl_d)

    @SafeSlot()
    def stop(self):
        self.term.stop()

    @SafeSlot(str)
    def push(self, text):
        return self.term.push(text)

    cols = pyqtProperty(int, get_cols, set_cols)
    rows = pyqtProperty(int, get_rows, set_rows)
    bgcolor = pyqtProperty(QColor, get_bgcolor, set_bgcolor)
    fgcolor = pyqtProperty(QColor, get_fgcolor, set_fgcolor)
    cmd = pyqtProperty(str, get_cmd, set_cmd)


class _TerminalWidget(QPlainTextEdit):
    def __init__(self, parent, cols=125, rows=50, **kwargs):
        self.backend = None
        self._cmd = ""
        self._deactivate_ctrl_d = False
        pal = QPalette()
        self._fg_color = pal.text().color().name()
        self._bg_color = pal.base().color().name()
        self._rows = rows
        self._cols = cols
        self.output = collections.deque()
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_bar = None
        self.setFont(QFont("Courier", 9))
        self.setFont(QFont("Monospace"))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        fmt = QFontMetrics(self.font())
        char_width = (
            fmt.width("w") if hasattr(fmt, "width") else fmt.horizontalAdvance("w")
        )
        self.setCursorWidth(max(1, char_width))
        self.adjustSize()
        self.updateGeometry()
        self.update_stylesheet()

    @property
    def bg_color(self):
        return self._bg_color

    @bg_color.setter
    def bg_color(self, hexcolor):
        self._bg_color = hexcolor
        self.update_stylesheet()

    @property
    def fg_color(self):
        return self._fg_color

    @fg_color.setter
    def fg_color(self, hexcolor):
        self._fg_color = hexcolor
        self.update_stylesheet()

    def update_stylesheet(self):
        self.setStyleSheet(
            f"QPlainTextEdit {{ border: 0; color: {theme.color26}; background-color: {theme.color2}; font-family: Consolas, monospace; font-size: 13px; }}"
        )

    @property
    def rows(self):
        return self._rows

    @rows.setter
    def rows(self, rows: int):
        if self.backend is None:
            self._rows = rows
            self.adjustSize()
            self.updateGeometry()

    @property
    def cols(self):
        return self._cols

    @cols.setter
    def cols(self, cols: int):
        if self.backend is None:
            self._cols = cols
            self.adjustSize()
            self.updateGeometry()

    def stop(self):
        if self.backend:
            self.backend.stop()

    def start(self, deactivate_ctrl_d: bool = False):
        self._deactivate_ctrl_d = deactivate_ctrl_d
        self.update_term_size()
        self.screen = Screen(self.write, self.cols, self.rows, 10000)
        self.stream = pyte.ByteStream()
        self.stream.attach(self.screen)
        self.backend = Backend(self._cmd, self.cols, self.rows)
        self.backend.dataReady.connect(self.data_ready)
        self.backend.processExited.connect(self.process_exited)
        self.backend.start()

    @SafeSlot()
    def process_exited(self):
        self.backend = None
        current_text = self.toPlainText()
        self.setPlainText(current_text + f"\n\n[Process exited: {self._cmd}]")
        self.setReadOnly(True)
        if hasattr(self.parent(), "closed"):
            self.parent().closed.emit()

    @SafeSlot(bytes)
    def data_ready(self, data):
        self.stream.feed(data)
        self.redraw_screen()
        self.adjust_scroll_bar()
        self.move_cursor()

    def minimumSizeHint(self):
        fmt = QFontMetrics(self.font())
        char_width = (
            fmt.width("w") if hasattr(fmt, "width") else fmt.horizontalAdvance("w")
        )
        char_height = fmt.height() if fmt.height() > 0 else 1
        width = char_width * self.cols
        height = char_height * self.rows
        return QSize(width, height)

    def sizeHint(self):
        return self.minimumSizeHint()

    def set_scroll_bar(self, scroll_bar):
        self.scroll_bar = scroll_bar
        self.scroll_bar.setMinimum(0)
        self.scroll_bar.valueChanged.connect(self.scroll_value_change)

    def scroll_value_change(self, value, old={"value": -1}):
        if self.backend is None:
            return
        if old["value"] == -1:
            old["value"] = self.scroll_bar.maximum()
        if value <= old["value"]:
            nlines = old["value"] - value
            for i in range(nlines):
                self.screen.prev_page()
        else:
            nlines = value - old["value"]
            for i in range(nlines):
                self.screen.next_page()
        old["value"] = value
        self.redraw_screen()

    def adjust_scroll_bar(self):
        sb = self.scroll_bar
        try:
            sb.valueChanged.disconnect(self.scroll_value_change)
        except TypeError:
            pass
        tmp = len(self.screen.history.top) + len(self.screen.history.bottom)
        sb.setMaximum(tmp if tmp > 0 else 0)
        sb.setSliderPosition(tmp if tmp > 0 else 0)
        sb.valueChanged.connect(self.scroll_value_change)

    def write(self, data):
        if self.backend and self.backend.running:
            self.backend.write(data)

    @SafeSlot(object)
    def keyPressEvent(self, event):
        if self.backend is None:
            return
        code = QtKeyToAscii(event)
        if code == "copy":
            self.copy()
        else:
            if isinstance(self.parent(), Terminal):
                self.parent().input_field.setFocus()
                self.parent().input_field.event(event)

    def push(self, text):
        self.write(text.encode("utf-8"))

    def contextMenuEvent(self, event):
        if self.backend is None:
            return
        menu = self.createStandardContextMenu()
        for action in menu.actions():
            if "opy" in action.text():
                action.setText("Copy")
                continue
            if "aste" in action.text():
                action.setText("Paste")
                action.triggered.connect(self._push_clipboard)
                continue
            menu.removeAction(action)
        menu.exec_(event.globalPos())

    @SafeSlot()
    def _push_clipboard(self):
        clipboard = QApplication.instance().clipboard()
        self.push(clipboard.text())

    def move_cursor(self):
        textCursor = self.textCursor()
        textCursor.setPosition(0)
        textCursor.movePosition(
            QTextCursor.Down, QTextCursor.MoveAnchor, self.screen.cursor.y
        )
        textCursor.movePosition(
            QTextCursor.Right, QTextCursor.MoveAnchor, self.screen.cursor.x
        )
        self.setTextCursor(textCursor)

    def mouseReleaseEvent(self, event):
        if self.backend is None:
            return
        if event.button() == Qt.MiddleButton:
            clipboard = QApplication.instance().clipboard()
            if clipboard.supportsSelection():
                self.push(clipboard.text(QClipboard.Selection))
            return None
        elif event.button() == Qt.LeftButton:
            textCursor = self.textCursor()
            if not textCursor.selectedText():
                self.scroll_bar.setSliderPosition(self.scroll_bar.maximum())
                self.move_cursor()
                return None
        return super().mouseReleaseEvent(event)

    def redraw_screen(self):
        screen = self.screen
        if screen.dirty:
            while len(self.output) < (max(screen.dirty) + 1):
                self.output.append("")
            while len(self.output) > (max(screen.dirty) + 1):
                self.output.pop()
            for line_no in screen.dirty:
                line = ""
                old_idx = 0
                for idx, ch in screen.buffer[line_no].items():
                    line += " " * (idx - old_idx - 1)
                    old_idx = idx
                    line += ch.data
                if line_no == screen.cursor.y:
                    llen = len(screen.buffer[line_no])
                    if llen < screen.cursor.x:
                        line += " " * (screen.cursor.x - llen)
                self.output[line_no] = line
            self.setPlainText(chr(10).join(self.output))
            screen.dirty.clear()

    def update_term_size(self):
        fmt = QFontMetrics(self.font())
        char_width = (
            fmt.width("w") if hasattr(fmt, "width") else fmt.horizontalAdvance("w")
        )
        char_height = fmt.height() if fmt.height() > 0 else 1
        char_width = max(1, char_width)
        cols = int(self.width() / char_width)
        rows = int(self.height() / char_height)
        self._cols = max(40, cols)
        self._rows = max(10, rows)

    def resizeEvent(self, event):
        self.update_term_size()
        if self.backend:
            self.backend.resize(self._rows, self._cols)
            self.screen.resize(self._rows, self._cols)
            self.redraw_screen()
            self.adjust_scroll_bar()
            self.move_cursor()

    def wheelEvent(self, event):
        if not self.backend:
            return
        y = event.angleDelta().y()
        if y > 0:
            self.screen.prev_page()
        else:
            self.screen.next_page()
        self.redraw_screen()
