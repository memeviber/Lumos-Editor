import json
import os
import shlex
import subprocess
import webbrowser
from pathlib import Path
from shutil import which

BASE_DIR = Path.cwd()
CONFIG_FILE = BASE_DIR / "runner_commands.json"


def shell_quote(value):
    text = str(value)
    if os.name == "nt":
        return subprocess.list2cmdline([text])
    return shlex.quote(text)


def detect_python_interpreter():
    if os.name == "nt":
        for name in ("python", "python3", "py -3"):
            if name == "py -3":
                return name
            path = which(name)
            if path:
                return shell_quote(path)
        return "python"
    for name in ("python3", "python"):
        path = which(name)
        if path:
            return shell_quote(path)
    return "python3"


def load_commands_config():
    if not CONFIG_FILE.exists():
        lumos.show_error(  # type: ignore
            "Config Error",
            "runner_commands.json was not found in the application root.",
        )
        return {}
    try:
        with CONFIG_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        lumos.show_error("Config Error", f"Failed to read runner_commands.json:\n{e}")  # type: ignore
        return {}
    if not isinstance(data, dict):
        lumos.show_error(  # type: ignore
            "Config Error", "runner_commands.json must contain a JSON object."
        )
        return {}
    return data


def build_template_values(file_path, args=""):
    p = Path(file_path).resolve()
    py = detect_python_interpreter()
    return {
        "{filepath}": str(p),
        "{filename}": p.name,
        "{dirname}": str(p.parent),
        "{stem}": p.stem,
        "{ext}": p.suffix.lower(),
        "{args}": args.strip(),
        "{python}": py,
        "{filepath_q}": shell_quote(p),
        "{filename_q}": shell_quote(p.name),
        "{dirname_q}": shell_quote(p.parent),
        "{stem_q}": shell_quote(p.stem),
        "{args_q}": shell_quote(args.strip()) if args.strip() else "",
    }


def render_command(template, file_path, args=""):
    cmd = str(template)
    values = build_template_values(file_path, args)
    for key, value in values.items():
        cmd = cmd.replace(key, value)
    return " ".join(cmd.split())


def run_current_file(args=""):
    filepath = lumos.get_current_file()  # type: ignore
    if isinstance(
        args, bool
    ):  # PyQt5 QAction.triggered passes a boolean, we ignore it and treat it as no args
        args = ""
    if not filepath:
        lumos.show_warning("Run File", "No file is currently open to run!")  # type: ignore
        return
    if not lumos.is_saved():  # type: ignore
        lumos.show_warning(  # type: ignore
            "Run File",
            "This file has unsaved changes. Please save it first before running!",
        )
        return
    file_path = Path(filepath)
    ext = file_path.suffix.lower()
    if ext in {".html", ".htm"}:
        webbrowser.open(file_path.resolve().as_uri())
        return
    if ext == ".json":
        lumos.show_message(  # type: ignore
            "Run File", "JSON files are for data storage only and cannot be run."
        )
        return
    commands = load_commands_config()
    if not commands:
        return
    raw_cmd = commands.get(ext)
    if not raw_cmd:
        lumos.show_warning(  # type: ignore
            "Run File",
            f"Auto-run is not configured for: {ext}\n"
            f"Add it manually to runner_commands.json.",
        )
        return
    cmd = render_command(raw_cmd, filepath, args)
    if os.name == "nt" and (cmd.strip().startswith("'") or cmd.strip().startswith('"')):
        cmd = "& " + cmd
    success = lumos.run_cmd_in_terminal(cmd)  # type: ignore
    if not success:
        lumos.show_warning(  # type: ignore
            "Terminal Error", "Terminal not found. Please open the terminal first!"
        )


lumos.plugin_manager.add_menu_action(  # type: ignore
    menu_name="Tools",
    text="Run Current File",
    callback=run_current_file,
    shortcut="Alt+R",
    add_separator=True,
)

lumos.plugin_manager.add_menu_action(  # type: ignore
    menu_name="Tools",
    text="Run Current File with Args...",
    callback=lambda: run_current_file(
        lumos.ask_text_input(  # type: ignore
            "Run Current File with Args",
            "Enter command-line arguments to pass to the file:",
        )
    ),
    shortcut="Ctrl+Alt+R",
)
