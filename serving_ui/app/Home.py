# --- Core imports & paths (must come first) ---
from pathlib import Path
import os
import time
from typing import Iterable, Set

import pandas as pd
import streamlit as st

st.set_page_config(page_title='Calculate Risk: Edge Finder — Home', page_icon='📈', layout='wide')

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent.parent
ASSETS_DIR = APP_DIR / 'assets'
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Optional: exports dir
EXPORTS = ROOT / 'exports'
env_exports = os.environ.get('EDGE_EXPORTS_DIR', '').strip()
if env_exports:
    EXPORTS = Path(env_exports)
EXPORTS.mkdir(parents=True, exist_ok=True)

# Fix the logo candidates (remove stray ".")
LOGO_CANDIDATES = [
    ASSETS_DIR / 'logo.png',
    ASSETS_DIR / 'calculated_risk_logo.png',
    ROOT / 'logo.png',
    ROOT / 'calculated_risk_logo.png',
]

try:
    # If your auth module exposes current_user() or similar, we use it.
    from app.lib.auth import current_user  # type: ignore
except Exception:  # pragma: no cover
    def current_user():  # type: ignore
        class _Anon:
            role = None
            email = None
            is_admin = False
        return _Anon()

US_STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"
]

DEFAULT_RESTRICTED: Set[str] = {"WA", "ID", "NV"}

BADGE_TEXT = (
    "Not a sportsbook. No wagers, deposits, or payouts. "
    "Analytics / education only. Not available in all states."
)


def _is_admin(allow_env: bool = True) -> bool:
    """Return True if the current user should bypass eligibility checks."""
    try:
        user = current_user()
        if getattr(user, "is_admin", False):
            return True
        role = (getattr(user, "role", None) or "").lower()
        if role in {"admin", "owner", "superuser"}:
            return True
    except Exception:
        pass
    if allow_env and os.getenv("EDGEFINDER_ADMIN", "").strip() in {"1", "true", "yes"}:
        return True
    return False


def show_compliance_badge(location: str = "sidebar") -> None:
    """Small always-on disclaimer badge."""
    txt = (
        "**Compliance:** Not a sportsbook. No money passes through us. "
        "For entertainment & education. Availability varies by state."
    )
    if location == "sidebar" and hasattr(st, "sidebar"):
        st.sidebar.caption(txt)
    else:
        st.caption(txt)


def require_eligibility(
    min_age: int = 18,
    restricted_states: Iterable[str] = DEFAULT_RESTRICTED,
    allow_admin_override: bool = True,
    banner: bool = True,
) -> None:
    """
    Gate access by (1) age confirmation and (2) self-reported state.

    Place near the top of each page *after* authentication but *before* showing live content.
    Will call st.stop() if the user is in a restricted state or has not confirmed age.
    """
    restricted = {s.strip().upper() for s in restricted_states if s}

    if banner:
        show_compliance_badge("sidebar")

    # Admins may bypass (for QA)
    if allow_admin_override and _is_admin(True):
        st.sidebar.success("Admin override: compliance gate bypassed.")
        return

    st.session_state.setdefault("elig_confirmed", False)
    st.session_state.setdefault("elig_state", "")

    # Render gate UI only if not already confirmed in this session
    if not st.session_state["elig_confirmed"]:
        with st.container(border=True):
            st.subheader("📜 Eligibility Check")
            st.write(
                "We are **not a sportsbook**. We do not accept or facilitate real money wagers, deposits, or payouts. "
                "This Service is for analytics, education, and entertainment only."
            )
            col1, col2 = st.columns([1,1])
            with col1:
                state = st.selectbox(
                    "Your U.S. state (or DC)",
                    options=[""] + US_STATES,
                    index=0,
                    help="Used only to apply availability rules.",
                )
            with col2:
                age_ok = st.checkbox(
                    f"I confirm I am at least {min_age}+ years old (or 21+ where required)", value=False
                )

            st.session_state["elig_state"] = state

            # Hard block if restricted state selected
            if state and state.upper() in restricted:
                st.error(
                    "We currently do not offer access in your state due to local restrictions."
                )
                st.stop()

            # Confirm button
            if st.button("Continue", type="primary"):
                if not state:
                    st.warning("Please select your state.")
                    st.stop()
                if not age_ok:
                    st.warning("You must confirm your age to continue.")
                    st.stop()
                st.session_state["elig_confirmed"] = True
                st.success("Eligibility confirmed for this session.")
                st.rerun()

        st.stop()  # Prevent page content until completed

    # If we get here, user previously confirmed in this session
    state = (st.session_state.get("elig_state") or "").upper()
    if state in restricted:
        st.error("Access restricted in your state.")
        st.stop()

    # Optional small banner on page body
    st.info(BADGE_TEXT, icon="🛡️")

# === AppImportGuard (nuclear) ===
try:
    from app.lib.auth import login, show_logout
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    here = Path(__file__).resolve()

    # Find .../<base>/app/lib/auth.py OR .../<base>/serving_ui/app/lib/auth.py
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
            # Try the normal import again after fixing sys.path
            from app.lib.auth import login, show_logout  # type: ignore
        except ModuleNotFoundError:
            # Fallback: load the module directly and register it under app.lib.auth
            import types, importlib.util
            # Ensure package containers exist in sys.modules
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
        raise  # no auth.py found at expected locations

def _find_disclaimer() -> Path | None:
    """Find a DISCLAIMER.md via env or common locations."""
    env_path = os.environ.get('EDGE_DISCLAIMER_PATH', '').strip()
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    candidates = [ASSETS_DIR / 'DISCLAIMER.md', ROOT / 'DISCLAIMER.md', ROOT / 'LEGAL' / 'DISCLAIMER.md']
    return next((p for p in candidates if p.exists()), None)

def _default_disclaimer_md() -> str:
    return '\n\n\n**A Man and Machine Productions.**  \n**From a bored room, not a boardroom!**  \n**Always calculate risk responsibly.**\n\n- **For entertainment and educational purposes only.** Nothing here is financial, legal, or investment advice.\n- **No guarantee of accuracy or availability.** Data may be delayed, incomplete, or contain errors. Use your own judgment.\n- **No wagering facilitation.** This application does not accept bets and is not a sportsbook.\n- **Age & jurisdiction.** Users must follow all applicable laws and be of legal age in their jurisdiction.\n- **Trademarks & data sources.** Team names, logos, and sportsbook names belong to their owners; used here for informational purposes.\n- **Privacy.** Local files like `exports/*.csv` stay on your machine unless you share them.\n\n**Responsible Gaming Resources (U.S.):**\n- Call/Text/Chat **1-800-GAMBLER** — https://www.1800gambler.net/\n- National Council on Problem Gambling — Helpline **1-800-522-4700**, Live Chat: https://www.ncpgambling.org/chat\n- New York: Text **HOPENY** to **467369**\n- Mississippi: Text **MSGAMBLE** to **53342**\n'.strip()
LOGO_CANDIDATES = [ASSETS_DIR / 'logo.png', ASSETS_DIR / 'calculated_risk_logo.png', ROOT / 'logo.png', ROOT / 'calculated_risk_logo.png', ASSETS_DIR / 'logo.png.']
LOGO_PATH = next((p for p in LOGO_CANDIDATES if p.exists()), None)
col_logo, col_title = st.columns([1, 3], vertical_alignment='center')
with col_logo:
    if LOGO_PATH:
        try:
            from PIL import Image
            st.image(Image.open(LOGO_PATH), width='stretch')
        except Exception:
            st.image(str(LOGO_PATH), width='stretch')
    else:
        st.subheader('📁 assets/logo.png')
        st.caption('No logo found. Place your logo image at:')
        st.code(str(ASSETS_DIR / 'logo.png'))
        st.warning('Missing logo: put your file at assets/logo.png', icon='⚠️')
# === /AppImportGuard ===
from pathlib import Path
import os
import time
import pandas as pd
import streamlit as st
st.set_page_config(page_title='Edge Finder — Home', page_icon='📈', layout='wide')

ROOT = APP_DIR.parent.parent
EXPORTS = ROOT / 'exports'
env_exports = os.environ.get('EDGE_EXPORTS_DIR', '').strip()
if env_exports:
    EXPORTS = Path(env_exports)
EXPORTS.mkdir(parents=True, exist_ok=True)

ASSETS_DIR.mkdir(parents=True, exist_ok=True)

def _resolve_tos_url() -> tuple[str, str]:
    """
    Return (display_label, url) for Terms of Service ("94 Legal").
    Priority:
      1) EDGE_TOS_URL env var (hosted https link)
      2) Local files -> file:// URL
    """
    label = 'Terms of Service — 94 Legal'
    env_url = os.environ.get('EDGE_TOS_URL', '').strip()
    if env_url:
        return (label, env_url)
    candidates = [ASSETS_DIR / 'TERMS.md', ASSETS_DIR / '94_LEGAL.md', ROOT / 'LEGAL' / 'TERMS.md', ROOT / 'LEGAL' / '94_LEGAL.md', ROOT / '94_LEGAL.md', ROOT / 'TERMS.md']
    for p in candidates:
        if p.exists():
            try:
                return (label, p.resolve().as_uri())
            except Exception:
                pass
    return (label, 'https://example.com/94-legal-terms')


with col_title:
    st.markdown('\n# **Edge Finder**\n##### Calculated Risk — Analytics & Parlay Builder\n        '.strip())
st.divider()

def _mtime(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
    except Exception:
        return '—'

@st.cache_data(show_spinner=False)
def _read_csv_safe(p: Path, nrows: int | None=5) -> pd.DataFrame:
    try:
        return pd.read_csv(p, nrows=nrows)
    except Exception:
        return pd.DataFrame()

def _page_link(label: str, page: str, icon: str=''):
    """Use st.page_link if available; fallback to markdown link."""
    try:
        st.page_link(f'pages/{page}', label=label, icon=icon)
    except Exception:
        st.markdown(f'- [{label}](pages/{page})')
st.subheader('Go to…')
nav_cols = st.columns(3)
with nav_cols[0]:
    _page_link('01 — Line Shop', '01_Line_Shop.py', '🛒')
    _page_link('02 — Odds Explorer', '02_Odds_Explorer.py', '📊')
    _page_link('03 — Backtest / Scores Browser', '03_Backtest.py', '🧪')
with nav_cols[1]:
    _page_link('04 — House Picks', '04_House_Picks.py', '🏠')
    _page_link('05 — Parlay Builder', '05_Parlay_Builder.py', '🧩')
    _page_link('06 — Ghost Parlay Calc', '06_Ghost_Parlay_Calc.py', '👻')
with nav_cols[2]:
    _page_link('07 — Parlay Scored Explorer', '07_Parlay_Scored_Explorer.py', '📈')
    _page_link('08 — User Manual / Help', '08_User_Manual.py', '📘')
    _page_link('09 — All Picks — Explorer', '09_All_Picks_Explorer.py', '🗂️')
st.divider()
st.subheader('Data Status')
edges_p = EXPORTS / 'edges_graded_full_normalized_std.csv'
odds_p = EXPORTS / 'odds_lines_all.csv'
scores_p = EXPORTS / 'scores_1966-2025.csv'
c1, c2, c3 = st.columns(3)
with c1:
    st.caption('Edges')
    st.code(str(edges_p))
    st.metric('Last modified', _mtime(edges_p))
    df = _read_csv_safe(edges_p, nrows=3)
    st.caption(f'Sample rows: {len(df)}' if not df.empty else 'No preview available.')
with c2:
    st.caption('Odds / Lines')
    st.code(str(odds_p))
    st.metric('Last modified', _mtime(odds_p))
    df = _read_csv_safe(odds_p, nrows=3)
    st.caption(f'Sample rows: {len(df)}' if not df.empty else 'No preview available.')
with c3:
    st.caption('Scores')
    st.code(str(scores_p))
    st.metric('Last modified', _mtime(scores_p))
    df = _read_csv_safe(scores_p, nrows=3)
    st.caption(f'Sample rows: {len(df)}' if not df.empty else 'No preview available.')
st.divider()
st.subheader('Parlay Cart (quick peek)')
cart_p = EXPORTS / 'parlay_cart.csv'
if cart_p.exists():
    cart = _read_csv_safe(cart_p, nrows=50)
    if cart.empty:
        st.info('Cart file exists but is empty.')
    else:
        st.caption(f'Showing up to 50 rows from {cart_p.name}')
        st.dataframe(cart, hide_index=True, width='stretch')
else:
    st.caption('No parlay_cart.csv found yet. Build parlays in **05 — Parlay Builder**.')
st.divider()
disc_path = _find_disclaimer()
disc_md = _default_disclaimer_md()
if disc_path:
    try:
        disc_md = disc_path.read_text(encoding='utf-8')
    except Exception:
        pass
tos_label, tos_url = _resolve_tos_url()
st.markdown(f'**By using this application, you acknowledge and agree to the [{tos_label}]({tos_url}).**')
st.subheader('Disclaimers & Notices')
st.markdown(disc_md)
st.divider()
with st.expander('Quick Tips', expanded=False):
    st.markdown('\n- Update data from the **00 — Data Diagnostics** page if something looks stale.\n- Place your logo at `serving_ui/app/assets/logo.png` (preferred). Other fallbacks: repo `logo.png` or `calculated_risk_logo.png`.\n- Set `EDGE_EXPORTS_DIR` if your exports live outside the repo.\n- Put your **DISCLAIMER.md** in `serving_ui/app/assets/` or set `EDGE_DISCLAIMER_PATH` to your file.\n- To control the Terms link, set **EDGE_TOS_URL** to your hosted page. If not set, the app will try local files and make a `file://` link.\n        '.strip())
st.caption('© Calculated Risk — Edge Finder')

