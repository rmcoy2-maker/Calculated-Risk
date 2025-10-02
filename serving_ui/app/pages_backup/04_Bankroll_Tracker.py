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
import sys, math, datetime as dt
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
EXPORTS = ROOT / 'exports'
EXPORTS.mkdir(parents=True, exist_ok=True)
BANKROLL_CSV = EXPORTS / 'bankroll.csv'

def _read_csv_safe(p: Path) -> pd.DataFrame:
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame()
    for enc in (None, 'utf-8', 'utf-8-sig'):
        try:
            return pd.read_csv(p, encoding=enc) if enc else pd.read_csv(p)
        except Exception:
            continue
    return pd.DataFrame()

def _to_datetime_series(s: pd.Series) -> pd.Series:
    s_num = pd.to_numeric(s, errors='coerce')
    if s_num.notna().any():
        epoch_ms = s_num > 100000000000.0
        dt_vals = pd.to_datetime(np.where(epoch_ms, s_num, s_num * 1000.0), errors='coerce', unit='ms', utc=True).tz_convert(None)
        if dt_vals.notna().sum() == 0:
            dt_vals = pd.to_datetime(s, errors='coerce')
        return dt_vals
    return pd.to_datetime(s, errors='coerce')

def _prep_bankroll(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=['date', 'bankroll', 'note', 'tag'])
    d = df.copy()
    d.columns = [str(c).strip().lower() for c in d.columns]
    date_candidates = ['date', 'placed_at', 'ts', 'timestamp', 'time']
    date_col = next((c for c in date_candidates if c in d.columns), None)
    if date_col is None:
        if isinstance(d.index, pd.DatetimeIndex):
            d['date'] = d.index.tz_localize(None)
        else:
            for c in d.columns:
                try_dt = pd.to_datetime(d[c], errors='coerce')
                if try_dt.notna().any():
                    d['date'] = try_dt
                    break
            if 'date' not in d.columns:
                d['date'] = pd.Timestamp.today().normalize()
    else:
        d['date'] = _to_datetime_series(d[date_col])
    for col in ['bankroll', 'note', 'tag']:
        if col not in d.columns:
            d[col] = None
    d['bankroll'] = pd.to_numeric(d['bankroll'], errors='coerce')
    d = d.dropna(subset=['date'])
    if d['bankroll'].notna().sum() == 0:
        return d[['date', 'bankroll', 'note', 'tag']].iloc[0:0]
    d = d.sort_values('date').drop_duplicates(subset=['date'], keep='last')
    d['daily_change'] = d['bankroll'].diff()
    return d[['date', 'bankroll', 'daily_change', 'note', 'tag']]

def _drawdown(curve: pd.Series) -> pd.Series:
    running_max = curve.cummax()
    return curve - running_max
st.set_page_config(page_title='Bankroll Tracker', layout='wide')
st.title('ðŸ’° Bankroll Tracker')
df_raw = _read_csv_safe(BANKROLL_CSV)
df = _prep_bankroll(df_raw)
if df.empty:
    st.warning(f'No bankroll data found at: {BANKROLL_CSV}')
    st.caption('Tip: create exports/bankroll.csv with columns like: date, bankroll, note')
else:
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values('date')
    df['date_only'] = df['date'].dt.date
    latest = df.iloc[-1]
    now_val = float(latest['bankroll'])

    def _change_since(days: int) -> float | None:
        cutoff = latest['date'] - pd.Timedelta(days=days)
        past = df[df['date'] <= cutoff]
        if past.empty:
            return None
        past_val = float(past.iloc[-1]['bankroll'])
        return now_val - past_val
    delta_7 = _change_since(7)
    delta_30 = _change_since(30)
    dd = _drawdown(df['bankroll'])
    max_dd = float(dd.min()) if not dd.empty else 0.0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric('Current bankroll', f'{now_val:,.2f}')
    c2.metric('Change (7d)', f'{delta_7 or 0:+.2f}')
    c3.metric('Change (30d)', f'{delta_30 or 0:+.2f}')
    c4.metric('Max drawdown', f'{max_dd:,.2f}')
    st.subheader('Bankroll over time')
    st.line_chart(df.set_index('date')['bankroll'], width='stretch')
    st.subheader('Daily changes')
    st.bar_chart(df.set_index('date')['daily_change'].fillna(0.0), width='stretch')
    st.subheader('History')
    show_cols = ['date', 'bankroll', 'daily_change', 'note', 'tag']
    st.dataframe(df[show_cols], hide_index=True, width='stretch')