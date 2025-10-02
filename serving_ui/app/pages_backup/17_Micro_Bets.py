import sys as _sys
from pathlib import Path as _Path
try:
    _ROOT = _Path(__file__).resolve().parents[2]
    _REPO = _ROOT.parents[1]
    if str(_REPO) not in _sys.path:
        _sys.path.insert(0, str(_REPO))
except Exception:
    pass
import sys
from pathlib import Path
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from app.utils.logger import log_error
import streamlit as st
try:
    from app.utils.logger import log_error
    try:
        from app.bootstrap import bootstrap_paths
        bootstrap_paths()
        import streamlit as st
        import pandas as pd
        from pathlib import Path
        import subprocess, sys
        ROOT = Path(__file__).resolve().parents[2]
        OUT = ROOT / 'exports' / 'micro_bets.csv'
        LOG = ROOT / 'exports' / 'bets_log.csv'
        st.set_page_config(page_title='Calculated Risk ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â\x9d Micro Calculations', layout='wide')
        st.title('Micro Calculations ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â\x9d Locks & Moonshots')
        st.caption('Locks: singles p_win > 0.65 with EV ÃƒÂ¢Ã¢â‚¬Â°Ã‚Â¥ 0 (stake 0.5u).  Moonshots: parlay odds ÃƒÂ¢Ã¢â‚¬Â°Ã‚Â¥ +1500 with positive EV (stake 0.5u).')
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            locks_p = st.slider('Locks min p', 0.55, 0.8, 0.65, 0.01)
        with c2:
            moon_min = st.number_input('Moonshots min odds (+)', 1000, 5000, 1500, 100)
        with c3:
            moon_legs = st.selectbox('Moonshot legs', [3, 4, 5], index=1)
        with c4:
            topn = st.number_input('Max per section', 1, 10, 5, 1)
        if st.button('Generate Micro Calculations'):
            cmd = [sys.executable, str(ROOT / 'serving' / 'micro_bets.py'), '--locks-min-p', str(float(locks_p)), '--moon-min-amer', str(int(moon_min)), '--moon-legs', str(int(moon_legs)), '--moon-max', str(int(topn))]
            cp = subprocess.run(cmd, capture_output=True, text=True)
            st.code(cp.stdout or '', language='bash')
            if cp.stderr:
                st.error(cp.stderr)
        if OUT.exists():
            df = pd.read_csv(OUT)
            if len(df) == 0:
                st.info('No Micro Calculations yet. Click the button above.')
            else:
                st.subheader('Locks')
                locks = df[df['section'] == 'locks'].copy()
                if not locks.empty:
                    show_cols = [c for c in ['market', 'ref', 'side', 'line', 'odds', 'p_win', 'ev', 'stake'] if c in locks.columns]
                    st.dataframe(locks[show_cols], width='stretch')
                else:
                    st.caption('No locks found for the current threshnews.')
                st.subheader('Moonshots')
                moons = df[df['section'] == 'moonshots'].copy()
                if not moons.empty:
                    st.dataframe(moons[['legs', 'american', 'p_combo', 'ev_est', 'stake', 'legs_json']], width='stretch')
                else:
                    st.caption('No moonshots for the current threshnews.')
                if st.button('Log both sections to Calculated History (beta-open)'):
                    cmd = [sys.executable, str(ROOT / 'serving' / 'micro_bets.py'), '--log', '--tag', 'micro_ui']
                    cp = subprocess.run(cmd, capture_output=True, text=True)
                    st.success(f'Logged to {LOG}')
        else:
            st.info('No micro_bets.csv yet. Generate first.')
    except Exception as e:
        log_error(e, context=__file__)
        st.error(f'Page error: {e}')
except Exception as e:
    try:
        log_error(e, context=__file__)
    except Exception:
        pass
    try:
        st.error(f'Page error: {e}')
    except Exception:
        print(f'Page error: {e}')
