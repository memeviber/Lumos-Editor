import logging

logger = logging.getLogger(__name__)


def on_file_opened(file_path, _):
    logger.info("Plugin received file-opened event")
    lumos.show_message(f"File opened: {file_path}")  # type: ignore


lumos.plugin_manager.register_hook("file_opened", on_file_opened)  # type: ignore
