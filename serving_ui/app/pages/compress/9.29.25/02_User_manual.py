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
import sys
from pathlib import Path
_HERE = Path(__file__).resolve()
_SERVING_UI = _HERE.parents[2]
if str(_SERVING_UI) not in sys.path:
    sys.path.insert(0, str(_SERVING_UI))
import io
from textwrap import dedent
try:
    from app.utils.diagnostics import mount_in_sidebar
except Exception:

    def mount_in_sidebar(_: str | None=None):
        return None
st.set_page_config(page_title='02 User manual', page_icon='📘', layout='wide')




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

mount_in_sidebar('02_User_manual')

def md(s: str):
    st.markdown(dedent(s), unsafe_allow_html=False)

def make_pdf_from_markdown(md_text: str) -> bytes | None:
    """Very simple PDF generation; install reportlab to enable."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
    except Exception:
        return None
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER
    left = 0.9 * inch
    top = height - 0.9 * inch
    line_height = 12
    max_chars = 95

    def draw_paragraph(text: str, y: float) -> float:
        for para_line in text.splitlines():
            line = para_line
            while len(line) > max_chars:
                c.drawString(left, y, line[:max_chars])
                y -= line_height
                line = line[max_chars:]
                if y < 0.9 * inch:
                    c.showPage()
                    y = height - 0.9 * inch
            c.drawString(left, y, line)
            y -= line_height
            if y < 0.9 * inch:
                c.showPage()
                y = height - 0.9 * inch
        y -= line_height
        if y < 0.9 * inch:
            c.showPage()
            y = height - 0.9 * inch
        return y
    c.setFont('Helvetica-Bold', 16)
    c.drawString(left, top, 'Edge Finder — User Manual')
    y = top - 24
    c.setFont('Helvetica', 10)
    y = draw_paragraph(MANUAL_MD, y)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
_MANUAL_LINES = ['# Edge Finder — User Manual', '', 'Edge Finder is a Streamlit toolkit for exploring betting opportunities, building/optimizing parlays, tracking wagers, and evaluating strategy over time. It reads CSV exports generated by your ETL pipeline and presents interactive pages to filter, optimize, record, and review bets.', '', '---', '', '## 1) Quick Start', '', '1. **Update data** via your ETL:', '   - `pull_stats.py`', '   - `pull_lines.py`', '2. **Verify exports exist** in `exports/`:', '   - `edges_graded_full.csv` (or normalized variant)', '   - `lines_live.csv`, `scores_*.csv`', '   - `bets_log.csv`', '3. **Launch the app**', '```bash', 'streamlit run serving_ui/app/Home.py --server.port 8501', '```', '', '---', '', '## 2) Pages Overview', '', '- **Data Diagnostics** — Validates presence/shape of exports.', '- **All Picks Explorer** — Filter by league/market/edge thresholds.', '- **Lines — Explorer** — Inspect open/close vs live lines by date/market/book.', '- **Backtest — Scores Browser** — Join edges ↔ scores; compute results.', '- **Parlay Builder** — Build legs; compute EV & payouts; save tickets.', '- **Parlay Scored Explorer** — Review settled legs and tickets.', '- **Micro Calculations — Locks & Moonshots** — Quick EV-positive singles and simple moonshot checks.', '- **Settled** — Reconciled results and summaries.', '- **User Manual** — This page.', '', '---', '', '## 3) Files & Folders', '', '- **Project root**: `C:\\Projects\\edge-finder\\`', '- **Exports**: `exports\\` — primary CSV outputs consumed by the app', '  - `edges_graded_full*.csv`', '  - `lines_live.csv`', '  - `scores_*.csv`', '  - `bets_log.csv`', '- **App**: `serving_ui\\app\\`', '  - `Home.py`', '  - `pages\\` — individual Streamlit pages', '  - `utils\\` — utilities (diagnostics, parlay_ui)', '  - `lib\\` — core helpers (io_paths, settlement, etc.)', '', '---', '', '## 4) Math Explainer — odds, probability, and EV', '', '### Decimal vs American odds', '- **Decimal** odds `d`: payout per $1 staked *including* stake.  ', '  Example: `d = 2.50` → win returns $2.50; profit = $1.50.', '- **American** odds `A`:', '  - `A > 0` (underdog): `d = 1 + A/100`  (e.g., +150 → 2.50)', '  - `A < 0` (favorite): `d = 1 + 100/|A|` (e.g., −200 → 1.50)', '', '### Implied probability', '- From decimal: `p_implied = 1 / d`', '- From American: convert to decimal first (above), then `1/d`.', '', '### Expected value (EV) per $1 stake (single-leg)', '- `EV = p * (d − 1) − (1 − p)`', '  - `p` = your model’s win probability', '  - `d` = decimal odds', '  - Interpretation: positive EV means the average profit per $1 is positive over the long run.', '', '### Parlays', '- **Parlay decimal odds**: multiply legs → `d_parlay = ∏ d_i`', '- **Parlay win probability** (assuming independence as a simplification): `p_parlay = ∏ p_i`', '- **Parlay EV per $1**: `EV_parlay = p_parlay * (d_parlay − 1) − (1 − p_parlay)`', '', '> Notes:', '> - Real legs are not fully independent (same-game correlations). Treat parlay EV as a *directional* estimate unless you explicitly model correlation.', '> - If you only have book odds (no model probability), `p = 1/d` describes the *break-even* probability under fair odds. Edge comes from `p_model − 1/d`.', '', '---', '', '## 5) Common Pitfalls', '', '- **“ImportError: numpy from source directory”**  ', '  Usually a chained error; fix the first SyntaxError on the failing page.', '- **Missing exports**  ', '  Diagnostics page shows exactly what’s missing.', '- **CSV encoding**  ', '  Save as UTF-8 (with BOM if opening in Excel on Windows).', '', '---', '', '## 6) Quick Recipes', '', '### Normalize Edges for Settlement', '```python', '# example only; adapt to your repo structure', 'from tools.lib_settle_normalize import normalize_edges_for_settlement', 'edges_norm = normalize_edges_for_settlement(edges, lines_live=live)', 'edges_norm.to_csv("exports/edges_graded_full_normalized.csv", index=False, encoding="utf-8-sig")', '```', '', '### Launch on a Free Port (Windows, PowerShell)', '```powershell', '$env:EDGE_SOURCE_FILE="C:\\Projects\\edge-finder\\exports\\edges_graded_full.csv"', 'python -m streamlit run serving_ui/app/Home.py --server.port 8501', '```', '', '---', '', '## 7) Support', 'If a page throws an error, open **Error Dashboard** or copy/paste the traceback with the page name and line number.']
MANUAL_MD = '\n'.join(_MANUAL_LINES)
st.title('📘 Edge Finder — User Manual')
with st.expander('View Manual', expanded=True):
    md(MANUAL_MD)
col1, col2 = st.columns(2)
with col1:
    st.download_button('Download as Markdown (.md)', MANUAL_MD.encode('utf-8'), file_name='edge_finder_user_manual.md', mime='text/markdown', width='stretch')
with col2:
    pdf_bytes = make_pdf_from_markdown(MANUAL_MD)
    if pdf_bytes:
        st.download_button('Download as PDF (.pdf)', pdf_bytes, file_name='edge_finder_user_manual.pdf', mime='application/pdf', width='stretch')
    else:
        st.caption('Install `reportlab` to enable PDF export.')







