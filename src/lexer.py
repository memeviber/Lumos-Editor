from .theme_manager import theme
import json
import keyword
import os
import re
from typing import TypedDict

import jedi
from pygments import lex
from pygments.lexer import bygroups, inherit
from pygments.lexers.data import JsonLexer as PyG_JsonLexer
from pygments.lexers.markup import MarkdownLexer as PyG_MarkdownLexer
from pygments.lexers.python import PythonLexer as PyG_PythonLexer
from pygments.token import (
    Comment,
    Generic,
    Keyword,
    Literal,
    Name,
    Number,
    Punctuation,
    String,
    Text,
    Token,
)
from PyQt5.Qsci import QsciAPIs, QsciLexerCustom, QsciScintilla
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor, QFont


class DefaultConfig(TypedDict):
    color: str
    paper: str
    font: tuple[str, int]


class BaseLexer(QsciLexerCustom):
    DEBOUNCE_DELAY = 35

    def __init__(
        self,
        language_name,
        editor,
        theme_name="default",
        defaults: DefaultConfig = None,
    ):
        super(BaseLexer, self).__init__(editor)
        self.editor = editor
        self.apis = QsciAPIs(self)
        self.language_name = language_name
        self.theme_json = None
        themes_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "themes"
        )
        self.theme = os.path.join(themes_dir, theme_name, "theme.json")
        if defaults is None:
            defaults: DefaultConfig = {}
            defaults["color"] = f"{theme.color27}"
            defaults["paper"] = f"{theme.color5}"
            defaults["font"] = ("Consolas", 14)
        self.setDefaultColor(QColor(defaults["color"]))
        self.setDefaultPaper(QColor(defaults["paper"]))
        fnt = QFont(defaults["font"][0], defaults["font"][1])
        fnt.setStyleStrategy(QFont.PreferAntialias)
        self.setDefaultFont(fnt)
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(self.DEBOUNCE_DELAY)
        self._debounce_timer.timeout.connect(self._process_pending_style)
        self._pending_style_start = None
        self._pending_style_end = None
        self._init_theme_vars()
        self._init_theme()

    def _init_theme_vars(self):
        self.DEFAULT = 0
        self.KEYWORD = 1
        self.TYPES = 2
        self.STRING = 3
        self.COMMENTS = 4
        self.CONSTANTS = 5
        self.FUNCTIONS = 6
        self.FUNCTION_DEF = 7
        self.CLASS_DEF = 8
        self.CLASSES = 9
        self.default_names = [
            "default",
            "keyword",
            "functions",
            "class_def",
            "function_def",
            "classes",
            "string",
            "types",
            "comments",
            "constants",
        ]
        self.style_map = {
            "default": self.DEFAULT,
            "keyword": self.KEYWORD,
            "types": self.TYPES,
            "string": self.STRING,
            "comments": self.COMMENTS,
            "constants": self.CONSTANTS,
            "functions": self.FUNCTIONS,
            "class_def": self.CLASS_DEF,
            "function_def": self.FUNCTION_DEF,
            "classes": self.CLASSES,
        }
        self.font_weights = {
            "thin": QFont.Thin,
            "extralight": QFont.ExtraLight,
            "light": QFont.Light,
            "normal": QFont.Normal,
            "medium": QFont.Medium,
            "demibold": QFont.DemiBold,
            "bold": QFont.Bold,
            "extrabold": QFont.ExtraBold,
            "black": QFont.Black,
        }

    def _init_theme(self):
        if not os.path.exists(self.theme):
            return
        try:
            with open(self.theme, "r", encoding="utf-8") as f:
                self.theme_json = json.load(f)
        except Exception:
            return
        paper_color = self.theme_json.get("theme", {}).get("paper-color")
        margin_color = self.theme_json.get("theme", {}).get("margin-color")
        if paper_color:
            bg_color = QColor(paper_color)
            self.setDefaultPaper(bg_color)
            if hasattr(self, "editor") and self.editor:
                self.editor.setPaper(bg_color)
                self.editor.setMarginsBackgroundColor(bg_color.darker(110))
                self.editor.setMarginsForegroundColor(
                    QColor(margin_color) if margin_color else bg_color.lighter(150)
                )
        else:
            self.setDefaultPaper(QColor(f"{theme.color5}"))
            self.editor.setPaper(self.defaultPaper())
            self.editor.setMarginsBackgroundColor(QColor(f"{theme.color1}"))
            self.editor.setMarginsForegroundColor(QColor(f"{theme.color25}"))
        self.editor.setStyleSheet(
            f"""
                    QAbstractItemView {{
                        background-color: {bg_color.lighter(110).name()};
                        color: {self.color(self.DEFAULT).name()};
                        border: None;
                        border-radius: 4px;
                        padding: 2px;
                        min-height: 28px;
                    }}
                    QAbstractItemView::item:selected {{
                        background-color: {bg_color.lighter(130).name()};
                        color: {self.color(self.DEFAULT).name()};
                    }}
                """
        )
        self.editor.setMatchedBraceBackgroundColor(bg_color.lighter(120))
        self.editor.setUnmatchedBraceBackgroundColor(bg_color.lighter(120))
        fold_bg = bg_color.darker(110)
        fold_fg = QColor(margin_color).lighter(150)
        self.editor.setFoldMarginColors(fold_bg, fold_bg)
        self.editor.setMarkerForegroundColor(fold_fg, 0)
        self.editor.setMarkerForegroundColor(fold_fg, 1)
        self.editor.setMarkerBackgroundColor(fold_bg, 0)
        self.editor.setMarkerBackgroundColor(fold_bg, 1)
        self.editor.markerDefine(
            QsciScintilla.SC_MARK_ARROW, QsciScintilla.SC_MARKNUM_FOLDER
        )
        self.editor.markerDefine(
            QsciScintilla.SC_MARK_ARROWDOWN, QsciScintilla.SC_MARKNUM_FOLDEROPEN
        )
        self.editor.setMarkerForegroundColor(fold_fg, QsciScintilla.SC_MARKNUM_FOLDER)
        self.editor.setMarkerForegroundColor(
            fold_fg, QsciScintilla.SC_MARKNUM_FOLDEROPEN
        )
        self.editor.setMarkerBackgroundColor(fold_bg, QsciScintilla.SC_MARKNUM_FOLDER)
        self.editor.setMarkerBackgroundColor(
            fold_bg, QsciScintilla.SC_MARKNUM_FOLDEROPEN
        )
        colors = self.theme_json.get("theme", {}).get("syntax", [])
        for clr in colors:
            name: str = list(clr.keys())[0]
            if name not in self.default_names:
                continue
            style_id = self.style_map.get(name)
            if style_id is None:
                continue
            for k, v in clr[name].items():
                if k == "color":
                    self.setColor(QColor(v), style_id)
                elif k == "paper-color":
                    self.setPaper(QColor(v), style_id)
                elif k == "font":
                    try:
                        fnt = QFont(
                            v.get("family", "Consolas"),
                            v.get("font-size", 14),
                            self.font_weights.get(v.get("font-weight", QFont.Normal)),
                            v.get("italic", False),
                        )
                        fnt.setStyleStrategy(QFont.PreferAntialias)
                        self.setFont(fnt, style_id)
                    except AttributeError:
                        pass

    def language(self) -> str:
        return self.language_name

    def description(self, style: int) -> str:
        reverse_map = {v: k.upper() for k, v in self.style_map.items()}
        return reverse_map.get(style, "")

    def _process_pending_style(self):
        if (
            self._pending_style_start is not None
            and self._pending_style_end is not None
        ):
            start = self._pending_style_start
            end = self._pending_style_end
            self._pending_style_start = None
            self._pending_style_end = None
            self._do_style_text(start, end)

    def _do_style_text(self, start: int, end: int):
        pass

    def styleText(self, start: int, end: int):
        if self._pending_style_start is None:
            self._pending_style_start = start
            self._pending_style_end = end
        else:
            self._pending_style_start = min(self._pending_style_start, start)
            self._pending_style_end = max(self._pending_style_end, end)
        self._debounce_timer.stop()
        self._debounce_timer.start()


class PygmentsBaseLexer(BaseLexer):
    def __init__(self, language_name, editor, theme_name="default"):
        super().__init__(language_name, editor, theme_name=theme_name)
        self.pygments_lexer = None
        self.token_map = {}

    def _do_style_text(self, start: int, end: int):
        if not self.pygments_lexer or not self.token_map:
            return

        all_text = self.editor.text()
        self.startStyling(start)
        tokens = lex(all_text, self.pygments_lexer)
        current_byte_pos = 0

        for ttype, value in tokens:
            token_len_bytes = len(value.encode("utf-8"))
            token_end_pos = current_byte_pos + token_len_bytes

            if token_end_pos > start and current_byte_pos < end:
                style_id = self._get_style_from_token(ttype)
                overlap_start = max(start, current_byte_pos)
                overlap_end = min(end, token_end_pos)
                overlap_len = overlap_end - overlap_start
                self.setStyling(overlap_len, style_id)

            current_byte_pos = token_end_pos
            if current_byte_pos >= end:
                break

    def _get_style_from_token(self, ttype):
        while ttype in self.token_map:
            return self.token_map[ttype]
        if ttype.parent:
            return self._get_style_from_token(ttype.parent)
        return self.DEFAULT


all_keywords = keyword.kwlist.copy()


if hasattr(keyword, "softkwlist"):
    all_keywords.extend(keyword.softkwlist)


KEYWORD_PATTERN = "|".join(map(re.escape, all_keywords))


class CustomPyG_PythonLexer(PyG_PythonLexer):
    tokens = {
        "root": [
            (
                rf"\b(?!(?:{KEYWORD_PATTERN})\b)([A-Za-z_]\w*)(\s*)(\()",
                bygroups(Name.Function.Call, Text, Punctuation),
            ),
            inherit,
        ]
    }


class PythonLexer(PygmentsBaseLexer):
    def __init__(self, editor, theme_name="default"):
        super().__init__("Python", editor, theme_name=theme_name)
        self.pygments_lexer = CustomPyG_PythonLexer()
        self.token_map = {
            Token.Text: self.DEFAULT,
            Token.Whitespace: self.DEFAULT,
            Comment: self.COMMENTS,
            Keyword: self.KEYWORD,
            Keyword.Namespace: self.KEYWORD,
            Keyword.Pseudo: self.KEYWORD,
            Keyword.Reserved: self.KEYWORD,
            Keyword.Type: self.TYPES,
            Keyword.Constant: self.CONSTANTS,
            Name.Builtin: self.FUNCTIONS,
            Name.Builtin.Pseudo: self.KEYWORD,
            Name.Class: self.CLASSES,
            Name.Exception: self.CLASSES,
            Name.Function: self.FUNCTION_DEF,
            Name.Decorator: self.FUNCTIONS,
            Name.Function.Call: self.FUNCTIONS,
            Name.Constant: self.CONSTANTS,
            Name.Attribute: self.DEFAULT,
            Number: self.CONSTANTS,
            String: self.STRING,
            String.Affix: self.KEYWORD,
            String.Doc: self.STRING,
            String.Escape: self.CONSTANTS,
            String.Interpol: self.DEFAULT,
            Name.Tag: self.KEYWORD,
        }

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


class JsonLexer(PygmentsBaseLexer):
    def __init__(self, editor, theme_name="default"):
        super().__init__("JSON", editor, theme_name=theme_name)
        self.pygments_lexer = PyG_JsonLexer()
        self.token_map = {
            Token.Text: self.DEFAULT,
            String: self.STRING,
            Number: self.CONSTANTS,
            Keyword: self.TYPES,
            Keyword.Constant: self.TYPES,
            Punctuation: self.DEFAULT,
            Name.Tag: self.CLASS_DEF,
        }

    def build_apis(self):
        self.apis.clear()
        pos = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
        style = (
            self.editor.SendScintilla(self.editor.SCI_GETSTYLEAT, pos - 1)
            if pos > 0
            else -1
        )
        if style not in (self.STRING,):
            self.apis.add("true")
            self.apis.add("false")
            self.apis.add("null")
        self.apis.prepare()


class MarkdownLexer(PygmentsBaseLexer):
    def __init__(self, editor, theme_name="default"):
        super().__init__("Markdown", editor, theme_name=theme_name)
        self.pygments_lexer = PyG_MarkdownLexer()
        self.token_map = {
            Token.Text: self.DEFAULT,
            Generic.Heading: self.CLASS_DEF,
            Generic.Subheading: self.CLASS_DEF,
            Generic.Strong: self.FUNCTIONS,
            Generic.Emph: self.TYPES,
            String.Backtick: self.STRING,
            Literal.String.Backtick: self.STRING,
            Comment.Preproc: self.STRING,
            Keyword: self.DEFAULT,
            Generic.Prompt: self.COMMENTS,
            Generic.Traceback: self.CONSTANTS,
            Name.Tag: self.FUNCTIONS,
            Name.Attribute: self.CONSTANTS,
        }

    def build_apis(self):
        self.apis.clear()
        self.apis.prepare()


class PlainTextLexer(BaseLexer):
    def __init__(self, editor, theme_name="default"):
        super().__init__("Plain Text", editor, theme_name=theme_name)

    def _do_style_text(self, start: int, end: int):
        pass

    def build_apis(self):
        self.apis.clear()
        self.apis.prepare()
