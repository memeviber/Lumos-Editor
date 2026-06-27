import os
import shutil
import zipfile
from pathlib import Path

current_dir = Path.cwd()
archive_name = current_dir.name + ".lmp"
archive_path = current_dir / archive_name

with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, _, files in os.walk(current_dir):
        for file in files:
            file_path = Path(root) / file

            if file_path.resolve() == archive_path.resolve():
                continue

            zf.write(file_path, file_path.relative_to(current_dir))

destination_dir = current_dir.parent.parent
destination_dir.mkdir(parents=True, exist_ok=True)

destination_path = destination_dir / archive_name
shutil.copy2(archive_path, destination_path)
archive_path.unlink()
