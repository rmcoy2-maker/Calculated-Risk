from __future__ import annotations
# === AppImportGuard (nuclear) ===
try:
    from app.lib.auth import login, show_logout
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    here = Path(__file__).resolve()

    base = None
    auth_path = None
    for p in [here] + list(here.parents):
        cand1 = p / "app" / "lib" / "auth.py"
        cand2 = p / "serving_ui" / "app" / "lib" / "auth.py"
        if cand1.exists():
            base, auth_path = p, cand1
            break
        if cand2.exists():
            base, auth_path = (p / "serving_ui"), cand2
            break

    if base and auth_path:
        s = str(base)
        if s not in sys.path:
            sys.path.insert(0, s)
        try:
            from app.lib.auth import login, show_logout  # type: ignore
        except ModuleNotFoundError:
            import types, importlib.util
            if "app" not in sys.modules:
                pkg_app = types.ModuleType("app")
                pkg_app.__path__ = [str(Path(base) / "app")]
                sys.modules["app"] = pkg_app
            if "app.lib" not in sys.modules:
                pkg_lib = types.ModuleType("app.lib")
                pkg_lib.__path__ = [str(Path(base) / "app" / "lib")]
                sys.modules["app.lib"] = pkg_lib
            spec = importlib.util.spec_from_file_location("app.lib.auth", str(auth_path))
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            assert spec and spec.loader
            spec.loader.exec_module(mod)  # type: ignore[attr-defined]
            sys.modules["app.lib.auth"] = mod
            login = mod.login
            show_logout = mod.show_logout
    else:
        raise
# === /AppImportGuard ===


import sys
from pathlib import Path
import streamlit as st
_here = Path(__file__).resolve()
for up in [_here] + list(_here.parents):
    cand = up / 'serving_ui' / 'app' / '__init__.py'
    if cand.exists():
        base = str((up / 'serving_ui').resolve())
        if base not in sys.path:
            sys.path.insert(0, base)
        break
PAGE_PROTECTED = False
auth = login(required=PAGE_PROTECTED)
if not auth.ok:
    st.stop()
show_logout()
auth = login(required=False)
if not auth.authenticated:
    st.info('You are in read-only mode.')
show_logout()
import sys, os
from pathlib import Path
_HERE = Path(__file__).resolve()
_SERVING_UI = _HERE.parents[2]
if str(_SERVING_UI) not in sys.path:
    sys.path.insert(0, str(_SERVING_UI))
from collections.abc import Mapping
try:
    from app.utils.diagnostics import mount_in_sidebar
except Exception:

    def mount_in_sidebar(_: str | None=None):
        return None
try:
    import bcrypt
except Exception:
    bcrypt = None
if os.environ.get('EDGE_DEBUG_SECRETS') == '1':
    try:
        u = st.secrets.get('credentials', {}).get('usernames', {})
        st.info(f"usernames visible in secrets: {list(getattr(u, 'keys', lambda: [])())}")
    except Exception as e:
        st.warning(f'secrets parse error: {e}')
st.set_page_config(page_title='00 Login', page_icon='📈', layout='wide')




# === Nudge+Session (auto-injected) ===
try:
    from app.utils.nudge import begin_session, touch_session, session_duration_str, bump_usage, show_nudge  # type: ignore
except Exception:
    def begin_session(): pass
    def touch_session(): pass
    def session_duration_str(): return ""
    bump_usage = lambda *a, **k: None
    def show_nudge(*a, **k): pass

# Initialize/refresh session and show live duration
begin_session()
touch_session()
if hasattr(st, "sidebar"):
    st.sidebar.caption(f"🕒 Session: {session_duration_str()}")

# Count a lightweight interaction per page load
bump_usage("page_visit")

# Optional upsell banner after threshold interactions in last 24h
show_nudge(feature="analytics", metric="page_visit", threshold=10, period="1D", demo_unlock=True, location="inline")
# === /Nudge+Session (auto-injected) ===

# === Nudge (auto-injected) ===
try:
    from app.utils.nudge import bump_usage, show_nudge  # type: ignore
except Exception:
    bump_usage = lambda *a, **k: None
    def show_nudge(*a, **k): pass

# Count a lightweight interaction per page load
bump_usage("page_visit")

# Show a nudge once usage crosses threshold in the last 24h
show_nudge(feature="analytics", metric="page_visit", threshold=10, period="1D", demo_unlock=True, location="inline")
# === /Nudge (auto-injected) ===

mount_in_sidebar('00_Login')
DEV_BYPASS = os.environ.get('EDGE_DEV_NO_AUTH', '') == '1'
if not DEV_BYPASS:
    try:
        DEV_BYPASS = str(st.secrets.get('auth_mode', '')).strip().upper() in {'OFF', 'DISABLED', 'BYPASS'}
    except Exception as e:
        st.warning(f'Secrets parse error: {e}. Set EDGE_DEV_NO_AUTH=1 to bypass temporarily.')

def _read_credentials() -> dict[str, dict]:
    """
    Expected secrets structure:

      auth_mode = "ON"

      [credentials.usernames.<username>]
      name = "..."
      email = "..."
      password = "<bcrypt hash>"
      role = "admin" | "guest" | "user"
    """
    from collections.abc import Mapping
    creds_root = st.secrets.get('credentials', {})
    users = {}
    if isinstance(creds_root, Mapping):
        users = creds_root.get('usernames', {}) or {}
    else:
        try:
            users = dict(creds_root).get('usernames', {}) or {}
        except Exception:
            users = {}
    out: dict[str, dict] = {}
    it = users.items() if isinstance(users, Mapping) else []
    for uname, blob in it:
        if not isinstance(blob, Mapping):
            try:
                blob = dict(blob)
            except Exception:
                continue
        out[str(uname)] = {'name': blob.get('name') or str(uname), 'email': blob.get('email', ''), 'password': str(blob.get('password', '')), 'role': blob.get('role', 'user')}
    return out

def _check_password(stored_hash: str, raw_pw: str) -> bool:
    if not stored_hash or not raw_pw:
        return False
    if bcrypt is None:
        st.error('bcrypt is not installed. In your venv run:  pip install bcrypt')
        return False
    try:
        return bcrypt.checkpw(raw_pw.encode('utf-8'), stored_hash.encode('utf-8'))
    except Exception:
        return False

def _login_ui():
    st.title('🔐 Sign in to Edge Finder')
    auth = st.session_state.get('auth', {'authenticated': False})
    if auth.get('authenticated'):
        st.success(f"Welcome, {auth.get('name')} ({auth.get('role')})!")
        st.page_link('Home.py', label='Go to Home', icon='🏠')
        st.divider()
        if st.button('Log out'):
            st.session_state.pop('auth', None)
            st.rerun()
        return
    if DEV_BYPASS:
        st.info('Auth bypass is enabled (DEV).')
        st.session_state['auth'] = {'authenticated': True, 'username': 'admin', 'name': 'Developer', 'email': '', 'role': 'admin'}
        st.rerun()
        return
    creds = _read_credentials()
    if not creds:
        st.error('No credentials found in secrets. Add a user under [credentials.usernames.<username>].')
        with st.expander('Example secrets.toml entry', expanded=False):
            st.code('auth_mode = "ON"\n\n[credentials.usernames.murphey]\nname = "Murphey Coy"\nemail = "rmcoy2y@gmail.com"\npassword = "$2b$12$9eoQypxuzyrOwwErAel4VOl5HgoEgCUj5u8YIhIelKnlWkyJ6iWau"  # bcrypt hash for \'bet247\'\nrole = "admin"\n\n[credentials.usernames.tester]\nname = "Guest"\nemail = ""\npassword = "$2b$12$uNiAG1j3QkaBnT2LzeSjYOy7fWxT47.OyJEW5/Z./JE8h5V0h0gPS"  # bcrypt for \'_guest\'\nrole = "guest"\n', language='toml')
        with st.expander('Generate a bcrypt hash (PowerShell)', expanded=False):
            st.code('.\\.venv\\Scripts\\python.exe -c "import bcrypt, getpass; pw=getpass.getpass(\'New password: \'); print(bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode())" ', language='powershell')
        return
    st.caption('Enter your username and password to continue.')
    u = st.text_input('Username', key='login_username')
    p = st.text_input('Password', type='password', key='login_password')
    colA, colB = st.columns([1, 1])
    with colA:
        submit = st.button('Sign in', type='primary')
    with colB:
        guest = st.button('Continue as guest (no password)')
    if submit:
        rec = creds.get(u.strip()) if u else None
        if not rec:
            st.error('Unknown username.')
            return
        if not _check_password(rec.get('password', ''), p):
            st.error('Incorrect password.')
            return
        st.session_state['auth'] = {'authenticated': True, 'username': u, 'name': rec.get('name') or u, 'email': rec.get('email', ''), 'role': rec.get('role', 'user')}
        st.rerun()
    if guest:
        st.session_state['auth'] = {'authenticated': True, 'username': 'guest', 'name': 'Guest', 'email': '', 'role': 'guest'}
        st.rerun()
_login_ui()







