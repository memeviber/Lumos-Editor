from .theme_manager import theme
import os
import shutil
import time

from git import Repo
from git.exc import InvalidGitRepositoryError
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class GitPoller(QThread):
    updateRequested = pyqtSignal()

    def __init__(self, interval_seconds=3, parent=None):
        super().__init__(parent)
        self.interval = float(interval_seconds)
        self._running = True

    def run(self):
        while self._running:
            self.updateRequested.emit()
            n = int(self.interval * 10)
            for _ in range(n):
                if not self._running:
                    break
                time.sleep(0.1)

    def stop(self):
        self._running = False
        self.wait()


class SourceControlTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.tabname = "Source Control"
        self.is_modified = None
        self.repo = None
        self.poller = None
        self._git_busy = False
        self.setup_ui()
        self.initialize_git()

    def setup_ui(self):
        self.setObjectName("SourceControlTab")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)
        branch_layout = QHBoxLayout()
        self.branch_btn = QPushButton("Initializing...")
        font = self.branch_btn.font()
        font.setPointSize(11)
        font.setBold(True)
        self.branch_btn.setFont(font)
        self.branch_btn.setObjectName("branchButton")
        self.branch_btn.setCursor(Qt.PointingHandCursor)
        self.branch_btn.clicked.connect(self.manage_branches)
        branch_layout.addWidget(self.branch_btn)
        header_layout.addLayout(branch_layout)
        header_layout.addStretch()
        self.refresh_button = QPushButton()
        self.refresh_button.setFixedSize(28, 28)
        self.refresh_button.setIcon(QIcon("resources:/refresh-icon.png"))
        self.refresh_button.setObjectName("iconButton")
        self.refresh_button.clicked.connect(self.update_git_status)
        header_layout.addWidget(self.refresh_button)
        main_layout.addWidget(header_frame)
        self.status_frame = QFrame()
        self.status_frame.setObjectName("statusFrame")
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(12, 6, 12, 6)
        self.staged_label = QLabel("\u2022 Staged: 0")
        self.modified_label = QLabel("\u2022 Modified: 0")
        self.untracked_label = QLabel("\u2022 Untracked: 0")
        for label in [self.staged_label, self.modified_label, self.untracked_label]:
            label.setFont(QFont("Segoe UI", 9))
            status_layout.addWidget(label)
        status_layout.addStretch()
        main_layout.addWidget(self.status_frame)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        self.commit_button = QPushButton("Commit")
        self.commit_button.clicked.connect(self.commit_changes)
        self.commit_button.setFixedHeight(32)
        self.commit_button.setObjectName("primaryButton")
        actions_layout.addWidget(self.commit_button)
        self.push_button = QPushButton("Push")
        self.push_button.clicked.connect(self.push_changes)
        self.push_button.setFixedHeight(32)
        actions_layout.addWidget(self.push_button)
        self.pull_button = QPushButton("Pull")
        self.pull_button.clicked.connect(self.pull_changes)
        self.pull_button.setFixedHeight(32)
        actions_layout.addWidget(self.pull_button)
        main_layout.addLayout(actions_layout)
        tree_header = QLabel("Changes")
        tree_header.setFont(QFont("Segoe UI", 10, QFont.Bold))
        main_layout.addWidget(tree_header)
        self.changes_tree = QTreeWidget()
        self.changes_tree.setAnimated(False)
        self.changes_tree.setHeaderLabels(["File", "Status"])
        self.changes_tree.setAlternatingRowColors(True)
        self.changes_tree.setIndentation(12)
        self.changes_tree.setObjectName("changesTree")
        self.changes_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.changes_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.changes_tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        main_layout.addWidget(self.changes_tree)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)
        self.start_poller(3)
        self.destroyed.connect(self._on_destroyed)
        self.setStyleSheet(f"""
            * {{
                color: {theme.color26};
            }}
            QWidget#SourceControlTab {{ 
                background-color: {theme.color1}; 
                color: {theme.color26};
                font-family: "Segoe UI", Arial, sans-serif;
            }}
            QFrame#headerFrame {{
                background-color: {theme.color2};
                border: 1px solid {theme.color13};
                border-radius: 6px;
            }}
            QFrame#statusFrame {{
                background-color: {theme.color7};
                border: 1px solid {theme.color13};
                border-radius: 4px;
            }}
            QPushButton {{
                background-color: {theme.color10};
                color: {theme.color26} !important;
                border: 1px solid {theme.color13};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {theme.color15};
                border-color: {theme.color18};
                color: {theme.color31} !important;
            }}
            QPushButton:pressed {{
                background-color: {theme.color18};
                color: {theme.color31} !important;
            }}
            QPushButton:disabled {{
                background-color: {theme.color3};
                color: {theme.color22} !important;
                border-color: {theme.color3};
            }}
            QPushButton#primaryButton {{
                background-color: {theme.color35};
                border-color: {theme.color38};
                color: {theme.color31} !important;
            }}
            QPushButton#primaryButton:hover {{
                background-color: {theme.color38};
                color: {theme.color31} !important;
            }}
            QPushButton#branchButton {{
                background-color: transparent;
                border: none;
                color: {theme.color31} !important;
                text-align: left;
                padding: 0;
            }}
            QPushButton#branchButton:hover {{
                color: {theme.color38} !important;
            }}
            QPushButton#iconButton {{
                background-color: transparent;
                border: none;
                padding: 4px;
                color: {theme.color26} !important;
            }}
            QPushButton#iconButton:hover {{
                background-color: {theme.color8};
                color: {theme.color31} !important;
            }}
            QTreeWidget#changesTree {{
                background-color: {theme.color2};
                color: {theme.color26};
                border: 1px solid {theme.color13};
                border-radius: 4px;
                outline: none;
                font-size: 11px;
                alternate-background-color: {theme.color3};
            }}
            QTreeWidget#changesTree::item {{
                padding: 4px;
                border: none;
                color: {theme.color26};
                background-color: transparent;
            }}
            QTreeWidget#changesTree::item:selected {{
                background-color: {theme.color11};
                color: {theme.color31};
            }}
            QTreeWidget#changesTree::item:hover {{
                background-color: {theme.color11};
                color: {theme.color31};
            }}
            QTreeWidget#changesTree QHeaderView::section {{
                background-color: {theme.color7};
                color: {theme.color26};
                border: none;
                padding: 6px;
                font-weight: bold;
                font-size: 11px;
            }}
            QTreeWidget#changesTree QHeaderView::section:hover {{
                background-color: {theme.color13};
                color: {theme.color31};
            }}
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {{
                image: url(resources:/chevron-right.png);
            }}
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings {{
                image: url(resources:/chevron-down.png);
            }}
            QProgressBar {{
                background-color: {theme.color7};
                border: 1px solid {theme.color13};
                border-radius: 4px;
                color: {theme.color26};
            }}
            QProgressBar::chunk {{
                background-color: {theme.color35};
                border-radius: 3px;
            }}
            QLabel {{
                color: {theme.color26};
                background: transparent;
            }}
            QMenu {{
                background-color: {theme.color2};
                color: {theme.color27};
                border: 1px solid {theme.color13};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 20px;
                border-radius: 2px;
            }}
            QMenu::item:selected {{
                background-color: {theme.color35};
                color: white;
            }}
            QMenu::separator {{
                height: 1px;
                background: {theme.color13};
                margin: 4px 0px;
            }}
            """)

    def start_poller(self, interval_seconds=3):
        if self.poller and self.poller.isRunning():
            return
        self.poller = GitPoller(interval_seconds)
        self.poller.updateRequested.connect(self.update_git_status)
        self.poller.start()

    def stop_poller(self):
        if self.poller:
            self.poller.stop()
            self.poller = None

    def _on_destroyed(self):
        self.stop_poller()

    @pyqtSlot(str)
    def on_project_changed(self, new_dir_path):
        self.initialize_git()

    def initialize_git(self):
        project_path = self.main_window.current_project_dir
        if not project_path:
            self.repo = None
            self.branch_btn.setText("No folder open")
            self.changes_tree.clear()
            self.update_git_status()
            return
        try:
            self.repo = Repo(project_path)
            self.update_git_status()
        except InvalidGitRepositoryError:
            self.repo = None
            self.branch_btn.setText("Not a git repository")
            self.changes_tree.clear()
            self.update_git_status()
        except Exception:
            self.repo = None
            self.branch_btn.setText("Error initializing repo")
            self.changes_tree.clear()
            self.update_git_status()

    def update_git_status(self):
        if self._git_busy:
            return
        if not self.repo:
            self.branch_btn.setText("Not a git repository")
            if not self.main_window.current_project_dir:
                self.branch_btn.setText("No folder open")
            self.staged_label.setText("\u2022 Staged: 0")
            self.modified_label.setText("\u2022 Modified: 0")
            self.untracked_label.setText("\u2022 Untracked: 0")
            self.changes_tree.clear()
            item = QTreeWidgetItem(["Open a git repository to see changes."])
            item.setData(0, Qt.UserRole, {"type": "info"})
            self.changes_tree.addTopLevelItem(item)
            self.commit_button.setEnabled(False)
            self.push_button.setEnabled(False)
            self.pull_button.setEnabled(False)
            self.branch_btn.setEnabled(False)
            return
        try:
            self.branch_btn.setEnabled(True)
            branch = self.repo.active_branch.name
            self.branch_btn.setText(f"Branch: {branch}")
            self.changes_tree.clear()
            staged_changes = self.repo.index.diff("HEAD")
            modified_changes = self.repo.index.diff(None)
            untracked_files = self.repo.untracked_files
            staged_count = len(list(staged_changes))
            modified_count = len(list(modified_changes))
            untracked_count = len(untracked_files)
            staged_item = QTreeWidgetItem(["Staged Changes", ""])
            staged_item.setData(0, Qt.UserRole, {"type": "header", "state": "staged"})
            for item in self.repo.index.diff("HEAD"):
                child = QTreeWidgetItem(staged_item, [item.a_path, "Staged"])
                child.setData(
                    0,
                    Qt.UserRole,
                    {"type": "file", "state": "staged", "path": item.a_path},
                )
            if staged_item.childCount() > 0:
                self.changes_tree.addTopLevelItem(staged_item)
                staged_item.setExpanded(True)
            modified_item = QTreeWidgetItem(["Modified Files", ""])
            modified_item.setData(
                0, Qt.UserRole, {"type": "header", "state": "modified"}
            )
            for item in self.repo.index.diff(None):
                child = QTreeWidgetItem(modified_item, [item.a_path, "Modified"])
                child.setData(
                    0,
                    Qt.UserRole,
                    {"type": "file", "state": "modified", "path": item.a_path},
                )
            if modified_item.childCount() > 0:
                self.changes_tree.addTopLevelItem(modified_item)
                modified_item.setExpanded(True)
            untracked_item = QTreeWidgetItem(["Untracked Files", ""])
            untracked_item.setData(
                0, Qt.UserRole, {"type": "header", "state": "untracked"}
            )
            for file_path in self.repo.untracked_files:
                child = QTreeWidgetItem(untracked_item, [file_path, "Untracked"])
                child.setData(
                    0,
                    Qt.UserRole,
                    {"type": "file", "state": "untracked", "path": file_path},
                )
            if untracked_item.childCount() > 0:
                self.changes_tree.addTopLevelItem(untracked_item)
                untracked_item.setExpanded(True)
            self.staged_label.setText(f"\u2022 Staged: {staged_count}")
            self.modified_label.setText(f"\u2022 Modified: {modified_count}")
            self.untracked_label.setText(f"\u2022 Untracked: {untracked_count}")
            if self.changes_tree.topLevelItemCount() == 0:
                no_changes_item = QTreeWidgetItem(["No changes", "Working tree clean"])
                no_changes_item.setData(0, Qt.UserRole, {"type": "info"})
                self.changes_tree.addTopLevelItem(no_changes_item)
            has_changes = staged_count > 0 or modified_count > 0 or untracked_count > 0
            self.commit_button.setEnabled(has_changes)
            if has_changes:
                self.push_button.setEnabled(False)
                self.pull_button.setEnabled(False)
            else:
                self.pull_button.setEnabled(True)
                can_push = False
                try:
                    if self.repo.remotes and self.repo.active_branch.tracking_branch():
                        tracking_branch_name = (
                            self.repo.active_branch.tracking_branch().name
                        )
                        commits_ahead = list(
                            self.repo.iter_commits(f"{tracking_branch_name}..HEAD")
                        )
                        if commits_ahead:
                            can_push = True
                except Exception:
                    pass
                self.push_button.setEnabled(can_push)
        except Exception as e:
            self.branch_btn.setText(f"Error: {str(e)}")
            self.commit_button.setEnabled(False)
            self.push_button.setEnabled(False)
            self.pull_button.setEnabled(False)

    def show_context_menu(self, pos):
        item = self.changes_tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.UserRole)
        if not data or data.get("type") == "info":
            return
        menu = QMenu(self)
        if data["type"] == "file":
            state = data["state"]
            file_path = data["path"]
            if state in ["modified", "untracked"]:
                menu.addAction("Stage Changes", lambda: self.stage_file(file_path))
                menu.addAction(
                    "Discard Changes", lambda: self.discard_file(file_path, state)
                )
            elif state == "staged":
                menu.addAction("Unstage Changes", lambda: self.unstage_file(file_path))
            menu.addSeparator()
            menu.addAction("Open File", lambda: self.open_file(file_path))
        elif data["type"] == "header":
            state = data["state"]
            if state in ["modified", "untracked"]:
                menu.addAction("Stage All", self.stage_all)
                menu.addAction(
                    "Discard All", lambda: self.discard_all_in_category(state)
                )
            elif state == "staged":
                menu.addAction("Unstage All", self.unstage_all)
        menu.exec_(self.changes_tree.viewport().mapToGlobal(pos))

    def on_item_double_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data and data.get("type") == "file":
            self.open_file(data["path"])

    def open_file(self, file_path):
        abs_path = os.path.join(self.main_window.current_project_dir, file_path)
        self.main_window.open_specific_file(abs_path)

    def stage_file(self, file_path):
        self._git_busy = True
        try:
            self.repo.git.add(file_path)
        finally:
            self._git_busy = False
            self.update_git_status()

    def unstage_file(self, file_path):
        self._git_busy = True
        try:
            self.repo.git.reset("HEAD", file_path)
        finally:
            self._git_busy = False
            self.update_git_status()

    def discard_file(self, file_path, state):
        reply = QMessageBox.question(
            self.main_window,
            "Discard Changes",
            f"Are you sure you want to discard changes in '{file_path}'?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._git_busy = True
            try:
                if state == "untracked":
                    abs_path = os.path.join(
                        self.main_window.current_project_dir, file_path
                    )
                    if os.path.isfile(abs_path):
                        os.remove(abs_path)
                    elif os.path.isdir(abs_path):
                        shutil.rmtree(abs_path)
                else:
                    self.repo.git.checkout("--", file_path)
            except Exception as e:
                QMessageBox.warning(self.main_window, "Error", str(e))
            finally:
                self._git_busy = False
                self.update_git_status()

    def stage_all(self):
        self._git_busy = True
        try:
            self.repo.git.add(A=True)
        finally:
            self._git_busy = False
            self.update_git_status()

    def unstage_all(self):
        self._git_busy = True
        try:
            self.repo.git.reset("HEAD")
        finally:
            self._git_busy = False
            self.update_git_status()

    def discard_all_in_category(self, category):
        reply = QMessageBox.question(
            self.main_window,
            "Discard All",
            f"Are you sure you want to discard ALL {category} changes? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._git_busy = True
            try:
                if category == "untracked":
                    self.repo.git.clean("-fd")
                else:
                    self.repo.git.checkout("--", ".")
            finally:
                self._git_busy = False
                self.update_git_status()

    def manage_branches(self):
        if not self.repo:
            return
        branches = [b.name for b in self.repo.branches]
        options = ["+ Create New Branch..."] + branches
        current = self.repo.active_branch.name
        branch, ok = QInputDialog.getItem(
            self.main_window,
            "Branch Management",
            "Select a branch to checkout:",
            options,
            options.index(current) if current in options else 0,
            False,
        )
        if ok and branch:
            if branch == "+ Create New Branch...":
                new_branch, ok2 = QInputDialog.getText(
                    self.main_window, "New Branch", "Enter new branch name:"
                )
                if ok2 and new_branch.strip():
                    self._git_busy = True
                    try:
                        self.repo.git.checkout("-b", new_branch.strip())
                    except Exception as e:
                        QMessageBox.warning(self.main_window, "Error", str(e))
                    finally:
                        self._git_busy = False
                        self.update_git_status()
            elif branch != current:
                self._git_busy = True
                try:
                    self.repo.git.checkout(branch)
                except Exception as e:
                    QMessageBox.warning(self.main_window, "Error", str(e))
                finally:
                    self._git_busy = False
                    self.update_git_status()

    def show_progress(self, show=True):
        self.progress_bar.setVisible(show)
        if show:
            self.progress_bar.setRange(0, 0)

    def commit_changes(self):
        if not self.repo:
            return
        staged_count = len(list(self.repo.index.diff("HEAD")))
        if staged_count == 0:
            reply = QMessageBox.question(
                self.main_window,
                "No Staged Changes",
                "There are no staged changes to commit.\n\nWould you like to stage all your changes and commit them directly?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.stage_all()
            else:
                return
        message, ok = QInputDialog.getMultiLineText(
            self.main_window, "Commit Changes", "Enter commit message:", ""
        )
        if ok and message.strip():
            self._git_busy = True
            self.show_progress(True)
            try:
                self.repo.index.commit(message.strip())
                self.branch_btn.setText(f"Branch: {self.repo.active_branch.name}")
            except Exception as e:
                QMessageBox.warning(self.main_window, "Commit Failed", str(e))
            finally:
                self.show_progress(False)
                self._git_busy = False
                self.update_git_status()

    def push_changes(self):
        if not self.repo:
            return
        self._git_busy = True
        self.show_progress(True)
        try:
            remote = self.repo.remote()
            branch = self.repo.active_branch
            remote.push(branch)
            self.branch_btn.setText("Changes pushed")
        except Exception as e:
            QMessageBox.warning(self.main_window, "Push Failed", str(e))
        finally:
            self.show_progress(False)
            self._git_busy = False
            QTimer.singleShot(1500, self.update_git_status)

    def pull_changes(self):
        if not self.repo:
            return
        self._git_busy = True
        self.show_progress(True)
        try:
            remote = self.repo.remote()
            remote.pull()
            self.branch_btn.setText("Changes pulled")
        except Exception as e:
            QMessageBox.warning(self.main_window, "Pull Failed", str(e))
        finally:
            self.show_progress(False)
            self._git_busy = False
            self.update_git_status()

    def refresh(self):
        self.update_git_status()
