import logging

from logging_config import configure_logging

from .ai_chat import AIChat
from .cmd_palette import CommandPalette
from .config_manager import ConfigManager
from .editor_tab import EditorTab
from .file_tree import FileTreeDelegate, FileTreeView
from .find_replace import FindReplaceDialog
from .media_viewer import AudioViewer, ImageViewer, VideoViewer
from .plugin_manager import PluginDialog, PluginManager
from .search_worker import SearchWorker
from .splash_screen import StartupSplash
from .source_control import SourceControlTab
from .split_tab import SplitTab
from .terminal import Terminal
from .welcome_screen import WelcomeScreen

logger = logging.getLogger(__name__)

__all__ = [
    "EditorTab",
    "FileTreeDelegate",
    "FileTreeView",
    "WelcomeScreen",
    "FindReplaceDialog",
    "PluginManager",
    "PluginDialog",
    "ConfigManager",
    "AIChat",
    "AudioViewer",
    "ImageViewer",
    "VideoViewer",
    "SplitTab",
    "SourceControlTab",
    "CommandPalette",
    "SearchWorker",
    "Terminal",
    "StartupSplash",
]

configure_logging()
logger.debug("Lumos editor package initialized")
