import platform, sys, os
import streamlit as st
import pandas as pd
st.set_page_config(page_title='Diagnostics', layout='wide')
st.title('Diagnostics')
st.write({'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(), 'cwd': os.getcwd()})
st.subheader('Sanity DataFrame')
st.dataframe(pd.DataFrame({'a': [1, 2, 3], 'b': [4, 5, 6]}))