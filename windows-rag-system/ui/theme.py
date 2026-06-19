"""Minimal Fluent Design theme for Windows RAG System."""
import streamlit as st


def theme_css(is_dark: bool) -> str:
    """Return full CSS block for the current theme with CSS variables."""
    if is_dark:
        bg0 = "#0f1117"
        bg1 = "#1a1d2e"
        bg2 = "rgba(255,255,255,0.03)"
        text0 = "#e4e6eb"
        text1 = "rgba(255,255,255,0.7)"
        text2 = "rgba(255,255,255,0.35)"
        border = "rgba(255,255,255,0.08)"
        border_hover = "rgba(0,188,242,0.3)"
        accent = "#00bcf2"
        accent_bg = "rgba(0,120,212,0.08)"
        card_bg = "rgba(255,255,255,0.03)"
        card_hover = "rgba(255,255,255,0.05)"
        input_bg = "rgba(255,255,255,0.03)"
        sidebar_bg = "rgba(16,18,27,0.95)"
        gradient = "linear-gradient(135deg, #0f1117 0%, #1a1d2e 50%, #0f1117 100%)"
    else:
        bg0 = "#f8f9fa"
        bg1 = "#ffffff"
        bg2 = "rgba(0,0,0,0.02)"
        text0 = "#1a1a2e"
        text1 = "rgba(0,0,0,0.7)"
        text2 = "rgba(0,0,0,0.4)"
        border = "rgba(0,0,0,0.1)"
        border_hover = "rgba(0,100,200,0.3)"
        accent = "#0066cc"
        accent_bg = "rgba(0,100,200,0.06)"
        card_bg = "rgba(0,0,0,0.02)"
        card_hover = "rgba(0,0,0,0.04)"
        input_bg = "rgba(255,255,255,0.8)"
        sidebar_bg = "rgba(255,255,255,0.97)"
        gradient = "linear-gradient(135deg, #f0f2f5 0%, #ffffff 50%, #f0f2f5 100%)"

    return f"""
<style>
    :root, .stApp {{
        --bg0: {bg0};
        --bg1: {bg1};
        --bg2: {bg2};
        --text0: {text0};
        --text1: {text1};
        --text2: {text2};
        --border: {border};
        --border-hover: {border_hover};
        --accent: {accent};
        --accent-bg: {accent_bg};
        --card-bg: {card_bg};
        --card-hover: {card_hover};
        --input-bg: {input_bg};
        --sidebar-bg: {sidebar_bg};
    }}

    .stApp {{
        background: {gradient};
        color: {text0};
    }}
    [data-testid="stSidebar"],
    [data-testid="stSidebarCollapseButton"],
    button[data-testid="stSidebarCollapseButton"],
    .stSidebar {{
        display: none !important;
    }}

    [data-testid="stHeader"] {{ display: none !important; }}
    button[kind="header"] {{ display: none !important; }}
    header[data-testid="stHeader"] {{ display: none !important; }}

    /* Sidebar layout to push bottom items down */
    [data-testid="stSidebarUserContent"] {{
        height: 100% !important;
        padding-top: 20px !important;
    }}
    [data-testid="stSidebarUserContent"] > div[data-testid="stVerticalBlock"] {{
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
    }}
    div[class*="st-key-sidebar_bottom"] {{
        margin-top: auto !important;
        padding-top: 20px !important;
    }}

    /* Main block container padding reduction to align with Copilot and sidebar */
    [data-testid="stMainBlockContainer"] {{
        padding-top: 20px !important;
        padding-bottom: 20px !important;
        padding-left: 20px !important;
    }}

    /* Ensure h1 titles start with zero margin at the top */
    h1 {{
        color: {text0};
        font-weight: 700;
        font-size: 1.8em;
        margin-top: 0 !important;
        padding-top: 0 !important;
        margin-bottom: 24px;
    }}

    /* Theme toggle in sidebar - always visible in both modes */
    [data-testid="stSidebar"] [data-testid="stBaseButton-label"] {{
        color: {text0} !important;
        font-weight: 500 !important;
    }}

    .stButton > button,
    .stPopover > button,
    div[data-testid="stPopover"] button {{
        background: #0078d4 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 10px 24px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }}
    .stButton > button:hover,
    .stPopover > button:hover,
    div[data-testid="stPopover"] button:hover {{
        background: #005a9e !important;
        color: white !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 120, 212, 0.3);
    }}
    .stButton > button:active,
    .stPopover > button:active,
    div[data-testid="stPopover"] button:active {{
        transform: translateY(0);
    }}

    /* Target direct child labels of popover button to guarantee white text on blue background */
    div[data-testid="stPopover"] button p,
    div[data-testid="stPopover"] button span {{
        color: white !important;
    }}

    /* Target sidebar widget labels and text in all modes to match theme colors */
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    [data-testid="stSidebar"] .stMarkdown p {{
        color: {text0} !important;
        font-weight: 500 !important;
    }}

    .stTextInput > div > div > input {{
        background: {input_bg};
        border: 1px solid {border};
        border-radius: 8px;
        color: {text0};
        padding: 10px 14px;
    }}
    .stTextInput > div > div > input:focus {{ border-color: rgba(0, 188, 242, 0.5); }}

    .stTextArea > div > div > textarea {{
        background: {input_bg};
        border: 1px solid {border};
        border-radius: 8px;
        color: {text0};
    }}

    .chat-message {{
        background: {bg2};
        border-radius: 12px;
        padding: 16px;
        margin: 8px 0;
        border: 1px solid {border};
    }}
    .chat-message.user {{
        background: {accent_bg};
        border-color: rgba(0, 120, 212, 0.2);
    }}

    .stFileUploader > div {{
        background: {bg2};
        border: 2px dashed {border};
        border-radius: 12px;
        padding: 32px;
    }}

    h1 {{ color: {text0}; font-weight: 700; font-size: 1.8em; margin-bottom: 24px; }}
    h2, h3 {{ color: {text0}; font-weight: 600; margin-top: 24px; margin-bottom: 12px; }}

    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: {bg2}; }}
    ::-webkit-scrollbar-thumb {{ background: rgba(128,128,128,0.2); border-radius: 3px; }}

    .stSelectbox > div > div {{
        background: {input_bg};
        border: 1px solid {border};
        border-radius: 8px;
    }}

    .stTabs [data-baseweb="tab-list"] {{
        background: {bg2};
        border-radius: 10px;
        padding: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{ border-radius: 6px; padding: 8px 16px; }}
    .stTabs [aria-selected="true"] {{
        background: rgba(0, 120, 212, 0.15);
        color: {accent};
    }}

    /* Popover and Dialog overlays - inherit theme */
    [data-testid="stPopoverBody"],
    [data-testid="stPopoverBody"] [data-testid="stVerticalBlock"] {{
        background: {bg1} !important;
        color: {text0} !important;
    }}
    [data-testid="stPopoverBody"] h1,
    [data-testid="stPopoverBody"] h2,
    [data-testid="stPopoverBody"] h3,
    [data-testid="stPopoverBody"] h4,
    [data-testid="stPopoverBody"] h5,
    [data-testid="stPopoverBody"] h6 {{
        color: {text0} !important;
    }}
    [data-testid="stPopoverBody"] .stMarkdown,
    [data-testid="stPopoverBody"] p {{
        color: {text0} !important;
    }}
    [data-testid="stPopoverBody"] hr {{
        border-color: {border} !important;
    }}

    /* Dialog/modal overlay */
    [data-testid="stDialog"] {{
        background: rgba(0,0,0,0.4) !important;
    }}
    [data-testid="stDialog"] [data-testid="stVerticalBlock"] {{
        background: {bg1} !important;
        color: {text0} !important;
    }}
    [data-testid="stDialog"] h1,
    [data-testid="stDialog"] h2,
    [data-testid="stDialog"] h3,
    [data-testid="stDialog"] h4 {{
        color: {text0} !important;
    }}

    /* Streamlit info/warning/error/success boxes - use theme */
    .stAlert {{
        color: {text0} !important;
    }}

    .minimal-divider {{ border: none; height: 1px; background: {border}; margin: 16px 0; }}

    .chat-actions-label {{ font-size: 0.78em; color: {text2}; }}

    /* Copy message button */
    .msg-copy-btn {{
        display: inline-flex; align-items: center; justify-content: center;
        background: transparent; border: none; cursor: pointer;
        font-size: 0.7em; padding: 2px 5px; border-radius: 4px;
        color: {text2}; transition: all 0.15s ease; line-height: 1; opacity: 0;
    }}
    [data-testid="stChatMessage"]:hover .msg-copy-btn {{ opacity: 0.6; }}
    .msg-copy-btn:hover {{
        background: rgba(128,128,128,0.15); color: {text0}; opacity: 1 !important;
    }}

    /* Preset buttons */
    .preset-btn {{
        background: {bg2}; border: 1px solid {border}; border-radius: 6px;
        padding: 4px 10px; font-size: 0.78em; color: {text1};
        cursor: pointer; transition: all 0.15s ease;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        display: block; width: 100%; text-align: left;
    }}
    .preset-btn:hover {{ border-color: {accent}; color: {accent}; }}

    .stChatMessage .stButton > button {{
        padding: 2px 8px !important; min-width: unset !important;
        font-size: 0.85em !important;
    }}

    /* Custom CSS components for Light/Dark Adaptability */
    .card {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
        transition: all 0.2s ease;
        color: {text0};
    }}
    .card:hover {{
        background: {card_hover};
        border-color: {border_hover};
    }}
    .accent-card {{
        background: {accent_bg};
        border: 1px solid rgba(0, 120, 212, 0.2);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
        color: {text0};
    }}
    .compact-metric {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }}
    .compact-metric .value {{
        font-size: 1.5em;
        font-weight: 700;
        color: {accent};
    }}
    .compact-metric .label {{
        font-size: 0.85em;
        color: {text1};
        margin-top: 4px;
    }}
    .status-bar {{
        display: flex;
        align-items: center;
        padding: 8px 12px;
        background: {bg2};
        border: 1px solid {border};
        border-radius: 6px;
        margin: 6px 0;
        font-size: 0.85em;
    }}
    .status-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
        display: inline-block;
    }}
    .status-dot.ready {{
        background: #00cc6a;
    }}
    .status-dot.error {{
        background: #ff4343;
    }}
    .status-text {{
        font-weight: 500;
        color: {text0};
        flex-grow: 1;
    }}
    .status-value {{
        color: {text1};
    }}
    .source-item {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 8px 12px;
        margin: 4px 0;
        color: {text0};
    }}

</style>"""


def apply_theme(is_dark: bool = True) -> None:
    """Inject themed CSS into Streamlit app."""
    st.markdown(theme_css(is_dark), unsafe_allow_html=True)


def render_card(title: str, content: str, accent: bool = False) -> None:
    """Render a styled card."""
    css_class = "accent-card" if accent else "card"
    st.markdown(f"""
    <div class="{css_class}">
        <h4 style="margin-top:0; margin-bottom:12px; color: inherit;">{title}</h4>
        <div>{content}</div>
    </div>
    """, unsafe_allow_html=True)


def render_compact_metric(label: str, value: str | int) -> None:
    """Render a compact metric."""
    st.markdown(f"""
    <div class="compact-metric">
        <div class="value">{value}</div>
        <div class="label">{label}</div>
    </div>
    """, unsafe_allow_html=True)


def render_status_bar(label: str, value: str, status: str = "ready") -> None:
    """Render a minimal status bar."""
    st.markdown(f"""
    <div class="status-bar">
        <span class="status-dot {status}"></span>
        <span class="status-text">{label}</span>
        <span class="status-value">{value}</span>
    </div>
    """, unsafe_allow_html=True)


def render_chat_message(role: str, content: str, sources: list | None = None) -> None:
    """Render a chat message bubble using Streamlit native components."""
    with st.chat_message(role):
        st.markdown(content)
        if sources and role == "assistant":
            with st.expander(f"Sources ({len(sources)})"):
                for s in sources:
                    src = s.get("source", "Unknown")
                    score = s.get("score", 0)
                    snippet = s.get("snippet", "")
                    st.markdown(f"**{src}** — score: `{score:.3f}`")
                    if snippet:
                        st.caption(snippet[:300])
