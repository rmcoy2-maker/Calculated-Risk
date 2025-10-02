from app.bootstrap import bootstrap_paths
bootstrap_paths()
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
        import streamlit as st, pandas as pd
        from pathlib import Path
        ROOT = Path(__file__).resolve().parents[2]
        BETLOG = ROOT / 'exports' / 'bets_log.csv'
        st.set_page_config(page_title='Calculated History', layout='wide')
        st.title('ðŸ“œ Calculated History')
        if BETLOG.exists():
            st.dataframe(pd.read_csv(BETLOG), width='stretch')
        else:
            st.info('No Calculated Log found yet.')
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
