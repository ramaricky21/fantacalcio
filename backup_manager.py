from pathlib import Path
from datetime import datetime
import zipfile
import shutil
import tempfile
from database import DB_PATH

BASE_DIR = Path(__file__).resolve().parent
BACKUP_DIR = BASE_DIR / "backups"
LOGO_DIR = BASE_DIR / "docs" / "assets" / "logos"

def _slots():
    return [BACKUP_DIR / "backup_1.zip", BACKUP_DIR / "backup_2.zip"]

def create_rotating_backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    slots = _slots()

    if not slots[0].exists():
        target = slots[0]
    elif not slots[1].exists():
        target = slots[1]
    else:
        target = min(slots, key=lambda p: p.stat().st_mtime)

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        if DB_PATH.exists():
            z.write(DB_PATH, "db.sqlite3")
        if LOGO_DIR.exists():
            for p in LOGO_DIR.rglob("*"):
                if p.is_file():
                    z.write(p, str(Path("logos") / p.relative_to(LOGO_DIR)))
        z.writestr(
            "backup_info.txt",
            "Backup Fantacalcio\nCreato: " + datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        )
    return target

def backup_list():
    result = []
    for p in _slots():
        if p.exists():
            result.append({
                "path": p,
                "modified": datetime.fromtimestamp(p.stat().st_mtime),
                "size": p.stat().st_size,
            })
    return sorted(result, key=lambda x: x["modified"], reverse=True)

def restore_backup(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        with zipfile.ZipFile(path, "r") as z:
            z.extractall(td)

        db = td / "db.sqlite3"
        if not db.exists():
            raise RuntimeError("Il backup non contiene db.sqlite3")

        shutil.copy2(db, DB_PATH)

        restored_logos = td / "logos"
        if restored_logos.exists():
            LOGO_DIR.mkdir(parents=True, exist_ok=True)
            for p in restored_logos.rglob("*"):
                if p.is_file():
                    dest = LOGO_DIR / p.relative_to(restored_logos)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, dest)
