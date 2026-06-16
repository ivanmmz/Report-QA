"""Minimal Fluent Design theme for Windows RAG System."""
import streamlit as st


MINIMAL_CSS = """
<style>
    /* Main app background */
    .stApp {
        background: linear-gradient(135deg, #0f1117 0%, #1a1d2e 50%, #0f1117 100%);
        color: #e4e6eb;
    }

    /* Sidebar styling - minimal */
    [data-testid="stSidebar"] {
        background: rgba(16, 18, 27, 0.95);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        min-width: 280px !important;
        max-width: 280px !important;
    }

    [data-testid="stSidebar"] .stMarkdown {
        color: #e4e6eb;
    }

    /* Hide sidebar collapse button */
    button[kind="header"] {
        display: none !important;
    }

    /* Navigation buttons - large and minimal */
    .nav-btn {
        display: block;
        width: 100%;
        padding: 14px 20px;
        margin: 6px 0;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        color: #e4e6eb;
        font-size: 1.1em;
        font-weight: 500;
        text-align: left;
        cursor: pointer;
        transition: all 0.2s ease;
        text-decoration: none;
    }

    .nav-btn:hover {
        background: rgba(255, 255, 255, 0.08);
        border-color: rgba(0, 188, 242, 0.3);
        transform: translateX(4px);
    }

    .nav-btn.active {
        background: linear-gradient(135deg, rgba(0, 120, 212, 0.2), rgba(0, 188, 242, 0.15));
        border-color: rgba(0, 188, 242, 0.4);
        color: #00bcf2;
        font-weight: 600;
    }

    .nav-btn .icon {
        font-size: 1.3em;
        margin-right: 12px;
        display: inline-block;
        width: 28px;
        text-align: center;
    }

    /* Cards - minimal */
    .card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
        transition: all 0.2s ease;
    }

    .card:hover {
        background: rgba(255, 255, 255, 0.05);
        border-color: rgba(255, 255, 255, 0.1);
    }

    /* Accent cards */
    .accent-card {
        background: linear-gradient(135deg, rgba(0, 120, 212, 0.12), rgba(0, 188, 242, 0.08));
        border: 1px solid rgba(0, 188, 242, 0.2);
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
    }

    /* Status bar - minimal */
    .status-bar {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 8px 12px;
        background: rgba(255, 255, 255, 0.02);
        border-radius: 8px;
        margin: 4px 0;
    }

    .status-bar .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .status-bar .status-dot.ready {
        background: #00cc6a;
        box-shadow: 0 0 6px rgba(0, 204, 106, 0.4);
    }

    .status-bar .status-dot.warning {
        background: #ffb800;
        box-shadow: 0 0 6px rgba(255, 184, 0, 0.4);
    }

    .status-bar .status-dot.error {
        background: #ff4343;
        box-shadow: 0 0 6px rgba(255, 67, 67, 0.4);
    }

    .status-bar .status-text {
        color: rgba(255, 255, 255, 0.7);
        font-size: 0.9em;
    }

    .status-bar .status-value {
        color: #e4e6eb;
        font-weight: 600;
        margin-left: auto;
    }

    /* Buttons */
    .stButton > button {
        background: rgba(0, 120, 212, 0.8);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: 500;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        background: rgba(0, 120, 212, 1);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 120, 212, 0.3);
    }

    .stButton > button:active {
        transform: translateY(0);
    }

    /* Secondary buttons */
    .stButton > button[kind="secondary"] {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
    }

    .stButton > button[kind="secondary"]:hover {
        background: rgba(255, 255, 255, 0.1);
    }

    /* Text inputs */
    .stTextInput > div > div > input {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        color: #e4e6eb;
        padding: 10px 14px;
    }

    .stTextInput > div > div > input:focus {
        border-color: rgba(0, 188, 242, 0.5);
    }

    /* Text area */
    .stTextArea > div > div > textarea {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        color: #e4e6eb;
    }

    /* Chat messages */
    .chat-message {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        border: 1px solid rgba(255, 255, 255, 0.06);
    }

    .chat-message.user {
        background: rgba(0, 120, 212, 0.08);
        border-color: rgba(0, 120, 212, 0.2);
    }

    /* File uploader */
    .stFileUploader > div {
        background: rgba(255, 255, 255, 0.02);
        border: 2px dashed rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 32px;
    }

    .stFileUploader > div:hover {
        border-color: rgba(0, 188, 242, 0.4);
        background: rgba(0, 188, 242, 0.03);
    }

    /* Headers */
    h1 {
        color: #ffffff;
        font-weight: 700;
        font-size: 1.8em;
        margin-bottom: 24px;
    }

    h2, h3 {
        color: #e4e6eb;
        font-weight: 600;
        margin-top: 24px;
        margin-bottom: 12px;
    }

    /* Citation badges */
    .citation {
        display: inline-block;
        background: rgba(0, 120, 212, 0.2);
        color: #00bcf2;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: 600;
        margin: 0 2px;
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }

    ::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.02);
    }

    ::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: rgba(255, 255, 255, 0.2);
    }

    /* Source list */
    .source-item {
        background: rgba(255, 255, 255, 0.02);
        border-left: 3px solid rgba(0, 120, 212, 0.6);
        border-radius: 0 8px 8px 0;
        padding: 12px 16px;
        margin: 6px 0;
        font-size: 0.9em;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.02) !important;
        border-radius: 8px !important;
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
    }

    /* Selectbox */
    .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 8px;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255, 255, 255, 0.02);
        border-radius: 10px;
        padding: 4px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 8px 16px;
    }

    .stTabs [aria-selected="true"] {
        background: rgba(0, 120, 212, 0.15);
        color: #00bcf2;
    }

    /* Divider */
    .minimal-divider {
        border: none;
        height: 1px;
        background: rgba(255, 255, 255, 0.06);
        margin: 16px 0;
    }

    /* Compact metrics */
    .compact-metrics {
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
    }

    .compact-metric {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 8px;
        padding: 12px 16px;
        min-width: 120px;
    }

    .compact-metric .value {
        font-size: 1.5em;
        font-weight: 700;
        color: #00bcf2;
    }

    .compact-metric .label {
        font-size: 0.8em;
        color: rgba(255, 255, 255, 0.5);
        margin-top: 4px;
    }
</style>
"""


def apply_theme() -> None:
    """Inject minimal Fluent Design CSS into Streamlit app."""
    st.markdown(MINIMAL_CSS, unsafe_allow_html=True)


def render_card(title: str, content: str, accent: bool = False) -> None:
    """Render a styled card.

    Args:
        title: Card title.
        content: Card content (markdown supported).
        accent: Use accent styling.
    """
    css_class = "accent-card" if accent else "card"
    st.markdown(f"""
    <div class="{css_class}">
        <h4 style="margin-top:0; margin-bottom:12px; color: #ffffff;">{title}</h4>
        <div style="color: #e4e6eb;">{content}</div>
    </div>
    """, unsafe_allow_html=True)


def render_compact_metric(label: str, value: str | int) -> None:
    """Render a compact metric.

    Args:
        label: Metric label.
        value: Metric value.
    """
    st.markdown(f"""
    <div class="compact-metric">
        <div class="value">{value}</div>
        <div class="label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def render_status_bar(label: str, value: str, status: str = "ready") -> None:
    """Render a minimal status bar.

    Args:
        label: Status label.
        value: Status value text.
        status: 'ready', 'warning', or 'error'.
    """
    st.markdown(f"""
    <div class="status-bar">
        <span class="status-dot {status}"></span>
        <span class="status-text">{label}</span>
        <span class="status-value">{value}</span>
    </div>
    """, unsafe_allow_html=True)


def render_nav_button(icon: str, label: str, page_id: str, active: bool = False) -> None:
    """Render a navigation button.

    Args:
        icon: Icon emoji.
        label: Button label.
        page_id: Page identifier.
        active: Whether this is the active page.
    """
    active_class = " active" if active else ""
    st.markdown(f"""
    <div class="nav-btn{active_class}" onclick="window.parent.postMessage({{type: 'streamlit:setComponentValue', value: '{page_id}'}}, '*')">
        <span class="icon">{icon}</span>
        <span>{label}</span>
    </div>
    """, unsafe_allow_html=True)


def render_chat_message(role: str, content: str, sources: list | None = None) -> None:
    """Render a chat message bubble using Streamlit native components.

    Uses st.chat_message() for proper positioning and st.markdown()
    for safe content rendering. Avoids raw HTML injection to prevent
    HTML code leak when content is copied or exported.

    Args:
        role: 'user' or 'assistant'.
        content: Message content (markdown supported).
        sources: Optional list of source dicts with keys: source, score, snippet.
    """
    with st.chat_message(role):
        st.markdown(content)
        if sources and role == "assistant":
            with st.expander(f"📎 Sources ({len(sources)})"):
                for s in sources:
                    src = s.get("source", "Unknown")
                    score = s.get("score", 0)
                    snippet = s.get("snippet", "")
                    st.markdown(f"**{src}** — score: `{score:.3f}`")
                    if snippet:
                        st.caption(snippet[:300])
