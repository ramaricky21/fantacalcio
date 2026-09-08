from pathlib import Path
from datetime import datetime
import subprocess
import shutil

BASE_DIR = Path(__file__).resolve().parent

class PublishError(RuntimeError):
    pass

def _run(args):
    result = subprocess.run(
        args, cwd=BASE_DIR, capture_output=True, text=True, shell=False
    )
    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip()
        raise PublishError(msg or "Comando Git non riuscito.")
    return result.stdout.strip()

def publish_to_github():
    if shutil.which("git") is None:
        raise PublishError(
            "Git non risulta installato. Installa Git e completa la configurazione iniziale."
        )
    if not (BASE_DIR / ".git").exists():
        raise PublishError(
            "Questa cartella non è ancora collegata a GitHub. "
            "Segui la sezione 'Prima pubblicazione' della guida."
        )

    _run(["git", "add", "docs"])

    status = _run(["git", "status", "--porcelain", "docs"])
    if status:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        _run(["git", "commit", "-m", f"Aggiornamento fantacalcio {stamp}"])

    # Recupera il nome del branch attuale, così non imponiamo per forza 'main'.
    branch = _run(["git", "branch", "--show-current"]) or "main"
    _run(["git", "push", "origin", branch])
    return "Pubblicazione completata su GitHub."
