import jedi
import builtins
import keyword
import array
from collections import OrderedDict
from PyQt5 import QtCore

TOK_NEWLINE = 0
TOK_SPACE = 1
TOK_IDENT = 2
TOK_NUMBER = 3
TOK_QUOTE = 4
TOK_COMMENT = 5
TOK_OPERATOR = 6
TOK_TEXT = 7

STYLE_DEFAULT = 0
STYLE_KEYWORD = 1
STYLE_TYPES = 2
STYLE_STRING = 3
STYLE_COMMENTS = 4
STYLE_CONSTANTS = 5
STYLE_FUNCTIONS = 6
STYLE_FUNCTION_DEF = 7
STYLE_CLASS_DEF = 8
STYLE_CLASSES = 9

KEYWORDS_BYTES = frozenset(s.encode('utf-8') for s in keyword.kwlist)
BUILTINS_BYTES = frozenset(s.encode('utf-8') for s in dir(builtins) if not s.startswith("_"))

TWO_OPS_BYTES = frozenset(op.encode('utf-8') for op in [
    "==", "!=", "<=", ">=", "//", "**", ":=", "->", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<", ">>"
])

IDENT_CHARS = bytearray(256)
for _c in b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_':
    IDENT_CHARS[_c] = 1

NUM_CHARS = bytearray(256)
for _c in b'0123456789_.':
    NUM_CHARS[_c] = 1

SPACE_CHARS = bytearray(256)
SPACE_CHARS[32] = 1
SPACE_CHARS[9] = 1

QUOTE_DOUBLE3 = b'"""'
QUOTE_SINGLE3 = b"'''"

STATE_NORMAL = 0
STATE_MULTILINE_DOUBLE = 1
STATE_MULTILINE_SINGLE = 2

EXPECT_NONE = 0
EXPECT_CLASS = 1
EXPECT_DEF = 2


class PyFlexWorker(QtCore.QObject):
    styling_ready = QtCore.pyqtSignal(int, object, object)

    def __init__(self):
        super().__init__()
        self.line_cache = OrderedDict()
        self.CACHE_MAX_SIZE = 8192
        self._is_cancelled = False

    @QtCore.pyqtSlot(int, int, int, bytes)
    def process(self, start_pos, start_line, initial_state, data):
        self._is_cancelled = False
        runs = array.array('i')
        line_states = {}

        i = 0
        n = len(data)
        current_line = start_line
        current_state = initial_state

        while i < n:
            if self._is_cancelled:
                return

            line_end = data.find(b'\n', i)
            if line_end == -1:
                line_end = n - 1

            actual_len = (line_end + 1) - i
            line_bytes = data[i:i + actual_len]

            cache_key = (hash(line_bytes), actual_len, current_state)
            cached = self.line_cache.get(cache_key)

            if cached is not None:
                self.line_cache.move_to_end(cache_key)
                runs.extend(cached[0])
                current_state = cached[1]
            else:
                line_runs = array.array('i')
                append = line_runs.append
                expect_state = EXPECT_NONE

                k = 0
                line_n = actual_len

                while k < line_n:
                    if current_state == STATE_MULTILINE_DOUBLE:
                        j = line_bytes.find(QUOTE_DOUBLE3, k)
                        if j == -1:
                            append(line_n - k)
                            append(STYLE_STRING)
                            k = line_n
                        else:
                            bs = 0
                            idx = j - 1
                            while idx >= k and line_bytes[idx] == 92:
                                bs += 1
                                idx -= 1
                            if bs % 2 == 0:
                                j += 3
                                append(j - k)
                                append(STYLE_STRING)
                                current_state = STATE_NORMAL
                                k = j
                            else:
                                j += 3
                                append(j - k)
                                append(STYLE_STRING)
                                k = j
                        continue

                    elif current_state == STATE_MULTILINE_SINGLE:
                        j = line_bytes.find(QUOTE_SINGLE3, k)
                        if j == -1:
                            append(line_n - k)
                            append(STYLE_STRING)
                            k = line_n
                        else:
                            bs = 0
                            idx = j - 1
                            while idx >= k and line_bytes[idx] == 92:
                                bs += 1
                                idx -= 1
                            if bs % 2 == 0:
                                j += 3
                                append(j - k)
                                append(STYLE_STRING)
                                current_state = STATE_NORMAL
                                k = j
                            else:
                                j += 3
                                append(j - k)
                                append(STYLE_STRING)
                                k = j
                        continue

                    c = line_bytes[k]

                    if SPACE_CHARS[c]:
                        j = k + 1
                        while j < line_n and SPACE_CHARS[line_bytes[j]]:
                            j += 1
                        append(j - k)
                        append(STYLE_DEFAULT)
                        k = j

                    elif c == 10 or c == 13:
                        j = k + 1
                        if c == 13 and j < line_n and line_bytes[j] == 10:
                            j += 1
                        append(j - k)
                        append(STYLE_DEFAULT)
                        k = j

                    elif c == 35:
                        j = line_bytes.find(b'\n', k)
                        if j == -1:
                            j = line_n
                        append(j - k)
                        append(STYLE_COMMENTS)
                        k = j
                        expect_state = EXPECT_NONE

                    elif c == 34 or c == 39:
                        if k + 2 < line_n and line_bytes[k + 1] == c and line_bytes[k + 2] == c:
                            current_state = STATE_MULTILINE_DOUBLE if c == 34 else STATE_MULTILINE_SINGLE
                            append(3)
                            append(STYLE_STRING)
                            k += 3
                        else:
                            quote = c
                            j = k + 1
                            while True:
                                j = line_bytes.find(quote, j)
                                if j == -1:
                                    j = line_n
                                    break
                                bs = 0
                                idx = j - 1
                                while idx >= k and line_bytes[idx] == 92:
                                    bs += 1
                                    idx -= 1
                                if bs % 2 == 0:
                                    j += 1
                                    break
                                j += 1
                            append(j - k)
                            append(STYLE_STRING)
                            k = j
                        expect_state = EXPECT_NONE

                    elif IDENT_CHARS[c] and not (48 <= c <= 57):
                        j = k + 1
                        while j < line_n and IDENT_CHARS[line_bytes[j]]:
                            j += 1

                        tok = line_bytes[k:j]
                        style_to_apply = STYLE_DEFAULT

                        if expect_state == EXPECT_CLASS:
                            style_to_apply = STYLE_CLASSES
                            expect_state = EXPECT_NONE
                        elif expect_state == EXPECT_DEF:
                            style_to_apply = STYLE_FUNCTION_DEF
                            expect_state = EXPECT_NONE
                        elif tok == b"class":
                            style_to_apply = STYLE_KEYWORD
                            expect_state = EXPECT_CLASS
                        elif tok == b"def":
                            style_to_apply = STYLE_KEYWORD
                            expect_state = EXPECT_DEF
                        elif tok == b"self":
                            style_to_apply = STYLE_KEYWORD
                        elif tok in KEYWORDS_BYTES:
                            style_to_apply = STYLE_KEYWORD
                        elif tok in BUILTINS_BYTES:
                            style_to_apply = STYLE_FUNCTIONS
                        else:
                            x = j
                            while x < line_n and SPACE_CHARS[line_bytes[x]]:
                                x += 1
                            if x < line_n and line_bytes[x] == 40:
                                style_to_apply = STYLE_FUNCTIONS

                        append(j - k)
                        append(style_to_apply)
                        k = j

                    elif NUM_CHARS[c]:
                        j = k + 1
                        while j < line_n and NUM_CHARS[line_bytes[j]]:
                            j += 1
                        append(j - k)
                        append(STYLE_CONSTANTS)
                        k = j
                        expect_state = EXPECT_NONE

                    elif c == 64:
                        j = k + 1
                        while j < line_n and SPACE_CHARS[line_bytes[j]]:
                            j += 1
                        if j < line_n and IDENT_CHARS[line_bytes[j]] and not (48 <= line_bytes[j] <= 57):
                            x = j + 1
                            while x < line_n and IDENT_CHARS[line_bytes[x]]:
                                x += 1
                            append(x - k)
                            append(STYLE_FUNCTIONS)
                            k = x
                        else:
                            append(1)
                            append(STYLE_DEFAULT)
                            k += 1
                        expect_state = EXPECT_NONE

                    else:
                        if k + 1 < line_n:
                            if line_bytes[k : k + 2] in TWO_OPS_BYTES:
                                append(2)
                                append(STYLE_DEFAULT)
                                k += 2
                                expect_state = EXPECT_NONE
                                continue
                        append(1)
                        append(STYLE_DEFAULT)
                        k += 1
                        expect_state = EXPECT_NONE

                runs.extend(line_runs)
                self.line_cache[cache_key] = (line_runs, current_state)
                if len(self.line_cache) > self.CACHE_MAX_SIZE:
                    self.line_cache.popitem(last=False)

            line_states[current_line] = current_state
            i += actual_len
            current_line += 1

        if not self._is_cancelled:
            self.styling_ready.emit(start_pos, runs, line_states)

    def cancel(self):
        self._is_cancelled = True


class PyFlex(lumos.BaseLexer):  # type: ignore
    def __init__(self, editor, theme_name="default"):
        super().__init__("Python", editor, theme_name=theme_name)
        
        self.worker_thread = QtCore.QThread(self.editor)
        self.worker = PyFlexWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker.styling_ready.connect(self._apply_styling)
        self.worker_thread.start()
        
        self.editor.destroyed.connect(self._cleanup_thread)

    def _do_style_text(self, start: int, end: int):
        self.worker.cancel()

        editor = self.editor
        start_line = editor.SendScintilla(editor.SCI_LINEFROMPOSITION, start)
        line_start_pos = editor.SendScintilla(editor.SCI_POSITIONFROMLINE, start_line)

        if line_start_pos < start:
            start = line_start_pos

        initial_state = editor.SendScintilla(editor.SCI_GETLINESTATE, start_line - 1) if start_line > 0 else STATE_NORMAL
        
        full_text = editor.text()
        full_bytes = full_text.encode('utf-8')
        data_slice = full_bytes[start:]

        QtCore.QMetaObject.invokeMethod(self.worker, "process",
                                        QtCore.Qt.QueuedConnection,
                                        QtCore.Q_ARG(int, start),
                                        QtCore.Q_ARG(int, start_line),
                                        QtCore.Q_ARG(int, initial_state),
                                        QtCore.Q_ARG(bytes, data_slice))

    @QtCore.pyqtSlot(int, object, object)
    def _apply_styling(self, start_pos, runs, line_states):
        self.startStyling(start_pos)
        setStyling = self.setStyling
        
        idx = 0
        r_len = len(runs)
        while idx < r_len:
            setStyling(runs[idx], runs[idx+1])
            idx += 2
            
        for line, state in line_states.items():
            self.editor.SendScintilla(self.editor.SCI_SETLINESTATE, line, state)

    def _cleanup_thread(self):
        self.worker.cancel()
        self.worker_thread.quit()
        self.worker_thread.wait()

    def build_apis(self):
        self.apis.clear()
        code = self.editor.text()
        line, col = self.editor.getCursorPosition()
        pos = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
        style = (
            self.editor.SendScintilla(self.editor.SCI_GETSTYLEAT, pos - 1)
            if pos > 0
            else -1
        )
        if style in (self.STRING, self.COMMENTS):
            self.apis.prepare()
            return
        try:
            script = jedi.Script(code=code)
            completions = script.complete(line + 1, col)
            for completion in completions:
                self.apis.add(completion.name)
        except Exception:
            pass
        self.apis.prepare()