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
    backup_path = RECOVERY_DIR / f"{recovery_id}.json.bak"
    backup_temporary_path = RECOVERY_DIR / f"{recovery_id}.bak.tmp"
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
        if recovery_path.exists():
            with recovery_path.open("rb") as previous_file:
                with backup_temporary_path.open("wb") as backup_file:
                    while True:
                        chunk = previous_file.read(1024 * 1024)
                        if not chunk:
                            break
                        backup_file.write(chunk)
                    backup_file.flush()
                    os.fsync(backup_file.fileno())
            os.replace(backup_temporary_path, backup_path)
        os.replace(temporary_path, recovery_path)
    except Exception:
        for path in (temporary_path, backup_temporary_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        raise


def _read_recovery(recovery_path, recovery_id):
    try:
        with recovery_path.open("r", encoding="utf-8") as recovery_file:
            recovery = json.load(recovery_file)
    except (json.JSONDecodeError, UnicodeError):
        logger.warning("Skipping corrupted recovery file: %s", recovery_path.name)
        return None
    except FileNotFoundError:
        return None
    except OSError:
        logger.exception("Could not read recovery file: %s", recovery_path.name)
        return None

    if (
        not isinstance(recovery, dict)
        or not isinstance(recovery.get("content"), str)
        or recovery.get("id") != recovery_id
        or not isinstance(recovery.get("saved_at", ""), str)
        or (
            recovery.get("filepath") is not None
            and not isinstance(recovery.get("filepath"), str)
        )
    ):
        logger.warning("Skipping invalid recovery file: %s", recovery_path.name)
        return None
    return recovery


def list_recoveries():
    if not RECOVERY_DIR.exists():
        return []

    recovery_ids = {
        recovery_path.stem for recovery_path in RECOVERY_DIR.glob("*.json")
    }
    recovery_ids.update(
        backup_path.name[:-9] for backup_path in RECOVERY_DIR.glob("*.json.bak")
    )

    recoveries = []
    for recovery_id in recovery_ids:
        if not re.fullmatch(r"[0-9a-f]{32}", recovery_id):
            continue

        recovery = _read_recovery(
            RECOVERY_DIR / f"{recovery_id}.json",
            recovery_id,
        )
        if recovery is None:
            recovery = _read_recovery(
                RECOVERY_DIR / f"{recovery_id}.json.bak",
                recovery_id,
            )
        if recovery is not None:
            recoveries.append(recovery)

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
    for path in (recovery_path, RECOVERY_DIR / f"{recovery_id}.json.bak"):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("Could not delete recovery file: %s", path.name)
