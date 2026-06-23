import json
import os
import threading
import zipfile

from PyQt5.QtCore import (
    QEventLoop,
    QObject,
    QRunnable,
    Qt,
    QThread,
    QThreadPool,
    pyqtSignal,
)
from PyQt5.QtGui import QIcon, QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from .API import LumosAPI
from .editor_tab import EditorTab
from .lexer import BaseLexer, PygmentsBaseLexer
from .split_tab import SplitTab


class PluginInfo:
    def __init__(self, manifest, zip_path):
        self.manifest = manifest
        self.zip_path = zip_path
        self.lexer_class = None
        self.icon = None
        self.plugin_type = None


class _MainThreadBridge(QObject):
    request = pyqtSignal(object)


class _PluginLoadTaskSignals(QObject):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str, str)


class _PluginLoadTask(QRunnable):
    def __init__(self, manager, filename, plugin_info):
        super().__init__()
        self.manager = manager
        self.filename = filename
        self.plugin_info = plugin_info
        self.signals = _PluginLoadTaskSignals()

    def run(self):
        try:
            plugin_content = self.manager._read_plugin_content(
                self.plugin_info.zip_path
            )
            if not plugin_content:
                self.signals.finished.emit(self.filename)
                return

            def _get_project_dir():
                try:
                    return getattr(
                        self.manager.parent_widget, "current_project_dir", None
                    )
                except Exception:
                    return None

            def _abs_in_project(target):
                proj = _get_project_dir()
                if not proj:
                    return False
                try:
                    return os.path.abspath(target).startswith(
                        os.path.abspath(proj) + os.sep
                    )
                except Exception:
                    return False

            def create_project_file(relpath, content=""):
                proj = _get_project_dir()
                if not proj:
                    raise RuntimeError("No project open")
                target = (
                    os.path.join(proj, relpath)
                    if not os.path.isabs(relpath)
                    else relpath
                )
                if not _abs_in_project(target):
                    raise RuntimeError("Target path must be inside the current project")
                d = os.path.dirname(target)
                os.makedirs(d, exist_ok=True)
                with open(target, "w", encoding="utf-8") as f:
                    f.write(content)
                return target

            def write_project_file(relpath, content):
                return create_project_file(relpath, content)

            def read_project_file(relpath):
                proj = _get_project_dir()
                if not proj:
                    raise RuntimeError("No project open")
                target = (
                    os.path.join(proj, relpath)
                    if not os.path.isabs(relpath)
                    else relpath
                )
                if not _abs_in_project(target):
                    raise RuntimeError("Target path must be inside the current project")
                with open(target, "r", encoding="utf-8") as f:
                    return f.read()

            def delete_project_file(relpath):
                proj = _get_project_dir()
                if not proj:
                    raise RuntimeError("No project open")
                target = (
                    os.path.join(proj, relpath)
                    if not os.path.isabs(relpath)
                    else relpath
                )
                if not _abs_in_project(target):
                    raise RuntimeError("Target path must be inside the current project")
                if os.path.isdir(target):
                    import shutil

                    shutil.rmtree(target)
                else:
                    os.remove(target)
                return True

            def show_message(title, message):
                self.manager._call_main_thread("message", title, message)

            def show_warning(title, message):
                self.manager._call_main_thread("warning", title, message)

            def show_error(title, message):
                self.manager._call_main_thread("error", title, message)

            def ask_yn_question(title, question):
                return self.manager._call_main_thread("ask_yn", title, question)

            def ask_text_input(title, label, default=""):
                return self.manager._call_main_thread("ask_text", title, label, default)

            def _get_editor_text():
                active_tab = self.manager._get_active_editor_tab()
                if (
                    active_tab
                    and isinstance(active_tab, EditorTab)
                    and active_tab.editor
                ):
                    return active_tab.editor.text()
                return None

            def _set_editor_text(text):
                active_tab = self.manager._get_active_editor_tab()
                if (
                    active_tab
                    and isinstance(active_tab, EditorTab)
                    and active_tab.editor
                ):
                    active_tab.editor.setText(str(text))
                    if hasattr(active_tab, "is_modified"):
                        active_tab.is_modified = True
                    main_window = self.manager.parent_widget
                    current_index = main_window.tabs.currentIndex()
                    current_text = main_window.tabs.tabText(current_index)
                    main_window.tabs.setTabText(current_index, "*" + current_text)
                    return True
                return False

            def _is_saved():
                active_tab = self.manager._get_active_editor_tab()
                if (
                    active_tab
                    and hasattr(active_tab, "is_modified")
                    and active_tab.is_modified is not None
                ):
                    return not active_tab.is_modified
                return True

            def _run_cmd_in_terminal(cmd):
                return self.manager._call_main_thread("run_cmd_in_terminal", cmd)

            lumos_api = LumosAPI(
                {
                    "config_manager": self.manager.config_manager,
                    "plugin_manager": self.manager,
                    "create_project_file": create_project_file,
                    "write_project_file": write_project_file,
                    "read_project_file": read_project_file,
                    "delete_project_file": delete_project_file,
                    "get_project_dir": _get_project_dir,
                    "show_message": show_message,
                    "show_warning": show_warning,
                    "show_error": show_error,
                    "ask_yn_question": ask_yn_question,
                    "ask_text_input": ask_text_input,
                    "get_current_file": self.manager._get_current_file,
                    "is_file": self.manager._is_file,
                    "get_editor_text": _get_editor_text,
                    "set_editor_text": _set_editor_text,
                    "run_cmd_in_terminal": _run_cmd_in_terminal,
                    "is_saved": _is_saved,
                }
            )
            plugin_globals = {
                "__builtins__": __import__("builtins").__dict__.copy(),
                "lumos": lumos_api,
            }
            try:
                exec(plugin_content, plugin_globals)
            except Exception as e:
                self.signals.failed.emit(self.filename, str(e))
                return
            self.signals.finished.emit(self.filename)
        except Exception as e:
            self.signals.failed.emit(self.filename, str(e))


class PluginManager:
    def __init__(self, parent, config_manager, plugins_dir="plugins"):
        self.parent_widget = parent
        self.config_manager = config_manager
        self.plugins_dir = plugins_dir
        self.extension_map = {}
        self.discovered_plugins = {}
        self.hooks = {}
        self.menu_actions = []
        self.plugins_loaded = False
        self._plugin_lock = threading.Lock()
        self._thread_pool = QThreadPool.globalInstance()
        self._bridge = _MainThreadBridge()
        self._bridge.request.connect(self._handle_main_thread_request)
        self._pending_tasks = 0
        self._running_tasks = []
        self._menus_ref = None
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)
        self._scan_for_plugins()
        if self.config_manager.get("plugins_enabled", True):
            self.load_enabled_plugins()

    def _is_valid_plugin_file(self, plugin_path):
        try:
            with open(plugin_path, "rb") as f:
                magic = f.read(4)
                return magic == b"PK\x03\x04"
        except:
            return False

    def _read_plugin_content(self, plugin_path, lexer=False):
        try:
            with zipfile.ZipFile(plugin_path, "r") as zf:
                manifest = self.discovered_plugins.get(
                    os.path.basename(plugin_path), {}
                )
                main_file = (
                    (manifest.get("mainFile") or "plugin.py")
                    if not lexer
                    else (manifest.get("lexerFile") or "lexer.py")
                )
                if main_file in zf.namelist():
                    return zf.read(main_file).decode("utf-8")
                else:
                    return None
        except Exception as e:
            QMessageBox.warning(
                self.parent_widget,
                "Plugin Load Error",
                f"Error reading plugin content: {e}",
            )
            return None

    def _scan_for_plugins(self):
        self.discovered_plugins.clear()
        for filename in os.listdir(self.plugins_dir):
            if filename.endswith(".lmp"):
                plugin_path = os.path.join(self.plugins_dir, filename)
                try:
                    with zipfile.ZipFile(plugin_path, "r") as zf:
                        if "manifest.json" not in zf.namelist():
                            QMessageBox.warning(
                                self.parent_widget,
                                "Plugin Load Error",
                                "manifest.json not found in the plugin archive.",
                            )
                        manifest_data = zf.read("manifest.json").decode("utf-8")
                        manifest = json.loads(manifest_data)
                        self.discovered_plugins[filename] = manifest
                except Exception as e:
                    error_message = f"Failed to scan plugin '{filename}':\n\n{e}"
                    QMessageBox.warning(
                        self.parent_widget, "Plugin Scan Error", error_message
                    )

    def _get_active_editor_tab(self):
        current_widget = self.parent_widget.tabs.currentWidget()
        if isinstance(current_widget, SplitTab):
            return current_widget.get_active_editor_tab()
        elif hasattr(current_widget, "editor"):
            return current_widget
        return None

    def _get_current_file(self):
        active_tab = self._get_active_editor_tab()
        if active_tab and hasattr(active_tab, "filepath"):
            return active_tab.filepath
        return None

    def _is_file(self):
        active_tab = self._get_active_editor_tab()
        if active_tab and hasattr(active_tab, "filepath") and active_tab.filepath:
            return True
        return False

    def _run_main_op(self, op, *args):
        if op == "message":
            QMessageBox.information(self.parent_widget, args[0], args[1])
            return None
        if op == "warning":
            QMessageBox.warning(self.parent_widget, args[0], args[1])
            return None
        if op == "error":
            QMessageBox.critical(self.parent_widget, args[0], args[1])
            return None
        if op == "ask_yn":
            reply = QMessageBox.question(
                self.parent_widget,
                args[0],
                args[1],
                QMessageBox.Yes | QMessageBox.No,
            )
            return reply == QMessageBox.Yes
        if op == "ask_text":
            text, ok = QInputDialog.getText(
                self.parent_widget,
                args[0],
                args[1],
                text=args[2] if len(args) > 2 else "",
            )
            return text if ok else None
        if op == "create_action":
            menu_name, text, callback, shortcut, checkable, add_separator = args
            if add_separator:
                menu = self._menus_ref.get(menu_name)
                if menu and isinstance(menu, QMenu):
                    menu.addSeparator()
            action = QAction(text, self.parent_widget)
            action.setData(shortcut)
            action.setCheckable(bool(checkable))
            action.triggered.connect(callback)
            self.menu_actions.append(
                {
                    "menu_name": menu_name,
                    "action": action,
                    "applied": False,
                }
            )
            return action
        if op == "run_cmd_in_terminal":
            cmd = args[0]
            terminal = getattr(self.parent_widget, "terminal", None)
            if terminal is None:
                for child in self.parent_widget.findChildren(QWidget):
                    if type(child).__name__ == "Terminal":
                        terminal = child
                        break
            if terminal:
                self.parent_widget.open_integrated_terminal(from_plugin=True)
                terminal.push(str(cmd) + "\r")
                return True
            else:
                QMessageBox.warning(
                    self.parent_widget,
                    "Terminal Not Found",
                    "No terminal widget found to run the command.",
                )
                return False
        raise RuntimeError(f"Unknown main-thread op: {op}")

    def _handle_main_thread_request(self, payload):
        try:
            payload["result"] = self._run_main_op(
                payload["op"], *payload.get("args", ())
            )
        except Exception as e:
            payload["error"] = e
        finally:
            loop = payload.get("loop")
            if loop and loop.isRunning():
                loop.quit()

    def _call_main_thread(self, op, *args):
        app = QApplication.instance()
        if app and QThread.currentThread() == app.thread():
            return self._run_main_op(op, *args)
        payload = {
            "op": op,
            "args": args,
            "result": None,
            "error": None,
            "loop": QEventLoop(),
        }
        self._bridge.request.emit(payload)
        payload["loop"].exec_()
        if payload["error"] is not None:
            raise payload["error"]
        return payload["result"]

    def load_enabled_plugins(self):
        if self.plugins_loaded:
            return
        self.extension_map.clear()
        self._pending_tasks = 0
        self._running_tasks.clear()
        self.plugins_loaded = False
        for filename, manifest in self.discovered_plugins.items():
            if not self.config_manager.is_plugin_enabled(filename):
                continue
            plugin_path = os.path.join(self.plugins_dir, filename)
            if not self._is_valid_plugin_file(plugin_path):
                continue
            plugin_info = PluginInfo(manifest, plugin_path)
            ptype = manifest.get("pluginType", None)
            if isinstance(ptype, str):
                ptypes = [ptype.lower()]
            elif isinstance(ptype, list):
                ptypes = [str(x).lower() for x in ptype]
            else:
                if manifest.get("fileExtensions"):
                    ptypes = ["language"]
                else:
                    ptypes = ["hook"]
            plugin_info.plugin_type = ptypes
            if "language" in ptypes or "both" in ptypes:
                for ext in manifest.get("fileExtensions", []):
                    self.extension_map[ext.lower()] = plugin_info
            if "hook" in ptypes or "both" in ptypes or manifest.get("mainFile"):
                task = _PluginLoadTask(self, filename, plugin_info)
                task.signals.finished.connect(self._on_plugin_task_finished)
                task.signals.failed.connect(self._on_plugin_task_failed)
                self._running_tasks.append(task)
                self._pending_tasks += 1
                self._thread_pool.start(task)
        if self._pending_tasks == 0:
            self.plugins_loaded = True

    def _on_plugin_task_finished(self, filename):
        self._pending_tasks -= 1
        if self._pending_tasks <= 0:
            self.plugins_loaded = True
            self._running_tasks.clear()
            if self._menus_ref:
                self.apply_menu_actions(self._menus_ref)

    def _on_plugin_task_failed(self, filename, error_text):
        QMessageBox.warning(
            self.parent_widget,
            "Plugin Load Error",
            f"Failed to process '{filename}':\n\n{error_text}",
        )
        self._pending_tasks -= 1
        if self._pending_tasks <= 0:
            self.plugins_loaded = True
            self._running_tasks.clear()
            if self._menus_ref:
                self.apply_menu_actions(self._menus_ref)

    def register_hook(self, event_name, func):
        with self._plugin_lock:
            self.hooks.setdefault(event_name, []).append(func)

    def trigger_hook(self, event_name, **kwargs):
        for fn in list(self.hooks.get(event_name, [])):
            try:
                fn(**kwargs)
            except Exception as e:
                QMessageBox.warning(
                    self.parent_widget,
                    "Plugin Hook Error",
                    f"Error in plugin hook '{event_name}':\n\n{e}",
                )

    def add_menu_action(
        self,
        menu_name,
        text,
        callback,
        shortcut=None,
        checkable=False,
        add_separator=False,
    ):
        return self._call_main_thread(
            "create_action",
            menu_name,
            text,
            callback,
            shortcut,
            checkable,
            add_separator,
        )

    def apply_menu_actions(self, menus):
        self._menus_ref = menus
        registered_shortcuts = set()
        core_menu_names = set(menus.keys())
        for menu in menus.values():
            if isinstance(menu, QMenu):
                for core_action in menu.actions():
                    shortcut_str = core_action.shortcut().toString(
                        QKeySequence.NativeText
                    )
                    if shortcut_str:
                        registered_shortcuts.add(shortcut_str.lower())
        for item in self.menu_actions:
            if item.get("applied"):
                continue
            menu_name = item["menu_name"]
            action = item["action"]
            if menu_name not in core_menu_names:
                QMessageBox.warning(
                    self.parent_widget,
                    "Plugin Menu Warning",
                    f"The plugin action '{action.text()}' attempted to add itself to the non-existent menu '{menu_name}'.\n\n"
                    "To ensure stability, plugins can only add items to existing core menus (e.g., 'File', 'Edit'). "
                    "This action has been blocked.",
                )
                continue
            menu = menus.get(menu_name)
            if not (menu and isinstance(menu, QMenu)):
                continue
            requested_shortcut = action.data()
            if requested_shortcut:
                try:
                    shortcut_str = (
                        QKeySequence(requested_shortcut)
                        .toString(QKeySequence.NativeText)
                        .lower()
                    )
                    if shortcut_str in registered_shortcuts:
                        QMessageBox.warning(
                            self.parent_widget,
                            "Plugin Shortcut Conflict",
                            f"The plugin action '{action.text()}' requested the shortcut '{requested_shortcut}', but this shortcut is already in use.\n\n"
                            "The menu item has been added without a shortcut to prevent conflicts.",
                        )
                    else:
                        action.setShortcut(QKeySequence(requested_shortcut))
                        registered_shortcuts.add(shortcut_str)
                except Exception:
                    QMessageBox.warning(
                        self.parent_widget,
                        "Invalid Plugin Shortcut",
                        f"The plugin action '{action.text()}' provided an invalid shortcut format: '{requested_shortcut}'.\n\n"
                        "This shortcut has been ignored.",
                    )
            if action not in menu.actions():
                menu.addAction(action)
            item["applied"] = True

    def unload_plugins(self):
        self.extension_map.clear()
        self.hooks.clear()
        if self._menus_ref:
            for item in self.menu_actions:
                action = item.get("action")
                if not action:
                    continue
                for menu in self._menus_ref.values():
                    if isinstance(menu, QMenu):
                        menu.removeAction(action)
        for item in self.menu_actions:
            try:
                item["action"].deleteLater()
            except:
                pass
        self.menu_actions.clear()
        self.plugins_loaded = False

    def reload_plugins(self):
        self.unload_plugins()
        self._scan_for_plugins()
        if self.config_manager.get("plugins_enabled", True):
            self.load_enabled_plugins()

    def _load_lexer_from_plugin(self, plugin_info):
        if plugin_info.lexer_class:
            return plugin_info.lexer_class
        try:
            plugin_content = self._read_plugin_content(plugin_info.zip_path, lexer=True)
            if not plugin_content:
                return None
            lexer_globals = {
                "__builtins__": __import__("builtins").__dict__.copy(),
            }
            lexer_globals["lumos"] = LumosAPI(
                {
                    "PygmentsBaseLexer": PygmentsBaseLexer,
                    "BaseLexer": BaseLexer,
                    "config_manager": self.config_manager,
                    "plugin_manager": self,
                }
            )
            exec(plugin_content, lexer_globals)
            plugin_info.lexer_class = lexer_globals.get(
                plugin_info.manifest["lexerClass"]
            )
            return plugin_info.lexer_class
        except Exception as e:
            QMessageBox.warning(
                self.parent_widget,
                "Plugin Load Error",
                f"Could not load lexer for {plugin_info.manifest['name']}:\n\n{e}",
            )
            return None

    def _load_icon_from_plugin(self, plugin_info):
        if plugin_info.icon:
            return plugin_info.icon
        try:
            with zipfile.ZipFile(plugin_info.zip_path, "r") as zf:
                manifest = plugin_info.manifest
                icon_data = zf.read(manifest["iconFile"])
                pixmap = QPixmap()
                pixmap.loadFromData(icon_data)
                plugin_info.icon = QIcon(pixmap)
                return plugin_info.icon
        except Exception as e:
            QMessageBox.warning(
                self.parent_widget,
                "Plugin Load Error",
                f"Could not load icon for {plugin_info.manifest['name']}:\n\n{e}",
            )
            return None

    def get_lexer_for_file(self, filepath):
        if not self.plugins_loaded:
            return None
        file_ext = os.path.splitext(filepath)[1].lower()
        plugin_info = self.extension_map.get(file_ext)
        if not plugin_info:
            return None
        return self._load_lexer_from_plugin(plugin_info)

    def get_icon_for_file(self, filepath):
        if not self.plugins_loaded:
            return None
        file_ext = os.path.splitext(filepath)[1].lower()
        plugin_info = self.extension_map.get(file_ext)
        if not plugin_info:
            return None
        return self._load_icon_from_plugin(plugin_info)


class PluginDialog(QDialog):
    def __init__(self, plugin_manager, config_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.config_manager = config_manager
        self.setWindowTitle("Manage Plugins")
        self.setMinimumWidth(400)
        self.layout = QVBoxLayout(self)
        self.info_label = QLabel(
            "Check the plugins you want to enable. Changes will apply after restarting."
        )
        self.layout.addWidget(self.info_label)
        self.plugin_list_widget = QListWidget()
        self.layout.addWidget(self.plugin_list_widget)
        self.populate_plugin_list()
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def populate_plugin_list(self):
        for filename, manifest in self.plugin_manager.discovered_plugins.items():
            item = QListWidgetItem(self.plugin_list_widget)
            item.setText(f"{manifest['name']} ({filename})")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            is_enabled = self.config_manager.is_plugin_enabled(filename)
            item.setCheckState(Qt.Checked if is_enabled else Qt.Unchecked)
            item.setData(Qt.UserRole, filename)

    def accept(self):
        for i in range(self.plugin_list_widget.count()):
            item = self.plugin_list_widget.item(i)
            filename = item.data(Qt.UserRole)
            is_enabled = item.checkState() == Qt.Checked
            self.config_manager.set_plugin_enabled(filename, is_enabled)
        super().accept()
