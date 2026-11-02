import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

RECOVERY_DIR = Path.home() / ".lumos_editor" / "recovery"


def new_recovery_id():
    return uuid.uuid4().hex


def write_recovery(recovery_id, filepath, content):
    if not re.fullmatch(r"[0-9a-f]{32}", recovery_id):
        raise ValueError("Invalid recovery identifier")

    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    recovery_path = RECOVERY_DIR / f"{recovery_id}.json"
    temporary_path = RECOVERY_DIR / f"{recovery_id}.tmp"
    payload = {
        "id": recovery_id,
        "filepath": filepath,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "content": content,
    }

    try:
        with temporary_path.open("w", encoding="utf-8") as recovery_file:
            json.dump(payload, recovery_file, ensure_ascii=False)
            recovery_file.flush()
            os.fsync(recovery_file.fileno())
        os.replace(temporary_path, recovery_path)
    except Exception:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
        raise


def list_recoveries():
    if not RECOVERY_DIR.exists():
        return []

    recoveries = []
    for recovery_path in RECOVERY_DIR.glob("*.json"):
        try:
            with recovery_path.open("r", encoding="utf-8") as recovery_file:
                recovery = json.load(recovery_file)
            recovery_id = recovery_path.stem
            if (
                not re.fullmatch(r"[0-9a-f]{32}", recovery_id)
                or not isinstance(recovery, dict)
                or not isinstance(recovery.get("content"), str)
                or recovery.get("id") != recovery_id
                or not isinstance(recovery.get("saved_at", ""), str)
                or (
                    recovery.get("filepath") is not None
                    and not isinstance(recovery.get("filepath"), str)
                )
            ):
                logger.warning("Skipping invalid recovery file: %s", recovery_path.name)
                continue
            recoveries.append(recovery)
        except (OSError, json.JSONDecodeError):
            logger.exception("Could not read recovery file: %s", recovery_path.name)

    return sorted(
        recoveries,
        key=lambda recovery: recovery.get("saved_at", ""),
        reverse=True,
    )


def delete_recovery(recovery_id):
    if not re.fullmatch(r"[0-9a-f]{32}", recovery_id):
        logger.warning("Ignoring invalid recovery identifier")
        return

    recovery_path = RECOVERY_DIR / f"{recovery_id}.json"
    try:
        recovery_path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        logger.exception("Could not delete recovery file: %s", recovery_path.name)
