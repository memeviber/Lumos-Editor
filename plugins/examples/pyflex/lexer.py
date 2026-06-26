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


class PyFlex(lumos.BaseLexer):  # type: ignore
    def __init__(self, editor, theme_name="default"):
        super().__init__("Python", editor, theme_name=theme_name)

    def _do_style_text(self, start: int, end: int):
        self.startStyling(start)

        text = self.editor.text()
        full_data = text.encode("utf-8")
        data = full_data[start:end]
        n = len(data)

        setStyling = self.setStyling
        DEFAULT = self.DEFAULT
        KEYWORD = self.KEYWORD
        STRING = self.STRING
        COMMENTS = self.COMMENTS
        FUNCTIONS = self.FUNCTIONS
        FUNCTION_DEF = self.FUNCTION_DEF
        CLASSES = self.CLASSES
        CONSTANTS = self.CONSTANTS

        current_line = self.editor.SendScintilla(
            self.editor.SCI_LINEFROMPOSITION, start
        )

        expect_class_name = False
        expect_def_name = False

        i = 0
        while i < n:
            c = data[i]

            if c == 32 or c == 9:
                j = i + 1
                while j < n:
                    oc = data[j]
                    if oc == 32 or oc == 9:
                        j += 1
                    else:
                        break
                setStyling(j - i, DEFAULT)
                i = j

            elif c == 10 or c == 13:
                if c == 13:
                    if i + 1 < n and data[i + 1] == 10:
                        setStyling(2, DEFAULT)
                        i += 2
                    else:
                        setStyling(1, DEFAULT)
                        i += 1
                else:
                    setStyling(1, DEFAULT)
                    i += 1

                self.editor.SendScintilla(
                    self.editor.SCI_SETLINESTATE, current_line, STATE_NORMAL
                )
                current_line += 1

            elif c == 35:
                j = i + 1
                while j < n and data[j] != 10 and data[j] != 13:
                    j += 1
                setStyling(j - i, COMMENTS)
                i = j
                expect_class_name = False
                expect_def_name = False

            elif c == 39 or c == 34:
                quote = c
                j = i + 1
                while j < n:
                    if data[j] == 92:
                        j += 2
                        continue
                    if data[j] == quote:
                        j += 1
                        break
                    if data[j] == 10 or data[j] == 13:
                        break
                    j += 1
                setStyling(j - i, STRING)
                i = j
                expect_class_name = False
                expect_def_name = False

            elif c == 95 or (65 <= c <= 90) or (97 <= c <= 122):
                j = i + 1
                while j < n:
                    oc = data[j]
                    if (
                        oc == 95
                        or (65 <= oc <= 90)
                        or (97 <= oc <= 122)
                        or (48 <= oc <= 57)
                    ):
                        j += 1
                    else:
                        break

                tok_bytes = data[i:j]
                tok = tok_bytes.decode("utf-8", errors="ignore")
                style_to_apply = DEFAULT

                if expect_class_name:
                    style_to_apply = CLASSES
                    expect_class_name = False
                elif expect_def_name:
                    style_to_apply = FUNCTION_DEF
                    expect_def_name = False
                elif tok == "class":
                    style_to_apply = KEYWORD
                    expect_class_name = True
                elif tok == "def":
                    style_to_apply = KEYWORD
                    expect_def_name = True
                elif tok == "self":
                    style_to_apply = KEYWORD
                elif tok in KEYWORDS:
                    style_to_apply = KEYWORD
                elif tok in BUILTINS:
                    style_to_apply = FUNCTIONS
                else:
                    is_func_call = False
                    k = j
                    while k < n and (data[k] == 32 or data[k] == 9):
                        k += 1
                    if k < n and data[k] == 40:
                        is_func_call = True

                    if is_func_call:
                        style_to_apply = FUNCTIONS
                    else:
                        style_to_apply = DEFAULT

                setStyling(j - i, style_to_apply)
                i = j

            elif 48 <= c <= 57:
                j = i + 1
                while j < n:
                    oc = data[j]
                    if (48 <= oc <= 57) or oc == 46 or oc == 95:
                        j += 1
                    else:
                        break
                setStyling(j - i, CONSTANTS)
                i = j
                expect_class_name = False
                expect_def_name = False

            elif c == 64:
                j = i + 1
                while j < n and (data[j] == 32 or data[j] == 9):
                    j += 1
                if j < n and (
                    data[j] == 95 or (65 <= data[j] <= 90) or (97 <= data[j] <= 122)
                ):
                    k = j + 1
                    while k < n:
                        oc = data[k]
                        if (
                            oc == 95
                            or (65 <= oc <= 90)
                            or (97 <= oc <= 122)
                            or (48 <= oc <= 57)
                        ):
                            k += 1
                        else:
                            break
                    setStyling(k - i, FUNCTIONS)
                    i = k
                else:
                    setStyling(1, DEFAULT)
                    i += 1
                expect_class_name = False
                expect_def_name = False

            else:
                if i + 1 < n:
                    two_bytes = data[i : i + 2]
                    two_op_str = two_bytes.decode("utf-8", errors="ignore")
                    if two_op_str in TWO_OPS:
                        setStyling(2, DEFAULT)
                        i += 2
                        expect_class_name = False
                        expect_def_name = False
                        continue
                setStyling(1, DEFAULT)
                i += 1
                expect_class_name = False
                expect_def_name = False

        self.editor.SendScintilla(
            self.editor.SCI_SETLINESTATE, current_line, STATE_NORMAL
        )

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
