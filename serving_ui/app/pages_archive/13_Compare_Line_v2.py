import streamlit as st
from app.lib.odds_utils import compare_prices
st.set_page_config(page_title='Compare Lines', layout='wide')
st.title('Compare Lines')
col = st.columns(3)
with col[0]:
    a = st.number_input('Book A Odds (American)', value=-110, step=5)
with col[1]:
    b = st.number_input('Book B Odds (American)', value=-105, step=5)
with col[2]:
    st.caption('Which is the better price (same side)?')
if st.button('Compare'):
    best, diff = compare_prices(int(a), int(b))
    st.success(f'**Book {best}** is better by **{diff * 100:.2f} pp** of implied probability.')
    st.info('Tip: Smaller implied probability = better payout for the same outcome.')