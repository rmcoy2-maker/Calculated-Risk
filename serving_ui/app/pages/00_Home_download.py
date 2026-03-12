import streamlit as st

st.set_page_config(
    page_title="Doc Odds Launcher",
    page_icon="🎯",
    layout="wide"
)

# ---------------- HEADER ----------------
st.title("🎯 Doc Odds – App Launcher")
st.markdown("""
### Your Home Base for All CR Tools  
This page loads correctly and confirms your Streamlit deployment is working.  
""")

st.divider()

# ---------------- BUTTONS ----------------
st.header("Available Tools")

col1, col2 = st.columns(2)

with col1:
    st.subheader("📊 Edge Finder Engine")
    st.write("Main analytics & betting-model interface.")
    st.button("Open Edge Finder (Coming Soon)")

with col2:
    st.subheader("🤖 Doc Odds Chat Assistant")
    st.write("AI assistant for CR explanations, analytics, and coaching.")
    st.button("Launch Chat Bot (Coming Soon)")

st.divider()

# ---------------- FOOTER ----------------
st.markdown("""
#### Deployment Status  
Everything is running!  
Now you can upload your full app code when ready.
""")