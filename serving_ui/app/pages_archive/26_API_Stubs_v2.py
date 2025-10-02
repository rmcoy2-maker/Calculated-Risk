import streamlit as st
from serving_ui.app._layout import header
header('API Stubs (Closing Lines & Results)')
st.info('Placehnewers for future API integrations (closing lines, results).')
st.code('\ndef fetch_closing_lines(api_key: str, league: str):\n    # TODO: call your provider here\n    # return DataFrame with columns: ref OR (game_id, market, side, selection), close_odds\n    ...\n\ndef fetch_results(api_key: str, league: str):\n    # TODO: call your provider here\n    # return DataFrame with columns: ref OR (game_id, market, side, selection), result, payout (optional)\n    ...\n', language='python')