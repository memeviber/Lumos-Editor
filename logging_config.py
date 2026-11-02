import logging
import os
from logging.handlers import RotatingFileHandler

_configured = False


def configure_logging():
    global _configured
    if _configured:
        return

    log_dir = os.path.join(os.path.expanduser("~"), ".lumos_editor")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "startup.log")
    handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] [%(threadName)s] %(message)s"
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)
    _configured = True
    logging.getLogger(__name__).info("Logging configured: file=%s", log_path)
