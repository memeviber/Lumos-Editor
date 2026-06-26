import jedi
import builtins
import keyword

TOK_NEWLINE = 0
TOK_SPACE = 1
TOK_IDENT = 2
TOK_NUMBER = 3
TOK_QUOTE = 4
TOK_COMMENT = 5
TOK_OPERATOR = 6
TOK_TEXT = 7

KEYWORDS = frozenset(keyword.kwlist)

BUILTINS = frozenset(name for name in dir(builtins) if not name.startswith("_"))

TWO_OPS = frozenset(
    {
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
    }
)

STATE_NORMAL = 0
STATE_MULTILINE_DOUBLE = 1
STATE_MULTILINE_SINGLE = 2


class PyFlex(lumos.BaseLexer):  # type: ignore
    def __init__(self, editor, theme_name="default"):
        super().__init__("Python", editor, theme_name=theme_name)

        self.line_cache = {}

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

        if len(self.line_cache) > 50000:
            self.line_cache.clear()

        while pos < end or pos < doc_len:
            line_len = editor.SendScintilla(editor.SCI_LINELENGTH, current_line)
            if line_len == 0:
                break

            text_str = editor.text(current_line)
            line_bytes = text_str.encode("utf-8")
            actual_len = len(line_bytes)

            cache_key = (line_bytes, current_state)
            cached = self.line_cache.get(cache_key)

            old_line_state = editor.SendScintilla(editor.SCI_GETLINESTATE, current_line)

            if cached is not None:
                runs, new_state = cached
                for length, style in runs:
                    setStyling(length, style)
                current_state = new_state

            else:
                runs = []
                i = 0
                n = actual_len
                expect_class_name = False
                expect_def_name = False

                while i < n:
                    if current_state == STATE_MULTILINE_DOUBLE:
                        j = i
                        found = False
                        while j < n:
                            if (
                                j + 2 < n
                                and line_bytes[j] == 34
                                and line_bytes[j + 1] == 34
                                and line_bytes[j + 2] == 34
                            ):
                                j += 3
                                found = True
                                break
                            if line_bytes[j] == 92:
                                j += 2
                                if j > n:
                                    j = n
                            else:
                                j += 1

                        runs.append((j - i, STRING))
                        if found:
                            current_state = STATE_NORMAL
                        i = j
                        continue

                    elif current_state == STATE_MULTILINE_SINGLE:
                        j = i
                        found = False
                        while j < n:
                            if (
                                j + 2 < n
                                and line_bytes[j] == 39
                                and line_bytes[j + 1] == 39
                                and line_bytes[j + 2] == 39
                            ):
                                j += 3
                                found = True
                                break
                            if line_bytes[j] == 92:
                                j += 2
                                if j > n:
                                    j = n
                            else:
                                j += 1

                        runs.append((j - i, STRING))
                        if found:
                            current_state = STATE_NORMAL
                        i = j
                        continue

                    c = line_bytes[i]

                    if c == 32 or c == 9:
                        j = i + 1
                        while j < n and (line_bytes[j] == 32 or line_bytes[j] == 9):
                            j += 1
                        runs.append((j - i, DEFAULT))
                        i = j

                    elif c == 10 or c == 13:
                        j = i + 1
                        if c == 13 and j < n and line_bytes[j] == 10:
                            j += 1
                        runs.append((j - i, DEFAULT))
                        i = j

                    elif c == 35:
                        j = i + 1
                        while j < n and line_bytes[j] not in (10, 13):
                            j += 1
                        runs.append((j - i, COMMENTS))
                        i = j
                        expect_class_name = False
                        expect_def_name = False

                    elif c == 34 or c == 39:
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
                            runs.append((3, STRING))
                            i += 3
                        else:
                            quote = c
                            j = i + 1
                            while j < n:
                                if line_bytes[j] == 92:
                                    j += 2
                                    if j > n:
                                        j = n
                                    continue
                                if line_bytes[j] == quote:
                                    j += 1
                                    break
                                if line_bytes[j] in (10, 13):
                                    break
                                j += 1
                            runs.append((j - i, STRING))
                            i = j
                        expect_class_name = False
                        expect_def_name = False

                    elif c == 95 or (65 <= c <= 90) or (97 <= c <= 122):
                        j = i + 1
                        while j < n:
                            oc = line_bytes[j]
                            if (
                                oc == 95
                                or (65 <= oc <= 90)
                                or (97 <= oc <= 122)
                                or (48 <= oc <= 57)
                            ):
                                j += 1
                            else:
                                break

                        tok_str = line_bytes[i:j].decode("utf-8", errors="ignore")
                        style_to_apply = DEFAULT

                        if expect_class_name:
                            style_to_apply = CLASSES
                            expect_class_name = False
                        elif expect_def_name:
                            style_to_apply = FUNCTION_DEF
                            expect_def_name = False
                        elif tok_str == "class":
                            style_to_apply = KEYWORD
                            expect_class_name = True
                        elif tok_str == "def":
                            style_to_apply = KEYWORD
                            expect_def_name = True
                        elif tok_str == "self":
                            style_to_apply = KEYWORD
                        elif tok_str in KEYWORDS:
                            style_to_apply = KEYWORD
                        elif tok_str in BUILTINS:
                            style_to_apply = FUNCTIONS
                        else:
                            is_func_call = False
                            k = j
                            while k < n and (line_bytes[k] == 32 or line_bytes[k] == 9):
                                k += 1
                            if k < n and line_bytes[k] == 40:
                                is_func_call = True
                            if is_func_call:
                                style_to_apply = FUNCTIONS

                        runs.append((j - i, style_to_apply))
                        i = j

                    elif 48 <= c <= 57:
                        j = i + 1
                        while j < n:
                            oc = line_bytes[j]
                            if (48 <= oc <= 57) or oc == 46 or oc == 95:
                                j += 1
                            else:
                                break
                        runs.append((j - i, CONSTANTS))
                        i = j
                        expect_class_name = False
                        expect_def_name = False

                    elif c == 64:
                        j = i + 1
                        while j < n and (line_bytes[j] == 32 or line_bytes[j] == 9):
                            j += 1
                        if j < n and (
                            line_bytes[j] == 95
                            or (65 <= line_bytes[j] <= 90)
                            or (97 <= line_bytes[j] <= 122)
                        ):
                            k = j + 1
                            while k < n:
                                oc = line_bytes[k]
                                if (
                                    oc == 95
                                    or (65 <= oc <= 90)
                                    or (97 <= oc <= 122)
                                    or (48 <= oc <= 57)
                                ):
                                    k += 1
                                else:
                                    break
                            runs.append((k - i, FUNCTIONS))
                            i = k
                        else:
                            runs.append((1, DEFAULT))
                            i += 1
                        expect_class_name = False
                        expect_def_name = False

                    else:
                        if i + 1 < n:
                            two_op_str = line_bytes[i : i + 2].decode(
                                "utf-8", errors="ignore"
                            )
                            if two_op_str in TWO_OPS:
                                runs.append((2, DEFAULT))
                                i += 2
                                expect_class_name = False
                                expect_def_name = False
                                continue
                        runs.append((1, DEFAULT))
                        i += 1
                        expect_class_name = False
                        expect_def_name = False

                for length, style in runs:
                    setStyling(length, style)

                self.line_cache[cache_key] = (runs, current_state)

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
