import jedi
import builtins
import keyword
from typing import Optional, Tuple, List


class PyFlex(lumos.BaseLexer):  # type: ignore
    def __init__(self, editor, theme_name="default"):
        super().__init__("Python", editor, theme_name=theme_name)

        self.keywords_list = set(keyword.kwlist)
        self.builtin_names = {
            name for name in dir(builtins) if not name.startswith("_")
        }

        self._tokens: List[Tuple[str, int]] = []
        self._tok_i = 0

    def _do_style_text(self, start: int, end: int):
        self.startStyling(start)

        text = self.editor.text()[start:end]
        self.generate_tokens(text)

        comment_flag = False
        string_flag = False
        string_delim = None
        expect_class_name = False
        expect_def_name = False

        previous_style_nr = -1
        if start > 0:
            previous_style_nr = self.editor.SendScintilla(
                self.editor.SCI_GETSTYLEAT, start - 1
            )
            if previous_style_nr == self.COMMENTS:
                comment_flag = True

        while True:
            curr_token = self.next_tok()
            if curr_token is None:
                break

            tok: str = curr_token[0]
            tok_len: int = curr_token[1]

            if comment_flag:
                self.setStyling(tok_len, self.COMMENTS)
                if "\n" in tok:
                    comment_flag = False
                continue

            if string_flag:
                self.setStyling(tok_len, self.STRING)
                if tok == string_delim:
                    string_flag = False
                    string_delim = None
                continue

            if tok in (" ", "\t", "\r", "\n"):
                self.setStyling(tok_len, self.DEFAULT)
                continue

            if expect_class_name:
                if tok.isidentifier():
                    self.setStyling(tok_len, self.CLASSES)
                    expect_class_name = False
                    continue
                expect_class_name = False

            if expect_def_name:
                if tok.isidentifier():
                    self.setStyling(tok_len, self.FUNCTION_DEF)
                    expect_def_name = False
                    continue
                expect_def_name = False

            if tok == "class":
                self.setStyling(tok_len, self.KEYWORD)
                expect_class_name = True
                continue

            if tok == "def":
                self.setStyling(tok_len, self.KEYWORD)
                expect_def_name = True
                continue

            if tok == "self":
                self.setStyling(tok_len, self.KEYWORD)
                continue

            if tok in self.keywords_list:
                self.setStyling(tok_len, self.KEYWORD)
                continue

            if tok in self.builtin_names:
                self.setStyling(tok_len, self.FUNCTIONS)
                continue

            if tok == "@":
                self.setStyling(tok_len, self.FUNCTIONS)
                nxt = self.peek_tok()
                if nxt and nxt[0].isidentifier():
                    dec = self.next_tok()
                    self.setStyling(dec[1], self.FUNCTIONS)
                continue

            if tok.isidentifier():
                is_func_call = False
                nxt = self.peek_tok()
                if nxt:
                    if nxt[0] == "(":
                        is_func_call = True
                    elif nxt[0] in (" ", "\t"):
                        ws_tok = self.next_tok()
                        nxt2 = self.peek_tok()
                        if nxt2 and nxt2[0] == "(":
                            is_func_call = True
                            self.setStyling(tok_len, self.FUNCTIONS)
                            self.setStyling(ws_tok[1], self.DEFAULT)
                            continue
                        else:
                            self.setStyling(tok_len, self.DEFAULT)
                            self.setStyling(ws_tok[1], self.DEFAULT)
                            continue

                if is_func_call:
                    self.setStyling(tok_len, self.FUNCTIONS)
                    continue

            if tok.isnumeric():
                self.setStyling(tok_len, self.CONSTANTS)
                continue

            if tok in ('"', "'"):
                self.setStyling(tok_len, self.STRING)
                string_flag = True
                string_delim = tok
                continue

            if tok == "#":
                self.setStyling(tok_len, self.COMMENTS)
                comment_flag = True
                continue

            self.setStyling(tok_len, self.DEFAULT)

    def generate_tokens(self, text: str):
        self._tokens = self._scan_text(text)
        self._tok_i = 0

    def next_tok(self, offset: Optional[int] = None):
        if offset is None:
            idx = self._tok_i
            self._tok_i += 1
        else:
            idx = self._tok_i + offset
            self._tok_i = idx + 1

        if 0 <= idx < len(self._tokens):
            return self._tokens[idx]
        return None

    def peek_tok(self, offset: int = 0):
        idx = self._tok_i + offset
        if 0 <= idx < len(self._tokens):
            return self._tokens[idx]
        return None

    def skip_spaces_peek(self, offset: int = 0):
        idx = self._tok_i + offset
        while idx < len(self._tokens):
            tok = self._tokens[idx]
            if tok[0].isspace() and tok[0] != "\n":
                idx += 1
                continue
            return tok, idx - self._tok_i
        return ("", 0), -1

    def _scan_text(self, text: str):
        tokens: List[Tuple[str, int]] = []
        i = 0
        n = len(text)

        two_ops = {
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

        while i < n:
            ch = text[i]

            if ch == "\r":
                if i + 1 < n and text[i + 1] == "\n":
                    tokens.append(("\n", 1))
                    i += 2
                else:
                    tokens.append(("\n", 1))
                    i += 1
                continue

            if ch == "\n":
                tokens.append(("\n", 1))
                i += 1
                continue

            if ch.isspace():
                j = i
                while j < n and text[j].isspace() and text[j] not in "\r\n":
                    j += 1
                tokens.append((text[i:j], j - i))
                i = j
                continue

            if ch == "#":
                tokens.append(("#", 1))
                i += 1
                j = i
                while j < n and text[j] not in "\r\n":
                    j += 1
                if j > i:
                    tokens.append((text[i:j], j - i))
                i = j
                continue

            if ch in ("'", '"'):
                quote = ch
                tokens.append((quote, 1))
                i += 1

                j = i
                while j < n:
                    if text[j] == "\\" and j + 1 < n:
                        j += 2
                        continue
                    if text[j] == quote:
                        break
                    if text[j] in "\r\n":
                        break
                    j += 1

                if j > i:
                    tokens.append((text[i:j], j - i))

                if j < n and text[j] == quote:
                    tokens.append((quote, 1))
                    j += 1

                i = j
                continue

            if ch.isalpha() or ch == "_":
                j = i + 1
                while j < n and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                tokens.append((text[i:j], j - i))
                i = j
                continue

            if ch.isdigit():
                j = i + 1
                while j < n and (text[j].isdigit() or text[j] in "_."):
                    j += 1
                tokens.append((text[i:j], j - i))
                i = j
                continue

            if i + 1 < n and text[i : i + 2] in two_ops:
                tokens.append((text[i : i + 2], 2))
                i += 2
                continue

            tokens.append((ch, 1))
            i += 1

        return tokens

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
