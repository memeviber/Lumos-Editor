import array

import jedi
import tree_sitter_python as tspython
from PyQt5 import QtCore
from tree_sitter import Language, Parser, Query, QueryCursor

PY_LANGUAGE = Language(tspython.language())

PYTHON_QUERY = Query(
    PY_LANGUAGE,
    """
    (comment) @comment
    (string) @string
    (integer) @number
    (float) @number
    
    "class" @keyword
    "def" @keyword
    "if" @keyword
    "else" @keyword
    "elif" @keyword
    "for" @keyword
    "while" @keyword
    "return" @keyword
    "import" @keyword
    "from" @keyword
    "try" @keyword
    "except" @keyword
    "pass" @keyword
    "break" @keyword
    "continue" @keyword
    "lambda" @keyword
    "with" @keyword
    "as" @keyword
    "global" @keyword
    "nonlocal" @keyword
    "assert" @keyword
    "del" @keyword
    "yield" @keyword
    
    (class_definition name: (identifier) @class_def)
    (function_definition name: (identifier) @function_def)
""",
)

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


class PyTreeSitterWorker(QtCore.QObject):
    styling_ready = QtCore.pyqtSignal(int, int, object)

    def __init__(self):
        super().__init__()
        self.parser = Parser(PY_LANGUAGE)
        self.current_tree = None
        self.latest_generation = 0
        self._is_cancelled = False

    @QtCore.pyqtSlot(bytes, list, int, int, int)
    def process_ast(self, data, edits, start_pos, end_pos, generation):
        try:
            if generation < self.latest_generation:
                return
            self.latest_generation = generation
            self._is_cancelled = False

            try:
                if self.current_tree is not None and edits:
                    for edit in edits:
                        self.current_tree.edit(
                            start_byte=edit["start_byte"],
                            old_end_byte=edit["old_end_byte"],
                            new_end_byte=edit["new_end_byte"],
                            start_point=edit["start_point"],
                            old_end_point=edit["old_end_point"],
                            new_end_point=edit["new_end_point"],
                        )

                tree = self.parser.parse(data, self.current_tree)
            except Exception:
                tree = self.parser.parse(data)

            self.current_tree = tree
            if not tree or not tree.root_node:
                return

            query_cursor = QueryCursor(PYTHON_QUERY)
            try:
                query_cursor.set_byte_range(start_pos, end_pos)
            except AttributeError:
                pass

            captures = query_cursor.captures(tree.root_node)

            node_styles = []
            for tag, nodes in captures.items():
                for node in nodes:
                    if node.start_byte < end_pos and node.end_byte > start_pos:
                        node_styles.append((node, tag))

            node_styles.sort(key=lambda x: x[0].start_byte)

            runs = array.array("i")
            append = runs.append

            last_pos = start_pos
            for node, tag in node_styles:
                if self._is_cancelled or generation < self.latest_generation:
                    return

                start = max(node.start_byte, start_pos)
                end = min(node.end_byte, end_pos)

                if start >= end:
                    continue

                if start < last_pos:
                    continue

                if start > last_pos:
                    append(start - last_pos)
                    append(STYLE_DEFAULT)

                style = STYLE_DEFAULT
                if tag == "comment":
                    style = STYLE_COMMENTS
                elif tag == "string":
                    style = STYLE_STRING
                elif tag == "class_def":
                    style = STYLE_CLASSES
                elif tag == "function_def":
                    style = STYLE_FUNCTION_DEF
                elif tag == "keyword":
                    style = STYLE_KEYWORD
                elif tag == "number":
                    style = STYLE_CONSTANTS

                append(end - start)
                append(style)
                last_pos = end

            if end_pos > last_pos:
                append(end_pos - last_pos)
                append(STYLE_DEFAULT)

            if not self._is_cancelled and generation == self.latest_generation:
                self.styling_ready.emit(generation, start_pos, runs)

        except Exception:
            import traceback

            traceback.print_exc()

    def cancel(self):
        self._is_cancelled = True


class PyFlex(lumos.BaseLexer):  # type: ignore
    def __init__(self, editor, theme_name="default"):
        super().__init__("Python", editor, theme_name=theme_name)

        self.DEBOUNCE_DELAY = 15
        self.generation = 0
        self.edits_queue = []

        self.worker_thread = QtCore.QThread(self.editor)
        self.worker = PyTreeSitterWorker()
        self.worker.moveToThread(self.worker_thread)
        self.worker.styling_ready.connect(self._apply_styling)
        self.worker_thread.start()

        self.editor.SCN_MODIFIED.connect(self._on_modified)
        self.editor.destroyed.connect(self._cleanup_thread)

    def _on_modified(
        self,
        position,
        modificationType,
        text,
        length,
        linesAdded,
        line,
        foldLevelNow,
        foldLevelPrev,
        token,
        annotationLinesAdded,
    ):
        try:
            SC_MOD_INSERTTEXT = 0x1
            SC_MOD_DELETETEXT = 0x2

            if not (modificationType & (SC_MOD_INSERTTEXT | SC_MOD_DELETETEXT)):
                return

            if isinstance(text, str):
                text_bytes = text.encode("utf-8", errors="ignore")
            else:
                text_bytes = text if text else b""

            editor = self.editor
            row = editor.SendScintilla(editor.SCI_LINEFROMPOSITION, position)
            col = position - editor.SendScintilla(editor.SCI_POSITIONFROMLINE, row)

            start_byte = position
            start_point = (row, col)

            if modificationType & SC_MOD_INSERTTEXT:
                old_end_byte = position
                new_end_byte = position + length
                old_end_point = (row, col)

                new_end_row = editor.SendScintilla(
                    editor.SCI_LINEFROMPOSITION, position + length
                )
                new_end_col = (position + length) - editor.SendScintilla(
                    editor.SCI_POSITIONFROMLINE, new_end_row
                )
                new_end_point = (new_end_row, new_end_col)
            else:
                old_end_byte = position + length
                new_end_byte = position
                new_end_point = (row, col)

                num_newlines = text_bytes.count(b"\n")
                if num_newlines == 0:
                    old_end_row = row
                    old_end_col = col + len(text_bytes)
                else:
                    old_end_row = row + num_newlines
                    old_end_col = len(text_bytes.split(b"\n")[-1])
                old_end_point = (old_end_row, old_end_col)

            edit_info = {
                "start_byte": start_byte,
                "old_end_byte": old_end_byte,
                "new_end_byte": new_end_byte,
                "start_point": start_point,
                "old_end_point": old_end_point,
                "new_end_point": new_end_point,
            }
            self.edits_queue.append(edit_info)
        except Exception:
            pass

    def _do_style_text(self, start: int, end: int):
        self.generation += 1
        self.worker.cancel()
        self.worker.latest_generation = self.generation

        editor = self.editor

        start_line = editor.SendScintilla(editor.SCI_LINEFROMPOSITION, start)
        line_start_pos = editor.SendScintilla(editor.SCI_POSITIONFROMLINE, start_line)
        if line_start_pos < start:
            start = line_start_pos

        doc_len = editor.SendScintilla(editor.SCI_GETTEXTLENGTH)
        if end > doc_len:
            end = doc_len

        if doc_len > 0:
            data_slice = bytearray(doc_len)
            editor.SendScintilla(editor.SCI_GETTEXTRANGE, 0, doc_len, data_slice)
            data_bytes = bytes(data_slice)
        else:
            data_bytes = b""

        edits_to_apply = list(self.edits_queue)
        self.edits_queue.clear()

        QtCore.QMetaObject.invokeMethod(
            self.worker,
            "process_ast",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(bytes, data_bytes),
            QtCore.Q_ARG(list, edits_to_apply),
            QtCore.Q_ARG(int, start),
            QtCore.Q_ARG(int, end),
            QtCore.Q_ARG(int, self.generation),
        )

    @QtCore.pyqtSlot(int, int, object)
    def _apply_styling(self, generation, start_pos, runs):
        if generation != self.generation:
            return

        self.startStyling(start_pos)
        setStyling = self.setStyling

        idx = 0
        r_len = len(runs)
        while idx < r_len:
            setStyling(runs[idx], runs[idx + 1])
            idx += 2

    def _cleanup_thread(self):
        self.worker.cancel()
        self.worker_thread.quit()
        self.worker_thread.wait()

    def build_apis(self):
        self.apis.clear()
        doc_len = self.editor.SendScintilla(self.editor.SCI_GETTEXTLENGTH)

        if doc_len > 0:
            source = bytearray(doc_len + 1)
            self.editor.SendScintilla(self.editor.SCI_GETTEXT, doc_len + 1, source)
            code = source[:-1].decode("utf-8", errors="ignore")
        else:
            code = ""

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
