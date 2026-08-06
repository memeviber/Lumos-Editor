import functools
import os
import queue
import sys
import time

import pyte
from PyQt5 import QtCore
from PyQt5.QtCore import QSize, Qt, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QClipboard, QColor, QFont, QFontMetrics, QPalette, QTextCursor
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollBar,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from pyte.screens import Char, History

from .theme_manager import theme

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


COLOR_MAP = {
    "black": "#000000",
    "red": "#cd3131",
    "green": "#0dbc79",
    "brown": "#e5e510",
    "yellow": "#e5e510",
    "blue": "#2472c8",
    "magenta": "#bc3fbc",
    "cyan": "#11a8cd",
    "white": "#e5e5e5",
    "brightblack": "#666666",
    "brightred": "#f14c4c",
    "brightgreen": "#23d18b",
    "brightyellow": "#f5f543",
    "brightblue": "#3b8eea",
    "brightmagenta": "#d670d6",
    "brightcyan": "#29b8db",
    "brightwhite": "#ffffff",
}


def get_color_hex(color_str, default_color):
    if not color_str or color_str == "default":
        return default_color

    color_str = color_str.lower().strip()
    if color_str in COLOR_MAP:
        return COLOR_MAP[color_str]

    clean_hex = color_str.lstrip("#")
    if len(clean_hex) in (3, 6) and all(c in "0123456789abcdef" for c in clean_hex):
        return f"#{clean_hex}"

    return default_color


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
    def __init__(self, write_callback, cols, rows, historyLength=1000):
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
    htmlReady = pyqtSignal(str, int, int)
    scrollBarUpdate = pyqtSignal(int)
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

        self.screen = Screen(self.write, self.cols, self.rows, 1000)
        self.stream = pyte.ByteStream()
        self.stream.attach(self.screen)

        self.output_buffer = []
        self.need_update = False

        self.pending_resize = None
        self.pending_page_action = None

        self.input_queue = queue.Queue()

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
                100, lambda: self.stream.feed(err_msg.encode("utf-8"))
            )

    def _init_posix(self):
        import pty

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
            import subprocess

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
                100, lambda: self.stream.feed(err_msg.encode("utf-8"))
            )
        os.close(slave_fd)

    def write(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.input_queue.put(data)

    def _process_input_queue(self):
        while not self.input_queue.empty():
            try:
                data = self.input_queue.get_nowait()
                if sys.platform == "win32":
                    if self.pty_win:
                        self.pty_win.write(data.decode("utf-8"))
                else:
                    if self.master_fd is not None:
                        os.write(self.master_fd, data)
            except queue.Empty:
                break
            except Exception:
                pass

    def resize(self, rows, cols):
        self.pending_resize = (rows, cols)

    def _execute_resize(self, rows, cols):
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
        self.screen.resize(rows, cols)
        self.need_update = True

    def prev_page(self):
        self.pending_page_action = "PREV"

    def next_page(self):
        self.pending_page_action = "NEXT"

    def run(self):
        last_update_time = 0
        base_interval = 0.033
        flood_interval = 0.20
        update_interval = base_interval
        consecutive_reads = 0

        if sys.platform == "win32":
            if not self.pty_win:
                self.processExited.emit()
                return
            while self.running:
                if self.pending_resize:
                    r, c = self.pending_resize
                    self.pending_resize = None
                    self._execute_resize(r, c)
                if self.pending_page_action:
                    act = self.pending_page_action
                    self.pending_page_action = None
                    if act == "PREV":
                        self.screen.prev_page()
                    elif act == "NEXT":
                        self.screen.next_page()
                    self.need_update = True

                self._process_input_queue()

                try:
                    try:
                        out = self.pty_win.read(length=16384, blocking=False)
                    except TypeError:
                        out = self.pty_win.read(blocking=False)
                    if out:
                        if isinstance(out, str):
                            out = out.encode("utf-8")
                        self.stream.feed(out)
                        self.need_update = True
                        consecutive_reads = min(consecutive_reads + 1, 20)
                    else:
                        consecutive_reads = max(consecutive_reads - 1, 0)
                        alive = True
                        if hasattr(self.pty_win, "isalive"):
                            alive = self.pty_win.isalive()
                        if not alive:
                            break
                        time.sleep(0.01)
                except EOFError:
                    break
                except Exception:
                    break

                if consecutive_reads >= 5:
                    update_interval = flood_interval
                    self.msleep(2)
                else:
                    update_interval = base_interval

                curr_time = time.time()
                force_instant_update = consecutive_reads == 0 and self.need_update

                if self.need_update and (
                    force_instant_update
                    or (curr_time - last_update_time >= update_interval)
                ):
                    html, cx, cy = self.render_html()
                    self.htmlReady.emit(html, cx, cy)
                    self.scrollBarUpdate.emit(
                        len(self.screen.history.top) + len(self.screen.history.bottom)
                    )
                    last_update_time = curr_time
                    self.need_update = False

            if self.need_update:
                html, cx, cy = self.render_html()
                self.htmlReady.emit(html, cx, cy)
                self.scrollBarUpdate.emit(
                    len(self.screen.history.top) + len(self.screen.history.bottom)
                )
        else:
            while self.running:
                if self.pending_resize:
                    r, c = self.pending_resize
                    self.pending_resize = None
                    self._execute_resize(r, c)
                if self.pending_page_action:
                    act = self.pending_page_action
                    self.pending_page_action = None
                    if act == "PREV":
                        self.screen.prev_page()
                    elif act == "NEXT":
                        self.screen.next_page()
                    self.need_update = True

                self._process_input_queue()

                try:
                    r_fds, _, _ = select.select([self.master_fd], [], [], 0.02)
                    if self.master_fd in r_fds:
                        out = os.read(self.master_fd, 16384)
                        if not out:
                            break
                        self.stream.feed(out)
                        self.need_update = True
                        consecutive_reads = min(consecutive_reads + 1, 20)
                    else:
                        consecutive_reads = max(consecutive_reads - 1, 0)
                    if self.proc and self.proc.poll() is not None:
                        break
                except OSError:
                    break

                if consecutive_reads >= 5:
                    update_interval = flood_interval
                    self.msleep(2)
                else:
                    update_interval = base_interval

                curr_time = time.time()
                force_instant_update = consecutive_reads == 0 and self.need_update

                if self.need_update and (
                    force_instant_update
                    or (curr_time - last_update_time >= update_interval)
                ):
                    html, cx, cy = self.render_html()
                    self.htmlReady.emit(html, cx, cy)
                    self.scrollBarUpdate.emit(
                        len(self.screen.history.top) + len(self.screen.history.bottom)
                    )
                    last_update_time = curr_time
                    self.need_update = False

            if self.need_update:
                html, cx, cy = self.render_html()
                self.htmlReady.emit(html, cx, cy)
                self.scrollBarUpdate.emit(
                    len(self.screen.history.top) + len(self.screen.history.bottom)
                )

        self.running = False
        self.processExited.emit()

    def render_html(self):
        screen = self.screen

        while len(self.output_buffer) < (
            max(screen.dirty) + 1 if screen.dirty else screen.lines
        ):
            self.output_buffer.append([])
        while len(self.output_buffer) > (
            max(screen.dirty) + 1 if screen.dirty else screen.lines
        ):
            self.output_buffer.pop()

        for line_no in screen.dirty:
            line_chars = []
            buffer_line = screen.buffer[line_no]
            for col in range(screen.columns):
                ch = buffer_line.get(col)
                if ch is None:
                    ch = Char(data=" ", fg="default", bg="default")
                line_chars.append(ch)
            self.output_buffer[line_no] = line_chars

        default_fg = theme.color26 if hasattr(theme, "color26") else "#e5e5e5"
        default_bg = theme.color2 if hasattr(theme, "color2") else "#1e1e1e"

        html_lines = []
        for line_chars in self.output_buffer:
            html_line = ""
            current_span = ""
            last_style = None

            for ch in line_chars:
                fg = ch.fg
                bg = ch.bg
                if getattr(ch, "reverse", False):
                    fg, bg = bg, fg

                fg_color = get_color_hex(fg, default_fg)
                bg_color = get_color_hex(bg, None)

                styles = []
                if fg_color:
                    styles.append(f"color:{fg_color}")
                if bg_color:
                    styles.append(f"background-color:{bg_color}")
                if getattr(ch, "bold", False):
                    styles.append("font-weight:bold")
                if getattr(ch, "italics", False):
                    styles.append("font-style:italic")

                text_decoration = []
                if getattr(ch, "underscore", False):
                    text_decoration.append("underline")
                if getattr(ch, "strikethrough", False):
                    text_decoration.append("line-through")
                if text_decoration:
                    styles.append(f"text-decoration:{' '.join(text_decoration)}")

                style_str = "; ".join(styles)

                char_data = ch.data
                if char_data == " ":
                    char_data = "&nbsp;"
                elif char_data == "<":
                    char_data = "&lt;"
                elif char_data == ">":
                    char_data = "&gt;"
                elif char_data == "&":
                    char_data = "&amp;"
                elif char_data == '"':
                    char_data = "&quot;"
                elif char_data == "'":
                    char_data = "&#39;"

                if style_str == last_style:
                    current_span += char_data
                else:
                    if current_span:
                        if last_style:
                            html_line += (
                                f'<span style="{last_style}">{current_span}</span>'
                            )
                        else:
                            html_line += current_span
                    current_span = char_data
                    last_style = style_str

            if current_span:
                if last_style:
                    html_line += f'<span style="{last_style}">{current_span}</span>'
                else:
                    html_line += current_span

            if not html_line:
                html_line = "&nbsp;"

            html_lines.append(html_line)

        div_lines = []
        for html_line in html_lines:
            div_lines.append(
                f'<div style="margin: 0; padding: 0; line-height: 1.2;">{html_line}</div>'
            )

        body_style = (
            f"background-color: {default_bg}; color: {default_fg}; "
            "font-family: Consolas, monospace; font-size: 13px; "
            "white-space: pre-wrap; margin: 0; padding: 0;"
        )
        full_html = (
            f'<html><body style="{body_style}">{"".join(div_lines)}</body></html>'
        )
        screen.dirty.clear()

        return full_html, screen.cursor.x, screen.cursor.y

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

    def get_current_dir(self):
        parent = self.parent()
        while parent:
            if hasattr(parent, "current_project_dir"):
                return parent.current_project_dir
            parent = parent.parent()
        return os.path.expanduser("~")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            text = self.text()
            if not text:
                return
            words = text.split()
            last_word = "" if text.endswith(" ") else (words[-1] if words else "")
            base_dir = self.get_current_dir() or os.path.expanduser("~")
            target_path = os.path.join(base_dir, last_word)
            if os.path.isdir(target_path) and last_word.endswith(("/", "\\")):
                search_dir = target_path
                prefix = ""
            else:
                search_dir = os.path.dirname(target_path)
                prefix = os.path.basename(target_path)
            if os.path.isdir(search_dir):
                try:
                    items = sorted(os.listdir(search_dir))
                except Exception:
                    items = []
            else:
                items = []
            matches = [
                item for item in items if item.lower().startswith(prefix.lower())
            ]
            if matches:
                best_match = matches[0]
                rel_dir = os.path.dirname(last_word)
                completed_word = (
                    os.path.join(rel_dir, best_match).replace("\\", "/")
                    if rel_dir
                    else best_match
                )
                if os.path.isdir(os.path.join(search_dir, best_match)):
                    completed_word += "/"
                if text.endswith(" "):
                    self.setText(text + completed_word)
                else:
                    words[-1] = completed_word
                    self.setText(" ".join(words))
                self.setCursorPosition(len(self.text()))
            event.accept()
            return
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
        if modifiers in (Qt.NoModifier, Qt.KeypadModifier):
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
            self.term.append(f"Terminal - {repr(cmd)}")

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


class _TerminalWidget(QTextEdit):
    def __init__(self, parent, cols=125, rows=50, **kwargs):
        self.backend = None
        self._cmd = ""
        self._deactivate_ctrl_d = False
        pal = QPalette()
        self._fg_color = pal.text().color().name()
        self._bg_color = pal.base().color().name()
        self._rows = rows
        self._cols = cols
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_bar = None
        self.setFont(QFont("Courier", 9))
        self.setFont(QFont("Monospace"))
        self.setLineWrapMode(QTextEdit.NoWrap)
        self.document().setDocumentMargin(0)
        fmt = QFontMetrics(self.font())
        char_width = (
            fmt.width("w") if hasattr(fmt, "width") else fmt.horizontalAdvance("w")
        )
        self.setCursorWidth(max(1, char_width))
        self.adjustSize()
        self.updateGeometry()
        self.update_stylesheet()

        self.last_scroll_value = -1

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
            f"QTextEdit {{ border: 0; color: {theme.color26}; background-color: {theme.color2}; font-family: Consolas, monospace; font-size: 13px; }}"
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
        self.last_scroll_value = -1

        self.backend = Backend(self._cmd, self.cols, self.rows)
        self.backend.htmlReady.connect(self.html_ready)
        self.backend.scrollBarUpdate.connect(self.update_scroll_bar)
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

    @SafeSlot(str, int, int)
    def html_ready(self, html, cursor_x, cursor_y):
        self.setHtml(html)
        self.move_cursor_to(cursor_x, cursor_y)

    @SafeSlot(int)
    def update_scroll_bar(self, max_val):
        sb = self.scroll_bar
        if sb is None:
            return
        try:
            sb.valueChanged.disconnect(self.scroll_value_change)
        except TypeError:
            pass
        sb.setMaximum(max_val)
        sb.setSliderPosition(max_val)
        self.last_scroll_value = max_val
        sb.valueChanged.connect(self.scroll_value_change)

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

    def scroll_value_change(self, value):
        if self.backend is None:
            return
        if self.last_scroll_value == -1:
            self.last_scroll_value = self.scroll_bar.maximum()
        if value < self.last_scroll_value:
            for _ in range(self.last_scroll_value - value):
                self.backend.prev_page()
        elif value > self.last_scroll_value:
            for _ in range(value - self.last_scroll_value):
                self.backend.next_page()
        self.last_scroll_value = value

    def write(self, data):
        if self.backend and self.backend.running:
            self.backend.write(data)

    @SafeSlot(object)
    def keyPressEvent(self, event):
        if self.backend is None:
            return
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
            if self.textCursor().hasSelection():
                self.copy()

                cursor = self.textCursor()
                cursor.clearSelection()
                self.setTextCursor(cursor)
                return
        code = QtKeyToAscii(event)
        if code == "copy":
            self.copy()
        else:
            if isinstance(self.parent(), Terminal):
                self.parent().input_field.setFocus()
                self.parent().input_field.event(event)

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

    def move_cursor_to(self, cursor_x, cursor_y):
        textCursor = self.textCursor()
        textCursor.setPosition(0)
        textCursor.movePosition(QTextCursor.Down, QTextCursor.MoveAnchor, cursor_y)
        textCursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, cursor_x)
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
                if self.backend and self.backend.running:
                    self.move_cursor_to(
                        self.backend.screen.cursor.x, self.backend.screen.cursor.y
                    )
                return None
        return super().mouseReleaseEvent(event)

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

    def wheelEvent(self, event):
        if not self.backend:
            return
        y = event.angleDelta().y()
        if y > 0:
            self.backend.prev_page()
        else:
            self.backend.next_page()

    def push(self, text):
        self.write(text.encode("utf-8"))
