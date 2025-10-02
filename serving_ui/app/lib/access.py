from __future__ import annotations

def live_enabled() -> bool:
    return False  # dev-safe default to avoid do_expensive_refresh()

def require_allowed_page(_page_path: str) -> None:
    return None

def beta_banner() -> None:
    try:
        import streamlit as st
        st.caption("🧪 Beta mode — access controls in dev shim.")
    except Exception:
        pass
