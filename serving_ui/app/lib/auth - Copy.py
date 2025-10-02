from __future__ import annotations
from types import SimpleNamespace
import streamlit as st

def login(*, required: bool=True, title: str='Sign in') -> SimpleNamespace:
    """
    Lightweight auth shim used by all pages.
    - required=False  -> auto-auth to a read-only 'beta' user (no UI).
    - required=True   -> simple username/password in the sidebar.
    Returns an object with .ok, .user, .role.
    """
    # already authed?
    state = st.session_state.get('_auth_state')
    if state and state.get('ok'):
        return SimpleNamespace(**state)

    # beta/viewer: auto-auth without UI
    if not required:
        state = {'ok': True, 'user': 'beta', 'role': 'viewer'}
        st.session_state['_auth_state'] = state
        _mount_logout()
        return SimpleNamespace(**state)

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
            # st.secrets['auth']['users'] is a Mapping of {username: password}
            users = dict(st.secrets['auth']['users'].items())
    except Exception:
        users = {}

    if go:
        if u and p and users.get(u) == p:
            st.session_state['_auth_state'] = {'ok': True, 'user': u, 'role': 'user'}
            st.rerun()
        else:
            st.error('Invalid username or password.')

    _mount_logout()
    return SimpleNamespace(**st.session_state.get('_auth_state', {'ok': False, 'user': None, 'role': None}))

def show_logout() -> None:
    """Public logout helper (kept for backward compatibility)."""
    _mount_logout()

def _mount_logout():
    with st.sidebar:
        if st.session_state.get('_auth_state', {}).get('ok'):
            if st.button('Log out', key='_auth_logout'):
                st.session_state.pop('_auth_state', None)
                st.rerun()
