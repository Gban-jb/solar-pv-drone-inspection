"""Shared portal-inspired appearance for the Streamlit inspection pages."""

import streamlit as st


FIELD_BOOK_CSS = """
<style>
:root {
    --fb-canvas: light-dark(#f7f3ed, #150d14);
    --fb-surface: light-dark(#ffffff, #261923);
    --fb-ink: light-dark(#292029, #f8f3ef);
    --fb-muted: light-dark(#74686d, #c5b5b6);
    --fb-rule: light-dark(#ded4ce, #49343e);
    --fb-green: light-dark(#943f43, #efaa64);
    --fb-action: light-dark(#8d3c42, #b55a42);
    --fb-action-hover: light-dark(#712f37, #ca704c);
    --fb-hover: light-dark(#efe4dc, #392631);
    --fb-warm: light-dark(#aa5839, #efa865);
    --fb-find-rule: light-dark(#ede3df, #49343e);
    --fb-candidate: light-dark(#faeee4, #482a29);
}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background: var(--fb-canvas);
    color: var(--fb-ink);
}
.stApp, .stApp button, .stApp input, .stApp textarea {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.stApp [data-testid="stMainBlockContainer"] {
    max-width: 1320px;
    padding-top: 4.25rem;
    padding-bottom: 3rem;
}
.stApp h1, .stApp h2, .stApp h3 {
    color: var(--fb-ink);
    letter-spacing: -0.025em;
}
.stApp h1 { font-size: 2rem; font-weight: 700; margin-bottom: .3rem; }
.stApp h2, .stApp h3 { font-weight: 650; }
.stApp [data-testid="stCaptionContainer"], .stApp .stCaption,
.stApp [data-testid="stWidgetLabel"] p { color: var(--fb-muted); }
.fieldbook-brand {
    display: flex; align-items: center; justify-content: space-between;
    border-bottom: 1px solid var(--fb-rule);
    padding: .3rem 0 .95rem; margin-bottom: .35rem;
    gap: 1rem; min-width: 0;
    color: var(--fb-ink); font-size: .98rem; font-weight: 700;
}
.fieldbook-brand > span:first-child { min-width: 0; }
.fieldbook-brand .fb-mark { color: var(--fb-green); font-size: 1.3rem; margin-right: .45rem; }
.fieldbook-brand .fb-sub { color: var(--fb-muted); font-size: .8rem; font-weight: 400; }
.stApp .st-key-fieldbook-nav {
    border-bottom: 1px solid var(--fb-rule);
    padding-bottom: .35rem;
    margin-bottom: 1.1rem;
}
.stApp .st-key-fieldbook-nav a {
    border-radius: 0; border: 0;
    background: transparent; color: var(--fb-muted);
    padding: .45rem .65rem;
    font-size: .88rem; font-weight: 500;
}
.stApp .st-key-fieldbook-nav a:hover {
    background: var(--fb-hover); color: var(--fb-ink);
}
.stApp .st-key-fieldbook-nav a[aria-current="page"] {
    border-bottom: 2px solid var(--fb-green);
    color: var(--fb-green); background: transparent;
}
.stApp div.stButton > button, .stApp div.stDownloadButton > button {
    border-radius: 6px;
    border-color: var(--fb-rule);
    color: var(--fb-ink);
    background: var(--fb-surface);
    box-shadow: none;
    font-weight: 600;
}
.stApp div.stButton > button:hover, .stApp div.stDownloadButton > button:hover {
    border-color: var(--fb-green);
    color: var(--fb-green);
    background: var(--fb-hover);
}
.stApp div.stButton > button[kind="primary"],
.stApp div.stDownloadButton > button[kind="primary"] {
    background: var(--fb-action); border-color: var(--fb-action); color: white;
}
.stApp div.stButton > button[kind="primary"]:hover {
    background: var(--fb-action-hover); border-color: var(--fb-action-hover); color: white;
}
.stApp [data-testid="stExpander"] {
    background: var(--fb-surface);
    border: 1px solid var(--fb-rule);
    border-radius: 7px;
    box-shadow: none;
}
.stApp [data-testid="stMetric"] {
    background: var(--fb-surface);
    border: 1px solid var(--fb-rule);
    border-radius: 7px;
    padding: .85rem 1rem;
}
.stApp [data-testid="stMetricLabel"] { color: var(--fb-muted); }
.stApp [data-testid="stMetricValue"] { color: var(--fb-ink); }
.stApp [data-testid="stImage"] img {
    border-radius: 5px;
}
.stApp [data-testid="stDataFrame"] {
    border: 1px solid var(--fb-rule);
    border-radius: 7px;
    overflow: hidden;
}
.stApp input, .stApp textarea, .stApp [data-baseweb="select"] > div {
    border-color: var(--fb-rule);
    border-radius: 5px;
}
.stApp [data-testid="stAlert"] { border-radius: 6px; }
.fieldbook-image-label {
    margin: 0 0 .45rem;
    color: var(--fb-muted);
    font-size: .68rem; font-weight: 700; letter-spacing: .09em;
}
.fieldbook-findings {
    background: var(--fb-surface);
    border: 1px solid var(--fb-rule);
    border-radius: 7px;
    overflow: hidden;
}
.fieldbook-findings .fb-findings-head {
    display: flex; align-items: baseline; justify-content: space-between;
    padding: .8rem .95rem;
    font-weight: 700; color: var(--fb-ink);
    border-bottom: 1px solid var(--fb-rule);
}
.fieldbook-findings .fb-findings-head span {
    color: var(--fb-muted); font-size: .75rem; font-weight: 500;
}
.fieldbook-findings .fb-finding {
    padding: .75rem .95rem;
    border-bottom: 1px solid var(--fb-find-rule);
}
.fieldbook-findings .fb-finding:last-child { border-bottom: 0; }
.fieldbook-findings .fb-finding.candidate {
    background: var(--fb-candidate);
    border-left: 3px solid var(--fb-warm);
    padding-left: calc(.95rem - 3px);
}
.fieldbook-findings .fb-finding-top {
    display: flex; justify-content: space-between; gap: .5rem;
    font-weight: 650; font-size: .86rem;
}
.fieldbook-findings .fb-finding-top strong { color: var(--fb-warm); }
.fieldbook-findings .fb-finding p {
    margin: .25rem 0 0; color: var(--fb-muted); font-size: .78rem;
}
@media (max-width: 720px) {
    .fieldbook-brand .fb-sub { display: none; }
    .stApp .st-key-fieldbook-nav {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: .1rem .35rem;
    }
    .stApp .st-key-fieldbook-nav > div { min-width: 0; width: 100%; }
    .stApp .st-key-fieldbook-nav a {
        display: block;
        width: 100%;
        padding: .45rem .4rem;
        font-size: .78rem;
        white-space: normal;
    }
}

/* Reference portal: warm editorial accents and restrained grid texture. */
.stApp [data-testid="stMain"] {
    background-image: linear-gradient(light-dark(rgba(80,44,53,.035), rgba(240,180,140,.045)) 1px, transparent 1px), linear-gradient(90deg, light-dark(rgba(80,44,53,.035), rgba(240,180,140,.045)) 1px, transparent 1px);
    background-size: 54px 54px;
}
.stApp h1 { font-size: clamp(2.1rem, 4vw, 3.3rem); font-weight: 800; letter-spacing: -.045em; line-height: 1.05; }
.fieldbook-brand { border-image: linear-gradient(90deg, #68253f, #b74b42, #e9aa50) 1; padding-bottom: 1rem; }
.fieldbook-brand .fb-mark { display: inline-block; width: 1.4rem; height: 1.4rem; color: transparent; vertical-align: middle; background: linear-gradient(90deg,#63233b 25%,#aa3e41 25% 50%,#db7344 50% 75%,#eab357 75%); }
.stApp .st-key-fieldbook-nav a { transition: color .18s ease, background-color .18s ease, border-color .18s ease; }
.stApp div.stButton > button, .stApp div.stDownloadButton > button { transition: color .18s ease, background-color .18s ease, border-color .18s ease; }
@media (prefers-reduced-motion: reduce) { .stApp * { transition-duration: 0.01ms !important; animation-duration: 0.01ms !important; } }
</style>
"""


def apply_fieldbook_theme() -> None:
    st.markdown(FIELD_BOOK_CSS, unsafe_allow_html=True)
