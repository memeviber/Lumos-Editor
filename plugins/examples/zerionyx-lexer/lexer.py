import os
import re
from pygments.lexer import RegexLexer, bygroups, words
from pygments.token import (
    Comment,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
)


class PyG_ZerionyxLexer(RegexLexer):
    name = "Zerionyx"
    aliases = ["zerionyx", "zyx"]
    filenames = ["*.zyx", "*.zex"]

    # fmt: off
    zyx_keywords = (
        "and", "or", "not", "if", "elif", "else", "for", "to", "do", "step", 
        "while", "defun", "done", "return", "continue", "break", "load", 
        "in", "del", "namespace", "using", "parent",
    )

    zyx_constants = ("true", "false", "none", "PI", "E", "ln2", "nan", "inf", "neg_inf", "is_main")

    zyx_builtins = (
        "println", "print", "input", "get_password", "clear", "type", "is_none", 
        "is_num", "is_bool", "is_str", "is_list", "is_func", "is_thread", 
        "is_thread_pool", "is_future", "is_namespace", "is_channel", "is_cfloat", 
        "is_py_obj", "is_nan", "is_panic", "len", "panic", "pop", "append", 
        "insert", "extend", "slice", "to_str", "to_int", "to_float", "to_cfloat", 
        "to_bytes", "pyexec", "clone", "keys", "values", "items", "has", "get", 
        "del_key", "get_member", "shl", "shr", "bitwise_and", "bitwise_or", 
        "bitwise_xor", "bitwise_not",
    )

    zyx_types = (
        "list", "str", "int", "float", "func", "bool", "hashmap", "thread", 
        "bytes", "py_obj", "cfloat", "namespace", "channel_type", 
        "thread_pool_type", "future_type", "none_type",
    )

    ZYX_KEYWORD_PATTERN = "|".join(zyx_keywords + zyx_constants + zyx_builtins + zyx_types)

    tokens = {
        "root": [
            (rf"\b(?!(?:{ZYX_KEYWORD_PATTERN})\b)([A-Za-z_]\w*)(\s*)(\()", bygroups(Name.Function.Call, Text, Punctuation)),
            (r"\s+", Text),
            (r"#.*$", Comment.Single),
            (r"&[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*", Name.Decorator),
            (r"(defun)(\s+)([a-zA-Z_]\w*)", bygroups(Keyword, Text, Name.Function)),
            (r"(namespace)(\s+)([a-zA-Z_]\w*)", bygroups(Keyword.Namespace, Text, Name.Namespace)),
            (r"(load)(\s+)", bygroups(Keyword.Namespace, Text), "load_string"),
            (words(zyx_keywords, suffix=r"\b"), Keyword),
            (words(zyx_constants, suffix=r"\b"), Keyword.Constant),
            (words(zyx_builtins, suffix=r"\b"), Name.Builtin),
            (words(zyx_types, suffix=r"\b"), Name.Builtin.Pseudo),
            (r'"""', String.Double, "string_double_multiline"),
            (r"'''", String.Single, "string_single_multiline"),
            (r'"', String.Double, "string_double"),
            (r"'", String.Single, "string_single"),
            (r"\d+\.\d+", Number.Float),
            (r"\d+", Number.Integer),
            (r"(\+=|-=|\*=|/=|//=|%=|\^=|==|!=|<=|>=|<|>|\+|-|\*|//|/|%|\^|\$|=)", Operator),
            (r"[.,:;(){}\[\]\\]", Punctuation),
            (r"[a-zA-Z_]\w*", Name),
        ],
        "load_string": [
            (r'"[^"]*"', String.Double, "#pop"),
            (r"'[^']*'", String.Single, "#pop"),
            (r"\s+", Text),
            (r"", Text, "#pop"),
        ],
        "string_double_multiline": [
            (r'[^"\\]+', String.Double),
            (r"\\.", String.Escape),
            (r'"""', String.Double, "#pop"),
            (r'"', String.Double),
        ],
        "string_single_multiline": [
            (r"[^'\\]+", String.Single),
            (r"\\.", String.Escape),
            (r"'''", String.Single, "#pop"),
            (r"'", String.Single),
        ],
        "string_double": [
            (r'[^"\\]+', String.Double),
            (r"\\.", String.Escape),
            (r'"', String.Double, "#pop"),
        ],
        "string_single": [
            (r"[^'\\]+", String.Single),
            (r"\\.", String.Escape),
            (r"'", String.Single, "#pop"),
        ],
    }
    # fmt: on


# fmt: off
LIBRARY_FUNCTIONS = {
    "msgbox": ["alert", "confirm", "prompt", "password"],
    "time.datetime": ["now", "diff", "add_days", "format", "today", "parse"],
    "listm": ["map", "filter", "reduce", "min", "max", "reverse", "zip", "zip_longest", "sort", "count", "index_of", "rand_int_list", "rand_float_list"],
    "string": ["split", "strip", "join", "replace", "to_upper", "to_lower", "ord", "chr", "is_digit", "is_ascii_lowercase", "is_ascii_uppercase", "is_ascii_letter", "is_space", "find", "find_all", "startswith", "endswith", "encode", "decode", "format"],
    "math": ["sqrt", "abs", "fact", "sin", "cos", "tan", "gcd", "lcm", "fib", "is_prime", "deg2rad", "rad2deg", "exp", "log", "sinh", "cosh", "tanh", "round", "is_close"],
    "ffio": ["write", "read", "exists", "get_cdir", "set_cdir", "list_dir", "make_dir", "remove_file", "rename", "remove_dir", "copy", "is_file", "abs_path", "base_name", "dir_name", "symlink", "readlink", "stat", "lstat", "walk", "chmod", "chown", "utime", "link", "unlink", "access", "path_join", "is_dir", "is_link", "is_mount"],
    "hash": ["md5", "sha1", "sha256", "sha512", "crc32"],
    "memory": ["remember", "recall", "forget", "clear_memory", "keys", "is_empty", "size"],
    "net": ["get_ip", "get_mac", "ping", "downl", "get_local_ip", "get_hostname", "request"],
    "random": ["rand", "rand_int", "rand_float", "rand_choice", "int_seed", "float_seed"],
    "sys": ["system", "osystem", "get_env", "set_env", "exit"],
    "threading": ["start", "sleep", "join", "is_alive", "cancel"],
    "threading.pool": ["new", "submit", "shutdown", "result", "is_done"],
    "time": ["sleep", "time", "ctime"],
    "keyboard": ["write", "press", "release", "wait", "is_pressed"],
    "termcolor": ["cprint", "cprintln", "get_code"],
    "mouse": ["move", "click", "right_click", "scroll", "position"],
    "screen": ["capture", "capture_area", "get_color"],
    "json": ["parse", "stringify"],
    "csv": ["read", "write"],
    "decorators": ["cache", "once", "retry", "timeout", "log_call", "measure_time", "repeat", "ignore_error", "deprecated", "lazy"],
    "channel": ["new", "send", "recv", "is_empty"]
}

LIBRARY_CONSTANTS = {
    "math": ["PI", "E", "ln2"],
    "ffio": ["os_sep"],
    "sys": ["argv", "os_name"]
}
# fmt: on


class ZerionyxLexer(lumos.PygmentsBaseLexer):  # type: ignore
    def __init__(self, editor, theme_name="default"):
        super().__init__("Zerionyx", editor, theme_name=theme_name)
        self.pygments_lexer = PyG_ZerionyxLexer()

        from pygments.token import Token

        self.token_map = {
            Token.Text: self.DEFAULT,
            Token.Whitespace: self.DEFAULT,
            Comment.Single: self.COMMENTS,
            Name.Decorator: self.FUNCTIONS,
            Keyword: self.KEYWORD,
            Keyword.Namespace: self.KEYWORD,
            Name.Function: self.FUNCTION_DEF,
            Name.Function.Call: self.FUNCTIONS,
            Name.Namespace: self.CLASS_DEF,
            Keyword.Constant: self.CONSTANTS,
            Name.Builtin: self.FUNCTIONS,
            Name.Builtin.Pseudo: self.TYPES,
            String.Double: self.STRING,
            String.Single: self.STRING,
            String.Escape: self.CONSTANTS,
            Number.Float: self.CONSTANTS,
            Number.Integer: self.CONSTANTS,
            Operator: self.DEFAULT,
            Punctuation: self.DEFAULT,
            Name: self.DEFAULT,
        }

    def build_apis(self):
        self.apis.clear()

        pos = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
        style = (
            self.editor.SendScintilla(self.editor.SCI_GETSTYLEAT, pos - 1)
            if pos > 0
            else -1
        )
        if style in (self.STRING, self.COMMENTS):
            self.apis.prepare()
            return

        text = self.editor.text()
        line, col = self.editor.getCursorPosition()
        line_text = self.editor.text(line)[:col]

        load_pattern = re.compile(r'load\s+["\']([^"\']+)["\']')
        std_libs_loaded = set()
        local_files_to_scan = set()

        for match in load_pattern.finditer(text):
            path = match.group(1)
            if path.startswith("libs."):
                std_libs_loaded.add(path.split("libs.", 1)[1])
            elif path.startswith("local."):
                local_files_to_scan.add(path.split("local.", 1)[1])

        current_file = lumos.plugin_manager._get_current_file()  # type: ignore
        base_dir = os.path.dirname(current_file) if current_file else ""

        local_ns_map = {}
        global_suggestions = set()

        def strip_comments_and_strings(code):
            code = re.sub(r"#.*", "", code)
            code = re.sub(r'"""(.*?)"""', "", code, flags=re.DOTALL)
            code = re.sub(r"'''(.*?)'''", "", code, flags=re.DOTALL)
            code = re.sub(r'"([^"\\]|\\.)*"', "", code)
            code = re.sub(r"'([^'\\]|\\.)*'", "", code)
            return code

        def parse_source(source_code):
            clean_code = strip_comments_and_strings(source_code)
            lines = clean_code.splitlines()

            ns_stack = []
            stack = []

            ns_start = re.compile(r"\bnamespace\s+([a-zA-Z_]\w*)")

            defun_multiline = re.compile(r"\bdefun\b(?!.*->)")
            if_multiline = re.compile(r"\b(?<!el)if\b.*?\bdo\s*$")
            while_multiline = re.compile(r"\bwhile\b.*?\bdo\s*$")
            for_multiline = re.compile(r"\bfor\b.*?\bdo\s*$")

            func_pattern = re.compile(r"defun\s+([a-zA-Z_]\w*)")
            var_pattern = re.compile(r"([a-zA-Z_]\w*)\s*=")
            for_pattern = re.compile(r"(?:\bfor|,)\s+([a-zA-Z_]\w*)")

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                if stripped == "done" or stripped.endswith(" done"):
                    if stack:
                        top = stack.pop()
                        if top.startswith("ns:"):
                            ns_stack.pop()
                    continue

                ns_match = ns_start.search(stripped)
                if ns_match:
                    ns_name = ns_match.group(1)
                    ns_stack.append(ns_name)
                    stack.append(f"ns:{ns_name}")

                    global_suggestions.add(ns_name)
                    global_suggestions.add(".".join(ns_stack))
                    continue

                if (
                    defun_multiline.search(stripped)
                    or if_multiline.search(stripped)
                    or while_multiline.search(stripped)
                    or for_multiline.search(stripped)
                ):
                    stack.append("generic")

                current_ns = ".".join(ns_stack)
                funcs = func_pattern.findall(stripped)
                vars_ = var_pattern.findall(stripped)
                fors = for_pattern.findall(stripped)

                if current_ns:
                    if current_ns not in local_ns_map:
                        local_ns_map[current_ns] = set()
                    local_ns_map[current_ns].update(funcs)
                    local_ns_map[current_ns].update(vars_)
                else:
                    global_suggestions.update(funcs)
                    global_suggestions.update(vars_)
                    global_suggestions.update(fors)

        parse_source(text)

        if base_dir:
            for loc in local_files_to_scan:
                local_path = os.path.join(base_dir, loc.replace(".", os.sep) + ".zyx")
                if not os.path.exists(local_path):
                    local_path = os.path.join(
                        base_dir, loc.replace(".", os.sep) + ".zex"
                    )

                if os.path.exists(local_path):
                    try:
                        with open(local_path, "r", encoding="utf-8") as f:
                            local_text = f.read()
                        parse_source(local_text)
                    except Exception:
                        pass

        match = re.search(
            r"([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)\.([a-zA-Z_]\w*)?$", line_text
        )
        if match:
            prefix = match.group(1)

            root_lib = prefix.split(".")[0]
            if prefix in std_libs_loaded or root_lib in std_libs_loaded:
                if prefix in LIBRARY_FUNCTIONS:
                    for func in LIBRARY_FUNCTIONS[prefix]:
                        self.apis.add(func)
                if prefix in LIBRARY_CONSTANTS:
                    for const in LIBRARY_CONSTANTS[prefix]:
                        self.apis.add(const)

            if prefix in local_ns_map:
                for member in local_ns_map[prefix]:
                    self.apis.add(member)

            self.apis.prepare()
            return

        global_suggestions.update(PyG_ZerionyxLexer.zyx_keywords)
        global_suggestions.update(PyG_ZerionyxLexer.zyx_constants)
        global_suggestions.update(PyG_ZerionyxLexer.zyx_builtins)
        global_suggestions.update(PyG_ZerionyxLexer.zyx_types)

        global_suggestions.update(std_libs_loaded)

        for word in global_suggestions:
            self.apis.add(word)

        self.apis.prepare()
