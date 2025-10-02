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
import sys
from pathlib import Path
_HERE = Path(__file__).resolve()
_SERVING_UI = _HERE.parents[2]
if str(_SERVING_UI) not in sys.path:
    sys.path.insert(0, str(_SERVING_UI))
import streamlit as st
st.set_page_config(page_title='94 Legal Terms Privacy', page_icon='📈', layout='wide')
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
import io
from textwrap import dedent
from pathlib import Path
import datetime as _dt
import streamlit as st
APP_NAME = 'Edge Finder'
ORG_NAME = 'Calculated Risk'
CONTACT_EMAIL = 'support@example.com'
CONTACT_ADDRESS = '123 Example St, Lexington, KY 40502, USA'
import streamlit as st
st.title('⚖️ Legal')
TODAY = _dt.date.today().strftime('%B %d, %Y')

def md(s: str):
    st.markdown(dedent(s), unsafe_allow_html=False)

def make_pdf_from_markdown(md_text: str) -> bytes | None:
    """Create a lightweight PDF (if reportlab is installed)."""
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=LETTER)
        W, H = LETTER
        L = 0.9 * inch
        T = H - 0.9 * inch
        lh = 12
        max_chars = 95
        c.setFont('Helvetica-Bold', 14)
        c.drawString(L, T, f'{APP_NAME} — Legal')
        y = T - 20
        c.setFont('Helvetica', 10)
        for line in md_text.splitlines():
            if not line.strip():
                y -= lh
            else:
                while len(line) > max_chars:
                    c.drawString(L, y, line[:max_chars])
                    y -= lh
                    line = line[max_chars:]
                    if y < 0.9 * inch:
                        c.showPage()
                        c.setFont('Helvetica', 10)
                        y = T
                c.drawString(L, y, line)
                y -= lh
            if y < 0.9 * inch:
                c.showPage()
                c.setFont('Helvetica', 10)
                y = T
        c.showPage()
        c.save()
        buf.seek(0)
        return buf.read()
    except Exception:
        return None
TERMS_MD = dedent(f'\n# Terms of Service\n**Effective Date:** {TODAY}  \n**Applies to:** {APP_NAME} by {ORG_NAME}\n\n## 1. Acceptance of Terms\nBy accessing or using {APP_NAME} (the “Service”), you agree to be bound by these Terms of Service (“Terms”). If you do not agree, do not use the Service.\n\n## 2. Eligibility & Responsible Use\nYou must be at least 21 years old (or the legal age for wagering in your jurisdiction) to use features related to betting analysis. You are responsible for complying with all applicable laws and regulations in your location.\n\n## 3. No Financial or Betting Advice\n{APP_NAME} provides **informational and educational** analytics only. Nothing in the Service constitutes financial, investment, or betting advice. Past performance does not guarantee future results. You assume full responsibility for decisions you make.\n\n## 4. Accounts & Security\nIf the Service allows user accounts, you are responsible for safeguarding credentials and for all activity under your account. Notify us promptly at {CONTACT_EMAIL} of any unauthorized use.\n\n## 5. Data Sources & Availability\nThe Service may rely on third-party data feeds and public or proprietary datasets. We do not warrant the accuracy, completeness, timeliness, or availability of any data or the Service itself and may change or discontinue features at any time.\n\n## 6. Acceptable Use\nYou agree not to:\n- Reverse engineer, scrape at scale without permission, or circumvent security controls.\n- Upload malware or content that is unlawful, infringing, or harmful.\n- Use the Service in violation of applicable law or third-party rights.\n\n## 7. Intellectual Property\nAll content, features, and functionality of the Service are owned by {ORG_NAME} or its licensors and are protected by applicable IP laws. You receive a limited, non-exclusive, non-transferable license to use the Service for personal, non-commercial purposes (unless otherwise agreed in writing).\n\n## 8. Paid Features (if any)\nFees (if charged) are due as stated at purchase. Except where required by law, payments are non-refundable. We may change pricing with notice for future billing cycles.\n\n## 9. Third-Party Services\nThe Service may link to third-party sites or integrate third-party services (e.g., sportsbooks, analytics). We are not responsible for their content, policies, or practices.\n\n## 10. Disclaimers\nTHE SERVICE IS PROVIDED “AS IS” AND “AS AVAILABLE.” TO THE MAXIMUM EXTENT PERMITTED BY LAW, {ORG_NAME} DISCLAIMS ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.\n\n## 11. Limitation of Liability\nTO THE MAXIMUM EXTENT PERMITTED BY LAW, {ORG_NAME} AND ITS AFFILIATES, OFFICERS, EMPLOYEES, AND AGENTS SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS, REVENUE, DATA, OR GOODWILL, ARISING FROM OR RELATED TO YOUR USE OF THE SERVICE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. OUR TOTAL LIABILITY SHALL NOT EXCEED THE AMOUNT YOU PAID FOR THE SERVICE IN THE 3 MONTHS PRECEDING THE CLAIM (OR USD $100 IF NO FEES WERE PAID).\n\n## 12. Indemnification\nYou agree to indemnify and hold harmless {ORG_NAME} from any claims, losses, or expenses (including reasonable attorneys’ fees) arising out of your use of the Service or violation of these Terms.\n\n## 13. Changes to the Service or Terms\nWe may modify or discontinue the Service or update these Terms at any time. Material changes will be posted in-app or via reasonable notice. Continued use after changes constitutes acceptance.\n\n## 14. Termination\nWe may suspend or terminate your access at any time, with or without notice, for any reason, including breach of these Terms.\n\n## 15. Governing Law & Dispute Resolution\nThese Terms are governed by the laws of the Commonwealth of Kentucky and applicable U.S. federal law, without regard to conflict-of-laws rules. You agree to the exclusive jurisdiction and venue of state and federal courts located in Fayette County, Kentucky.\n\n## 16. Contact\nQuestions about these Terms? Contact us at **{CONTACT_EMAIL}** or mail **{CONTACT_ADDRESS}**.\n').strip()
PRIVACY_MD = dedent(f'\n# Privacy Policy\n**Effective Date:** {TODAY}  \n**Applies to:** {APP_NAME} by {ORG_NAME}\n\n## 1. Overview\nThis Privacy Policy explains what information we collect, how we use it, and your choices. By using {APP_NAME}, you agree to the practices described here.\n\n## 2. Information We Collect\n- **Account & Contact Data:** name, email, and any details you provide when contacting support.\n- **Usage Data:** app interactions, page views, diagnostic logs, device and browser information.\n- **Files & Inputs:** CSV uploads or data you load into the app.\n- **Cookies & Local Storage:** used to maintain sessions, preferences, and improve functionality.\n\n## 3. How We Use Information\n- To operate, maintain, and improve the Service.\n- To provide support and respond to inquiries.\n- To analyze performance and develop new features.\n- To enforce Terms, prevent abuse, and ensure security.\n\n## 4. Processing Bases\nWhere required, we rely on one or more legal bases: your consent, contractual necessity, legitimate interests (e.g., security, analytics), or compliance with legal obligations.\n\n## 5. Sharing & Disclosure\nWe do not sell your personal information. We may share information with:\n- **Service Providers** who help us operate the Service (e.g., hosting, analytics) under appropriate confidentiality and security commitments.\n- **Legal & Safety** when required by law, regulation, or to protect rights, safety, and integrity.\n- **Business Transfers** in connection with a merger, acquisition, or asset sale.\n\n## 6. Data Retention\nWe retain information as long as necessary for the purposes described above or as required by law. We may anonymize or aggregate data for longer-term analytics.\n\n## 7. Security\nWe use reasonable administrative, technical, and physical safeguards to protect information. No method of transmission or storage is 100% secure.\n\n## 8. Your Choices & Rights\n- **Access/Correction/Deletion:** contact **{CONTACT_EMAIL}** to request.\n- **Email Preferences:** you can opt out of non-essential emails.\n- **Cookies:** you can control cookies via browser settings; some features may not function without them.\n- **Do Not Track:** we do not respond to DNT signals at this time.\n\n## 9. Children’s Privacy\nThe Service is not directed to children under 13 (or under 16 in some regions). We do not knowingly collect personal data from children.\n\n## 10. International Users\nIf you access the Service from outside the U.S., you consent to processing in the U.S., where laws may differ from those in your country.\n\n## 11. Changes to this Policy\nWe may update this Policy. Material changes will be posted in-app or via reasonable notice. Your continued use constitutes acceptance.\n\n## 12. Contact\nFor privacy questions or requests, contact **{CONTACT_EMAIL}** or mail **{CONTACT_ADDRESS}**.\n').strip()
st.sidebar.link_button('Terms of Service', '#terms-of-service', width='stretch')
st.sidebar.link_button('Privacy Policy', '#privacy-policy', width='stretch')
t_terms, t_priv = st.tabs(['Terms of Service', 'Privacy Policy'])
with t_terms:
    md(TERMS_MD)
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.download_button('⬇️ Download Terms (Markdown)', data=TERMS_MD.encode('utf-8'), file_name=f"{APP_NAME.replace(' ', '_')}_Terms_of_Service.md", mime='text/markdown', width='stretch')
    with c2:
        pdf_bytes = make_pdf_from_markdown(TERMS_MD)
        if pdf_bytes:
            st.download_button('⬇️ Download Terms (PDF)', data=pdf_bytes, file_name=f"{APP_NAME.replace(' ', '_')}_Terms_of_Service.pdf", mime='application/pdf', width='stretch')
        else:
            st.info('Install **reportlab** for PDF export: `pip install reportlab`', icon='ℹ️')
with t_priv:
    md(PRIVACY_MD)
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.download_button('⬇️ Download Privacy (Markdown)', data=PRIVACY_MD.encode('utf-8'), file_name=f"{APP_NAME.replace(' ', '_')}_Privacy_Policy.md", mime='text/markdown', width='stretch')
    with c2:
        pdf_bytes = make_pdf_from_markdown(PRIVACY_MD)
        if pdf_bytes:
            st.download_button('⬇️ Download Privacy (PDF)', data=pdf_bytes, file_name=f"{APP_NAME.replace(' ', '_')}_Privacy_Policy.pdf", mime='application/pdf', width='stretch')
        else:
            st.info('Install **reportlab** for PDF export: `pip install reportlab`', icon='ℹ️')
st.divider()
st.caption(f'© {ORG_NAME} — {APP_NAME}. This page is generic boilerplate and not legal advice.')