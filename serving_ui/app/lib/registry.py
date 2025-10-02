def current_model_version() -> str:
    try:
        from app.lib.config import MODEL_VERSION
        return str(MODEL_VERSION)
    except Exception:
        return 'v1'

def enrich_record_with_model(rec: dict) -> dict:
    rec = {**rec}
    rec.setdefault('model_version', current_model_version())
    return rec