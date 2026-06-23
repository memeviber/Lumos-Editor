import re

# You need to install tree-sitter and tree-sitter-javascript with: pip install tree-sitter tree-sitter-javascript
try:
    import tree_sitter_javascript as tsjavascript  # type: ignore
    from tree_sitter import Language, Parser  # type: ignore
except ImportError:
    lumos.show_warning(  # type: ignore
        "JavaScript Lexer",
        "tree-sitter-javascript is required for JavaScript syntax analysis. Please install it with: pip install tree-sitter tree-sitter-javascript",
    )
import re

from pygments.lexer import bygroups, inherit
from pygments.lexers.javascript import JavascriptLexer as PyG_JavascriptLexer
from pygments.token import (
    Comment,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
    Token,
)

js_keywords = {
    "default",
    "finally",
    "window",
    "else",
    "import",
    "void",
    "await",
    "Object",
    "Symbol",
    "String",
    "return",
    "function",
    "class",
    "null",
    "Set",
    "catch",
    "Promise",
    "RangeError",
    "with",
    "let",
    "Math",
    "WeakSet",
    "const",
    "yield",
    "true",
    "Array",
    "do",
    "this",
    "console",
    "Error",
    "EvalError",
    "if",
    "while",
    "SyntaxError",
    "for",
    "break",
    "instanceof",
    "static",
    "var",
    "Number",
    "switch",
    "throw",
    "try",
    "ReferenceError",
    "Boolean",
    "WeakMap",
    "RegExp",
    "export",
    "enum",
    "typeof",
    "extends",
    "document",
    "Date",
    "TypeError",
    "debugger",
    "new",
    "in",
    "log",
    "delete",
    "URIError",
    "async",
    "false",
    "continue",
    "case",
    "undefined",
    "Map",
    "super",
    "JSON",
}

JS_KEYWORD_PATTERN = "|".join(map(re.escape, js_keywords))


class CustomPyG_JavascriptLexer(PyG_JavascriptLexer):
    tokens = {
        "root": [
            (
                rf"\b(?!(?:{JS_KEYWORD_PATTERN})\b)([A-Za-z_]\w*)(\s*)(\()",
                bygroups(Name.Function.Call, Text, Punctuation),
            ),
            inherit,
        ]
    }


print(tsjavascript.language())
JS_LANGUAGE = Language(tsjavascript.language())


class JavaScriptLexer(lumos.PygmentsBaseLexer):  # type: ignore

    def __init__(self, editor, theme_name="default"):
        super().__init__("JavaScript", editor, theme_name=theme_name)
        self.pygments_lexer = CustomPyG_JavascriptLexer()
        self.token_map = {
            Token.Text: self.DEFAULT,
            Token.Whitespace: self.DEFAULT,
            Punctuation: self.DEFAULT,
            Operator: self.DEFAULT,
            Comment: self.COMMENTS,
            Comment.Hashbang: self.COMMENTS,
            Comment.Single: self.COMMENTS,
            Comment.Multiline: self.COMMENTS,
            String.Doc: self.STRING,
            Keyword: self.KEYWORD,
            Keyword.ControlFlow: self.KEYWORD,
            Keyword.Declaration: self.KEYWORD,
            Keyword.Namespace: self.KEYWORD,
            Keyword.Pseudo: self.KEYWORD,
            Keyword.Reserved: self.KEYWORD,
            Keyword.Operator: self.KEYWORD,
            Keyword.Type: self.TYPES,
            Name.Class: self.CLASSES,
            Name.Exception: self.CLASSES,
            Name.Builtin.Pseudo: self.KEYWORD,
            Name.Function: self.FUNCTION_DEF,
            Name.Builtin: self.FUNCTIONS,
            Name.Decorator: self.FUNCTIONS,
            Name.Function.Call: self.FUNCTIONS,
            Number: self.CONSTANTS,
            Number.Bin: self.CONSTANTS,
            Number.Float: self.CONSTANTS,
            Number.Hex: self.CONSTANTS,
            Number.Integer: self.CONSTANTS,
            Number.Integer.Long: self.CONSTANTS,
            Number.Oct: self.CONSTANTS,
            Keyword.Constant: self.CONSTANTS,
            Name.Constant: self.CONSTANTS,
            String: self.STRING,
            String.Affix: self.KEYWORD,
            String.Backtick: self.STRING,
            String.Char: self.STRING,
            String.Delimiter: self.STRING,
            String.Double: self.STRING,
            String.Escape: self.CONSTANTS,
            String.Heredoc: self.STRING,
            String.Interpol: self.DEFAULT,
            String.Other: self.STRING,
            String.Regex: self.STRING,
            String.Single: self.STRING,
            Name.Variable: self.DEFAULT,
            Name.Variable.Class: self.DEFAULT,
            Name.Variable.Global: self.DEFAULT,
            Name.Variable.Instance: self.DEFAULT,
            Name.Variable.Magic: self.DEFAULT,
            Name.Attribute: self.DEFAULT,
            Name.Label: self.DEFAULT,
            Name.Tag: self.KEYWORD,
        }
        self.parser = Parser(JS_LANGUAGE)
        self._ident_re = re.compile(r"[A-Za-z_$][\w$]*")
        self._js_globals = {
            "console",
            "window",
            "document",
            "JSON",
            "Math",
            "Object",
            "Array",
            "String",
            "Number",
            "Boolean",
            "Symbol",
            "Set",
            "Map",
            "WeakSet",
            "WeakMap",
            "Date",
            "RegExp",
            "Promise",
            "Error",
            "EvalError",
            "RangeError",
            "ReferenceError",
            "SyntaxError",
            "TypeError",
            "URIError",
            "undefined",
            "null",
            "true",
            "false",
            "Infinity",
            "NaN",
        }

    def _node_text(self, src, node):
        if node is None:
            return ""
        return src[node.start_byte : node.end_byte].decode("utf-8", "ignore")

    def _first_name_text(self, src, node):
        if node is None:
            return ""
        if node.type in {
            "identifier",
            "property_identifier",
            "shorthand_property_identifier",
            "shorthand_property_identifier_pattern",
            "private_property_identifier",
        }:
            return self._node_text(src, node)
        for ch in node.children:
            if ch.type in {
                "identifier",
                "property_identifier",
                "shorthand_property_identifier",
                "shorthand_property_identifier_pattern",
                "private_property_identifier",
            }:
                return self._node_text(src, ch)
        return ""

    def _collect_object_members(self, src, node):
        members = set()
        if node is None:
            return members
        for ch in node.children:
            if ch.type == "pair":
                key = ch.child_by_field_name("key")
                if key is not None:
                    name = self._first_name_text(src, key) or self._node_text(src, key)
                    if name:
                        members.add(name)
            elif ch.type == "method_definition":
                name = ch.child_by_field_name("name")
                name = self._first_name_text(src, name) or self._node_text(src, name)
                if name:
                    members.add(name)
        return members

    def _collect_class_members(self, src, class_body):
        members = set()
        if class_body is None:
            return members
        for ch in class_body.children:
            if ch.type == "method_definition":
                name = ch.child_by_field_name("name")
                name = self._first_name_text(src, name) or self._node_text(src, name)
                if name:
                    members.add(name)
            elif ch.type in {
                "public_field_definition",
                "field_definition",
                "property_definition",
            }:
                name = ch.child_by_field_name("name")
                name = self._first_name_text(src, name) or self._node_text(src, name)
                if name:
                    members.add(name)
        return members

    def _collect_defs(self, node, src, ctx):
        if node is None:
            return
        t = node.type
        if t == "class_declaration":
            name_node = node.child_by_field_name("name")
            class_name = self._first_name_text(src, name_node) or self._node_text(
                src, name_node
            )
            if class_name:
                ctx["symbols"].add(class_name)
                ctx["classes"].add(class_name)
            body = node.child_by_field_name("body")
            if class_name and body is not None:
                ctx["class_members"].setdefault(class_name, set()).update(
                    self._collect_class_members(src, body)
                )
            for ch in node.children:
                if ch.type != "body":
                    self._collect_defs(ch, src, ctx)
            return
        if t in {"function_declaration", "generator_function_declaration"}:
            name_node = node.child_by_field_name("name")
            name = self._first_name_text(src, name_node) or self._node_text(
                src, name_node
            )
            if name:
                ctx["symbols"].add(name)
        elif t in {"lexical_declaration", "variable_declaration"}:
            for ch in node.children:
                self._collect_defs(ch, src, ctx)
        elif t == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            var_name = self._first_name_text(src, name_node) or self._node_text(
                src, name_node
            )
            if var_name:
                ctx["symbols"].add(var_name)
                if value_node is not None:
                    if value_node.type == "new_expression":
                        ctor = value_node.child_by_field_name("constructor")
                        ctor_name = self._first_name_text(src, ctor) or self._node_text(
                            src, ctor
                        )
                        if ctor_name:
                            ctx["var_types"][var_name] = ctor_name
                    elif value_node.type == "object":
                        ctx["object_members"][var_name] = self._collect_object_members(
                            src, value_node
                        )
                    elif value_node.type == "identifier":
                        aliased = self._node_text(src, value_node)
                        if aliased:
                            ctx["var_alias"][var_name] = aliased
            for ch in node.children:
                if ch.type not in {"name", "value"}:
                    self._collect_defs(ch, src, ctx)
        elif t == "import_statement":
            for ch in node.children:
                if ch.type in {
                    "identifier",
                    "namespace_import",
                    "named_imports",
                    "import_clause",
                    "named_import_specifier",
                }:
                    txt = self._node_text(src, ch)
                    for m in self._ident_re.finditer(txt):
                        ctx["symbols"].add(m.group(0))
        elif t == "formal_parameters":
            for ch in node.children:
                txt = self._first_name_text(src, ch) or self._node_text(src, ch)
                if txt:
                    ctx["symbols"].add(txt)
        elif t == "method_definition":
            name_node = node.child_by_field_name("name")
            name = self._first_name_text(src, name_node) or self._node_text(
                src, name_node
            )
            if name:
                ctx["symbols"].add(name)
        elif t == "pair":
            key = node.child_by_field_name("key")
            name = self._first_name_text(src, key) or self._node_text(src, key)
            if name:
                ctx["symbols"].add(name)
        for ch in node.children:
            self._collect_defs(ch, src, ctx)

    def _cursor_member_context(self, src, cursor_byte):
        before = src[:cursor_byte].decode("utf-8", "ignore")
        m = re.search(r"([A-Za-z_$][\w$]*)\.\s*([A-Za-z_$][\w$]*)?$", before)
        if not m:
            return "", ""
        return m.group(1) or "", m.group(2) or ""

    def _current_class_name(self, tree, cursor_byte, src):
        node = tree.root_node.descendant_for_byte_range(
            max(0, cursor_byte - 1), max(0, cursor_byte - 1)
        )
        while node is not None:
            if node.type == "class_declaration":
                name = node.child_by_field_name("name")
                return self._first_name_text(src, name) or self._node_text(src, name)
            node = node.parent
        return ""

    def _node_prefix(self, before_text):
        m = re.search(r"([A-Za-z_$][\w$]*)$", before_text)
        return m.group(1) if m else ""

    def debug_tree(self, node, src, level=0):
        node_text = src[node.start_byte : node.end_byte][:30].decode(
            "utf-8", "ignore"
        ) + ("..." if node.end_byte - node.start_byte > 30 else "")
        print("  " * level + f"{node.type.encode('utf-8', 'ignore')}: {node_text}")
        for ch in node.children:
            self.debug_tree(ch, src, level + 1)

    def build_apis(self):
        self.apis.clear()
        code = self.editor.text()
        src = code.encode("utf-8", "ignore")
        cursor = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
        style = (
            self.editor.SendScintilla(self.editor.SCI_GETSTYLEAT, cursor - 1)
            if cursor > 0
            else -1
        )
        if style in (self.STRING, self.COMMENTS):
            self.apis.prepare()
            return
        ctx = {
            "symbols": set(),
            "classes": set(),
            "class_members": {},
            "object_members": {},
            "var_types": {},
            "var_alias": {},
        }
        try:
            tree = self.parser.parse(src)
            self._collect_defs(tree.root_node, src, ctx)
            # self.debug_tree(tree.root_node, src)
            before = src[:cursor].decode("utf-8", "ignore")
            receiver, member_prefix = self._cursor_member_context(src, cursor)
            suggestions = set()
            suggestions.update(ctx["symbols"])
            suggestions.update(self._js_globals)
            suggestions.update(ctx["classes"])
            if receiver:
                current_class = self._current_class_name(tree, cursor, src)
                if receiver in {"this", "super"} and current_class:
                    suggestions.update(ctx["class_members"].get(current_class, set()))
                elif receiver in ctx["object_members"]:
                    suggestions.update(ctx["object_members"].get(receiver, set()))
                elif receiver in ctx["var_types"]:
                    suggestions.update(
                        ctx["class_members"].get(ctx["var_types"][receiver], set())
                    )
                elif receiver in ctx["classes"]:
                    suggestions.update(ctx["class_members"].get(receiver, set()))
                if receiver in ctx["var_alias"]:
                    suggestions.add(ctx["var_alias"][receiver])
            prefix = member_prefix or self._node_prefix(before)
            for name in sorted(suggestions):
                if not name:
                    continue
                if prefix and not name.startswith(prefix):
                    continue
                self.apis.add(name)
        except Exception:
            pass
        self.apis.prepare()
