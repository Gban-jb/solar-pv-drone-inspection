"""Single browser entry point for the inspection prototype."""

from pathlib import Path

import streamlit as st

from solar_pv.ui.theme import apply_fieldbook_theme


UI_DIR = Path(__file__).resolve().parent

inventory = st.Page(UI_DIR / "inventory.py", title="Inspection inventory", url_path="inventory", default=True)
intake = st.Page(UI_DIR / "intake.py", title="New inspection", url_path="intake")
annotations = st.Page(UI_DIR / "annotator.py", title="Panel annotations", url_path="annotations")
thermal = st.Page(UI_DIR / "thermal.py", title="Thermal review", url_path="thermal")
review = st.Page(UI_DIR / "review.py", title="Inspection review", url_path="review")
meter = st.Page(UI_DIR / "meter.py", title="Meter data", url_path="meter")
site_layout = st.Page(UI_DIR / "site_layout.py", title="Solar Farm Map", url_path="site-layout")
page = st.navigation([inventory, intake, annotations, thermal, review, meter, site_layout], position="hidden")

apply_fieldbook_theme()
st.markdown(
    '<div class="fieldbook-brand"><span><span class="fb-mark">▦</span>'
    'Solar inspection <span class="fb-sub">/ AAMU inspection workspace</span></span>'
    '<span class="fb-sub">Sudin Pokharel</span></div>',
    unsafe_allow_html=True,
)
with st.container(horizontal=True, gap="small", key="fieldbook-nav"):
    st.page_link(inventory, label="Inspection inventory")
    st.page_link(intake, label="New inspection")
    st.page_link(annotations, label="Panel annotations")
    st.page_link(thermal, label="Thermal review")
    st.page_link(review, label="Inspection review")
    st.page_link(meter, label="Meter data")
    st.page_link(site_layout, label="Solar Farm Map")

page.run()
