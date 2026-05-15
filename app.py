"""
Pit Wall Dashboard — FastF1 + Streamlit
Visualise lap telemetry for any F1 session since 2018.
"""

import os
import warnings
import streamlit as st
import streamlit.components.v1 as components
import fastf1
import fastf1.plotting
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np
import plotly.graph_objects as go

warnings.filterwarnings("ignore")

# ── FastF1 cache ──────────────────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🏎  Pit Wall — F1 Telemetry",
    page_icon="🏎",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Progressive Web App (PWA) Injection ───────────────────────────────────────
# Streamlit does not expose the raw <head> for static file handling in Community Cloud.
# We bypass this by injecting an invisible HTML component snippet that constructs and
# attaches a Blob URL Web Manifest alongside iOS specific meta tags so mobile devices
# can "Add to Home Screen" as a standalone app.
components.html(
    """
    <script>
        const manifestObj = {
            "name": "Pit Wall Telemetry",
            "short_name": "Pit Wall",
            "start_url": ".",
            "display": "standalone",
            "background_color": "#000000",
            "theme_color": "#FF8700",
            "icons": [{
                "src": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48dGV4dCB5PSIuOWVtIiBmb250LXNpemU9IjkwIj7🏎PC90ZXh0Pjwvc3ZnPg==",
                "sizes": "192x192",
                "type": "image/svg+xml"
            }]
        };
        
        // Generate Blob URL
        const blob = new Blob([JSON.stringify(manifestObj)], {type: 'application/json'});
        const manifestUrl = URL.createObjectURL(blob);
        
        // Locate parent document to break out of iframe
        const parentDoc = window.parent.document;
        
        // Inject Manifest Link
        if (!parentDoc.querySelector('link[rel="manifest"]')) {
            const manifestLink = parentDoc.createElement('link');
            manifestLink.rel = 'manifest';
            manifestLink.href = manifestUrl;
            parentDoc.head.appendChild(manifestLink);
        }

        // Inject iOS Safari Meta tags
        const metaTags = {
            "apple-mobile-web-app-capable": "yes",
            "apple-mobile-web-app-status-bar-style": "black-translucent",
            "apple-mobile-web-app-title": "Pit Wall"
        };
        for (const [name, content] of Object.entries(metaTags)) {
            if (!parentDoc.querySelector(`meta[name="${name}"]`)) {
                const meta = parentDoc.createElement('meta');
                meta.name = name;
                meta.content = content;
                parentDoc.head.appendChild(meta);
            }
        }
        
        // Inject Apple Touch Icon
        if (!parentDoc.querySelector('link[rel="apple-touch-icon"]')) {
            const appleIcon = parentDoc.createElement('link');
            appleIcon.rel = 'apple-touch-icon';
            appleIcon.href = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48dGV4dCB5PSIuOWVtIiBmb250LXNpemU9IjkwIj7🏎PC90ZXh0Pjwvc3ZnPg==";
            parentDoc.head.appendChild(appleIcon);
        }
    </script>
    """,
    height=0,
)

# ── Page-transition JS ────────────────────────────────────────────────────────
# Streamlit re-renders by toggling a [data-stale="true"] attribute on the root.
# We watch for that attribute flip and replay the pageEnter animation each time.
components.html(
    """
    <script>
    (function () {
        const parentDoc = window.parent.document;

        function replayAnimation() {
            const targets = parentDoc.querySelectorAll(
                'section.main > div.block-container, [data-testid="stMain"]'
            );
            targets.forEach(el => {
                el.style.animation = 'none';
                // Force reflow so the browser registers the reset
                void el.offsetHeight;
                el.style.animation = '';
            });
        }

        // Observe the stale attribute on the Streamlit root
        const root = parentDoc.querySelector('[data-testid="stApp"]')
                  || parentDoc.body;
        const observer = new MutationObserver((mutations) => {
            for (const m of mutations) {
                if (m.attributeName === 'data-stale') {
                    const wasStale = m.oldValue === 'true';
                    const nowFresh = root.getAttribute('data-stale') === 'false';
                    if (wasStale && nowFresh) {
                        // A rerender just finished — replay transition
                        requestAnimationFrame(replayAnimation);
                    }
                }
            }
        });
        observer.observe(root, { attributes: true, attributeOldValue: true });
    })();
    </script>
    """,
    height=0,
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""<!-- ── Google Font: Inter for premium typographic quality ── -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
    :root {
        --primary-color: var(--primary-color);
        --primary-rgb: 255, 135, 0;
    }
    /* ═══════════════════════════════════════════════════════════
       KEYFRAME ANIMATIONS
    ═══════════════════════════════════════════════════════════ */
    @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
    }
    @keyframes slideUp {
        from { opacity: 0; transform: translateY(18px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes slideInLeft {
        from { opacity: 0; transform: translateX(-14px); }
        to   { opacity: 1; transform: translateX(0); }
    }
    @keyframes shimmer {
        0%   { background-position: -800px 0; }
        100% { background-position:  800px 0; }
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50%       { opacity: 0.55; }
    }
    @keyframes accentGrow {
        from { width: 0; }
        to   { width: 100%; }
    }
    /* Rich page-enter: fade + rise + very subtle scale */
    @keyframes pageEnter {
        0%   { opacity: 0; transform: translateY(14px) scale(0.995); filter: blur(3px); }
        60%  { opacity: 1; filter: blur(0); }
        100% { opacity: 1; transform: translateY(0) scale(1); filter: blur(0); }
    }

    /* ═══════════════════════════════════════════════════════════
       BASE FONT
    ═══════════════════════════════════════════════════════════ */
    html, body, * {
        font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI",
                     Roboto, Helvetica, Arial, sans-serif;
        font-weight: 300;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    /* Restore Google Material Symbols icons */
    .material-symbols-rounded,
    .material-symbols-outlined,
    [data-testid="collapsedControl"] span,
    button[kind="header"] span {
        font-family: "Material Symbols Rounded", "Material Symbols Outlined" !important;
        font-weight: 400 !important;
    }

    /* ═══════════════════════════════════════════════════════════
       PAGE & SIDEBAR BASE
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stAppViewContainer"] {
        background-color: var(--background-color);
        color: var(--text-color);
        /* smooth background when theme switches */
        transition: background-color 0.35s ease, color 0.35s ease;
    }
    /* Main content: rich entry every rerender */
    [data-testid="stMain"],
    section.main > div.block-container {
        animation: pageEnter 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
        /* smooth background when theme switches */
        transition: background-color 0.35s ease, color 0.35s ease;
    }
    [data-testid="stSidebar"] {
        background-color: var(--secondary-background-color) !important;
        border-right: 1px solid rgba(128,128,128,0.12) !important;
        animation: slideInLeft 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards;
        transition: background-color 0.35s ease;
    }
    [data-testid="stSidebar"] .stButton > button { width: 100%; }

    /* ═══════════════════════════════════════════════════════════
       IMAGES / MEDIA
    ═══════════════════════════════════════════════════════════ */
    img, iframe, canvas, video {
        max-width: 100% !important;
        height: auto !important;
        transition: opacity 0.3s ease;
    }

    /* ═══════════════════════════════════════════════════════════
       TYPOGRAPHY
    ═══════════════════════════════════════════════════════════ */
    h1, h2, h3 {
        letter-spacing: -0.5px;
        font-weight: 600;
        color: var(--text-color);
    }

    .section-title {
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: var(--primary-color);
        margin: 36px 0 18px;
        display: flex;
        align-items: center;
        gap: 12px;
        animation: slideUp 0.4s ease both;
        opacity: 0.9;
    }
    .section-title::before {
        content: '';
        width: 3px;
        height: 14px;
        border-radius: 2px;
        background: var(--primary-color);
        flex-shrink: 0;
    }
    .section-title::after {
        content: '';
        flex: 1;
        height: 1px;
        background: linear-gradient(to right, rgba(var(--primary-rgb),0.25), rgba(128,128,128,0.08));
    }

    /* ═══════════════════════════════════════════════════════════
       METRIC CARDS
    ═══════════════════════════════════════════════════════════ */
    .metric-card {
        background: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,0.15);
        border-radius: 20px;
        padding: 18px 18px 16px;
        text-align: center;
        position: relative;
        overflow: hidden;
        min-width: 0;
        box-sizing: border-box;
        transition: transform 0.25s cubic-bezier(0.34,1.56,0.64,1),
                    border-color 0.25s ease,
                    box-shadow 0.25s ease;
        animation: slideUp 0.45s ease both;
    }
    .metric-card::before {
        /* Subtle top accent line */
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(to right, var(--primary-color), transparent);
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-4px) scale(1.015);
        border-color: rgba(var(--primary-rgb),0.3);
        box-shadow: 0 12px 32px rgba(0,0,0,0.18), 0 0 0 1px rgba(var(--primary-rgb),0.12);
    }
    .metric-card:hover::before { opacity: 1; }

    .metric-label {
        font-size: 10px;
        color: #8e8e93;
        letter-spacing: 1.8px;
        text-transform: uppercase;
        font-weight: 500;
    }
    .metric-value {
        font-size: clamp(18px, 2.5vw, 26px);
        font-weight: 300;
        color: var(--text-color);
        margin-top: 10px;
        letter-spacing: -0.5px;
        transition: color 0.2s ease;
    }
    .metric-sub { font-size: 11px; color: #8e8e93; margin-top: 4px; font-weight: 300; }

    /* ═══════════════════════════════════════════════════════════
       DRIVER BANNER
    ═══════════════════════════════════════════════════════════ */
    .driver-banner {
        border-radius: 20px;
        padding: 16px 160px 16px 22px;
        margin-bottom: 14px;
        border: 1px solid rgba(128,128,128,0.15);
        background: var(--secondary-background-color);
        display: flex;
        align-items: center;
        gap: 14px;
        min-width: 0;
        box-sizing: border-box;
        flex-wrap: nowrap;
        transition: border-color 0.3s ease, box-shadow 0.3s ease;
        animation: slideUp 0.4s ease both;
        position: relative;
        overflow: visible;
    }
    .driver-banner::after {
        content: '';
        position: absolute;
        left: 0; top: 0; bottom: 0;
        width: 3px;
        background: var(--colour, var(--primary-color));
        border-radius: 0 2px 2px 0;
    }
    .driver-banner:hover {
        border-color: rgba(var(--primary-rgb),0.25);
        box-shadow: 0 6px 24px rgba(0,0,0,0.1);
    }
    .team-badge {
        position: absolute;
        top: 50%;
        right: 18px;
        transform: translateY(-50%);
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 6px;
        transition: transform 0.3s ease;
        z-index: 2;
    }
    .team-logo {
        height: 30px;
        width: auto;
        max-width: 110px;
        opacity: 0.85;
        object-fit: contain;
        filter: drop-shadow(0 2px 6px rgba(0,0,0,0.15));
        transition: opacity 0.3s ease;
    }
    .team-name-label {
        font-size: 9px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: #8e8e93;
        font-weight: 600;
        text-align: right;
        white-space: nowrap;
    }
    .driver-banner:hover .team-badge {
        transform: translateY(-50%) scale(1.04);
    }
    .driver-banner:hover .team-logo {
        opacity: 1;
    }
    .driver-code {
        font-size: clamp(26px, 4vw, 34px);
        font-weight: 200;
        letter-spacing: -1px;
        color: var(--colour, var(--primary-color));
        line-height: 1;
    }
    .driver-meta {
        font-size: 10px;
        color: #8e8e93;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-weight: 500;
    }
    .driver-headshot {
        width: 64px;
        height: 64px;
        border-radius: 50%;
        object-fit: cover;
        object-position: top center;
        border: 2.5px solid var(--colour, var(--primary-color));
        box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        flex-shrink: 0;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        background: rgba(128,128,128,0.08);
    }
    .driver-banner:hover .driver-headshot {
        transform: scale(1.06);
        box-shadow: 0 6px 22px rgba(0,0,0,0.35);
    }

    /* ═══════════════════════════════════════════════════════════
       TYRE BADGE
    ═══════════════════════════════════════════════════════════ */
    .tyre-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border-radius: 24px;
        padding: 5px 14px 5px 5px;
        font-size: 12px;
        font-weight: 600;
        background: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,0.25);
        max-width: 100%;
        box-sizing: border-box;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .tyre-badge:hover {
        transform: scale(1.04);
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    .tyre-dot {
        width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
        font-size: 10px; font-weight: 800;
        box-shadow: 0 2px 6px rgba(0,0,0,0.25);
    }

    /* ═══════════════════════════════════════════════════════════
       WEATHER STRIP
    ═══════════════════════════════════════════════════════════ */
    .weather-strip {
        display: flex; gap: 18px; flex-wrap: wrap;
        background: var(--secondary-background-color);
        border: 1px solid rgba(128,128,128,0.15);
        border-radius: 20px;
        padding: 14px 20px;
        font-size: 13px;
        color: #a0a0a0;
        font-weight: 300;
        margin-top: 10px;
        width: 100%;
        box-sizing: border-box;
        animation: slideUp 0.5s ease both;
        transition: border-color 0.3s ease;
    }
    .weather-strip:hover { border-color: rgba(var(--primary-rgb),0.2); }
    .weather-item { display: flex; align-items: center; gap: 5px; flex-shrink: 0; }
    .weather-item strong { color: var(--text-color); font-weight: 500; }

    /* ═══════════════════════════════════════════════════════════
       BUTTONS  — McLaren Orange pill
    ═══════════════════════════════════════════════════════════ */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-color) 100%);
        color: #fff;
        border: none;
        border-radius: 40px;
        font-weight: 600;
        font-size: 14px;
        padding: 12px 28px;
        letter-spacing: 0.3px;
        transition: transform 0.18s cubic-bezier(0.34,1.56,0.64,1),
                    box-shadow 0.2s ease,
                    opacity 0.15s ease;
        box-shadow: 0 4px 14px rgba(var(--primary-rgb),0.35);
        width: 100%;
        position: relative;
        overflow: hidden;
    }
    .stButton > button::after {
        /* Shine sweep animation on hover */
        content: '';
        position: absolute;
        top: -50%; left: -60%;
        width: 30%; height: 200%;
        background: rgba(255,255,255,0.18);
        transform: skewX(-20deg);
        transition: left 0.4s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 8px 22px rgba(var(--primary-rgb),0.45);
    }
    .stButton > button:hover::after { left: 130%; }
    .stButton > button:active {
        transform: translateY(0) scale(0.97);
        box-shadow: 0 2px 8px rgba(var(--primary-rgb),0.25);
    }

    /* ═══════════════════════════════════════════════════════════
       STREAMLIT TABS — polished, animated indicator
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stTabs"] [role="tab"] {
        font-weight: 500 !important;
        font-size: 13px !important;
        letter-spacing: 0.3px;
        transition: color 0.2s ease;
        padding-bottom: 10px !important;
    }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
        color: var(--primary-color) !important;
    }
    [data-testid="stTabs"] [role="tablist"] {
        border-bottom: 1px solid rgba(128,128,128,0.15) !important;
    }

    /* ═══════════════════════════════════════════════════════════
       PLOTLY / PYPLOT CONTAINERS
    ═══════════════════════════════════════════════════════════ */
    [data-testid="stPlotlyChart"],
    [data-testid="stImage"],
    .element-container {
        animation: slideUp 0.5s ease both;
    }
    /* Subtle border + radius around charts */
    [data-testid="stPlotlyChart"] > div {
        border-radius: 16px;
        overflow: hidden;
        transition: box-shadow 0.3s ease;
    }
    [data-testid="stPlotlyChart"] > div:hover {
        box-shadow: 0 8px 32px rgba(0,0,0,0.12);
    }

    /* ═══════════════════════════════════════════════════════════
       MISCELLANEOUS
    ═══════════════════════════════════════════════════════════ */
    hr { border-color: rgba(128,128,128,0.15); margin: 24px 0; }

    /* Selectbox and widget labels */
    label[data-baseweb] {
        font-size: 11px !important;
        font-weight: 500;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        opacity: 0.6;
    }

    /* Info/warning boxes */
    [data-testid="stAlert"] {
        border-radius: 14px !important;
        border-left: 3px solid var(--primary-color) !important;
        animation: slideUp 0.35s ease both;
    }

    /* Expander */
    [data-testid="stExpander"] {
        border-radius: 14px !important;
        border: 1px solid rgba(128,128,128,0.15) !important;
        transition: box-shadow 0.2s ease;
    }
    [data-testid="stExpander"]:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }

    /* Spinner */
    [data-testid="stSpinner"] {
        animation: pulse 1.4s ease-in-out infinite;
    }

    /* Caption / footnote */
    [data-testid="stCaptionContainer"] {
        font-size: 11px;
        opacity: 0.55;
        letter-spacing: 0.3px;
    }

    /* ═══════════════════════════════════════════════════════════
       RESPONSIVE
    ═══════════════════════════════════════════════════════════ */
    @media (max-width: 768px) {
        .driver-code   { font-size: 20px; }
        .metric-value  { font-size: 14px; }
        .weather-strip { gap: 10px; font-size: 11px; }
        .tyre-badge    { font-size: 11px; }
        .section-title { font-size: 10px; letter-spacing: 2px; }
    }
</style>
""", unsafe_allow_html=True)

# ── Theme CSS override (dark / light) ─────────────────────────────────────────
# Initialize theme state early so CSS is applied on every render
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = True

def _toggle_theme():
    """Called before rerun — so the CSS block above sees the new value immediately."""
    st.session_state["dark_mode"] = not st.session_state["dark_mode"]

if st.session_state["dark_mode"]:
    st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main,
    section.main > div.block-container {
        background-color: #0d0d0d !important;
        color: #e8e8e8 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #111111 !important;
    }
    [data-testid="stSidebar"] * {
        color: #e8e8e8 !important;
    }
    .stSelectbox label, .stCheckbox label, div[data-baseweb] label,
    p, span:not([class*="badge"]):not([class*="label"]) {
        color: #e8e8e8 !important;
    }
    /* ── Selectbox control box ── */
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="select"] > div:hover,
    [data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"] {
        background-color: #1e1e1e !important;
        border-color: rgba(255,255,255,0.12) !important;
        color: #e8e8e8 !important;
    }
    /* ── Selectbox selected value text ── */
    [data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] div[class*="ValueContainer"] {
        color: #e8e8e8 !important;
    }
    /* ── Dropdown popup list ── */
    [data-baseweb="popover"] [data-baseweb="menu"],
    ul[data-testid="stSelectboxVirtualDropdown"] {
        background-color: #1a1a1a !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
    }
    [data-baseweb="popover"] li,
    [data-baseweb="menu"] li,
    ul[data-testid="stSelectboxVirtualDropdown"] li {
        background-color: #1a1a1a !important;
        color: #e8e8e8 !important;
    }
    [data-baseweb="popover"] li:hover,
    [data-baseweb="menu"] li:hover,
    ul[data-testid="stSelectboxVirtualDropdown"] li:hover {
        background-color: #2a2a2a !important;
    }
    /* ── Radio buttons ── */
    [data-testid="stSidebar"] [data-testid="stRadio"] label,
    [data-testid="stSidebar"] .stRadio span { color: #e8e8e8 !important; }
    /* ── Checkbox ── */
    [data-testid="stSidebar"] [data-testid="stCheckbox"] label { color: #e8e8e8 !important; }
    /* ── Spinner text ── */
    [data-testid="stSidebar"] [data-testid="stSpinner"] p { color: #e8e8e8 !important; }
    [data-testid="metric-container"] *, .stMetric * { color: #e8e8e8 !important; }
    hr { border-color: rgba(255,255,255,0.1) !important; }
    [data-testid="stDataFrame"], .dataframe { background: #1a1a1a !important; color: #e8e8e8 !important; }
    /* ── Top toolbar / header bar ── */
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    header[data-testid="stHeader"] {
        background-color: #0d0d0d !important;
        border-bottom: 1px solid rgba(255,255,255,0.06) !important;
    }
    [data-testid="stHeader"] * {
        color: #e8e8e8 !important;
    }
    [data-testid="stHeader"] button,
    [data-testid="stHeader"] svg {
        fill: #e8e8e8 !important;
        color: #e8e8e8 !important;
    }
    [data-testid="stDecoration"] {
        background: linear-gradient(90deg, var(--primary-color), transparent) !important;
    }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main,
    section.main > div.block-container {
        background-color: #f5f5f7 !important;
        color: #111111 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #ffffff !important;
    }
    [data-testid="stSidebar"] * {
        color: #111111 !important;
    }
    .stSelectbox label, .stCheckbox label, div[data-baseweb] label,
    p, span:not([class*="badge"]):not([class*="label"]) {
        color: #111111 !important;
    }
    /* ── Selectbox control box ── */
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="select"] > div:hover,
    [data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"] {
        background-color: #f0f0f0 !important;
        border-color: rgba(0,0,0,0.15) !important;
        color: #111111 !important;
    }
    /* ── Selectbox selected value text ── */
    [data-testid="stSidebar"] [data-baseweb="select"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] div[class*="ValueContainer"] {
        color: #111111 !important;
    }
    /* ── Dropdown popup list ── */
    [data-baseweb="popover"] [data-baseweb="menu"],
    ul[data-testid="stSelectboxVirtualDropdown"] {
        background-color: #ffffff !important;
        border: 1px solid rgba(0,0,0,0.12) !important;
    }
    [data-baseweb="popover"] li,
    [data-baseweb="menu"] li,
    ul[data-testid="stSelectboxVirtualDropdown"] li {
        background-color: #ffffff !important;
        color: #111111 !important;
    }
    [data-baseweb="popover"] li:hover,
    [data-baseweb="menu"] li:hover,
    ul[data-testid="stSelectboxVirtualDropdown"] li:hover {
        background-color: #f0f0f0 !important;
    }
    /* ── Radio buttons ── */
    [data-testid="stSidebar"] [data-testid="stRadio"] label,
    [data-testid="stSidebar"] .stRadio span { color: #111111 !important; }
    /* ── Checkbox ── */
    [data-testid="stSidebar"] [data-testid="stCheckbox"] label { color: #111111 !important; }
    [data-testid="metric-container"] *, .stMetric * { color: #111111 !important; }
    .metric-card { background: #ffffff !important; border-color: rgba(0,0,0,0.08) !important; }
    .metric-value, .metric-label, .metric-sub { color: #111111 !important; }
    .driver-banner { background: #ffffff !important; }
    .section-title { color: #111111 !important; }
    .weather-strip { background: #ffffff !important; }
    hr { border-color: rgba(0,0,0,0.1) !important; }
    /* ── Top toolbar / header bar ── */
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    header[data-testid="stHeader"] {
        background-color: #f5f5f7 !important;
        border-bottom: 1px solid rgba(0,0,0,0.08) !important;
    }
    [data-testid="stHeader"] * {
        color: #111111 !important;
    }
    [data-testid="stHeader"] button,
    [data-testid="stHeader"] svg {
        fill: #111111 !important;
        color: #111111 !important;
    }
    [data-testid="stDecoration"] {
        background: linear-gradient(90deg, var(--primary-color), transparent) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
TEAM_COLOURS = {
    # ── 2024–2025 active grid ─────────────────────────────────────────────────
    "Red Bull Racing": "#3671C6",
    "Ferrari":         "#E8002D",
    "Mercedes":        "#27F4D2",
    "McLaren":         "#FF8000",
    "Aston Martin":    "#229971",
    "Alpine":          "#FF87BC",
    "Williams":        "#64C4FF",
    "RB":              "#6692FF",
    "Kick Sauber":     "#52E252",
    "Haas F1 Team":    "#B6BABD",

    # ── 2020–2023 predecessor names ───────────────────────────────────────────
    "AlphaTauri":      "#4E7C9B",  # navy blue (2020-2023)
    "Alfa Romeo":      "#B12039",  # dark crimson (2018-2023)
    "Alfa Romeo Racing": "#B12039",
    "Racing Point":    "#F596C8",  # bubblegum pink (2019-2020)

    # ── 2018–2019 era teams ───────────────────────────────────────────────────
    "Renault":         "#FFF500",  # bright Renault yellow
    "Force India":     "#F596C8",  # magenta / pink (same livery family as Racing Point)
    "Toro Rosso":      "#469BFF",  # powder blue (pre-AlphaTauri)
    "Haas":            "#B6BABD",  # same grey as "Haas F1 Team"
    "Sauber":          "#B12039",  # Sauber red (pre-Alfa Romeo branding)
}

# Single source of truth for compound colours.
# Keys are UPPER-CASE compound names.
# fill   → background hex used in charts / badges
# text   → label text colour (for contrast on filled backgrounds)
# letter → single-character abbreviation shown on tyre badge
COMPOUND_COLOURS = {
    "SOFT":         {"fill": "#FF3333", "text": "#ffffff", "letter": "S"},
    "MEDIUM":       {"fill": "#FFD700", "text": "#111111", "letter": "M"},
    "HARD":         {"fill": "#CCCCCC", "text": "#111111", "letter": "H"},
    "INTERMEDIATE": {"fill": "#39B54A", "text": "#ffffff", "letter": "I"},
    "WET":          {"fill": "#0067FF", "text": "#ffffff", "letter": "W"},
    "UNKNOWN":      {"fill": "#888888", "text": "#ffffff", "letter": "?"},
}

TRACK_STATUS_MAP = {
    "1": ("🟢", "Clear"), "2": ("🟡", "Yellow"),
    "4": ("🚗", "Safety Car"), "5": ("🔴", "Red Flag"),
    "6": ("🐢", "VSC"), "7": ("🐢", "VSC End"),
}

MATPLOTLIB_THEME = {
    "font.family": "DejaVu Sans",
    "xtick.labelsize": 10, "ytick.labelsize": 10,
    "figure.facecolor": "none",
    "axes.facecolor": "none",
    "axes.edgecolor": "#888888",
    "text.color": "#888888",
    "axes.labelcolor": "#888888",
    "xtick.color": "#888888",
    "ytick.color": "#888888",
    "savefig.transparent": True,
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def hex_to_rgb(hex_col: str) -> str:
    hex_col = hex_col.lstrip("#")
    if len(hex_col) == 3:
        hex_col = "".join([c*2 for c in hex_col])
    try:
        return ",".join(str(int(hex_col[i:i+2], 16)) for i in (0, 2, 4))
    except Exception:
        return "255, 135, 0"

def _team_logo(team: str, year: int = 2024) -> str:
    t = team.lower()
    mapping = {
        "red bull": "red-bull-racing-logo.png",
        "ferrari": "ferrari-logo.png",
        "mclaren": "mclaren-logo.png",
        "mercedes": "mercedes-logo.png",
        "aston martin": "aston-martin-logo.png",
        "haas": "haas-f1-team-logo.png",
        "williams": "williams-logo.png",
        "alpine": "alpine-logo.png",
        "rb": "rb-logo.png",
        "vcarb": "rb-logo.png",
        "sauber": "kick-sauber-logo.png",
        "alfa romeo": "alfaromeo-logo.png",
        "racing point": "racing-point-logo.png",
        "renault": "renault-logo.png",
        "alphatauri": "alphatauri-logo.png"
    }
    for k, filename in mapping.items():
        if k in t:
            return f"https://media.formula1.com/content/dam/fom-website/teams/{year}/{filename}"
    return ""

def _team_colour(team: str) -> str:
    for k, v in TEAM_COLOURS.items():
        if k.lower() in team.lower():
            return v
    return "#FF8700"


@st.cache_data(show_spinner=False, ttl=3600)
def load_schedule(year: int) -> pd.DataFrame:
    return fastf1.get_event_schedule(year, include_testing=False)


@st.cache_resource(show_spinner=False, ttl=3600)
def load_session(year: int, gp: str, session_type: str = "R"):
    sess = fastf1.get_session(year, gp, session_type)
    sess.load(telemetry=True, laps=True, weather=True, messages=True)
    return sess


def format_laptime(td) -> str:
    try:
        if pd.isna(td):
            return "N/A"
        total = td.total_seconds()
        return f"{int(total // 60)}:{total % 60:06.3f}"
    except Exception:
        return "N/A"


def driver_colour(sess, driver: str) -> str:
    try:
        return _team_colour(sess.get_driver(driver).get("TeamName", ""))
    except Exception:
        return "#FF8700"


def _build_driver_labels(session) -> dict:
    """
    Build a mapping of driver number → display label, e.g. '4' → 'NOR · Norris'.
    Uses FastF1 driver info for the actual season; falls back to the raw number.
    """
    labels = {}
    try:
        for drv in session.laps["Driver"].dropna().unique():
            try:
                info    = session.get_driver(str(drv))
                abbr    = info.get("Abbreviation", str(drv))
                last    = info.get("LastName", "").strip()
                labels[str(drv)] = f"{abbr} · {last}" if last else abbr
            except Exception:
                labels[str(drv)] = str(drv)
    except Exception:
        pass
    return labels


def get_telemetry_cached(driver: str, lap, sess_key: str):
    if lap is None:
        return None
    try:
        lap_num = int(lap["LapNumber"])
    except Exception:
        lap_num = -1
    key = f"tel_{sess_key}_{driver}_{lap_num}"
    if key not in st.session_state:
        try:
            st.session_state[key] = lap.get_car_data().add_distance()
        except Exception as exc:
            st.warning(f"⚠️ No telemetry for {driver}: {exc}")
            st.session_state[key] = None
    return st.session_state[key]


def style_ax(ax, ylabel: str, special: str = ""):
    ax.set_ylabel(ylabel, fontsize=11, labelpad=8)
    ax.grid(True, linestyle=":", linewidth=0.3, alpha=0.8, color="#888888")
    ax.tick_params(axis="both", length=3, labelsize=10, colors="#888888")
    for spine in ax.spines.values():
        spine.set_edgecolor("#888888")
        spine.set_alpha(0.3)
    if special == "brake":
        ax.set_ylim(-0.05, 1.05)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["Off", "On"], fontsize=10)
    elif special == "drs":
        ax.set_ylim(-1, 15)
        ax.set_yticks([0, 8, 12])
        ax.set_yticklabels(["Off", "On", "On"], fontsize=9)
    else:
        ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='padding: 4px 0 16px'>"
        "<div style='font-size:22px; font-weight:800; letter-spacing:-0.5px;'>🏎 Pit Wall</div>"
        "<div style='font-size:11px; letter-spacing:2px; text-transform:uppercase; margin-top:2px; opacity: 0.6;'>F1 Telemetry Explorer</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr style='margin:0 0 16px'>", unsafe_allow_html=True)

    _years = list(range(2026, 2017, -1))
    year = st.selectbox("Season", _years, index=_years.index(2025) if 2025 in _years else 0, label_visibility="visible")

    with st.spinner("Loading calendar…"):
        try:
            schedule = load_schedule(year)
            gp_names = schedule["EventName"].tolist()
        except Exception as e:
            st.error(f"Could not load {year} schedule: {e}")
            st.stop()

    _def_gp_idx = gp_names.index("British Grand Prix") if "British Grand Prix" in gp_names else min(4, len(gp_names) - 1)
    gp = st.selectbox("Grand Prix", gp_names, index=_def_gp_idx)

    session_map = {
        "Race": "R", "Qualifying": "Q", "Sprint": "S",
        "Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3",
    }
    session_label = st.selectbox("Session", list(session_map.keys()))
    session_type = session_map[session_label]

    st.markdown("<hr style='margin:16px 0'>", unsafe_allow_html=True)

    mode_label = "☀️  Light Mode" if st.session_state["dark_mode"] else "🌙  Dark Mode"
    st.button(mode_label, key="theme_toggle", on_click=_toggle_theme, width="stretch")

    st.markdown("<hr style='margin:12px 0'>", unsafe_allow_html=True)
    load_btn = st.button("⬇️  Load Session", width="stretch")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:10px; opacity:0.5; letter-spacing:0.5px; text-align:center;'>"
        "Data © FastF1 / Ergast / F1<br>Educational use only"
        "</div>",
        unsafe_allow_html=True,
    )

# ── Session state ─────────────────────────────────────────────────────────────
if "session" not in st.session_state:
    st.session_state["session"] = None
    st.session_state["sess_key"] = None

sess_key = f"{year}_{gp}_{session_type}"

if load_btn:
    with st.spinner(f"Loading {gp} {year} {session_label}…  (first load ~30 s)"):
        try:
            sess = load_session(year, gp, session_type)
            st.session_state["session"] = sess
            st.session_state["sess_key"] = sess_key
        except Exception as e:
            st.error(f"❌ {e}")
            st.stop()

sess = st.session_state.get("session")

# ── Landing ───────────────────────────────────────────────────────────────────
if sess is None:
    st.markdown(
        "<div style='max-width:560px; margin:80px auto; text-align:center;'>"
        "<div style='font-size:64px; margin-bottom:16px;'>🏎</div>"
        "<h1 style='font-size:36px; font-weight:800; color:var(--text-color); margin-bottom:8px;'>Pit Wall</h1>"
        "<p style='opacity:0.7; font-size:15px; line-height:1.6; margin-bottom:32px;'>"
        "Professional F1 lap telemetry explorer. Select a season, Grand Prix and session "
        "in the sidebar, then hit <strong style='color:var(--primary-color);'>Load Session</strong>."
        "</p>"
        "<div style='display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; text-align:left;'>"
        "<div style='background:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.2); border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>📈</div><div style='font-size:13px; opacity:0.7; margin-top:4px;'>Speed · Throttle · Brake<br>RPM · Gear · DRS</div></div>"
        "<div style='background:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.2); border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>⏱</div><div style='font-size:13px; opacity:0.7; margin-top:4px;'>Lap time &amp; sector splits<br>Tyre compound &amp; age</div></div>"
        "<div style='background:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.2); border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>👥</div><div style='font-size:13px; opacity:0.7; margin-top:4px;'>Head-to-head comparison<br>Overlapping or separate</div></div>"
        "<div style='background:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.2); border-radius:10px; padding:14px 16px;'>"
        "<div style='font-size:18px;'>🌤</div><div style='font-size:13px; opacity:0.7; margin-top:4px;'>Weather conditions<br>Track status per lap</div></div>"
        "</div></div>",
        unsafe_allow_html=True,
    )
    st.stop()

# ── Driver & lap controls ──────────────────────────────────────────────────────
try:
    all_drivers = sorted(sess.laps["Driver"].dropna().unique().tolist())
    if not all_drivers:
        raise ValueError("Empty drivers list")
except Exception:
    st.markdown("<br>", unsafe_allow_html=True)
    st.error(
        "**Session Data Unavailable**\n\n"
        "FastF1 could not load the lap data for this session. This usually happens if "
        "the session is very recent and official telemetry hasn't been published yet, "
        "or if the session was cancelled."
    )
    st.stop()

# ── Laps snapshot — single extraction used by all cached builders ─────────────
# Extracting here (outside @st.cache_data functions) fixes the cache isolation
# bug: builders now receive the DataFrame as an argument so @st.cache_data can
# hash it correctly rather than reading from st.session_state internally.
# Cast to plain pd.DataFrame so @st.cache_data can hash it.
# fastf1.core.Laps is a subclass with custom internal state that Streamlit's
# hasher cannot serialise, causing UnhashableParamError.
_all_laps: pd.DataFrame = pd.DataFrame(sess.laps.copy())

# ── Driver name labels (built once per session) ───────────────────────────────
_drv_labels: dict = _build_driver_labels(sess)

def _fmt_driver(num: str) -> str:
    """Format function for st.selectbox — shows 'ABR · Last Name' instead of raw number."""
    return _drv_labels.get(str(num), str(num))


# ── Session Info Header ───────────────────────────────────────────────────────
def _session_info_header(session, sess_type_code: str) -> None:
    """Render a slim banner summarising the loaded session."""
    try:
        ev = session.event

        # Human-readable session type
        _type_labels = {
            "R": "Race", "Q": "Qualifying", "SQ": "Sprint Qualifying",
            "S": "Sprint", "FP1": "Practice 1", "FP2": "Practice 2",
            "FP3": "Practice 3",
        }
        session_label = _type_labels.get(str(sess_type_code).upper(), str(sess_type_code))

        # Basic event fields — safe fallback for each
        circuit  = str(ev.get("Location",   ev.get("EventName", "—")))
        country  = str(ev.get("Country",    "—"))
        round_no = ev.get("RoundNumber",  "—")
        raw_date = ev.get("EventDate",    None)

        # Format date nicely
        try:
            date_str = pd.Timestamp(raw_date).strftime("%-d %B %Y")
        except Exception:
            date_str = str(raw_date)[:10] if raw_date else "—"

        # Country → flag emoji lookup
        _flags = {
            "United Kingdom": "🇬🇧", "United States": "🇺🇸", "Italy": "🇮🇹",
            "Monaco": "🇲🇨", "Spain": "🇪🇸", "France": "🇫🇷", "Germany": "🇩🇪",
            "Belgium": "🇧🇪", "Netherlands": "🇳🇱", "Hungary": "🇭🇺",
            "Austria": "🇦🇹", "Canada": "🇨🇦", "Australia": "🇦🇺",
            "Japan": "🇯🇵", "China": "🇨🇳", "Bahrain": "🇧🇭",
            "Saudi Arabia": "🇸🇦", "Azerbaijan": "🇦🇿", "Singapore": "🇸🇬",
            "Mexico": "🇲🇽", "Brazil": "🇧🇷", "Abu Dhabi": "🇦🇪",
            "United Arab Emirates": "🇦🇪", "Qatar": "🇶🇦", "Miami": "🇺🇸",
            "Las Vegas": "🇺🇸",
        }
        flag = _flags.get(country, "🏁")

        # Session type → icon
        _type_icons = {
            "Race": "🏆", "Qualifying": "⏱", "Sprint": "⚡",
            "Sprint Qualifying": "⚡", "Practice 1": "🔧",
            "Practice 2": "🔧", "Practice 3": "🔧",
        }
        sess_icon = _type_icons.get(session_label, "🏎")

        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg,
                    rgba(var(--primary-rgb), 0.08) 0%,
                    var(--secondary-background-color) 60%);
                border: 1px solid rgba(var(--primary-rgb), 0.25);
                border-left: 4px solid var(--primary-color);
                border-radius: 14px;
                padding: 14px 20px;
                margin-bottom: 18px;
                display: flex;
                align-items: center;
                gap: 24px;
                flex-wrap: wrap;
            ">
                <div style="font-size: 36px; line-height: 1;">{flag}</div>
                <div style="flex: 1; min-width: 200px;">
                    <div style="
                        font-size: 18px; font-weight: 700;
                        letter-spacing: -0.3px; margin-bottom: 3px;
                    ">{circuit}</div>
                    <div style="font-size: 12px; opacity: 0.55; letter-spacing: 0.5px;">
                        {country} &nbsp;·&nbsp; Round {round_no}
                    </div>
                </div>
                <div style="display:flex; gap:28px; flex-wrap:wrap;">
                    <div style="text-align:center;">
                        <div style="font-size:20px;">{sess_icon}</div>
                        <div style="font-size:11px; opacity:0.6; margin-top:2px;">{session_label}</div>
                    </div>
                    <div style="text-align:center;">
                        <div style="
                            font-size:13px; font-weight:600;
                            color:var(--primary-color); white-space:nowrap;
                        ">{date_str}</div>
                        <div style="font-size:11px; opacity:0.6; margin-top:2px;">Event Date</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass   # Never crash the page for a cosmetic header


_session_info_header(sess, session_type)

# ── Driver Selection ──────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Driver Selection</div>", unsafe_allow_html=True)
col_a, col_b = st.columns([1, 1])
with col_a:
    _def_d1_idx = all_drivers.index("4") if "4" in all_drivers else 0
    driver1 = st.selectbox(
        "Driver 1", all_drivers, index=_def_d1_idx, key="d1",
        format_func=_fmt_driver,
    )
with col_b:
    compare = st.checkbox("Compare with Driver 2", value=False)
    driver2 = None
    if compare:
        remaining = [d for d in all_drivers if d != driver1]
        driver2 = st.selectbox(
            "Driver 2", remaining, key="d2",
            format_func=_fmt_driver,
        )


def lap_selector(driver: str, suffix: str = ""):
    dlaps = sess.laps.pick_drivers(driver).pick_quicklaps().reset_index(drop=True)
    if dlaps.empty:
        dlaps = sess.laps.pick_drivers(driver).dropna(subset=["LapTime"]).reset_index(drop=True)
    if dlaps.empty:
        st.warning(f"No valid laps for {_fmt_driver(driver)}.")
        return None, None
    opts   = ["Fastest"] + [str(int(ln)) for ln in dlaps["LapNumber"].tolist()]
    choice = st.selectbox(f"Lap — {_fmt_driver(driver)}", opts, key=f"lap_{driver}{suffix}")
    lap    = dlaps.loc[dlaps["LapTime"].idxmin()] if choice == "Fastest" \
        else dlaps[dlaps["LapNumber"] == int(choice)].iloc[0]
    return lap, dlaps


col_c, col_d = st.columns([1, 1] if compare else [1, 2])
with col_c:
    lap1, laps1 = lap_selector(driver1, "_1")
with col_d:
    if compare and driver2:
        lap2, laps2 = lap_selector(driver2, "_2")
    else:
        lap2 = laps2 = None

# Chart mode toggle
chart_mode = "Overlapping"
if compare and driver2:
    chart_mode = st.radio(
        "Chart View", ["Overlapping", "Separate"], horizontal=True, index=0,
        help="Overlapping: both drivers on same axes | Separate: individual side-by-side charts",
    )

# ── Telemetry ─────────────────────────────────────────────────────────────────
tel1 = get_telemetry_cached(driver1, lap1, sess_key)
tel2 = get_telemetry_cached(driver2, lap2, sess_key) if (compare and driver2 and lap2 is not None) else None

colour1 = driver_colour(sess, driver1)

# Dynamically override the entire app theme to match the Driver's constructor colour
st.markdown(f"<style>:root {{ --primary-color: {colour1}; --primary-rgb: {hex_to_rgb(colour1)}; }}</style>", unsafe_allow_html=True)
colour2 = driver_colour(sess, driver2) if driver2 else "#27F4D2"

matplotlib.rcParams.update(MATPLOTLIB_THEME)

# ── Lap Summary ───────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Lap Summary</div>", unsafe_allow_html=True)


def tyre_badge_html(compound: str, age_str: str, fresh: bool) -> str:
    raw    = str(compound).upper() if compound and compound != "?" else "UNKNOWN"
    pal    = COMPOUND_COLOURS.get(raw, COMPOUND_COLOURS["UNKNOWN"])
    col    = pal["fill"]
    letter = pal["letter"]
    text_col = pal["text"]
    worn_label = "fresh" if fresh else f"{age_str} laps"
    return (
        f"<span class='tyre-badge'>"
        f"<span class='tyre-dot' style='background:{col}; color:{text_col};'>{letter}</span>"
        f"<span style='color:#ccc;'>{raw.title()}</span>"
        f"<span style='color:#555; font-size:11px;'>· {worn_label}</span>"
        f"</span>"
    )


def weather_strip_html(lap) -> str:
    try:
        w = lap.get_weather_data()
        air = f"{w['AirTemp']:.1f}°C" if not pd.isna(w.get("AirTemp")) else "—"
        trk = f"{w['TrackTemp']:.1f}°C" if not pd.isna(w.get("TrackTemp")) else "—"
        hum = f"{w['Humidity']:.0f}%" if not pd.isna(w.get("Humidity")) else "—"
        rain = "Yes" if w.get("Rainfall") else "No"

        ts = str(lap.get("TrackStatus", "1"))
        if len(ts) > 1:
            status_str = "Multiple"
        else:
            ico, lbl = TRACK_STATUS_MAP.get(ts, ("🟢", "Clear"))
            status_str = f"{ico} {lbl}"

        return (
            f"<div class='weather-strip'>"
            f"<div class='weather-item'>🌡 <strong>{air}</strong> air</div>"
            f"<div class='weather-item'>☀️ <strong>{trk}</strong> track</div>"
            f"<div class='weather-item'>💧 <strong>{hum}</strong> humidity</div>"
            f"<div class='weather-item'>🌧 Rain: <strong>{rain}</strong></div>"
            f"<div class='weather-item' style='margin-left:auto;'>Track: <strong>{status_str}</strong></div>"
            f"</div>"
        )
    except Exception:
        return ""


def render_summary(lap, driver: str, colour: str = "#FF8700"):
    if lap is None:
        return
    try:
        lap_num_str = f"Lap {int(lap.get('LapNumber', '?'))}"
    except Exception:
        lap_num_str = ""

    try:
        driver_info = sess.get_driver(driver)
        raw_team    = driver_info.get("TeamName", "")
        logo_url    = _team_logo(raw_team, year)
        headshot_url = driver_info.get("HeadshotUrl", "") or ""
    except Exception:
        raw_team     = ""
        logo_url     = ""
        headshot_url = ""

    if logo_url and raw_team:
        team_badge_html = (
            f"<div class='team-badge'>"
            f"<img src='{logo_url}' class='team-logo'>"
            f"<span class='team-name-label'>{raw_team}</span>"
            f"</div>"
        )
    elif logo_url:
        team_badge_html = f"<div class='team-badge'><img src='{logo_url}' class='team-logo'></div>"
    elif raw_team:
        team_badge_html = f"<div class='team-badge'><span class='team-name-label'>{raw_team}</span></div>"
    else:
        team_badge_html = ""

    headshot_html = (
        f"<img src='{headshot_url}' class='driver-headshot' "
        f"onerror=\"this.style.display='none'\" alt='{driver}'>"
        if headshot_url else ""
    )

    st.markdown(
        f"<div class='driver-banner' style='--colour:{colour}; --colour-dim:{colour}18;'>"
        f"{headshot_html}"
        f"<div style='display:flex; flex-direction:column; gap:3px; min-width:0;'>"
        f"<div class='driver-code'>{driver}</div>"
        f"<div class='driver-meta'>{lap_num_str}</div>"
        f"</div>"
        f"{team_badge_html}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Lap time + sectors
    c1, c2, c3, c4 = st.columns(4)

    def mc(col_obj, label, value):
        col_obj.markdown(
            f"<div class='metric-card' style='--accent:{colour};'>"
            f"<div class='metric-label'>{label}</div>"
            f"<div class='metric-value'>{value}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    mc(c1, "Lap Time",  format_laptime(lap.get("LapTime")))
    mc(c2, "Sector 1",  format_laptime(lap.get("Sector1Time")))
    mc(c3, "Sector 2",  format_laptime(lap.get("Sector2Time")))
    mc(c4, "Sector 3",  format_laptime(lap.get("Sector3Time")))

    # ── Speed traps (if available)
    si1 = lap.get("SpeedI1"); si2 = lap.get("SpeedI2")
    sfl = lap.get("SpeedFL"); sst = lap.get("SpeedST")
    speed_cols = [
        ("I1  Speed",  f"{si1:.0f} km/h"  if si1 and not pd.isna(si1) else "—"),
        ("I2  Speed",  f"{si2:.0f} km/h"  if si2 and not pd.isna(si2) else "—"),
        ("FL  Speed",  f"{sfl:.0f} km/h"  if sfl and not pd.isna(sfl) else "—"),
        ("ST  Speed",  f"{sst:.0f} km/h"  if sst and not pd.isna(sst) else "—"),
    ]
    sc1, sc2, sc3, sc4 = st.columns(4)
    for col_obj, (lbl, val) in zip([sc1, sc2, sc3, sc4], speed_cols):
        col_obj.markdown(
            f"<div class='metric-card' style='--accent:#333;'>"
            f"<div class='metric-label'>{lbl}</div>"
            f"<div class='metric-value' style='font-size:16px; color:#aaa;'>{val}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Tyre badge + weather
    compound = lap.get("Compound", "?")
    tyre_age = lap.get("TyreLife", "?")
    try:
        tyre_age_str = str(int(tyre_age)) if tyre_age != "?" and not pd.isna(tyre_age) else "?"
    except Exception:
        tyre_age_str = "?"
    fresh = lap.get("FreshTyre", False)

    st.markdown(
        f"<div style='margin-top:10px; display:flex; align-items:center; gap:10px;'>"
        f"{tyre_badge_html(compound, tyre_age_str, fresh)}"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(weather_strip_html(lap), unsafe_allow_html=True)


if compare and lap2 is not None:
    s1, s2 = st.columns(2)
    with s1:
        render_summary(lap1, driver1, colour1)
    with s2:
        render_summary(lap2, driver2, colour2)
else:
    render_summary(lap1, driver1, colour1)

# ── Session Statistics ────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Session Statistics</div>", unsafe_allow_html=True)

def render_session_stats(driver: str, colour: str):
    try:
        drv_info = sess.get_driver(driver)
        grid = drv_info.get("GridPosition", "N/A")
        pos = drv_info.get("Position", "N/A")
        status = str(drv_info.get("Status", "N/A"))
        try:
            grid_str = f"P{int(grid)}" if pd.notna(grid) else "N/A"
        except Exception:
            grid_str = str(grid)
        try:
            pos_str = f"P{int(pos)}" if pd.notna(pos) else "N/A"
        except Exception:
            pos_str = str(pos)

        dlaps = _all_laps[_all_laps["Driver"] == driver].copy()
        
        # Best Lap
        if not dlaps.empty and "LapTime" in dlaps.columns:
            best_lap = format_laptime(dlaps["LapTime"].min())
        else:
            best_lap = "N/A"
            
        # Top Speed
        if not dlaps.empty and "SpeedST" in dlaps.columns:
            max_speed = dlaps["SpeedST"].max()
            speed_str = f"{max_speed:.0f} km/h" if pd.notna(max_speed) else "N/A"
        else:
            speed_str = "N/A"
            
        # Avg Pace (Median of valid laps)
        if not dlaps.empty and "LapTime" in dlaps.columns:
            valid_laps = dlaps.dropna(subset=["LapTime"])
            if not valid_laps.empty:
                min_t = valid_laps["LapTime"].dt.total_seconds().min()
                valid_secs = valid_laps["LapTime"].dt.total_seconds()
                valid_secs = valid_secs[valid_secs < min_t * 1.07]
                avg_pace = pd.to_timedelta(valid_secs.median(), unit="s")
                avg_pace_str = format_laptime(avg_pace)
            else:
                avg_pace_str = "N/A"
        else:
            avg_pace_str = "N/A"

        c1, c2, c3 = st.columns(3)
        c4, c5, c6 = st.columns(3)

        def mc(col_obj, label, value):
            col_obj.markdown(
                f"<div class='metric-card' style='--accent:{colour}; margin-bottom: 14px;'>"
                f"<div class='metric-label'>{label}</div>"
                f"<div class='metric-value' style='font-size: clamp(16px, 2vw, 22px);'>{value}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        mc(c1, "Grid Position", grid_str)
        mc(c2, "Finish Position", pos_str)
        mc(c3, "Status", status)
        mc(c4, "Best Lap", best_lap)
        mc(c5, "Race Pace (Avg)", avg_pace_str)
        mc(c6, "Top Speed (ST)", speed_str)
    except Exception as e:
        st.warning(f"Session data unavailable for {driver}.")

if compare and driver2:
    s1, s2 = st.columns(2)
    with s1:
        st.markdown(f"<div style='text-align: center; font-size: 14px; font-weight: 600; letter-spacing: 1px; color: {colour1}; margin-bottom: 14px;'>{_fmt_driver(driver1)}</div>", unsafe_allow_html=True)
        render_session_stats(driver1, colour1)
    with s2:
        st.markdown(f"<div style='text-align: center; font-size: 14px; font-weight: 600; letter-spacing: 1px; color: {colour2}; margin-bottom: 14px;'>{_fmt_driver(driver2)}</div>", unsafe_allow_html=True)
        render_session_stats(driver2, colour2)
else:
    render_session_stats(driver1, colour1)

# ── Lap Time History ──────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Lap Time History</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_lap_history(driver: str, sess_k: str, laps_df: pd.DataFrame):
    """Return cleaned lap DataFrame for a single driver."""
    try:
        # laps_df is a plain pd.DataFrame (not fastf1.core.Laps), so we
        # filter by the Driver column instead of using .pick_drivers().
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.dropna(subset=["LapTime", "LapNumber"])
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()
        # filter out obvious outliers (safety car laps, pit laps > 3× median)
        median_t = laps["LapTimeSec"].median()
        laps = laps[laps["LapTimeSec"] < median_t * 2.5].copy()
        laps = laps.sort_values("LapNumber").reset_index(drop=True)
        return laps
    except Exception:
        return None


def _lap_history_fig(drivers_data: list, highlight_laps: list) -> go.Figure:
    """
    drivers_data : list of (driver, colour, laps_df)
    highlight_laps: list of selected LapNumber per driver (same order)
    """
    fig = go.Figure()

    for (driver, colour, laps), sel_lap in zip(drivers_data, highlight_laps):
        if laps is None or laps.empty:
            continue

        # ── Compound-coloured marker colours
        cmp_colours = {
            "SOFT": "#FF3333", "MEDIUM": "#FFD700", "HARD": "#CCCCCC",
            "INTERMEDIATE": "#39B54A", "WET": "#0067FF",
        }
        marker_colors = [
            cmp_colours.get(str(c).upper(), "#888888")
            for c in laps.get("Compound", ["?"] * len(laps))
        ]

        # ── Pit-out lap markers (first lap after a pit stop)
        pit_mask = laps["PitOutTime"].notna() if "PitOutTime" in laps.columns else pd.Series(False, index=laps.index)
        pit_laps  = laps[pit_mask]

        # ── Main line trace
        fig.add_trace(go.Scatter(
            x=laps["LapNumber"],
            y=laps["LapTimeSec"],
            mode="lines+markers",
            name=driver,
            line=dict(color=colour, width=2),
            marker=dict(
                color=marker_colors,
                size=7,
                line=dict(color=colour, width=1.2),
                symbol="circle",
            ),
            hovertemplate=(
                f"<b>{driver}</b><br>"
                "Lap %{x}<br>"
                "Time: %{customdata}<br>"
                "<extra></extra>"
            ),
            customdata=[
                f"{int(t//60)}:{t%60:06.3f}"
                for t in laps["LapTimeSec"]
            ],
        ))

        # ── Pit-stop triangles
        if not pit_laps.empty:
            fig.add_trace(go.Scatter(
                x=pit_laps["LapNumber"],
                y=pit_laps["LapTimeSec"],
                mode="markers",
                marker=dict(symbol="triangle-up", size=11, color=colour,
                            line=dict(color="white", width=1.2)),
                name=f"{driver} pit-out",
                hovertemplate=f"<b>{driver}</b> PIT OUT<br>Lap %{{x}}<extra></extra>",
                showlegend=True,
            ))

        # ── Highlight selected lap
        if sel_lap is not None:
            try:
                sel_row = laps[laps["LapNumber"] == int(sel_lap.get("LapNumber", -1))]
                if not sel_row.empty:
                    fig.add_vline(
                        x=int(sel_row["LapNumber"].iloc[0]),
                        line=dict(color=colour, width=1.5, dash="dot"),
                        opacity=0.6,
                        annotation_text=driver,
                        annotation_position="top",
                        annotation_font_size=10,
                    )
            except Exception:
                pass

    fig.update_layout(
        margin=dict(l=0, r=0, t=16, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Lap", gridcolor="rgba(128,128,128,0.15)",
            tickmode="linear", dtick=5, zeroline=False,
        ),
        yaxis=dict(
            title="Lap Time (s)", gridcolor="rgba(128,128,128,0.15)",
            zeroline=False,
            tickformat=".1f",
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
        height=280,
    )
    return fig


_hist_pairs = [(driver1, colour1, _build_lap_history(driver1, sess_key, _all_laps))]
_hist_laps  = [lap1]
if compare and driver2:
    _hist_pairs.append((driver2, colour2, _build_lap_history(driver2, sess_key, _all_laps)))
    _hist_laps.append(lap2)

_all_none = all(p[2] is None or p[2].empty for p in _hist_pairs)
if _all_none:
    st.info("Lap time history not available for this session.")
else:
    # ── Compound filter ───────────────────────────────────────────────────────
    _all_compounds = sorted({
        str(c).upper()
        for _, _, _ldf in _hist_pairs if _ldf is not None and not _ldf.empty
        for c in _ldf["Compound"].dropna().unique()
        if str(c).upper() not in ("NAN", "NONE", "")
    })
    if _all_compounds:
        _selected_compounds = st.multiselect(
            "Filter by compound",
            options=_all_compounds,
            default=_all_compounds,
            format_func=lambda c: COMPOUND_COLOURS.get(c, {}).get("letter", c[0]) + f"  {c.title()}",
            key="lap_hist_compound_filter",
            label_visibility="collapsed",
        )
    else:
        _selected_compounds = _all_compounds

    # Apply compound filter to each driver's laps before plotting
    if _selected_compounds:
        _hist_pairs_filtered = [
            (drv, col,
             ldf[ldf["Compound"].str.upper().isin(_selected_compounds)].copy()
             if ldf is not None else None)
            for drv, col, ldf in _hist_pairs
        ]
    else:
        _hist_pairs_filtered = _hist_pairs

    st.plotly_chart(_lap_history_fig(_hist_pairs_filtered, _hist_laps), width="stretch")

# ── Fuel-Adjusted Pace Analysis ───────────────────────────────────────────────
st.markdown("<div class='section-title'>Fuel-Adjusted Pace</div>", unsafe_allow_html=True)
st.markdown(
    "<div style='font-size:11px; opacity:0.55; margin:-6px 0 10px; letter-spacing:0.3px;'>"
    "Estimates each driver's true one-lap pace by removing the fuel-load penalty. "
    "Each lap of fuel adds roughly <strong>0.03 s</strong> to the lap time — "
    "correcting for this normalises all laps to equivalent <em>empty-tank</em> pace, "
    "making it easier to compare stints across different fuel levels."
    "</div>",
    unsafe_allow_html=True,
)

# ── Fuel effect tuner
_fuel_col, _ = st.columns([1, 3])
with _fuel_col:
    _fuel_effect = st.slider(
        "Fuel effect (s / lap of fuel)",
        min_value=0.01, max_value=0.06,
        value=0.03, step=0.005, format="%.3f",
        help="Industry standard is ~0.030 s per lap of fuel. Adjust to explore sensitivity.",
        key="fuel_effect_slider",
    )


@st.cache_data(show_spinner=False, ttl=3600)
def _build_fuel_adjusted(driver: str, sess_k: str, fuel_effect: float,
                         laps_df: pd.DataFrame):
    """
    Return DataFrame with raw LapTimeSec and FuelAdjSec columns.
    Fuel correction: subtract (total_laps - lap_number) * fuel_effect
    → normalises all laps to empty-tank pace (equivalent to a flying Q-lap).
    """
    try:
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.dropna(subset=["LapTime", "LapNumber"])
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()

        # Outlier filter — same as lap history (>2.5× median removed)
        median_t = laps["LapTimeSec"].median()
        laps = laps[laps["LapTimeSec"] < median_t * 2.5].copy()
        laps = laps.sort_values("LapNumber").reset_index(drop=True)

        # Total laps in the session (used to compute remaining fuel)
        total_laps = int(laps_df["LapNumber"].max())

        # Remaining fuel = laps left to run AFTER current lap
        laps["FuelLapsRemaining"] = (total_laps - laps["LapNumber"]).clip(lower=0)
        laps["FuelCorrection"]    = laps["FuelLapsRemaining"] * fuel_effect
        laps["FuelAdjSec"]        = laps["LapTimeSec"] - laps["FuelCorrection"]

        return laps[["LapNumber", "LapTimeSec", "FuelAdjSec",
                     "FuelCorrection", "Compound"]].copy()
    except Exception:
        return None


def _fuel_pace_fig(drivers_data: list) -> go.Figure:
    """
    drivers_data: list of (driver, colour, df_with_raw_and_adj)
    Plots raw (solid) and fuel-adjusted (dashed) traces side-by-side.
    """
    fig = go.Figure()

    for driver, colour, df in drivers_data:
        if df is None or df.empty:
            continue

        marker_colors = [
            COMPOUND_COLOURS.get(str(c).upper(), COMPOUND_COLOURS["UNKNOWN"])["fill"]
            for c in df["Compound"]
        ]

        # ── Raw pace (solid line, semi-transparent)
        fig.add_trace(go.Scatter(
            x=df["LapNumber"], y=df["LapTimeSec"],
            mode="lines",
            name=f"{driver} raw",
            line=dict(color=colour, width=1.5, dash="dot"),
            opacity=0.45,
            hovertemplate=(
                f"<b>{driver} — Raw</b><br>Lap %{{x}}<br>"
                "Time: %{customdata}<extra></extra>"
            ),
            customdata=[f"{int(t//60)}:{t%60:06.3f}" for t in df["LapTimeSec"]],
        ))

        # ── Fuel-adjusted pace (solid, full opacity with compound markers)
        fig.add_trace(go.Scatter(
            x=df["LapNumber"], y=df["FuelAdjSec"],
            mode="lines+markers",
            name=f"{driver} fuel-adj",
            line=dict(color=colour, width=2.2),
            marker=dict(
                color=marker_colors, size=6,
                line=dict(color=colour, width=1),
            ),
            hovertemplate=(
                f"<b>{driver} — Fuel-Adj</b><br>Lap %{{x}}<br>"
                "Adj Time: %{customdata[0]}<br>"
                "Correction: −%{customdata[1]:.3f} s"
                "<extra></extra>"
            ),
            customdata=[
                [f"{int(t//60)}:{t%60:06.3f}", c]
                for t, c in zip(df["FuelAdjSec"], df["FuelCorrection"])
            ],
        ))

    # ── Annotation for how to read the chart
    fig.add_annotation(
        text="— · — Raw pace  ——  Fuel-adjusted pace",
        xref="paper", yref="paper", x=0.01, y=1.06,
        showarrow=False, font=dict(size=10), opacity=0.5,
        xanchor="left",
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=32, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Lap", gridcolor="rgba(128,128,128,0.15)",
            tickmode="linear", dtick=5, zeroline=False,
        ),
        yaxis=dict(
            title="Lap Time (s)", gridcolor="rgba(128,128,128,0.15)",
            zeroline=False, tickformat=".1f",
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.04,
            xanchor="left", x=0, bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
        height=300,
    )
    return fig


_fuel_pairs = [
    (
        driver1, colour1,
        _build_fuel_adjusted(driver1, sess_key, _fuel_effect, _all_laps)
    )
]
if compare and driver2:
    _fuel_pairs.append((
        driver2, colour2,
        _build_fuel_adjusted(driver2, sess_key, _fuel_effect, _all_laps)
    ))

_fuel_all_none = all(p[2] is None or p[2].empty for p in _fuel_pairs)
if _fuel_all_none:
    st.info("Fuel-adjusted pace not available for this session.")
else:
    st.plotly_chart(_fuel_pace_fig(_fuel_pairs), width="stretch")

    # ── Pace summary stat cards
    _pace_cols = st.columns(len(_fuel_pairs))
    for _pc, (drv, col, df) in zip(_pace_cols, _fuel_pairs):
        if df is None or df.empty:
            continue
        _best_raw  = df["LapTimeSec"].min()
        _best_adj  = df["FuelAdjSec"].min()
        _avg_adj   = df["FuelAdjSec"].median()
        _pc.markdown(
            f"<div class='metric-card' style='--accent:{col};'>"
            f"<div class='metric-label'>{_fmt_driver(drv)} — Fuel-Adj Pace</div>"
            f"<div class='metric-value'>{int(_best_adj//60)}:{_best_adj%60:06.3f}</div>"
            f"<div class='metric-sub'>"
            f"Best raw: {int(_best_raw//60)}:{_best_raw%60:06.3f} · "
            f"Median adj: {int(_avg_adj//60)}:{_avg_adj%60:06.3f}"
            f"</div></div>",
            unsafe_allow_html=True,
        )

# ── Tyre Stint Timeline ───────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Tyre Stint Timeline</div>", unsafe_allow_html=True)

# _CMP_PALETTE removed — use COMPOUND_COLOURS (defined in Constants block) directly.


@st.cache_data(show_spinner=False, ttl=3600)
def _build_stints(driver: str, sess_k: str, laps_df: pd.DataFrame):
    """Return a list of stint dicts: {compound, start_lap, end_lap, laps, fresh}."""
    try:
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.dropna(subset=["LapNumber"]).sort_values("LapNumber")
        stints, current = [], None
        for _, row in laps.iterrows():
            cmp = str(row.get("Compound", "UNKNOWN")).upper()
            if cmp in ("NAN", "NONE", ""):
                cmp = "UNKNOWN"
            ln = int(row["LapNumber"])
            fresh = bool(row.get("FreshTyre", False))
            if current is None or cmp != current["compound"] or (
                "PitOutTime" in row and pd.notna(row.get("PitOutTime"))
            ):
                if current:
                    stints.append(current)
                current = {"compound": cmp, "start_lap": ln,
                           "end_lap": ln, "fresh": fresh}
            else:
                current["end_lap"] = ln
        if current:
            stints.append(current)
        for s in stints:
            s["laps"] = s["end_lap"] - s["start_lap"] + 1
        return stints
    except Exception:
        return []


def _stint_fig(drivers_stints: list) -> go.Figure:
    """
    drivers_stints: list of (driver_label, stints_list)
    Draws a horizontal Gantt-style bar per driver, coloured by compound.
    """
    fig = go.Figure()

    for driver, stints in drivers_stints:
        for s in stints:
            palette = COMPOUND_COLOURS.get(s["compound"], COMPOUND_COLOURS["UNKNOWN"])
            width   = s["end_lap"] - s["start_lap"] + 1
            fresh_marker = " ★" if s.get("fresh") else ""

            fig.add_trace(go.Bar(
                x=[width],
                y=[driver],
                base=[s["start_lap"] - 1],   # base = left-edge of bar
                orientation="h",
                name=s["compound"].title(),
                marker=dict(
                    color=palette["fill"],
                    line=dict(color="rgba(255,255,255,0.25)", width=1),
                ),
                text=f"{s['compound'].title()}{fresh_marker} · {s['laps']}L",
                textposition="inside",
                insidetextfont=dict(color=palette["text"], size=10),
                hovertemplate=(
                    f"<b>{driver}</b><br>"
                    f"Compound: {s['compound'].title()}{fresh_marker}<br>"
                    f"Laps {s['start_lap']}–{s['end_lap']} "
                    f"({s['laps']} laps)<extra></extra>"
                ),
                showlegend=False,
            ))

    # ── Compound legend swatches (manual)
    for cmp, pal in COMPOUND_COLOURS.items():
        if cmp == "UNKNOWN":
            continue
        fig.add_trace(go.Bar(
            x=[0], y=[""], orientation="h",
            marker=dict(color=pal["fill"]),
            name=cmp.title(),
            showlegend=True,
        ))

    fig.update_layout(
        barmode="stack",
        margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Lap", gridcolor="rgba(128,128,128,0.15)",
            tickmode="linear", dtick=5, zeroline=False,
        ),
        yaxis=dict(
            gridcolor="rgba(0,0,0,0)", zeroline=False,
            categoryorder="array",
            categoryarray=[d for d, _ in reversed(drivers_stints)],
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="left", x=0, bgcolor="rgba(0,0,0,0)",
            title_text="Compound:",
        ),
        height=max(120, 100 + 70 * len(drivers_stints)),
    )
    return fig


_stint_data = [(driver1, _build_stints(driver1, sess_key, _all_laps))]
if compare and driver2:
    _stint_data.append((driver2, _build_stints(driver2, sess_key, _all_laps)))

if all(not s for _, s in _stint_data):
    st.info("Stint data not available for this session.")
else:
    st.plotly_chart(_stint_fig(_stint_data), width="stretch")




# ── Pit Stop Summary ──────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Pit Stop Summary</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_pit_stops(driver: str, sess_k: str, laps_df: pd.DataFrame) -> list[dict] | None:
    """Return a list of pit stop dicts for one driver: lap, duration_s, old_cmp, new_cmp."""
    try:
        laps = laps_df[laps_df["Driver"] == driver].copy()
        laps = laps.sort_values("LapNumber").reset_index(drop=True)

        stops = []
        for i, row in laps.iterrows():
            if pd.isna(row.get("PitInTime")) or pd.isna(row.get("PitOutTime")):
                continue
            try:
                duration_s = (row["PitOutTime"] - row["PitInTime"]).total_seconds()
            except Exception:
                duration_s = None

            # Compound before pit = this lap's compound
            old_cmp = str(row.get("Compound", "?")).title()

            # Compound after pit = next lap's compound
            new_cmp = "?"
            if i + 1 < len(laps):
                next_cmp = laps.iloc[i + 1].get("Compound", "?")
                if pd.notna(next_cmp):
                    new_cmp = str(next_cmp).title()

            stops.append({
                "lap":      int(row["LapNumber"]),
                "duration": round(duration_s, 1) if duration_s is not None else None,
                "old_cmp":  old_cmp,
                "new_cmp":  new_cmp,
            })
        return stops if stops else None
    except Exception:
        return None


def _render_pit_table(stops: list[dict], colour: str, driver_label: str) -> str:
    """Build an HTML pit stop table for one driver."""
    def _cmp_dot(cmp: str) -> str:
        pal = COMPOUND_COLOURS.get(cmp.upper(), COMPOUND_COLOURS["UNKNOWN"])
        return (
            f"<span style='display:inline-block; width:8px; height:8px; border-radius:50%; "
            f"background:{pal['fill']}; margin-right:5px; vertical-align:middle;'></span>"
        )

    rows_html = ""
    for idx, s in enumerate(stops):
        row_bg = "rgba(255,255,255,0.03)" if idx % 2 == 0 else "transparent"
        dur    = f"{s['duration']:.1f}s" if s["duration"] is not None else "—"
        rows_html += (
            f"<tr style='background:{row_bg};'>"
            f"<td style='padding:7px 10px; color:#aaa;'>#{idx+1}</td>"
            f"<td style='padding:7px 10px;'>Lap {s['lap']}</td>"
            f"<td style='padding:7px 10px; font-weight:600; color:{colour};'>{dur}</td>"
            f"<td style='padding:7px 10px;'>{_cmp_dot(s['old_cmp'])}{s['old_cmp']}</td>"
            f"<td style='padding:7px 10px;'>{_cmp_dot(s['new_cmp'])}{s['new_cmp']}</td>"
            f"</tr>"
        )

    return (
        f"<div style='margin-bottom:16px;'>"
        f"<div style='font-size:12px; font-weight:600; color:{colour}; "
        f"letter-spacing:0.5px; margin-bottom:6px;'>{driver_label}</div>"
        f"<table style='width:100%; border-collapse:collapse; font-size:13px;'>"
        f"<thead><tr style='border-bottom:1px solid rgba(128,128,128,0.2); "
        f"font-size:11px; opacity:0.55; text-transform:uppercase; letter-spacing:0.5px;'>"
        f"<th style='padding:5px 10px; text-align:left;'>Stop</th>"
        f"<th style='padding:5px 10px; text-align:left;'>Lap</th>"
        f"<th style='padding:5px 10px; text-align:left;'>Duration</th>"
        f"<th style='padding:5px 10px; text-align:left;'>From</th>"
        f"<th style='padding:5px 10px; text-align:left;'>To</th>"
        f"</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table></div>"
    )


_pit_d1 = _build_pit_stops(driver1, sess_key, _all_laps)
_pit_d2 = _build_pit_stops(driver2, sess_key, _all_laps) if compare and driver2 else None

if _pit_d1 is None and _pit_d2 is None:
    st.info("Pit stop data is not available for this session "
            "(Race and Sprint sessions only).")
else:
    _pit_html = ""
    if _pit_d1:
        _pit_html += _render_pit_table(_pit_d1, colour1, _fmt_driver(driver1))
    if _pit_d2:
        _pit_html += _render_pit_table(_pit_d2, colour2, _fmt_driver(driver2))
    if _pit_html:
        st.markdown(
            f"<div style='background:var(--secondary-background-color); "
            f"border:1px solid rgba(128,128,128,0.15); border-radius:12px; "
            f"padding:16px 20px;'>{_pit_html}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("No pit stops recorded for the selected driver(s).")


st.markdown("<div class='section-title'>Telemetry</div>", unsafe_allow_html=True)

if tel1 is None:
    st.warning("No telemetry available for the selected lap.")
    st.stop()

# channel definitions: (subplot_title, df_col, y_label, special_flag)
CHANNELS = [
    ("Speed",    "Speed",    "km/h",   ""),
    ("Throttle", "Throttle", "%",       ""),
    ("Brake",    "Brake",    "",        "brake"),
    ("RPM",      "RPM",      "RPM",    ""),
    ("Gear",     "nGear",    "Gear",   "gear"),
    ("DRS",      "DRS",      "DRS",    "drs"),
]
N = len(CHANNELS)

# Height ratios — brake/DRS rows are shorter
H_RATIOS = [3, 2, 1, 2, 1.5, 1]


def build_chart(drivers_telemetry: list, title_str: str, fig_width: float = 14):
    """drivers_telemetry: list of (driver_label, colour, tel_df)"""
    fig = plt.figure(figsize=(fig_width, 11), facecolor="none")
    gs = gridspec.GridSpec(N, 1, figure=fig, hspace=0.04,
                           height_ratios=H_RATIOS, top=0.94, bottom=0.06,
                           left=0.07, right=0.97)
    axes = [fig.add_subplot(gs[i]) for i in range(N)]

    for ax_i, (_, col, ylabel, special) in enumerate(CHANNELS):
        ax = axes[ax_i]
        for drv_label, colour, tel in drivers_telemetry:
            if tel is not None and col in tel.columns:
                lw = 1.7 if drv_label == drivers_telemetry[0][0] else 1.5
                ls = "-" if drv_label == drivers_telemetry[0][0] else "--"
                al = 0.95 if drv_label == drivers_telemetry[0][0] else 0.80
                ax.plot(tel["Distance"], tel[col],
                        color=colour, linewidth=lw, linestyle=ls, alpha=al,
                        label=drv_label, solid_capstyle="round")
                if col == "Speed" and drv_label == drivers_telemetry[0][0]:
                    ax.fill_between(tel["Distance"], tel[col], alpha=0.05, color=colour)

        unit = f" ({ylabel})" if ylabel else ""
        style_ax(ax, col if not ylabel else ylabel + unit if special not in ("brake","drs","gear") else col, special)

        # gear: integer y ticks
        if special == "gear":
            ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%d"))
            ax.set_ylim(0.5, 8.5)
            ax.set_yticks(range(1, 9))

        if ax_i < N - 1:
            ax.set_xticklabels([])
        else:
            ax.set_xlabel("Distance (m)", fontsize=11, labelpad=8)

    for ax_i, (label, _, _, _) in enumerate(CHANNELS):
        axes[ax_i].yaxis.set_label_position("left")
        axes[ax_i].text(1.002, 0.5, label, transform=axes[ax_i].transAxes,
                        fontsize=10, va="center", ha="left",
                        rotation=0, fontweight="600", alpha=0.6)

    fig.suptitle(title_str, fontsize=12, fontweight="bold", y=0.98)

    # Legend
    handles = [mpatches.Patch(color=c, label=d) for d, c, _ in drivers_telemetry]
    if len(handles) > 1:
        fig.legend(handles=handles, loc="upper right",
                   bbox_to_anchor=(0.97, 0.965), fontsize=9,
                   framealpha=0.9, handlelength=1.2, handleheight=0.8)
    return fig


# ── Overlapping ───────────────────────────────────────────────────────────────
if chart_mode == "Overlapping" or not compare:
    drv_list = [(driver1, colour1, tel1)]
    if compare and tel2 is not None:
        drv_list.append((driver2, colour2, tel2))

    title = f"{gp} {year}  ·  {session_label}"
    if compare and driver2:
        title += f"  ·  {driver1} vs {driver2}"
    else:
        title += f"  ·  {driver1}"

    fig = build_chart(drv_list, title)
    st.pyplot(fig, width="stretch")
    plt.close(fig)

# ── Separate ──────────────────────────────────────────────────────────────────
else:
    lc, rc = st.columns(2)
    for col_ctx, driver, tel, colour, lap_obj in [
        (lc, driver1, tel1, colour1, lap1),
        (rc, driver2, tel2, colour2, lap2),
    ]:
        with col_ctx:
            if tel is None:
                st.warning(f"No telemetry for {driver}")
                continue
            try:
                lt = format_laptime(lap_obj.get("LapTime"))
            except Exception:
                lt = ""
            title = f"{driver}  ·  {lt}"
            fig = build_chart([(driver, colour, tel)], title, fig_width=7)
            st.pyplot(fig, width="stretch")
            plt.close(fig)


# ── Export Telemetry ──────────────────────────────────────────────────────────
with st.expander("⬇️  Export Telemetry Data", expanded=False):
    st.markdown(
        "<div style='font-size:12px; opacity:0.65; margin-bottom:10px;'>"
        "Download the raw telemetry for the selected lap(s) as a CSV file. "
        "Includes Distance, Speed, Throttle, Brake, RPM, Gear, DRS, "
        "Sector 1/2/3 times, and lap metadata."
        "</div>",
        unsafe_allow_html=True,
    )

    def _build_export_csv(driver: str, tel_df, lap_obj) -> bytes:
        """Merge lap metadata into the telemetry dataframe and return CSV bytes."""
        if tel_df is None or tel_df.empty:
            return b""
        export_cols = [c for c in
                       ["Distance", "Speed", "Throttle", "Brake", "RPM", "nGear", "DRS",
                        "X", "Y", "Z", "Time", "SessionTime"]
                       if c in tel_df.columns]
        df = tel_df[export_cols].copy()
        # Rename nGear → Gear for clarity
        df = df.rename(columns={"nGear": "Gear"})
        # Inject lap metadata as constant columns at the front
        df.insert(0, "Driver",    driver)
        df.insert(1, "LapNumber", int(lap_obj.get("LapNumber", 0)) if lap_obj is not None else "")
        df.insert(2, "LapTime",   format_laptime(lap_obj.get("LapTime")) if lap_obj is not None else "")
        df.insert(3, "Compound",  str(lap_obj.get("Compound", "?")).title() if lap_obj is not None else "")
        # Sector times — formatted as seconds (3 dp) for readability
        for _scol, _slabel in [
            ("Sector1Time", "Sector1Time_s"),
            ("Sector2Time", "Sector2Time_s"),
            ("Sector3Time", "Sector3Time_s"),
        ]:
            _sval = lap_obj.get(_scol) if lap_obj is not None else None
            try:
                _ssec = round(_sval.total_seconds(), 3) if _sval is not None and pd.notna(_sval) else ""
            except Exception:
                _ssec = ""
            df.insert(4, _slabel, _ssec)
        return df.to_csv(index=False).encode("utf-8")

    # ── Driver 1 download
    exp_cols = [st.columns(2)[0]]   # left half
    if compare and driver2 and tel2 is not None:
        exp_cols = list(st.columns(2))

    with exp_cols[0]:
        csv1 = _build_export_csv(driver1, tel1, lap1)
        fname1 = f"pitwall_{driver1}_lap{int(lap1.get('LapNumber', 0)) if lap1 is not None else 'X'}.csv"
        st.download_button(
            label=f"📥  {driver1} — Download CSV",
            data=csv1,
            file_name=fname1,
            mime="text/csv",
            disabled=(csv1 == b""),
            width="stretch",
        )

    # ── Driver 2 download (comparison mode only)
    if compare and driver2 and tel2 is not None and len(exp_cols) > 1:
        with exp_cols[1]:
            csv2 = _build_export_csv(driver2, tel2, lap2)
            fname2 = f"pitwall_{driver2}_lap{int(lap2.get('LapNumber', 0)) if lap2 is not None else 'X'}.csv"
            st.download_button(
                label=f"📥  {driver2} — Download CSV",
                data=csv2,
                file_name=fname2,
                mime="text/csv",
                disabled=(csv2 == b""),
                width="stretch",
            )

# ── Speed delta (overlapping + comparison) ────────────────────────────────────

if compare and chart_mode == "Overlapping" and tel1 is not None and tel2 is not None:
    if "Speed" in tel1.columns and "Speed" in tel2.columns:
        st.markdown("<div class='section-title'>Speed Delta</div>", unsafe_allow_html=True)

        speed2_i = np.interp(tel1["Distance"], tel2["Distance"], tel2["Speed"])
        delta = tel1["Speed"].values - speed2_i

        fig_d, ax_d = plt.subplots(figsize=(14, 2.8), facecolor="none")
        ax_d.set_facecolor("none")
        ax_d.axhline(0, color="gray", alpha=0.5, linewidth=0.8)
        ax_d.fill_between(tel1["Distance"], delta,
                          where=(delta >= 0), color=colour1, alpha=0.6,
                          label=f"{driver1} faster", interpolate=True)
        ax_d.fill_between(tel1["Distance"], delta,
                          where=(delta < 0),  color=colour2, alpha=0.6,
                          label=f"{driver2} faster", interpolate=True)
        ax_d.set_ylabel("Δ Speed (km/h)", fontsize=11)
        ax_d.set_xlabel("Distance (m)", fontsize=11)
        ax_d.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f"))
        for spine in ax_d.spines.values():
            spine.set_edgecolor("gray")
            spine.set_alpha(0.3)
        ax_d.grid(True, linestyle=":", linewidth=0.3, alpha=0.8)
        ax_d.tick_params(labelsize=10)
        ax_d.legend(fontsize=10, framealpha=0.9)
        fig_d.tight_layout()
        st.pyplot(fig_d, width='stretch')
        plt.close(fig_d)

# ── Fastest Laps Leaderboard ──────────────────────────────────────────────────
st.markdown("<div class='section-title'>Fastest Laps Leaderboard</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_leaderboard(sess_k: str, laps_df: pd.DataFrame):
    """Return a ranked DataFrame of all drivers' fastest laps."""
    try:
        laps = laps_df.copy()
        laps = laps.dropna(subset=["LapTime", "Driver"])
        # Get each driver's fastest lap
        idx = laps.groupby("Driver")["LapTime"].idxmin()
        best = laps.loc[idx].copy().reset_index(drop=True)
        best["LapTimeSec"] = best["LapTime"].dt.total_seconds()
        best = best.sort_values("LapTimeSec").reset_index(drop=True)

        # Gap to P1
        p1_time = best["LapTimeSec"].iloc[0]
        best["GapToP1"] = best["LapTimeSec"] - p1_time

        # Format columns
        best["Pos"]      = best.index + 1
        best["Time"]     = best["LapTime"].apply(format_laptime)
        best["Gap"]      = best["GapToP1"].apply(
            lambda g: "—" if g == 0 else f"+{g:.3f}s"
        )
        best["Lap"]      = best["LapNumber"].astype(int)
        best["Compound"] = best["Compound"].fillna("?").astype(str).str.title()
        best["Top Speed (km/h)"] = best["SpeedST"].apply(
            lambda s: f"{s:.0f}" if pd.notna(s) else "—"
        )

        return best[["Pos", "Driver", "Time", "Gap", "Compound", "Lap", "Top Speed (km/h)"]]
    except Exception:
        return None


def _render_leaderboard(lb_df, highlight_drivers: list, highlight_colours: list):
    """Render leaderboard as a styled HTML table."""
    colour_map = dict(zip(highlight_drivers, highlight_colours))
    rows_html = ""
    for _, row in lb_df.iterrows():
        drv        = str(row["Driver"])
        is_hl      = drv in colour_map
        accent     = colour_map.get(drv, "transparent")
        row_bg     = f"{accent}18" if is_hl else "transparent"
        border_css = f"border-left: 3px solid {accent};" if is_hl else "border-left: 3px solid transparent;"
        pos_col    = f"<span style='color:{accent}; font-weight:700;'>{row['Pos']}</span>" if is_hl else str(row["Pos"])

        # Compound colour dot — derived from canonical COMPOUND_COLOURS
        cmp     = str(row["Compound"])
        dot_col = COMPOUND_COLOURS.get(cmp.upper(), COMPOUND_COLOURS["UNKNOWN"])["fill"]
        cmp_html = (
            f"<span style='display:inline-block; width:8px; height:8px; "
            f"border-radius:50%; background:{dot_col}; margin-right:5px; vertical-align:middle;'></span>"
            f"{cmp}"
        )

        rows_html += (
            f"<tr style='background:{row_bg}; {border_css}'>"
            f"<td style='padding:7px 10px; text-align:center;'>{pos_col}</td>"
            f"<td style='padding:7px 10px; font-weight:{'600' if is_hl else '400'};'>{_fmt_driver(drv)}</td>"
            f"<td style='padding:7px 10px; font-family:monospace; font-size:13px;'>{row['Time']}</td>"
            f"<td style='padding:7px 10px; font-family:monospace; font-size:12px; opacity:0.7;'>{row['Gap']}</td>"
            f"<td style='padding:7px 10px;'>{cmp_html}</td>"
            f"<td style='padding:7px 10px; text-align:center;'>{row['Lap']}</td>"
            f"<td style='padding:7px 10px; text-align:center;'>{row['Top Speed (km/h)']}</td>"
            "</tr>"
        )

    table_html = f"""
    <div style='overflow-x:auto; border-radius:12px; border:1px solid rgba(128,128,128,0.15); margin-bottom:8px;'>
    <table style='width:100%; border-collapse:collapse; font-size:13px;'>
      <thead>
        <tr style='border-bottom:1px solid rgba(128,128,128,0.2); opacity:0.6; font-size:10px;
                   letter-spacing:1.5px; text-transform:uppercase;'>
          <th style='padding:8px 10px;'>Pos</th>
          <th style='padding:8px 10px; text-align:left;'>Driver</th>
          <th style='padding:8px 10px; text-align:left;'>Time</th>
          <th style='padding:8px 10px; text-align:left;'>Gap</th>
          <th style='padding:8px 10px; text-align:left;'>Compound</th>
          <th style='padding:8px 10px;'>Lap</th>
          <th style='padding:8px 10px;'>Top Speed</th>
        </tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)


_lb = _build_leaderboard(sess_key, _all_laps)
if _lb is None or _lb.empty:
    st.info("Leaderboard not available for this session.")
else:
    _hl_drivers  = [driver1] + ([driver2] if compare and driver2 else [])
    _hl_colours  = [colour1] + ([colour2] if compare and driver2 else [])
    _render_leaderboard(_lb, _hl_drivers, _hl_colours)

# ── Ideal Lap vs Actual Lap ───────────────────────────────────────────────────
st.markdown("<div class='section-title'>Ideal Lap vs Actual Lap</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_ideal_lap(sess_k: str, laps_df: pd.DataFrame) -> pd.DataFrame | None:
    """
    For every driver, find best S1, best S2, best S3 across all valid laps.
    Returns a DataFrame with columns:
        Driver, BestS1, BestS2, BestS3, TheoreticalBest,
        ActualBest, Delta, BestS1Lap, BestS2Lap, BestS3Lap
    sorted by TheoreticalBest ascending.
    """
    try:
        laps = laps_df.copy()
        needed = ["Driver", "LapNumber", "Sector1Time", "Sector2Time",
                  "Sector3Time", "LapTime"]
        laps = laps.dropna(subset=["Driver", "LapTime"])

        # Check sector columns exist and have at least some data
        for col in ["Sector1Time", "Sector2Time", "Sector3Time"]:
            if col not in laps.columns or laps[col].dropna().empty:
                return None

        records = []
        for drv, grp in laps.groupby("Driver"):
            s1 = grp.dropna(subset=["Sector1Time"])
            s2 = grp.dropna(subset=["Sector2Time"])
            s3 = grp.dropna(subset=["Sector3Time"])
            lt = grp.dropna(subset=["LapTime"])
            if s1.empty or s2.empty or s3.empty or lt.empty:
                continue

            best_s1_row = s1.loc[s1["Sector1Time"].idxmin()]
            best_s2_row = s2.loc[s2["Sector2Time"].idxmin()]
            best_s3_row = s3.loc[s3["Sector3Time"].idxmin()]

            best_s1 = best_s1_row["Sector1Time"].total_seconds()
            best_s2 = best_s2_row["Sector2Time"].total_seconds()
            best_s3 = best_s3_row["Sector3Time"].total_seconds()

            theoretical = best_s1 + best_s2 + best_s3
            actual_best = lt["LapTime"].min().total_seconds()
            delta = actual_best - theoretical

            records.append({
                "Driver":          str(drv),
                "BestS1":          best_s1,
                "BestS2":          best_s2,
                "BestS3":          best_s3,
                "TheoreticalBest": theoretical,
                "ActualBest":      actual_best,
                "Delta":           delta,
                "BestS1Lap":       int(best_s1_row["LapNumber"]),
                "BestS2Lap":       int(best_s2_row["LapNumber"]),
                "BestS3Lap":       int(best_s3_row["LapNumber"]),
            })

        if not records:
            return None

        df = pd.DataFrame(records).sort_values("TheoreticalBest").reset_index(drop=True)
        df["Pos"] = df.index + 1

        # Gap to theoretical pole (best theoretical lap overall)
        pole_time = df["TheoreticalBest"].iloc[0]
        df["GapToPole"] = df["TheoreticalBest"] - pole_time

        return df
    except Exception:
        return None


def _fmt_sec(s: float) -> str:
    """Format seconds as M:SS.mmm lap-time string."""
    m = int(s // 60)
    return f"{m}:{s % 60:06.3f}"


_ideal_df = _build_ideal_lap(sess_key, _all_laps)

if _ideal_df is None or _ideal_df.empty:
    st.info(
        "Sector time data is not available for this session — "
        "Ideal Lap analysis requires Sector1Time / Sector2Time / Sector3Time data."
    )
else:
    # ── Per-driver delta cards for selected driver(s) ──────────────────────────
    _card_drivers  = [driver1] + ([driver2] if compare and driver2 else [])
    _card_colours  = [colour1] + ([colour2] if compare and driver2 else [])

    _delta_cards_html = ""
    for _cd, _cc in zip(_card_drivers, _card_colours):
        _row = _ideal_df[_ideal_df["Driver"] == _cd]
        if _row.empty:
            continue
        _r = _row.iloc[0]
        _sign = "+" if _r["Delta"] >= 0 else "-"
        _delta_str = f"{_sign}{abs(_r['Delta']):.3f}s"
        _delta_col  = "#ff6b6b" if _r["Delta"] > 0.05 else "#51cf66"
        _delta_cards_html += (
            f"<div style='background:var(--secondary-background-color);"
            f" border:1px solid rgba(128,128,128,0.15); border-radius:12px;"
            f" padding:14px 18px; flex:1; min-width:220px;'>"
            f"<div style='font-size:11px; font-weight:600; letter-spacing:1px;"
            f" text-transform:uppercase; color:{_cc}; margin-bottom:8px;'>"
            f"{_fmt_driver(_cd)}</div>"
            f"<div style='display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px;"
            f" margin-bottom:10px;'>"
            f"<div style='font-size:11px; opacity:0.6;'>S1</div>"
            f"<div style='font-size:11px; opacity:0.6;'>S2</div>"
            f"<div style='font-size:11px; opacity:0.6;'>S3</div>"
            f"<div style='font-size:13px; font-weight:600;'>{_r['BestS1']:.3f}s</div>"
            f"<div style='font-size:13px; font-weight:600;'>{_r['BestS2']:.3f}s</div>"
            f"<div style='font-size:13px; font-weight:600;'>{_r['BestS3']:.3f}s</div>"
            f"<div style='font-size:10px; opacity:0.45;'>Lap {_r['BestS1Lap']}</div>"
            f"<div style='font-size:10px; opacity:0.45;'>Lap {_r['BestS2Lap']}</div>"
            f"<div style='font-size:10px; opacity:0.45;'>Lap {_r['BestS3Lap']}</div>"
            f"</div>"
            f"<div style='border-top:1px solid rgba(128,128,128,0.15);"
            f" padding-top:8px; display:flex; justify-content:space-between;"
            f" align-items:center;'>"
            f"<div><div style='font-size:10px; opacity:0.5;'>Theoretical Best</div>"
            f"<div style='font-size:15px; font-weight:700;'>"
            f"{_fmt_sec(_r['TheoreticalBest'])}</div></div>"
            f"<div style='text-align:right;'>"
            f"<div style='font-size:10px; opacity:0.5;'>Time Left on Table</div>"
            f"<div style='font-size:15px; font-weight:700; color:{_delta_col};'>"
            f"{_delta_str}</div></div>"
            f"</div></div>"
        )

    if _delta_cards_html:
        st.markdown(
            f"<div style='display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px;'>"
            f"{_delta_cards_html}</div>",
            unsafe_allow_html=True,
        )

    # ── Full-field ideal lap table ─────────────────────────────────────────────
    _hl_set = set([driver1] + ([driver2] if compare and driver2 else []))
    _pole_t  = _ideal_df["TheoreticalBest"].iloc[0]

    _tbl_rows = ""
    for _, _r in _ideal_df.iterrows():
        _is_hl  = _r["Driver"] in _hl_set
        _hl_col = colour1 if _r["Driver"] == driver1 else (
                  colour2 if compare and _r["Driver"] == driver2 else None)
        _row_style = (
            f"border-left: 3px solid {_hl_col};"
            f" background: rgba({hex_to_rgb(_hl_col)},0.06);"
        ) if _is_hl and _hl_col else ""

        _gap_str  = "—" if _r["GapToPole"] < 0.001 else f"+{_r['GapToPole']:.3f}s"
        _sign     = "+" if _r["Delta"] >= 0 else "-"
        _d_str    = f"{_sign}{abs(_r['Delta']):.3f}s"
        _d_col    = "#ff6b6b" if _r["Delta"] > 0.05 else "#51cf66"
        _name     = _fmt_driver(_r["Driver"])

        _tbl_rows += (
            f"<tr style='{_row_style}'>"
            f"<td style='padding:7px 10px; opacity:0.5;'>{int(_r['Pos'])}</td>"
            f"<td style='padding:7px 10px; font-weight:{'700' if _is_hl else '400'};'>"
            f"{_name}</td>"
            f"<td style='padding:7px 10px;'>{_r['BestS1']:.3f}s</td>"
            f"<td style='padding:7px 10px;'>{_r['BestS2']:.3f}s</td>"
            f"<td style='padding:7px 10px;'>{_r['BestS3']:.3f}s</td>"
            f"<td style='padding:7px 10px; font-weight:600;'>"
            f"{_fmt_sec(_r['TheoreticalBest'])}</td>"
            f"<td style='padding:7px 10px; opacity:0.6;'>{_gap_str}</td>"
            f"<td style='padding:7px 10px; font-weight:600; color:{_d_col};'>{_d_str}</td>"
            f"</tr>"
        )

    _ideal_tbl = f"""
    <div style='background:var(--secondary-background-color);
                border:1px solid rgba(128,128,128,0.15);
                border-radius:12px; padding:16px 20px; overflow-x:auto;'>
      <table style='width:100%; border-collapse:collapse; font-size:13px;'>
        <thead>
          <tr style='border-bottom:1px solid rgba(128,128,128,0.2);
                     font-size:11px; opacity:0.55; text-transform:uppercase;
                     letter-spacing:0.5px;'>
            <th style='padding:5px 10px; text-align:left;'>Pos</th>
            <th style='padding:5px 10px; text-align:left;'>Driver</th>
            <th style='padding:5px 10px; text-align:left;'>Best S1</th>
            <th style='padding:5px 10px; text-align:left;'>Best S2</th>
            <th style='padding:5px 10px; text-align:left;'>Best S3</th>
            <th style='padding:5px 10px; text-align:left;'>Theoretical Best</th>
            <th style='padding:5px 10px; text-align:left;'>Gap to Pole</th>
            <th style='padding:5px 10px; text-align:left;'>Time on Table</th>
          </tr>
        </thead>
        <tbody>{_tbl_rows}</tbody>
      </table>
    </div>
    """
    st.markdown(_ideal_tbl, unsafe_allow_html=True)



# ── Gap to Leader ─────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Gap to Leader</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_gap_data(sess_k: str, laps_df: pd.DataFrame):
    """Return a dict {driver: pd.Series(gap_seconds, index=lap_number)} for all drivers."""
    try:
        laps = laps_df.copy()
        # Only use valid laps with a recorded LapTime
        laps = laps.dropna(subset=["LapTime", "LapNumber", "Driver"])
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()
        # For each driver sort by lap number and compute cumulative race time
        gap_dict = {}
        for drv, grp in laps.groupby("Driver"):
            grp = grp.sort_values("LapNumber").copy()
            grp["CumTime"] = grp["LapTimeSec"].cumsum()
            gap_dict[drv] = grp.set_index("LapNumber")["CumTime"]
        if not gap_dict:
            return None, None
        # Build leader reference: at each lap, min cumulative time across drivers
        all_laps_idx = sorted({lap for s in gap_dict.values() for lap in s.index})
        leader_time = pd.Series(index=all_laps_idx, dtype=float)
        for lap in all_laps_idx:
            times_at_lap = [s.get(lap) for s in gap_dict.values() if lap in s.index]
            times_at_lap = [t for t in times_at_lap if t is not None]
            if times_at_lap:
                leader_time[lap] = min(times_at_lap)
        # Convert each driver's cumulative time to gap vs leader
        gap_to_leader = {}
        for drv, cum in gap_dict.items():
            gap = cum - leader_time.reindex(cum.index)
            gap_to_leader[drv] = gap
        # Also return track status by lap for shading
        try:
            ts = st.session_state["session"].track_status.copy()
            ts["LapNumber"] = ts.index
        except Exception:
            ts = None
        return gap_to_leader, ts
    except Exception:
        return None, None

def _gap_chart_fig(gap_to_leader, highlight_drivers, highlight_colours, session_laps):
    """Build and return a Plotly figure of gap to leader."""
    fig = go.Figure()

    # Grey background traces for all other drivers
    for drv, gap in gap_to_leader.items():
        if drv in highlight_drivers:
            continue
        fig.add_trace(go.Scatter(
            x=list(gap.index), y=list(gap.values),
            mode="lines",
            line=dict(color="rgba(180,180,180,0.18)", width=1),
            showlegend=False,
            hoverinfo="skip",
        ))

    # Mark pit laps for highlighted drivers
    try:
        pit_laps_all = session_laps[session_laps["PitOutTime"].notna()]["LapNumber"].tolist()
    except Exception:
        pit_laps_all = []

    # Highlighted driver traces
    for drv, col in zip(highlight_drivers, highlight_colours):
        if drv not in gap_to_leader:
            continue
        gap = gap_to_leader[drv]
        # Pit lap markers
        pit_x = [ln for ln in pit_laps_all
                 if ln in gap.index and
                 session_laps[(session_laps["Driver"] == drv) &
                              (session_laps["LapNumber"] == ln)].shape[0] > 0]
        fig.add_trace(go.Scatter(
            x=list(gap.index), y=list(gap.values),
            mode="lines",
            line=dict(color=col, width=2.5),
            name=drv,
            hovertemplate=f"<b>{drv}</b><br>Lap %{{x}}<br>Gap: +%{{y:.1f}} s<extra></extra>",
        ))
        if pit_x:
            fig.add_trace(go.Scatter(
                x=pit_x,
                y=[gap.get(ln) for ln in pit_x],
                mode="markers",
                marker=dict(symbol="triangle-down", size=10, color=col,
                            line=dict(color="white", width=1)),
                name=f"{drv} pit",
                hovertemplate=f"<b>{drv}</b> PIT<br>Lap %{{x}}<extra></extra>",
                showlegend=True,
            ))

    # Leader line at 0
    fig.add_hline(y=0, line=dict(color="rgba(255,135,0,0.5)", width=1.5, dash="dot"),
                  annotation_text="Leader", annotation_position="right")

    fig.update_layout(
        margin=dict(l=0, r=0, t=16, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(title="Lap", gridcolor="rgba(128,128,128,0.15)",
                   tickmode="linear", dtick=5, zeroline=False),
        yaxis=dict(title="Gap to Leader (s)", gridcolor="rgba(128,128,128,0.15)",
                   zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                    bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        height=420,
    )
    return fig

# Only show for race/qualifying sessions (gap is meaningful)
_gtl_data, _ts_data = _build_gap_data(sess_key, _all_laps)

if _gtl_data is None:
    st.info("Gap to Leader data is not available for this session.")
else:
    _highlight = [driver1]
    _colours   = [colour1]
    if compare and driver2 and driver2 in _gtl_data:
        _highlight.append(driver2)
        _colours.append(colour2)

    _gtl_fig = _gap_chart_fig(_gtl_data, _highlight, _colours, sess.laps)
    st.plotly_chart(_gtl_fig, width="stretch")

    # Show quick stats below the chart
    _stat_cols = st.columns(len(_highlight))
    for _col, _drv, _col_colour in zip(_stat_cols, _highlight, _colours):
        if _drv in _gtl_data:
            _gap_s = _gtl_data[_drv]
            _final_gap = _gap_s.iloc[-1]
            _max_gap   = _gap_s.max()
            _col.markdown(
                f"<div class='metric-card'>"
                f"<div class='metric-label'>{_drv} — Final Gap</div>"
                f"<div class='metric-value' style='color:{_col_colour};'>+{_final_gap:.1f}s</div>"
                f"<div class='metric-sub'>Peak: +{_max_gap:.1f} s behind leader</div>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ── Race Position Chart ───────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Race Position</div>", unsafe_allow_html=True)


@st.cache_data(show_spinner=False, ttl=3600)
def _build_position_data(sess_k: str, laps_df: pd.DataFrame):
    """Return a dict {driver: pd.Series(position, index=lap_number)} for all drivers."""
    try:
        laps = laps_df.copy()
        laps = laps.dropna(subset=["LapNumber", "Position", "Driver"])
        laps["LapNumber"] = laps["LapNumber"].astype(int)
        laps["Position"]  = laps["Position"].astype(int)
        pos_dict = {}
        for drv, grp in laps.groupby("Driver"):
            grp = grp.sort_values("LapNumber")
            pos_dict[str(drv)] = grp.set_index("LapNumber")["Position"]
        return pos_dict if pos_dict else None
    except Exception:
        return None


_pos_data = _build_position_data(sess_key, _all_laps)

if _pos_data is None or not _pos_data:
    st.info("Race position data is not available for this session type "
            "(only Race and Sprint sessions carry lap-by-lap position data).")
else:
    _highlight = {driver1: colour1}
    if compare and driver2:
        _highlight[driver2] = colour2

    _pos_fig = go.Figure()

    # ── All drivers — faint grey background lines
    for _drv, _series in _pos_data.items():
        if _drv in _highlight:
            continue   # drawn as highlighted traces below
        _pos_fig.add_trace(go.Scatter(
            x=_series.index.tolist(),
            y=_series.tolist(),
            mode="lines",
            name=_fmt_driver(_drv),
            line=dict(color="rgba(160,160,160,0.18)", width=1),
            hovertemplate=(
                f"<b>{_fmt_driver(_drv)}</b><br>"
                "Lap %{x}<br>P%{y}<extra></extra>"
            ),
            showlegend=False,
        ))

    # ── Selected driver(s) — vivid team-coloured lines with markers
    for _drv, _col in _highlight.items():
        if _drv not in _pos_data:
            continue
        _series = _pos_data[_drv]
        _pos_fig.add_trace(go.Scatter(
            x=_series.index.tolist(),
            y=_series.tolist(),
            mode="lines+markers",
            name=_fmt_driver(_drv),
            line=dict(color=_col, width=2.5),
            marker=dict(size=4, color=_col),
            hovertemplate=(
                f"<b>{_fmt_driver(_drv)}</b><br>"
                "Lap %{x}<br>P%{y}<extra></extra>"
            ),
            showlegend=True,
        ))

    # Max lap for x range
    _max_lap = max(
        (s.index.max() for s in _pos_data.values() if not s.empty),
        default=1,
    )

    _pos_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=12, b=0),
        height=360,
        xaxis=dict(
            title="Lap",
            range=[1, _max_lap],
            gridcolor="rgba(128,128,128,0.12)",
            zeroline=False,
        ),
        yaxis=dict(
            title="Position",
            autorange="reversed",   # P1 at top
            tickmode="linear",
            tick0=1,
            dtick=1,
            gridcolor="rgba(128,128,128,0.12)",
            zeroline=False,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right",  x=1,
            font=dict(size=11),
        ),
        font=dict(color="#888888", size=11),
        hoverlabel=dict(bgcolor="rgba(20,20,20,0.85)", font_size=12),
    )

    st.plotly_chart(_pos_fig, width="stretch")

# ── Track Map ─────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Track Map</div>", unsafe_allow_html=True)

map_tab1, map_tab2 = st.tabs(["🎨  Speed Map", "🎬  Race Replay"])

# ────────────────────────────────────────────────────────────────────────────
# TAB 1 — Static speed-coloured track map
# ────────────────────────────────────────────────────────────────────────────
with map_tab1:
    @st.cache_data(show_spinner=False, ttl=600)
    def _get_telemetry_for_map(_lap, driver: str, sess_k: str):
        """Return merged position + car telemetry for a lap."""
        try:
            return _lap.get_telemetry()
        except Exception:
            return None

    def _speed_map_fig(lap, driver: str, colour: str, lap2=None, driver2=None, colour2=None):
        tel = _get_telemetry_for_map(lap, driver, sess_key)
        if tel is None or tel.empty:
            return None

        # Need X, Y and Speed columns
        needed = {"X", "Y", "Speed"}
        if not needed.issubset(tel.columns):
            return None

        fig = go.Figure()

        # ── Track outline (thick dark grey line)
        fig.add_trace(go.Scatter(
            x=tel["X"], y=tel["Y"],
            mode="lines",
            line=dict(color="gray", width=16),
            showlegend=False, hoverinfo="skip",
        ))

        # ── Driver 2 path (solid team colour, lower opacity)
        if lap2 is not None and driver2:
            tel2 = _get_telemetry_for_map(lap2, driver2, sess_key)
            if tel2 is not None and needed.issubset(tel2.columns):
                fig.add_trace(go.Scatter(
                    x=tel2["X"], y=tel2["Y"],
                    mode="markers",
                    marker=dict(color=colour2, size=3, opacity=0.45),
                    name=f"{driver2} path",
                    hoverinfo="skip",
                ))

        # ── Driver 1 speed-coloured scatter
        fig.add_trace(go.Scatter(
            x=tel["X"], y=tel["Y"],
            mode="markers",
            marker=dict(
                color=tel["Speed"],
                colorscale=[
                    [0.0,  "#1a1aff"],
                    [0.35, "#00c8ff"],
                    [0.65, "#00e400"],
                    [0.85, "#ffd700"],
                    [1.0,  "#ff2200"],
                ],
                size=4,
                colorbar=dict(
                    title=dict(text="Speed (km/h)"),
                    thickness=10, len=0.7,
                    bgcolor="rgba(0,0,0,0)",
                    x=1.02,
                ),
                showscale=True,
            ),
            name=driver,
            hovertemplate=(
                f"<b>{driver}</b><br>"
                "Speed: %{marker.color:.0f} km/h<br>"
                "X: %{x:.0f}  Y: %{y:.0f}"
                "<extra></extra>"
            ),
        ))

        # ── Start / finish marker
        fig.add_trace(go.Scatter(
            x=[tel["X"].iloc[0]], y=[tel["Y"].iloc[0]],
            mode="markers",
            marker=dict(symbol="circle", size=14, color=colour,
                        line=dict(color="white", width=2)),
            name="Start / Finish",
            hovertemplate="Start / Finish<extra></extra>",
        ))

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            showlegend=True,
            xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
            yaxis=dict(visible=False),
            height=520,
            margin=dict(l=0, r=80, t=10, b=10),
        )
        return fig

    if lap1 is not None:
        sm_fig = _speed_map_fig(
            lap1, driver1, colour1,
            lap2=(lap2 if compare else None),
            driver2=(driver2 if compare else None),
            colour2=colour2,
        )
        if sm_fig:
            st.plotly_chart(sm_fig, width="stretch")
        else:
            st.info("Position data not available for this lap.")
    else:
        st.info("Load a session and select a lap to view the speed map.")

# ────────────────────────────────────────────────────────────────────────────
# TAB 2 — Animated race replay with all cars
# ────────────────────────────────────────────────────────────────────────────
with map_tab2:
    replay_key = f"replay_{sess_key}"
    if replay_key not in st.session_state:
        st.session_state[replay_key] = None

    # ── Placeholder / button
    if st.session_state[replay_key] is None:
        st.markdown(
            "<div style='text-align:center; padding:56px 24px; border:1px dashed var(--text-color); "
            "border-radius:12px; margin:8px 0;'>"
            "<div style='font-size:52px; margin-bottom:14px;'>🎬</div>"
            "<div style='font-size:14px;'>Animated replay of all cars on track.</div>"
            "<div style='font-size:12px; margin-top:6px;'>"
            "Samples every 5 s · up to 500 frames · ~20 s to build"
            "</div></div>",
            unsafe_allow_html=True,
        )

    gen_col, _ = st.columns([1, 3])
    with gen_col:
        gen_btn = st.button("🎬  Generate Race Replay", key="gen_replay",
                            width="stretch")

    if gen_btn:
        st.session_state[replay_key] = None   # reset so we rebuild
        with st.spinner("Building animation — sampling all car positions…"):
            try:
                # ── Build driver number → abbr + colour map
                drv_meta = {}
                for drv_num in sess.drivers:
                    try:
                        info = sess.get_driver(drv_num)
                        abbr   = info.get("Abbreviation", drv_num)
                        colour = _team_colour(info.get("TeamName", ""))
                        drv_meta[drv_num] = {"abbr": abbr, "colour": colour}
                    except Exception:
                        drv_meta[drv_num] = {"abbr": drv_num, "colour": "#888"}

                # ── Extract position time series for each driver
                T_STEP   = 5          # seconds between animation frames
                MAX_SECS = 7200       # cap at 2 hours
                MAX_FRAMES = 500

                all_data = {}         # drv_num -> {t, x, y}
                for drv_num in sess.drivers:
                    try:
                        pdf = sess.pos_data[drv_num]
                        if pdf is None or pdf.empty:
                            continue
                        t_s = pdf["SessionTime"].dt.total_seconds().values
                        all_data[drv_num] = {
                            "t": t_s,
                            "x": pdf["X"].values,
                            "y": pdf["Y"].values,
                        }
                    except Exception:
                        pass

                if not all_data:
                    st.warning("No position data available for this session.")
                    st.stop()

                # ── Build common time grid
                t_min = min(d["t"][0]  for d in all_data.values())
                t_max = min(max(d["t"][-1] for d in all_data.values()), t_min + MAX_SECS)
                t_grid = np.arange(t_min, t_max, T_STEP)
                if len(t_grid) > MAX_FRAMES:
                    t_grid = t_grid[:MAX_FRAMES]

                # ── Pre-interpolate positions for every driver onto t_grid
                grids = {}
                valid_drvs = []
                for drv_num, d in all_data.items():
                    if len(d["t"]) < 10:
                        continue
                    xi = np.interp(t_grid, d["t"], d["x"],
                                   left=np.nan, right=np.nan)
                    yi = np.interp(t_grid, d["t"], d["y"],
                                   left=np.nan, right=np.nan)
                    # Mark frames where driver has retired as NaN
                    retired_at = d["t"][-1]
                    xi[t_grid > retired_at + T_STEP] = np.nan
                    yi[t_grid > retired_at + T_STEP] = np.nan
                    grids[drv_num] = (xi, yi)
                    valid_drvs.append(drv_num)

                if not valid_drvs:
                    st.warning("Insufficient position data for animation.")
                    st.stop()

                # ── Track outline from the driver with most data points
                longest = max(all_data, key=lambda k: len(all_data[k]["t"]))
                track_x = all_data[longest]["x"]
                track_y = all_data[longest]["y"]

                # Thin track to ~1000 pts for display
                thin = max(1, len(track_x) // 1000)
                track_x = track_x[::thin]
                track_y = track_y[::thin]

                # ── Helper: format seconds as MM:SS
                def _fmt(sec: float) -> str:
                    m, s = int(sec // 60), int(sec % 60)
                    return f"{m:02d}:{s:02d}"

                # ── Build initial traces
                init_traces = [
                    go.Scatter(
                        x=track_x, y=track_y, mode="lines",
                        line=dict(color="gray", width=14),
                        showlegend=False, hoverinfo="skip",
                    )
                ]
                for drv_num in valid_drvs:
                    meta  = drv_meta.get(drv_num, {"abbr": drv_num, "colour": "#888"})
                    xi, yi = grids[drv_num]
                    x0 = [xi[0]] if not np.isnan(xi[0]) else []
                    y0 = [yi[0]] if not np.isnan(yi[0]) else []
                    init_traces.append(go.Scatter(
                        x=x0, y=y0,
                        mode="markers+text",
                        marker=dict(
                            color=meta["colour"], size=14,
                            line=dict(color="black", width=1.5),
                        ),
                        text=[meta["abbr"]],
                        textposition="top center",
                        textfont=dict(size=8, color=meta["colour"]),
                        name=meta["abbr"],
                        hovertemplate=f"<b>{meta['abbr']}</b><extra></extra>",
                        showlegend=True,
                    ))

                # ── Build animation frames
                frames = []
                slider_steps = []
                n_drvs = len(valid_drvs)

                for f_i, t_sec in enumerate(t_grid):
                    label = _fmt(t_sec)
                    fdata = [
                        go.Scatter(
                            x=track_x, y=track_y, mode="lines",
                            line=dict(color="gray", width=14),
                            showlegend=False, hoverinfo="skip",
                        )
                    ]
                    for drv_num in valid_drvs:
                        meta  = drv_meta.get(drv_num, {"abbr": drv_num, "colour": "#888"})
                        xi, yi = grids[drv_num]
                        px, py = xi[f_i], yi[f_i]
                        fdata.append(go.Scatter(
                            x=[px] if not np.isnan(px) else [],
                            y=[py] if not np.isnan(py) else [],
                            mode="markers+text",
                            marker=dict(
                                color=meta["colour"], size=14,
                                line=dict(color="black", width=1.5),
                            ),
                            text=[meta["abbr"]],
                            textposition="top center",
                            textfont=dict(size=8, color=meta["colour"]),
                            name=meta["abbr"],
                            hovertemplate=f"<b>{meta['abbr']}</b><extra></extra>",
                        ))

                    frames.append(go.Frame(data=fdata, name=label))
                    # Add slider step only every ~5 frames to reduce clutter
                    slider_steps.append(dict(
                        args=[[label], dict(
                            frame=dict(duration=150, redraw=False),
                            transition=dict(duration=0),
                            mode="immediate",
                        )],
                        label=label if f_i % 12 == 0 else "",
                        method="animate",
                    ))

                # ── Compose layout
                layout = go.Layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=True,
                    legend=dict(
                        bordercolor="gray", borderwidth=0.5,
                        orientation="v", x=1.01, y=0.5,
                        yanchor="middle",
                        itemsizing="constant",
                    ),
                    xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
                    yaxis=dict(visible=False),
                    height=560,
                    margin=dict(l=0, r=130, t=20, b=70),
                    hoverlabel=dict(bgcolor="#111", font_color="#eee",
                                   bordercolor="#333"),
                    updatemenus=[dict(
                        type="buttons", showactive=False,
                        x=0.04, y=-0.10, xanchor="left",
                        buttons=[
                            dict(
                                label="▶  Play",
                                method="animate",
                                args=[None, dict(
                                    frame=dict(duration=150, redraw=False),
                                    transition=dict(duration=0),
                                    fromcurrent=True, mode="immediate",
                                )],
                            ),
                            dict(
                                label="⏸  Pause",
                                method="animate",
                                args=[[None], dict(
                                    frame=dict(duration=0, redraw=False),
                                    transition=dict(duration=0),
                                    mode="immediate",
                                )],
                            ),
                        ],
                        font=dict(color="#ccc", size=12),
                        bgcolor="#1a1a1a", bordercolor="#333",
                        pad=dict(r=10, t=8),
                    )],
                    sliders=[dict(
                        active=0,
                        steps=slider_steps,
                        currentvalue=dict(
                            prefix="Session time  ",
                            font=dict(color="#777", size=11),
                            visible=True, xanchor="center",
                        ),
                        pad=dict(t=45, b=8),
                        font=dict(color="#444", size=8),
                        bgcolor="#111", bordercolor="#1e1e1e",
                        tickcolor="#2a2a2a",
                        len=0.88, x=0.06,
                    )],
                )

                replay_fig = go.Figure(
                    data=init_traces, layout=layout, frames=frames
                )
                st.session_state[replay_key] = replay_fig

            except Exception as exc:
                import traceback
                st.error(f"Could not build replay: {exc}")
                with st.expander("Full traceback"):
                    st.code(traceback.format_exc())

    if st.session_state[replay_key] is not None:
        st.plotly_chart(st.session_state[replay_key], width="stretch")
        n_frames = len(st.session_state[replay_key].frames)
        session_secs = n_frames * 5
        st.caption(
            f"⏱  {n_frames} frames · {session_secs // 60} min {session_secs % 60} s covered · "
            "5 s per frame · Click ▶ Play or drag the slider"
        )
