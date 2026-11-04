import logging
import os
import shutil
import time

from git import Repo
from git.exc import InvalidGitRepositoryError
from git.remote import PushInfo
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QFont, QIcon, QPalette
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .message_box import QMessageBox
from .theme_manager import theme
from .themed_dialog import ThemedInputDialog as QInputDialog

logger = logging.getLogger(__name__)


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
        self._connected_ai_widget = None
        self._group_expanded = {"staged": True, "changes": True}
        self._post_commit_action = None
        self.setup_ui()
        self.initialize_git()

    def setup_ui(self):
        self.setObjectName("SourceControlTab")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(6, 3, 4, 3)
        self.branch_btn = QPushButton("Initializing...")
        self.branch_btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.branch_btn.setAccessibleName("Current Git branch")
        font = self.branch_btn.font()
        font.setPointSize(9)
        font.setBold(True)
        self.branch_btn.setFont(font)
        self.branch_btn.setObjectName("branchButton")
        self.branch_btn.setCursor(Qt.PointingHandCursor)
        self.branch_btn.clicked.connect(self.manage_branches)
        header_layout.addWidget(self.branch_btn, 1)
        self.refresh_button = QPushButton()
        self.refresh_button.setFixedSize(28, 28)
        self.refresh_button.setIcon(QIcon("resources:/refresh-icon.png"))
        self.refresh_button.setObjectName("iconButton")
        self.refresh_button.setAccessibleName("Refresh source control")
        self.refresh_button.setToolTip("Refresh source control")
        self.refresh_button.clicked.connect(self.update_git_status)
        header_layout.addWidget(self.refresh_button)
        main_layout.addWidget(header_frame)
        self.commit_message_input = QTextEdit()
        self.commit_message_input.setObjectName("commitMessageInput")
        self.commit_message_input.setAccessibleName("Commit message")
        self.commit_message_input.setPlaceholderText("Message (required)")
        self.commit_message_input.setMinimumHeight(54)
        self.commit_message_input.setMaximumHeight(72)
        main_layout.addWidget(self.commit_message_input)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(4)
        self.commit_actions_widget = QWidget()
        commit_actions_layout = QHBoxLayout(self.commit_actions_widget)
        commit_actions_layout.setContentsMargins(0, 0, 0, 0)
        commit_actions_layout.setSpacing(4)
        self.commit_button = QPushButton("Commit")
        self.commit_button.clicked.connect(self.commit_changes)
        self.commit_button.setFixedHeight(29)
        self.commit_button.setObjectName("primaryButton")
        self.ai_commit_button = QPushButton("AI Commit")
        self.ai_commit_button.clicked.connect(self.generate_ai_commit_message)
        self.ai_commit_button.setFixedHeight(29)
        self.ai_commit_button.setToolTip(
            "Generate a commit message from the staged changes"
        )
        commit_actions_layout.addWidget(self.commit_button, 3)
        commit_actions_layout.addWidget(self.ai_commit_button, 2)
        actions_layout.addWidget(self.commit_actions_widget, 1)
        self.sync_button = QPushButton()
        self.sync_button.setFixedHeight(29)
        self.sync_button.setObjectName("primaryButton")
        self.sync_button.clicked.connect(self.run_next_sync_action)
        self.sync_button.hide()
        actions_layout.addWidget(self.sync_button, 1)
        main_layout.addLayout(actions_layout)
        self.changes_tree = QTreeWidget()
        self.changes_tree.setAnimated(False)
        self.changes_tree.setColumnCount(1)
        self.changes_tree.setHeaderHidden(True)
        self.changes_tree.setAlternatingRowColors(False)
        self.changes_tree.setIndentation(14)
        self.changes_tree.setObjectName("changesTree")
        tree_palette = self.changes_tree.palette()
        tree_palette.setColor(QPalette.Highlight, QColor(theme.color9))
        tree_palette.setColor(QPalette.HighlightedText, QColor(theme.color27))
        self.changes_tree.setPalette(tree_palette)
        self.changes_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.changes_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.changes_tree.itemClicked.connect(self.on_item_clicked)
        main_layout.addWidget(self.changes_tree, 1)
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
            QTextEdit#commitMessageInput {{
                background-color: {theme.color2};
                color: {theme.color27};
                border: 1px solid {theme.color13};
                border-radius: 4px;
                padding: 6px;
                selection-background-color: {theme.color35};
            }}
            QTextEdit#commitMessageInput:focus {{
                border-color: {theme.color35};
            }}
            QPushButton {{
                background-color: {theme.color10};
                color: {theme.color26} !important;
                border: 1px solid {theme.color13};
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 10px;
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
                border: none;
                outline: none;
                font-size: 11px;
                selection-background-color: {theme.color9};
                selection-color: {theme.color27};
            }}
            QTreeWidget#changesTree::item {{
                padding: 3px 4px;
                border: none;
                color: {theme.color26};
                background-color: transparent;
            }}
            QTreeWidget#changesTree::item:selected {{
                background-color: {theme.color9};
                color: {theme.color27};
            }}
            QTreeWidget#changesTree::item:hover {{
                background-color: {theme.color9};
                color: {theme.color27};
            }}
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {{
                image: url(resources:/chevron-right.png);
                width: 10px;
                height: 10px;
            }}
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings {{
                image: url(resources:/chevron-down.png);
                width: 10px;
                height: 10px;
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
        self._post_commit_action = None
        project_path = self.main_window.current_project_dir
        if not project_path:
            logger.info("Source control disabled: no project folder open")
            self.repo = None
            self.branch_btn.setText("No folder open")
            self.changes_tree.clear()
            self.update_git_status()
            return
        try:
            self.repo = Repo(project_path)
            logger.info("Git repository initialized")
            self.update_git_status()
        except InvalidGitRepositoryError:
            logger.info("Project folder is not a Git repository")
            self.repo = None
            self.branch_btn.setText("Not a git repository")
            self.changes_tree.clear()
            self.update_git_status()
        except Exception:
            logger.exception("Could not initialize Git repository")
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
            self.branch_btn.setToolTip(self.branch_btn.text())
            self.changes_tree.clear()
            item = QTreeWidgetItem(["Open a git repository to see changes."])
            item.setData(0, Qt.UserRole, {"type": "info"})
            self.changes_tree.addTopLevelItem(item)
            self.commit_button.setEnabled(False)
            self.ai_commit_button.setEnabled(False)
            self._update_action_controls(False)
            self.branch_btn.setEnabled(False)
            return
        try:
            self.branch_btn.setEnabled(True)
            self.ai_commit_button.setEnabled(True)
            is_detached = self.repo.head.is_detached
            if is_detached:
                commit_id = self.repo.head.commit.hexsha[:7]
                self.branch_btn.setText(f"Detached HEAD ({commit_id})")
                self.branch_btn.setToolTip(
                    f"Detached HEAD at commit {self.repo.head.commit.hexsha}"
                )
                self._post_commit_action = None
            else:
                branch = self.repo.active_branch.name
                self.branch_btn.setText(branch)
                self.branch_btn.setToolTip(f"Current branch: {branch}")
            expanded_states = dict(self._group_expanded)
            for index in range(self.changes_tree.topLevelItemCount()):
                item = self.changes_tree.topLevelItem(index)
                item_data = item.data(0, Qt.UserRole)
                if item_data and item_data.get("type") == "header":
                    expanded_states[item_data["state"]] = item.isExpanded()
            self.changes_tree.clear()
            staged_changes = list(self.repo.index.diff("HEAD"))
            modified_changes = list(self.repo.index.diff(None))
            untracked_files = list(self.repo.untracked_files)
            staged_count = len(staged_changes)
            modified_count = len(modified_changes)
            untracked_count = len(untracked_files)
            staged_item = QTreeWidgetItem([f"Staged Changes ({staged_count})"])
            staged_item.setData(0, Qt.UserRole, {"type": "header", "state": "staged"})
            staged_item.setFont(0, QFont("Segoe UI", 9, QFont.Bold))
            for change in staged_changes:
                child = QTreeWidgetItem(staged_item, [change.a_path])
                child.setData(
                    0,
                    Qt.UserRole,
                    {"type": "file", "state": "staged", "path": change.a_path},
                )
                child.setToolTip(0, f"Staged: {change.a_path}")
            self.changes_tree.addTopLevelItem(staged_item)
            staged_item.setExpanded(expanded_states["staged"])
            changes_count = modified_count + untracked_count
            changes_item = QTreeWidgetItem([f"Changes ({changes_count})"])
            changes_item.setData(0, Qt.UserRole, {"type": "header", "state": "changes"})
            changes_item.setFont(0, QFont("Segoe UI", 9, QFont.Bold))
            for change in modified_changes:
                child = QTreeWidgetItem(changes_item, [change.a_path])
                child.setData(
                    0,
                    Qt.UserRole,
                    {"type": "file", "state": "modified", "path": change.a_path},
                )
                child.setToolTip(0, f"Modified: {change.a_path}")
            for file_path in untracked_files:
                child = QTreeWidgetItem(changes_item, [file_path])
                child.setData(
                    0,
                    Qt.UserRole,
                    {"type": "file", "state": "untracked", "path": file_path},
                )
                child.setToolTip(0, f"Untracked: {file_path}")
            self.changes_tree.addTopLevelItem(changes_item)
            changes_item.setExpanded(expanded_states["changes"])
            self._group_expanded = expanded_states
            logger.debug(
                "Git status refreshed: staged=%d, modified=%d, untracked=%d",
                staged_count,
                modified_count,
                untracked_count,
            )
            if staged_count == 0 and changes_count == 0:
                no_changes_item = QTreeWidgetItem(["No changes"])
                no_changes_item.setData(0, Qt.UserRole, {"type": "info"})
                self.changes_tree.addTopLevelItem(no_changes_item)
            has_changes = staged_count > 0 or modified_count > 0 or untracked_count > 0
            commits_ahead = 0
            commits_behind = 0
            tracking_branch = None
            try:
                tracking_branch = (
                    self.repo.active_branch.tracking_branch()
                    if not is_detached
                    else None
                )
                if tracking_branch:
                    commits_ahead = sum(
                        1
                        for _ in self.repo.iter_commits(
                            f"{tracking_branch.name}..HEAD"
                        )
                    )
                    commits_behind = sum(
                        1
                        for _ in self.repo.iter_commits(
                            f"HEAD..{tracking_branch.name}"
                        )
                    )
            except Exception:
                logger.exception("Could not determine remote branch status")
            if is_detached:
                self._post_commit_action = None
            elif commits_ahead:
                self._post_commit_action = "push"
            elif commits_behind:
                self._post_commit_action = "pull"
            elif tracking_branch or self._post_commit_action != "push":
                self._post_commit_action = None
            self._update_action_controls(has_changes)
        except Exception as e:
            logger.exception("Could not refresh Git status")
            self.branch_btn.setText(f"Error: {str(e)}")
            self.commit_button.setEnabled(False)
            self._update_action_controls(False)

    def _update_action_controls(self, has_changes):
        action = self._post_commit_action
        if action in {"push", "pull"} and not has_changes:
            self.commit_message_input.hide()
            self.commit_actions_widget.hide()
            self.sync_button.setText("Push" if action == "push" else "Pull")
            self.sync_button.setToolTip(
                "Send your commit to the remote repository"
                if action == "push"
                else "Get the latest changes from the remote repository"
            )
            self.sync_button.setEnabled(bool(self.repo and self.repo.remotes))
            self.sync_button.show()
            if action == "push" and self.repo and not self.repo.remotes:
                self.sync_button.setToolTip(
                    "Add a remote repository before pushing this commit"
                )
            return
        self.sync_button.hide()
        self.commit_message_input.show()
        self.commit_actions_widget.show()
        self.commit_button.setEnabled(has_changes)
        self.ai_commit_button.setEnabled(has_changes)
        if not has_changes:
            self.commit_button.setEnabled(False)
            self.ai_commit_button.setEnabled(False)

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
            if state == "changes":
                menu.addAction("Stage All", self.stage_all)
                menu.addAction("Discard All Changes", self.discard_all_changes)
            elif state == "staged":
                menu.addAction("Unstage All", self.unstage_all)
        menu.exec_(self.changes_tree.viewport().mapToGlobal(pos))

    def on_item_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if data and data.get("type") == "file":
            self.open_file(data["path"])

    def open_file(self, file_path):
        abs_path = os.path.join(self.main_window.current_project_dir, file_path)
        self.main_window.open_specific_file(abs_path)

    def stage_file(self, file_path):
        logger.info("Staging file in Git")
        self._git_busy = True
        try:
            self.repo.git.add(file_path)
        finally:
            self._git_busy = False
            self.update_git_status()

    def unstage_file(self, file_path):
        logger.info("Unstaging file in Git")
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
        logger.info("Staging all changes in Git")
        self._git_busy = True
        try:
            self.repo.git.add(A=True)
        finally:
            self._git_busy = False
            self.update_git_status()

    def unstage_all(self):
        logger.info("Unstaging all changes in Git")
        self._git_busy = True
        try:
            self.repo.git.reset("HEAD")
        finally:
            self._git_busy = False
            self.update_git_status()

    def discard_all_changes(self):
        reply = QMessageBox.question(
            self.main_window,
            "Discard All Changes",
            "Are you sure you want to discard all modified and untracked files? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._git_busy = True
            try:
                self.repo.git.checkout("--", ".")
                self.repo.git.clean("-fd")
            except Exception as error:
                logger.exception("Could not discard all working tree changes")
                QMessageBox.warning(
                    self.main_window, "Discard Changes Failed", str(error)
                )
            finally:
                self._git_busy = False
                self.update_git_status()

    def manage_branches(self):
        if not self.repo:
            return
        branches = [b.name for b in self.repo.branches]
        options = ["+ Create New Branch..."] + branches
        current = None if self.repo.head.is_detached else self.repo.active_branch.name
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
        message = self.commit_message_input.toPlainText().strip()
        if not message:
            QMessageBox.information(
                self.main_window,
                "Commit Message Required",
                "Enter a commit message before creating the commit.",
            )
            self.commit_message_input.setFocus()
            return
        self._commit_with_message(message)

    def generate_ai_commit_message(self):
        if not self.repo or self._git_busy:
            return
        staged_diff = self.repo.git.diff("--cached", "--no-ext-diff")
        if not staged_diff.strip():
            QMessageBox.information(
                self.main_window,
                "AI Commit Message",
                "Stage changes first. The AI generates a message from staged changes only.",
            )
            return
        diff_limit_notice = (
            "\nOnly the first 30,000 characters will be sent."
            if len(staged_diff) > 30000
            else ""
        )
        reply = QMessageBox.question(
            self.main_window,
            "Send Staged Changes to AI?",
            "The staged diff will be sent to your selected AI provider to generate a commit message."
            f"{diff_limit_notice}\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        ai_chat = self.main_window.show_ai_chat()
        if ai_chat is None:
            return
        if self._connected_ai_widget is not ai_chat:
            ai_chat.commit_message_generated.connect(self._on_ai_commit_message)
            ai_chat.commit_message_failed.connect(self._on_ai_commit_message_failed)
            self._connected_ai_widget = ai_chat
        if not ai_chat.generate_commit_message(staged_diff[:30000]):
            QMessageBox.information(
                self.main_window,
                "AI Commit Message",
                "Configure an AI profile in the AI panel, then try again.",
            )
            return
        self._git_busy = True
        self.ai_commit_button.setEnabled(False)
        self.show_progress(True)

    def _on_ai_commit_message(self, generated_message):
        self._git_busy = False
        self.ai_commit_button.setEnabled(True)
        self.show_progress(False)
        self.commit_message_input.setPlainText(generated_message)
        self.commit_message_input.setFocus()

    def _on_ai_commit_message_failed(self, error):
        self._git_busy = False
        self.ai_commit_button.setEnabled(True)
        self.show_progress(False)
        QMessageBox.warning(
            self.main_window,
            "AI Commit Message Failed",
            error,
        )

    def _commit_with_message(self, message):
        logger.info("Creating Git commit")
        self._git_busy = True
        self.show_progress(True)
        committed = False
        try:
            self.repo.index.commit(message)
            committed = True
            self._post_commit_action = (
                None if self.repo.head.is_detached else "push"
            )
            self.commit_message_input.clear()
            if not self.repo.head.is_detached:
                branch = self.repo.active_branch.name
                self.branch_btn.setText(branch)
                self.branch_btn.setToolTip(f"Current branch: {branch}")
        except Exception as e:
            logger.exception("Git commit failed")
            QMessageBox.warning(self.main_window, "Commit Failed", str(e))
        finally:
            self.show_progress(False)
            self._git_busy = False
            if not committed:
                self._post_commit_action = None
            self.update_git_status()

    def run_next_sync_action(self):
        if self._post_commit_action == "push":
            self.push_changes()
        elif self._post_commit_action == "pull":
            self.pull_changes()

    def push_changes(self):
        if not self.repo:
            return
        if self.repo.head.is_detached:
            QMessageBox.information(
                self.main_window,
                "Push Unavailable",
                "Check out a branch before pushing this commit.",
            )
            return
        self._git_busy = True
        self.show_progress(True)
        pushed = False
        try:
            logger.info("Pushing Git changes")
            remote = self.repo.remote()
            branch = self.repo.active_branch
            if branch.tracking_branch():
                push_results = remote.push(branch)
                failed_push = next(
                    (
                        result
                        for result in push_results
                        if result.flags & (PushInfo.ERROR | PushInfo.REJECTED)
                    ),
                    None,
                )
                if failed_push:
                    raise RuntimeError(failed_push.summary.strip())
            else:
                self.repo.git.push(
                    "--set-upstream",
                    remote.name,
                    branch.name,
                )
            pushed = True
            self._post_commit_action = None
            self.branch_btn.setText("Changes pushed")
        except Exception as e:
            logger.exception("Git push failed")
            QMessageBox.warning(self.main_window, "Push Failed", str(e))
        finally:
            self.show_progress(False)
            self._git_busy = False
            if pushed:
                self.update_git_status()
            else:
                QTimer.singleShot(1500, self.update_git_status)

    def pull_changes(self):
        if not self.repo:
            return
        if self.repo.head.is_detached:
            QMessageBox.information(
                self.main_window,
                "Pull Unavailable",
                "Check out a branch before pulling changes.",
            )
            return
        self._git_busy = True
        self.show_progress(True)
        pulled = False
        try:
            logger.info("Pulling Git changes")
            remote = self.repo.remote()
            remote.pull()
            pulled = True
            self._post_commit_action = None
            self.branch_btn.setText("Changes pulled")
        except Exception as e:
            logger.exception("Git pull failed")
            QMessageBox.warning(self.main_window, "Pull Failed", str(e))
        finally:
            self.show_progress(False)
            self._git_busy = False
            if not pulled:
                self._update_action_controls(False)
            self.update_git_status()

    def refresh(self):
        self.update_git_status()
