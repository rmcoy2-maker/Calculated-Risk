# -*- coding: utf-8 -*-
"""
nudge.py — lightweight upsell + session tracking (Streamlit)
"""
from __future__ import annotations
import uuid
import pandas as pd
import streamlit as st
from datetime import timedelta

# ---------- time helpers ----------
def _now():
    try:
        return pd.Timestamp.now()
    except Exception:
        return pd.Timestamp.utcnow()

# ---------- premium helpers ----------
def _has_premium() -> bool:
    try:
        if bool(st.secrets.get("PREMIUM", False)):
            return True
    except Exception:
        pass
    until = st.session_state.get("premium_temp_until")
    if until:
        try:
            return pd.Timestamp(until) > _now()
        except Exception:
            return False
    return False

def _unlock_temp_premium(hours: int = 24) -> None:
    st.session_state["premium_temp_until"] = _now() + timedelta(hours=hours)

# ---------- usage counters ----------
def bump_usage(metric: str, n: int = 1, period: str = "1D") -> None:
    key = f"_usage_{metric}"
    now = _now()
    window = pd.Timedelta(period)
    hist = st.session_state.get(key, [])
    hist = [ts for ts in hist if (now - pd.Timestamp(ts)) <= window]
    hist.extend([now] * max(1, n))
    st.session_state[key] = hist

def usage_count(metric: str, period: str = "1D") -> int:
    key = f"_usage_{metric}"
    now = _now()
    window = pd.Timedelta(period)
    hist = st.session_state.get(key, [])
    return sum(1 for ts in hist if (now - pd.Timestamp(ts)) <= window)

# ---------- session tracking ----------
def begin_session() -> None:
    """Initialize session_id, session_start, last_seen if not present."""
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())[:8]
    if "session_start" not in st.session_state:
        st.session_state["session_start"] = _now()
    if "last_seen" not in st.session_state:
        st.session_state["last_seen"] = st.session_state["session_start"]

def touch_session() -> None:
    """Mark activity for this session."""
    if "session_start" not in st.session_state:
        begin_session()
    st.session_state["last_seen"] = _now()

def session_duration_seconds() -> int:
    """Return seconds since session_start (wall time)."""
    if "session_start" not in st.session_state:
        return 0
    delta = _now() - pd.Timestamp(st.session_state["session_start"])
    try:
        return int(delta.total_seconds())
    except Exception:
        return 0

def _fmt_seconds(s: int) -> str:
    if s <= 0: return "0s"
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h: return f"{h}h {m}m {sec}s"
    if m: return f"{m}m {sec}s"
    return f"{sec}s"

def session_duration_str() -> str:
    return _fmt_seconds(session_duration_seconds())

# ---------- nudge UI ----------
def show_nudge(
    *, feature: str = "analytics",
    metric: str = "page_visit",
    threshold: int = 10,
    period: str = "1D",
    demo_unlock: bool = True,
    location: str = "inline"
) -> None:
    """Render upsell banner when usage crosses threshold (unless premium)."""
    if _has_premium():
        return
    cnt = usage_count(metric, period=period)
    if cnt < threshold:
        return

    msg = f"👀 You’ve been active ({cnt} interactions today). Want more {feature}? Get a 24-hr Premium Pass for $5."
    box = st.sidebar if location == "sidebar" else st
    with box.container():
        st.info(msg)
        cols = st.columns([1,1,3])
        with cols[0]:
            if demo_unlock and st.button("🔑 Unlock 24-hr Pass (demo)"):
                _unlock_temp_premium(24)
                st.success("Premium pass activated for 24 hours (demo). Reload the page.")
                st.experimental_rerun()
        with cols[1]:
            st.caption("Premium disables this banner.")
