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


import streamlit as st
auth = login(required=False)
if not auth.authenticated:
    st.info('You are in read-only mode.')
show_logout()
from textwrap import dedent
import json
from pathlib import Path
try:
    from app.bootstrap import bootstrap_paths
    bootstrap_paths()
except Exception:
    pass
st.title('Help / User Guide')

def md(s: str):
    st.markdown(dedent(s), unsafe_allow_html=False)

def latex(s: str):
    st.latex(s)
MANUAL_MD = dedent('\n# Edge Finder â€“ User Manual\n\n## 1) General Overview\nEdge Finder is a Streamlit toolkit for exploring betting opportunities, simulating parlays, and tracking wagers. It reads CSV exports and presents interactive pages for filtering, optimizing, and recording bets.\n\n**Key files**\n- `exports/edges.csv` â€” single-leg edges produced by your ETL (e.g., `pull_stats.py`, `pull_lines.py`).\n- `exports/bets_log.csv` â€” master bet ledger, appended by multiple pages.\n- `exports/hedge_candidates.csv` â€” candidate rows for hedge analysis.\n\n---\n\n## 2) Pages & Workflows\n\n### Hub (`00_Hub.py`)\nNavigation only.\n\n### Edge Scanner (`15_Edge_Scanner.py`)\n**Purpose:** Identify single-leg edges where model probability beats the price.\n\n**Inputs & controls**\n- Reads `edges.csv`.\n- Sidebar filters: minimum win probability, odds range, distinct games only, top-K cap.\n\n**Outputs**\n- Filtered edges table.\n- Action: append selected edges to `bets_log.csv`.\n\n### Ghost Parlay Calculator (`08_Ghost_Parlay_Calc.py`)\n**Purpose:** Build parlays and then â€œghost optimizeâ€\x9d by dropping weak legs to improve EV.\n\n**Key sidebar controls**\n- Max legs, Min leg win probability.\n- Min |odds| (exclude heavy favorites if desired).\n- Distinct games only (avoid correlated legs).\n- ROI% / Kelly thresholds and Top-N display.\n\n**Workflow**\n1. Click **Generate Ghost Parlays**.\n2. Review results table (odds, EV, ROI, Kelly).\n3. In **Select parlays to add to Calculated Log**, choose parlays, set Stake/Book/Notes, click **Add selected to Calculated Log**.\n\n### Calculated Log (`06_Bet_Log.py`)\n**Purpose:** Central ledger of all wagers.\n\n**Inputs & actions**\n- Reads/writes `bets_log.csv`.\n- Add bets via UI or from other pages.\n- Add notes.\n\n**Outputs**\n- Full table (ts, game_id/market/side/odds/stake/p_win/EV/book/notes).\n- Good for backtesting and bankroll rollups.\n\n### Bankroll Tracker (`04_Bankroll_Tracker.py`)\n**Purpose:** Monitor bankroll performance.\n\n**Inputs**\n- Reads `bets_log.csv`, filter by date/book/stake.\n\n**Outputs**\n- ROI, cumulative P/L, weekly/monthly views.\n\n### Backtest (`03_Backt est.py`)\n**Purpose:** Simulate historical performance.\n\n**Inputs**\n- `edges.csv` + historical outcomes.\n- Choose seasons/weeks and stake strategy (flat, Kelly, fractional).\n\n**Outputs**\n- Equity curves, ROI by season/week.\n\n### Hedge Finder (`16_Hedge_Finder.py`)\n**Purpose:** Find profitable hedges across books.\n\n**Inputs**\n- `hedge_candidates.csv` + filters for min ROI, spreads, etc.\n\n**Outputs**\n- Hedge opportunities and stake splits.\n\n---\n\n## 3) Metrics & Formulas\n\n### Expected Value (EV)\nPer-unit EV:\n\\[\nEV = p_{win} \\cdot (D - 1) - (1 - p_{win})\n\\]\nwhere \\( D \\) is decimal odds and \\(p_{win}\\) is the event probability.\n\nInterpretation: average profit per 1 unit staked. \\(EV > 0\\) is favorable in the long run.\n\n### ROI (Return on Investment)\n\\[\nROI = \\frac{EV}{\\text{stake}}\n\\]\nOften shown as a percent. Example: \\(EV = 0.10\\), stake \\(=1.0 \\Rightarrow ROI = 10\\%\\).\n\n### Kelly Fraction\nOptimal bankroll fraction for growth:\n\\[\nf^\\* = \\frac{b p - q}{b}, \\quad b = D - 1,\\; p = p_{win},\\; q = 1 - p\n\\]\n- If \\(f^\\* \\le 0\\): do not bet.\n- Many use half-Kelly or quarter-Kelly to reduce variance.\n\n### American â†” Decimal Odds\n\\[\nD =\n\\begin{cases}\n1 + \\frac{A}{100} & \\text{if } A > 0 \\\\\n1 + \\frac{100}{|A|} & \\text{if } A < 0\n\\end{cases}\n\\]\nand convert back accordingly.\n\n### Ghost Optimization (intuitive)\nStart with a parlay; if removing any single leg increases EV, drop it. Repeat until no single removal helps. This avoids â€œdead weightâ€\x9d legs.\n\n### Distinct Games Filter\nBlocks correlated legs (e.g., Team ML + Team spread) to prevent overstated combined probability.\n\n---\n\n## 4) Practical Workflow\n\n1. **Update data** (ETL: `pull_stats.py`, `pull_lines.py`).\n2. **Scan edges** in Edge Scanner.\n3. **Build parlays** in Ghost Parlay.\n4. **Append to log** via Ghost Parlay or Calculated Log.\n5. **Track bankroll** in Bankroll Tracker.\n6. **Backtest** strategy variants.\n7. **Explore hedges** when available.\n\n---\n\n## 5) Troubleshooting\n\n- **No parlays appear**  \n  Either `edges.csv` is empty or filters are too strict. Loosen min probability/odds and uncheck Distinct Games only to test; confirm `edges.csv` has rows.\n\n- **Buttons clear the table**  \n  Streamlit reruns pages on interaction. Persist results using `st.session_state` (the Ghost Parlay page in this repo already does this).\n\n- **`experimental_rerun` error**  \n  Newer Streamlit uses `st.rerun()`.\n\n- **Data not saving**  \n  Ensure `exports/` exists; create it if missing. Pages will create `bets_log.csv` when first saving.\n\n- **Weird characters (mojibake)**  \n  Save source files as UTF-8; prefer plain ASCII for button labels.\n\n---\n').strip('\n')
sections = ['Overview', 'Pages & Workflows', 'Metrics & Formulas', 'Practical Workflow', 'Troubleshooting', 'Download Manual']
choice = st.sidebar.radio('Jump to section', sections, index=0, key='guide_section')
if choice == 'Overview':
    md('\n'.join(MANUAL_MD.split('\n')[0:40]))
elif choice == 'Pages & Workflows':
    start = MANUAL_MD.find('## 2) Pages & Workflows')
    end = MANUAL_MD.find('## 3) Metrics & Formulas')
    md(MANUAL_MD[start:end])
elif choice == 'Metrics & Formulas':
    md('### Expected Value (EV)')
    latex('EV = p_{win} \\cdot (D - 1) - (1 - p_{win})')
    md('Where `D` is decimal odds.')
    md('### ROI (Return on Investment)')
    latex('ROI = \\frac{EV}{\\text{stake}}')
    md('### Kelly Fraction')
    latex('f^\\* = \\frac{b p - q}{b}, \\quad b=D-1,\\; p = p_{win},\\; q=1-p')
    md('### American â†” Decimal Odds')
    latex('D = 1 + \\frac{A}{100}\\ \\text{if}\\ A>0;\\quad D = 1 + \\frac{100}{|A|}\\ \\text{if}\\ A<0')
    md('### Ghost Optimization & Distinct Games')
    md('Greedy leg-dropping to improve EV; distinct-games prevents correlated legs.')
elif choice == 'Practical Workflow':
    start = MANUAL_MD.find('## 4) Practical Workflow')
    end = MANUAL_MD.find('## 5) Troubleshooting')
    md(MANUAL_MD[start:end])
elif choice == 'Troubleshooting':
    start = MANUAL_MD.find('## 5) Troubleshooting')
    md(MANUAL_MD[start:])
else:
    st.download_button(label='Download Manual (Markdown)', data=MANUAL_MD.encode('utf-8'), file_name='USER_MANUAL.md', mime='text/markdown', width='stretch')
st.divider()
t1, t2, t3, t4, t5 = st.tabs(['Overview', 'Pages', 'Metrics', 'Workflow', 'Troubleshooting'])
with t1:
    md(MANUAL_MD.split('---')[0])
with t2:
    start = MANUAL_MD.find('## 2) Pages & Workflows')
    end = MANUAL_MD.find('## 3) Metrics & Formulas')
    md(MANUAL_MD[start:end])
with t3:
    st.write('Formulas rendered with LaTeX:')
    latex('EV = p_{win} \\cdot (D - 1) - (1 - p_{win})')
    latex('ROI = \\frac{EV}{\\text{stake}}')
    latex('f^\\* = \\frac{b p - q}{b},\\quad b = D - 1,\\; p = p_{win},\\; q = 1 - p')
    latex('D = 1 + \\frac{A}{100}\\ (A>0),\\quad D = 1 + \\frac{100}{|A|}\\ (A<0)')
with t4:
    start = MANUAL_MD.find('## 4) Practical Workflow')
    end = MANUAL_MD.find('## 5) Troubleshooting')
    md(MANUAL_MD[start:end])
with t5:
    start = MANUAL_MD.find('## 5) Troubleshooting')
    md(MANUAL_MD[start:])

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


