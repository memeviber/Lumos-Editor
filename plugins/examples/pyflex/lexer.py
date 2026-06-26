import jedi
import builtins
import keyword
import array
from collections import OrderedDict

TOK_NEWLINE = 0
TOK_SPACE = 1
TOK_IDENT = 2
TOK_NUMBER = 3
TOK_QUOTE = 4
TOK_COMMENT = 5
TOK_OPERATOR = 6
TOK_TEXT = 7

KEYWORDS_BYTES = frozenset(s.encode("utf-8") for s in keyword.kwlist)
BUILTINS_BYTES = frozenset(
    s.encode("utf-8") for s in dir(builtins) if not s.startswith("_")
)

TWO_OPS_BYTES = frozenset(
    op.encode("utf-8")
    for op in [
        "==",
        "!=",
        "<=",
        ">=",
        "//",
        "**",
        ":=",
        "->",
        "+=",
        "-=",
        "*=",
        "/=",
        "%=",
        "&=",
        "|=",
        "^=",
        "<<",
        ">>",
    ]
)

IDENT_CHARS = bytearray(256)
for _c in b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_":
    IDENT_CHARS[_c] = 1

NUM_CHARS = bytearray(256)
for _c in b"0123456789_.":
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


class PyFlex(lumos.BaseLexer):  # type: ignore
    def __init__(self, editor, theme_name="default"):
        super().__init__("Python", editor, theme_name=theme_name)
        self.line_cache = OrderedDict()
        self.CACHE_MAX_SIZE = 2048

    def _do_style_text(self, start: int, end: int):
        editor = self.editor

        start_line = editor.SendScintilla(editor.SCI_LINEFROMPOSITION, start)
        line_start_pos = editor.SendScintilla(editor.SCI_POSITIONFROMLINE, start_line)

        if line_start_pos < start:
            start = line_start_pos

        self.startStyling(start)

        doc_len = editor.length()
        pos = start
        current_line = start_line

        current_state = (
            editor.SendScintilla(editor.SCI_GETLINESTATE, current_line - 1)
            if current_line > 0
            else STATE_NORMAL
        )

        setStyling = self.setStyling
        DEFAULT = self.DEFAULT
        KEYWORD = self.KEYWORD
        STRING = self.STRING
        COMMENTS = self.COMMENTS
        FUNCTIONS = self.FUNCTIONS
        FUNCTION_DEF = self.FUNCTION_DEF
        CLASSES = self.CLASSES
        CONSTANTS = self.CONSTANTS

        while pos < end or pos < doc_len:
            line_len = editor.SendScintilla(editor.SCI_LINELENGTH, current_line)
            if line_len == 0:
                break

            text_str = editor.text(current_line)
            line_bytes = text_str.encode("utf-8")
            actual_len = len(line_bytes)

            h_val = hash(line_bytes)
            cache_key = (h_val, actual_len, current_state)

            cached = self.line_cache.get(cache_key)
            old_line_state = editor.SendScintilla(editor.SCI_GETLINESTATE, current_line)

            if cached is not None:
                self.line_cache.move_to_end(cache_key)
                runs, new_state = cached

                idx = 0
                r_len = len(runs)
                while idx < r_len:
                    setStyling(runs[idx], runs[idx + 1])
                    idx += 2
                current_state = new_state

            else:
                runs = array.array("i")
                runs_append = runs.append

                i = 0
                n = actual_len
                expect_state = EXPECT_NONE

                while i < n:
                    if current_state == STATE_MULTILINE_DOUBLE:
                        j = line_bytes.find(QUOTE_DOUBLE3, i)
                        if j == -1:
                            runs_append(n - i)
                            runs_append(STRING)
                            i = n
                        else:
                            bs = 0
                            k = j - 1
                            while k >= i and line_bytes[k] == 92:
                                bs += 1
                                k -= 1
                            if bs % 2 == 0:
                                j += 3
                                runs_append(j - i)
                                runs_append(STRING)
                                current_state = STATE_NORMAL
                                i = j
                            else:
                                j += 3
                                runs_append(j - i)
                                runs_append(STRING)
                                i = j
                        continue

                    elif current_state == STATE_MULTILINE_SINGLE:
                        j = line_bytes.find(QUOTE_SINGLE3, i)
                        if j == -1:
                            runs_append(n - i)
                            runs_append(STRING)
                            i = n
                        else:
                            bs = 0
                            k = j - 1
                            while k >= i and line_bytes[k] == 92:
                                bs += 1
                                k -= 1
                            if bs % 2 == 0:
                                j += 3
                                runs_append(j - i)
                                runs_append(STRING)
                                current_state = STATE_NORMAL
                                i = j
                            else:
                                j += 3
                                runs_append(j - i)
                                runs_append(STRING)
                                i = j
                        continue

                    c = line_bytes[i]

                    if SPACE_CHARS[c]:
                        j = i + 1
                        while j < n and SPACE_CHARS[line_bytes[j]]:
                            j += 1
                        runs_append(j - i)
                        runs_append(DEFAULT)
                        i = j

                    elif c == 10 or c == 13:
                        j = i + 1
                        if c == 13 and j < n and line_bytes[j] == 10:
                            j += 1
                        runs_append(j - i)
                        runs_append(DEFAULT)
                        i = j

                    elif c == 35:  # '#'
                        j = line_bytes.find(b"\n", i)
                        if j == -1:
                            j = n
                        runs_append(j - i)
                        runs_append(COMMENTS)
                        i = j
                        expect_state = EXPECT_NONE

                    elif c == 34 or c == 39:  # '"' or "'"
                        if (
                            i + 2 < n
                            and line_bytes[i + 1] == c
                            and line_bytes[i + 2] == c
                        ):
                            current_state = (
                                STATE_MULTILINE_DOUBLE
                                if c == 34
                                else STATE_MULTILINE_SINGLE
                            )
                            runs_append(3)
                            runs_append(STRING)
                            i += 3
                        else:
                            j = i + 1
                            while True:
                                j = line_bytes.find(c, j)
                                if j == -1:
                                    j = n
                                    break
                                bs = 0
                                k = j - 1
                                while k >= i and line_bytes[k] == 92:
                                    bs += 1
                                    k -= 1
                                if bs % 2 == 0:
                                    j += 1
                                    break
                                j += 1

                            runs_append(j - i)
                            runs_append(STRING)
                            i = j
                        expect_state = EXPECT_NONE

                    elif IDENT_CHARS[c] and not (48 <= c <= 57):
                        j = i + 1
                        while j < n and IDENT_CHARS[line_bytes[j]]:
                            j += 1

                        tok = line_bytes[i:j]
                        style_to_apply = DEFAULT

                        if expect_state == EXPECT_CLASS:
                            style_to_apply = CLASSES
                            expect_state = EXPECT_NONE
                        elif expect_state == EXPECT_DEF:
                            style_to_apply = FUNCTION_DEF
                            expect_state = EXPECT_NONE
                        elif tok == b"class":
                            style_to_apply = KEYWORD
                            expect_state = EXPECT_CLASS
                        elif tok == b"def":
                            style_to_apply = KEYWORD
                            expect_state = EXPECT_DEF
                        elif tok == b"self":
                            style_to_apply = KEYWORD
                        elif tok in KEYWORDS_BYTES:
                            style_to_apply = KEYWORD
                        elif tok in BUILTINS_BYTES:
                            style_to_apply = FUNCTIONS
                        else:
                            k = j
                            while k < n and SPACE_CHARS[line_bytes[k]]:
                                k += 1
                            if k < n and line_bytes[k] == 40:  # '('
                                style_to_apply = FUNCTIONS

                        runs_append(j - i)
                        runs_append(style_to_apply)
                        i = j

                    elif NUM_CHARS[c]:
                        j = i + 1
                        while j < n and NUM_CHARS[line_bytes[j]]:
                            j += 1
                        runs_append(j - i)
                        runs_append(CONSTANTS)
                        i = j
                        expect_state = EXPECT_NONE

                    elif c == 64:  # '@'
                        j = i + 1
                        while j < n and SPACE_CHARS[line_bytes[j]]:
                            j += 1
                        if (
                            j < n
                            and IDENT_CHARS[line_bytes[j]]
                            and not (48 <= line_bytes[j] <= 57)
                        ):
                            k = j + 1
                            while k < n and IDENT_CHARS[line_bytes[k]]:
                                k += 1
                            runs_append(k - i)
                            runs_append(FUNCTIONS)
                            i = k
                        else:
                            runs_append(1)
                            runs_append(DEFAULT)
                            i += 1
                        expect_state = EXPECT_NONE

                    else:
                        if i + 1 < n:
                            if line_bytes[i : i + 2] in TWO_OPS_BYTES:
                                runs_append(2)
                                runs_append(DEFAULT)
                                i += 2
                                expect_state = EXPECT_NONE
                                continue
                        runs_append(1)
                        runs_append(DEFAULT)
                        i += 1
                        expect_state = EXPECT_NONE

                idx = 0
                r_len = len(runs)
                while idx < r_len:
                    setStyling(runs[idx], runs[idx + 1])
                    idx += 2

                self.line_cache[cache_key] = (runs, current_state)
                if len(self.line_cache) > self.CACHE_MAX_SIZE:
                    self.line_cache.popitem(last=False)

            editor.SendScintilla(editor.SCI_SETLINESTATE, current_line, current_state)

            pos += actual_len
            current_line += 1

            if pos >= end and current_state == old_line_state:
                break

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
