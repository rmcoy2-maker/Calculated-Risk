from datetime import datetime, timezone
from pathlib import Path

def _logfile() -> Path:
    root = Path(__file__).resolve().parents[2]
    logd = root / 'logs'
    logd.mkdir(exist_ok=True)
    return logd / 'app.log'

def log_error(msg: str):
    try:
        ts = datetime.now(timezone.utc).isoformat()
        _logfile().write_text(f'[{ts}] ERROR {msg}\n', encoding='utf-8', append=True)
    except Exception:
        pass