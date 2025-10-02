from __future__ import annotations
import streamlit as st
from app.lib.auth import login, show_logout
import streamlit as st
from app.lib.auth import login, show_logout
auth = login(required=False)
if not auth.authenticated:
    st.info('You are in read-only mode.')
show_logout()
from __future__ import annotations
import streamlit as st
import sys
from pathlib import Path
_HERE = Path(__file__).resolve()
_SERVING_UI = _HERE.parents[2]
if str(_SERVING_UI) not in sys.path:
    sys.path.insert(0, str(_SERVING_UI))
st.set_page_config(page_title='96 Data Diagnostics', page_icon='📈', layout='wide')
import streamlit as st
import streamlit as st
import streamlit as st
import pandas as pd
import streamlit as st
from lib.io_paths import load_edges, load_scores
from lib.join_scores import attach_scores
try:
    from app.utils.diagnostics import mount_in_sidebar
except ModuleNotFoundError:
    try:
        import sys
        from pathlib import Path as _efP
        sys.path.append(str(_efP(__file__).resolve().parents[3]))
        from app.utils.diagnostics import mount_in_sidebar
    except Exception:
        try:
            from utils.diagnostics import mount_in_sidebar
        except Exception:

            def mount_in_sidebar(page_name: str):
                return None
st.title('Data Diagnostics — Date Alignment & Join')
edges = load_edges()
scores = load_scores()
for df in (edges, scores):
    for c in ['Season', 'Week']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').astype('Int64')
joined = attach_scores(edges.assign(HomeScore=pd.NA, AwayScore=pd.NA).copy(), scores.copy())
st.metric('Edges', len(edges))
st.metric('Scores', len(scores))
st.metric('Joined (has scores)', int(joined.get('_joined_with_scores', pd.Series([False] * len(joined))).sum()))
with st.expander('Join methods breakdown', expanded=False):
    if '_join_method' in joined.columns:
        st.dataframe(joined['_join_method'].value_counts(dropna=False))
    else:
        st.write('No _join_method column in joined.')