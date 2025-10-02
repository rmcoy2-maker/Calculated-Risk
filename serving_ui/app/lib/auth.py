from __future__ import annotations
from types import SimpleNamespace
import streamlit as st
import inspect
from pathlib import Path

def _ns(**kw):
    # Pop keys we set explicitly so SimpleNamespace doesn't get duplicates
    ok   = bool(kw.pop("ok", False))
    user = kw.pop("user", None)
    role = kw.pop("role", None)
    return SimpleNamespace(
        ok=ok,
        authenticated=ok,           # legacy compatibility
        user=user,
        username=user,  # some pages use .username
        role=role,
        name=user,            # some pages use .name
        is_viewer=(role == "viewer"),
        is_user=(role in {"user", "admin"}),
        **kw
    )

def _logout_key() -> str:
    """
    Make a stable, per-page key for the logout button by inspecting the call stack
    and grabbing the first .py file that looks like a Streamlit page (or Home.py).
    """
    try:
        for fr in inspect.stack():
            fn = fr.filename
            if not fn or not fn.endswith(".py"):
                continue
            name = Path(fn).stem
            # prefer app pages/Home over library files
            if name and name not in {"auth"}:
                return f"_auth_logout__{name}"
    except Exception:
        pass
    return "_auth_logout__fallback"

def login(*, required: bool=True, title: str='Sign in') -> SimpleNamespace:
    """
    Lightweight auth shim used by all pages.
    - required=False  -> auto-auth to a read-only 'beta' user (no UI).
    - required=True   -> simple username/password in the sidebar.
    Returns: SimpleNamespace with .ok, .authenticated, .user, .username, .role, …
    """
    # already authed?
    state = st.session_state.get('_auth_state')
    if state and state.get('ok'):
        return _ns(**state)

    # beta/viewer: auto-auth without UI
    if not required:
        state = {'ok': True, 'user': 'beta', 'role': 'viewer'}
        st.session_state['_auth_state'] = state
        _mount_logout()
        return _ns(**state)

    # simple sidebar login UI
    with st.sidebar:
        st.subheader(title)
        u = st.text_input('Username', key='_auth_user')
        p = st.text_input('Password', type='password', key='_auth_pass')
        go = st.button('Sign in', key='_auth_go')

    # users can be provided via st.secrets['auth']['users']
    # Example secrets.toml:
    # [auth.users]
    # demo = "demo123"
    users = {}
    try:
        if 'auth' in st.secrets and 'users' in st.secrets['auth']:
            users = dict(st.secrets['auth']['users'].items())  # {username: password}
    except Exception:
        users = {}

    if go:
        if u and p and users.get(u) == p:
            st.session_state['_auth_state'] = {'ok': True, 'user': u, 'role': 'user'}
            st.rerun()
        else:
            st.error('Invalid username or password.')

    _mount_logout()
    return _ns(**st.session_state.get('_auth_state', {'ok': False, 'user': None, 'role': None}))

def show_logout() -> None:
    """Public logout helper (kept for backward compatibility)."""
    _mount_logout()

def _mount_logout():
    key = _logout_key()
    rendered_flag = f"{key}__rendered"

    # If this page already rendered the button this run, skip a duplicate
    if st.session_state.get(rendered_flag):
        return

    with st.sidebar:
        if st.session_state.get('_auth_state', {}).get('ok'):
            if st.button('Log out', key=key):
                st.session_state.pop('_auth_state', None)
                st.rerun()

    # mark rendered for this page
    st.session_state[rendered_flag] = True


