import os

from PyQt5.QtCore import QThread, pyqtSignal


class SearchWorker(QThread):
    file_matches_found = pyqtSignal(str, list)
    finished = pyqtSignal()

    def __init__(self, directory, term, match_case):
        super().__init__()
        self.directory = directory
        self.term = term
        self.match_case = match_case
        self.is_running = True

    def run(self):
        term_cmp = self.term if self.match_case else self.term.lower()
        ignore_dirs = {
            ".git",
            "__pycache__",
            "node_modules",
            "venv",
            ".venv",
            "dist",
            "build",
        }
        ignore_exts = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".png",
            ".exe",
            ".dll",
            ".so",
            ".pyc",
            ".mp4",
            ".mp3",
            ".wav",
            ".zip",
            ".tar",
            ".gz",
        }
        for root, dirs, files in os.walk(self.directory):
            if not self.is_running:
                break
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                if not self.is_running:
                    break
                ext = os.path.splitext(file)[1].lower()
                if ext in ignore_exts:
                    continue
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    file_matches = []
                    for line_idx, line in enumerate(lines):
                        line_cmp = line if self.match_case else line.lower()
                        if term_cmp in line_cmp:
                            file_matches.append((line_idx, line.strip()))
                    if file_matches:
                        self.file_matches_found.emit(filepath, file_matches)
                except Exception:
                    pass
        self.finished.emit()

    def stop(self):
        self.is_running = False
