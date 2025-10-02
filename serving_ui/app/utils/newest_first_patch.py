import pandas as pd

def apply_newest_first_patch(st, key: str='_nfp_newest_first'):
    if getattr(st, '__nfp_applied__', False):
        return
    _orig_df = st.dataframe
    if key not in st.session_state:
        st.session_state[key] = True
    st.toggle('Newest first', key=key, help='When a time column exists (sort_ts or ts), show newest rows first.')

    def _patched_dataframe(data, *args, **kwargs):
        try:
            df = data
            if isinstance(df, pd.DataFrame):
                col = 'sort_ts' if 'sort_ts' in df.columns else 'ts' if 'ts' in df.columns else None
                if col is not None:
                    df = df.copy()
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    newest_first = bool(st.session_state.get(key, True))
                    df = df.sort_values(col, ascending=not newest_first, na_position='last')
                    data = df
        except Exception:
            pass
        return _orig_df(data, *args, **kwargs)
    st.dataframe = _patched_dataframe
    st.__nfp_applied__ = True