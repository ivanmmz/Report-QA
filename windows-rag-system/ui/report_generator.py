"""Report Generator and AI Copilot UI for Windows RAG System.

Combines report generation, manual report editing, persistent report saving/loading,
and an Edge-Copilot style assistant chat in a split-column layout.
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import streamlit as st
import streamlit.components.v1 as components
from utils.file_io import read_json, write_json
from utils.background_task import BackgroundTask
from utils.paths import PROJECT_ROOT
from core.report_generator import ReportGenerator, Report
from core.rag_pipeline import RAGPipeline
from llm.gateway import LLMGateway

# Chart renderer script helper with dynamic theme support.
def get_chart_render_script(is_dark: bool) -> str:
    """Return the Chart.js rendering script with theme-specific colors."""
    chart_color = '#b0b3be' if is_dark else '#4a4a4a'
    chart_border = 'rgba(255,255,255,0.08)' if is_dark else 'rgba(0,0,0,0.1)'
    chart_grid = 'rgba(255,255,255,0.05)' if is_dark else 'rgba(0,0,0,0.05)'
    chart_ticks = '#9ca3af' if is_dark else '#555555'
    chart_title = '#e4e6eb' if is_dark else '#1a1a2e'

    return f"""
<script>
(function() {{
    'use strict';
    var containers = document.querySelectorAll('.chart-placeholder');
    if (!containers.length) return;
    var COLORS = ['#00bcf2', '#ffb800', '#4ecdc4', '#ff6b6b', '#c084fc', '#fb923c', '#34d399', '#60a5fa'];
    containers.forEach(function(div) {{
        try {{
            var spec = JSON.parse(div.getAttribute('data-chart') || '{{}}');
            var type = spec.type || 'bar';
            var datasets = (spec.datasets || []).map(function(ds, i) {{
                var c = COLORS[i % COLORS.length];
                return {{
                    label: ds.label || '',
                    data: ds.data || [],
                    backgroundColor: ds.backgroundColor || (type === 'doughnut' || type === 'polarArea' ? COLORS.map(function(x){{ return x + 'CC'; }}) : c + '33'),
                    borderColor: ds.borderColor || c,
                    borderWidth: ds.borderWidth || (type === 'line' ? 2 : 1),
                    fill: ds.fill !== undefined ? ds.fill : (type === 'line' ? false : undefined),
                    tension: ds.tension !== undefined ? ds.tension : 0.3,
                    pointRadius: ds.pointRadius !== undefined ? ds.pointRadius : 3
                }};
            }});
            var labels = spec.labels || [];
            div.innerHTML = '';
            var canvas = document.createElement('canvas');
            div.appendChild(canvas);
            canvas.style.width = (spec.width || 600) + 'px';
            canvas.style.height = (spec.height || 300) + 'px';
            canvas.style.maxWidth = '100%';
            canvas.style.margin = '12px 0';
            Chart.defaults.color = '{chart_color}';
            Chart.defaults.borderColor = '{chart_border}';
            new Chart(canvas.getContext('2d'), {{
                type: type,
                data: {{ labels: labels, datasets: datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        title: {{ display: !!spec.title, text: spec.title || '', color: '{chart_title}', font: {{ size: 14 }} }},
                        legend: {{ labels: {{ color: '{chart_color}', boxWidth: 12, padding: 12 }} }}
                    }},
                    scales: (type === 'doughnut' || type === 'polarArea' || type === 'radar') ? undefined : {{
                        x: {{ grid: {{ color: '{chart_grid}' }}, ticks: {{ color: '{chart_ticks}' }} }},
                        y: {{ grid: {{ color: '{chart_grid}' }}, ticks: {{ color: '{chart_ticks}' }} }}
                    }}
                }}
            }});
        }} catch(e) {{
            div.innerHTML = '<p style="color:#ff6b6b;">⚠️ Chart render error: ' + e.message + '</p>';
        }}
    }});
}})();
</script>"""


def _markdown_to_html(text: str) -> str:
    """Convert simplified markdown to styled HTML."""
    import re

    lines = text.split('\n')
    html_parts = []
    in_code_block = False
    in_chart_block = False
    code_buffer = []
    chart_id_counter = 0
    table_rows = []
    in_table = False

    def _inline(text: str) -> str:
        """Process inline formatting."""
        t = text
        t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
        t = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', t)
        t = re.sub(r'`([^`]+)`', r'<code>\1</code>', t)
        t = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" target="_blank">\1</a>', t)
        return t

    def _flush_table():
        nonlocal table_rows, in_table
        if not in_table or not table_rows:
            return
        html_parts.append('<div class="table-wrap"><table>')
        # Header row
        html_parts.append('<thead><tr>' + ''.join(f'<th>{_inline(c)}</th>' for c in table_rows[0]) + '</tr></thead>')
        if len(table_rows) > 1:
            html_parts.append('<tbody>')
            for row in table_rows[1:]:
                html_parts.append('<tr>' + ''.join(f'<td>{_inline(c)}</td>' for c in row) + '</tr>')
            html_parts.append('</tbody>')
        html_parts.append('</table></div>')
        table_rows = []
        in_table = False

    for line in lines:
        # Code blocks
        stripped = line.strip()
        if stripped.startswith('```'):
            if in_code_block:
                if in_chart_block:
                    # Chart block — generate placeholder div that JS will render
                    chart_json = ''.join(code_buffer)
                    placeholder_id = f"chart-{chart_id_counter}"
                    chart_id_counter += 1
                    html_parts.append(
                        f'<div id="{placeholder_id}" class="chart-placeholder" '
                        f'data-chart=\'{chart_json}\'></div>'
                    )
                    in_chart_block = False
                else:
                    html_parts.append(f'<pre><code>{"".join(code_buffer)}</code></pre>')
                code_buffer = []
                in_code_block = False
            else:
                # Opening fence
                lang = stripped[3:].strip()
                if lang == 'chart':
                    in_chart_block = True
                in_code_block = True
            continue
        if in_code_block:
            code_buffer.append(line + '\n')
            continue

        # Flush any open table on non-table lines
        if not stripped.startswith('|'):
            _flush_table()

        # Headers
        if stripped.startswith('###### '):
            html_parts.append(f'<h6>{_inline(stripped[7:])}</h6>')
            continue
        if stripped.startswith('##### '):
            html_parts.append(f'<h5>{_inline(stripped[6:])}</h5>')
            continue
        if stripped.startswith('#### '):
            html_parts.append(f'<h4>{_inline(stripped[5:])}</h4>')
            continue
        if stripped.startswith('### '):
            html_parts.append(f'<h3>{_inline(stripped[4:])}</h3>')
            continue
        if stripped.startswith('## '):
            html_parts.append(f'<h2>{_inline(stripped[3:])}</h2>')
            continue
        if stripped.startswith('# '):
            html_parts.append(f'<h1>{_inline(stripped[2:])}</h1>')
            continue

        # Horizontal rule
        if stripped == '---':
            html_parts.append('<hr>')
            continue

        # Table rows
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            # Skip separator rows (|---|---|)
            if all(re.match(r'^[-:\s]+$', c) for c in cells):
                continue
            if not in_table:
                in_table = True
            table_rows.append(cells)
            continue

        # Empty line
        if not stripped:
            html_parts.append('<br>')
            continue

        # Regular paragraph
        html_parts.append(f'<p>{_inline(stripped)}</p>')

    _flush_table()
    if in_code_block and code_buffer:
        html_parts.append(f'<pre><code>{"".join(code_buffer)}</code></pre>')

    return '\n'.join(html_parts)


def _build_canvas_html(title: str, md_content: str, is_dark: bool = True) -> str:
    """Build a full HTML page with floating download buttons and rendered content."""
    body_html = _markdown_to_html(md_content)
    chart_render_script = get_chart_render_script(is_dark)

    # Theme settings
    if is_dark:
        bg = "transparent"
        color = "#e4e6eb"
        h_color = "#ffffff"
        muted_text = "#d0d2db"
        border = "rgba(255,255,255,0.08)"
        code_bg = "rgba(255,255,255,0.07)"
        pre_bg = "rgba(0,0,0,0.3)"
        table_th_bg = "rgba(0, 188, 242, 0.1)"
        dl_btn_bg = "rgba(26, 29, 46, 0.92)"
        dl_btn_border = "rgba(255,255,255,0.15)"
        dl_btn_color = "#c8cbd6"
    else:
        bg = "transparent"
        color = "#1a1a2e"
        h_color = "#000000"
        muted_text = "#4a4a4a"
        border = "rgba(0,0,0,0.1)"
        code_bg = "rgba(0,0,0,0.05)"
        pre_bg = "rgba(0,0,0,0.02)"
        table_th_bg = "rgba(0, 100, 200, 0.08)"
        dl_btn_bg = "rgba(255, 255, 255, 0.92)"
        dl_btn_border = "rgba(0,0,0,0.15)"
        dl_btn_color = "#1a1a2e"

    chart_color = '#b0b3be' if is_dark else '#4a4a4a'
    chart_border = 'rgba(255,255,255,0.08)' if is_dark else 'rgba(0,0,0,0.1)'
    chart_grid = 'rgba(255,255,255,0.05)' if is_dark else 'rgba(0,0,0,0.05)'
    chart_ticks = '#9ca3af' if is_dark else '#555555'
    chart_title_color = '#e4e6eb' if is_dark else '#1a1a2e'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;
    background: {bg};
    color: {color};
    line-height: 1.6;
    padding: 20px 0 24px 0;
    min-height: 200px;
}}
h1 {{ font-size: 1.6em; color: {h_color}; margin: 0 0 16px 0; padding-bottom: 8px; border-bottom: 1px solid {border}; }}
h2 {{ font-size: 1.3em; color: {h_color}; margin: 24px 0 12px 0; }}
h3 {{ font-size: 1.15em; color: {color}; margin: 20px 0 10px 0; }}
h4, h5, h6 {{ font-size: 1.05em; color: {color}; margin: 16px 0 8px 0; }}
p {{ margin: 8px 0; color: {muted_text}; }}
br {{ display: block; content: ''; margin: 4px 0; }}
hr {{ border: none; border-top: 1px solid {border}; margin: 20px 0; }}
strong {{ color: {h_color}; }}
code {{
    background: {code_bg};
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
    font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
}}
pre {{
    background: {pre_bg};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
    margin: 12px 0;
}}
pre code {{ background: none; padding: 0; }}
a {{ color: #00bcf2; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 0.9em;
}}
th {{
    background: {table_th_bg};
    color: {h_color};
    font-weight: 600;
    text-align: left;
    padding: 8px 12px;
    border: 1px solid {border};
}}
td {{
    padding: 8px 12px;
    border: 1px solid {border};
    color: {muted_text};
}}
tr:nth-child(even) td {{ background: {pre_bg}; }}
.table-wrap {{ overflow-x: auto; }}
ul, ol {{ padding-left: 24px; margin: 8px 0; }}
li {{ margin: 4px 0; }}
.chart-placeholder {{ height: 350px; width: 100%; position: relative; }}
.chart-placeholder canvas {{ display: block; margin: 12px 0; }}

/* Floating download buttons */
.floating-bar {{
    position: sticky;
    top: 0;
    float: right;
    z-index: 100;
    display: flex;
    gap: 6px;
    margin-bottom: 8px;
}}
.dl-btn {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 14px;
    border: 1px solid {dl_btn_border};
    border-radius: 6px;
    background: {dl_btn_bg};
    backdrop-filter: blur(8px);
    color: {dl_btn_color};
    font-size: 0.82em;
    font-family: inherit;
    cursor: pointer;
    transition: all 0.15s ease;
}}
.dl-btn:hover {{
    background: rgba(0, 188, 242, 0.15);
    border-color: rgba(0, 188, 242, 0.4);
    color: {h_color};
}}
.dl-btn svg {{ width: 14px; height: 14px; fill: currentColor; }}
</style>
</head>
<body>
<div class="floating-bar">
    <button class="dl-btn" onclick="downloadMD()">
        <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM6 20V4h7v5h5v11H6z"/><path d="M12 11v6m-3-3 3 3 3-3"/></svg>
        MD
    </button>
    <button class="dl-btn" onclick="downloadHTML()">
        <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zM6 20V4h7v5h5v11H6z"/><path d="M12 11v6m-3-3 3 3 3-3"/></svg>
        HTML
    </button>
</div>
<div class="content">
{body_html}
</div>
<script>
var mdContent = {json.dumps(md_content, ensure_ascii=False)};
function downloadMD() {{
    var blob = new Blob([mdContent], {{type: 'text/markdown;charset=utf-8'}});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '{_sanitize_filename(title)}.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
}}
function downloadHTML() {{
    // Inject chart render script so exported file renders charts standalone
    var chartInit = `<script>
(function() {{
    'use strict';
    var containers = document.querySelectorAll('.chart-placeholder');
    if (!containers.length) return;
    var COLORS = ['#00bcf2','#ffb800','#4ecdc4','#ff6b6b','#c084fc','#fb923c','#34d399','#60a5fa'];
    containers.forEach(function(div) {{
        try {{
            var spec = JSON.parse(div.getAttribute('data-chart') || '{{}}');
            var type = spec.type || 'bar';
            var datasets = (spec.datasets || []).map(function(ds, i) {{
                var c = COLORS[i % COLORS.length];
                return {{ label: ds.label || '', data: ds.data || [], backgroundColor: c + '33', borderColor: c, borderWidth: type === 'line' ? 2 : 1, tension: 0.3, pointRadius: 3 }};
            }});
            div.innerHTML = '';
            var canvas = document.createElement('canvas');
            div.appendChild(canvas);
            canvas.style.width = (spec.width || 600) + 'px';
            canvas.style.height = (spec.height || 300) + 'px';
            canvas.style.maxWidth = '100%';
            Chart.defaults.color = '{chart_color}';
            new Chart(canvas.getContext('2d'), {{
                type: type,
                data: {{ labels: spec.labels || [], datasets: datasets }},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{ title: {{ display: !!spec.title, text: spec.title || '', color: '{chart_title_color}', font: {{ size: 14 }} }}, legend: {{ labels: {{ color: '{chart_color}', boxWidth: 12 }} }} }},
                    scales: (type === 'doughnut' || type === 'polarArea' || type === 'radar') ? undefined : {{
                        x: {{ grid: {{ color: '{chart_grid}' }}, ticks: {{ color: '{chart_ticks}' }} }},
                        y: {{ grid: {{ color: '{chart_grid}' }}, ticks: {{ color: '{chart_ticks}' }} }}
                    }}
                }}
            }});
        }} catch(e) {{ div.innerHTML = '<p style="color:#ff6b6b;">Chart error: ' + e.message + '</p>'; }}
    }});
}})();
<\\/script>`;
    var docType = '<!DOCTYPE html>\\n';
    var fullHtml = docType + document.documentElement.outerHTML.replace('</body>', chartInit + '</body>');
    var blob = new Blob([fullHtml], {{type: 'text/html;charset=utf-8'}});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '{_sanitize_filename(title)}.html';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
}}
</script>
<!--CHART_RENDER_SCRIPT-->
</body>
</html>""".replace("<!--CHART_RENDER_SCRIPT-->", chart_render_script)


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    import re
    # Replace invalid chars with underscore
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Trim whitespace and dots
    sanitized = sanitized.strip('. ')
    # Collapse multiple underscores/spaces
    sanitized = re.sub(r'[_\s]+', '_', sanitized)
    return sanitized or 'report'


def init_report_state() -> None:
    """Initialize report generator and editor session state."""
    if "active_report_title" not in st.session_state:
        st.session_state.active_report_title = "Untitled Report"
    if "active_report_content" not in st.session_state:
        st.session_state.active_report_content = "# Active Report\n\nStart typing or ask Copilot to generate report sections."
    if "copilot_messages" not in st.session_state:
        st.session_state.copilot_messages = []
    if "report_task" not in st.session_state:
        st.session_state.report_task = None
    if "selected_template_prompt" not in st.session_state:
        st.session_state.selected_template_prompt = ""
    if "report_generator" not in st.session_state:
        st.session_state.report_generator = None
    if "copilot_presets" not in st.session_state:
        st.session_state.copilot_presets = []


# ---------------------------------------------------------------------------
# Copilot Chat Session Management
# ---------------------------------------------------------------------------

COPILOT_HISTORY_DIR = PROJECT_ROOT / "data" / "copilot_history"


def _ensure_copilot_history_dir() -> Path:
    """Ensure the copilot history directory exists."""
    COPILOT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return COPILOT_HISTORY_DIR


def save_copilot_session(session_id: str, title: str) -> bool:
    """Save current copilot messages to a session file."""
    messages = st.session_state.get("copilot_messages", [])
    if not messages:
        return False
    history_dir = _ensure_copilot_history_dir()
    session = {
        "id": session_id,
        "title": title,
        "messages": messages,
        "updated_at": datetime.now().isoformat(),
    }
    write_json(history_dir / f"{session_id}.json", session)
    return True


def list_copilot_sessions() -> List[Dict[str, Any]]:
    """List all saved copilot chat sessions, newest first."""
    history_dir = _ensure_copilot_history_dir()
    sessions = []
    for f in sorted(history_dir.glob("*.json"), reverse=True):
        try:
            data = read_json(f)
            sessions.append({
                "id": data.get("id", f.stem),
                "title": data.get("title", f"Session {f.stem[:8]}"),
                "message_count": len(data.get("messages", [])),
                "updated_at": data.get("updated_at", ""),
            })
        except Exception:
            continue
    return sessions


def load_copilot_session(session_id: str) -> Optional[List]:
    """Load messages from a saved session."""
    history_dir = _ensure_copilot_history_dir()
    file_path = history_dir / f"{session_id}.json"
    if not file_path.exists():
        return None
    try:
        data = read_json(file_path)
        return data.get("messages", [])
    except Exception:
        return None


def delete_copilot_session(session_id: str) -> None:
    """Delete a saved copilot session."""
    history_dir = _ensure_copilot_history_dir()
    file_path = history_dir / f"{session_id}.json"
    if file_path.exists():
        file_path.unlink()


def get_copilot_session_title(messages: List) -> str:
    """Generate a title from the first user message or timestamp."""
    for msg in messages:
        if msg.get("role") == "user":
            text = msg.get("content", "").strip()
            if text:
                return text[:48] + ("..." if len(text) > 48 else "")
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _render_copilot_history() -> None:
    """Render the copilot chat history popover content."""
    sessions = list_copilot_sessions()
    if not sessions:
        st.markdown("<p style='color:var(--text2); text-align:center;'>No saved sessions</p>", unsafe_allow_html=True)
        return

    for sess in sessions:
        cols = st.columns([5, 1])
        with cols[0]:
            title = sess.get("title", "Untitled")
            count = sess.get("message_count", 0)
            updated = sess.get("updated_at", "")[:16] if sess.get("updated_at") else ""
            label = f"**{title}**  \n{count} messages · {updated}" if updated else f"**{title}**  \n{count} messages"
            if st.button(label, key=f"hist_load_{sess['id']}", use_container_width=True):
                messages = load_copilot_session(sess["id"])
                if messages:
                    st.session_state.copilot_messages = messages
                    st.toast(f"Loaded: {title}")
                    st.rerun()
                else:
                    st.error("Failed to load session.")
        with cols[1]:
            if st.button("🗑️", key=f"hist_del_{sess['id']}", help="Delete this session"):
                delete_copilot_session(sess["id"])
                st.toast("Session deleted.")
                st.rerun()
        st.markdown("<hr style='margin:4px 0; opacity:0.15;'>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------


def load_templates() -> Dict[str, Any]:
    """Load report templates from config/report_templates.json."""
    template_file = PROJECT_ROOT / "config" / "report_templates.json"
    if not template_file.exists():
        default_templates = {
            "OSE": {
                "name": "OSE",
                "description": "Operation System Efficiency Report (运行效率报告)",
                "prompt": "Operation System Efficiency Report (OSE):\nAnalyze the operation system efficiency, identify runtime bottlenecks, summarize chiller plant / system COP metrics, and suggest energy saving optimizations based on the documents."
            }
        }
        write_json(template_file, default_templates)
        return default_templates
    return read_json(template_file)


def save_template(name: str, description: str, prompt: str) -> None:
    """Save a custom report template."""
    templates = load_templates()
    templates[name] = {
        "name": name,
        "description": description,
        "prompt": prompt
    }
    write_json(PROJECT_ROOT / "config" / "report_templates.json", templates)


def delete_template(name: str) -> None:
    """Delete a custom report template."""
    templates = load_templates()
    if name in templates:
        del templates[name]
        write_json(PROJECT_ROOT / "config" / "report_templates.json", templates)


def load_saved_reports() -> List[Dict[str, Any]]:
    """Load saved reports from data/reports/."""
    reports_dir = PROJECT_ROOT / "data" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    saved_reports = []
    for file in reports_dir.glob("report_*.json"):
        try:
            data = read_json(file)
            if data:
                data["file_path"] = str(file)
                saved_reports.append(data)
        except Exception:
            pass
    # Sort by saved time descending
    saved_reports.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
    return saved_reports


def delete_report(file_path: str) -> None:
    """Delete a saved report from disk."""
    try:
        p = Path(file_path)
        if p.exists() and p.is_file():
            p.unlink()
    except Exception as e:
        st.error(f"Failed to delete report: {e}")


def generate_report_job(
    report_gen: ReportGenerator,
    report_type: str,
    query: str,
    start_date: Optional[str],
    end_date: Optional[str],
    custom_prompt: Optional[str]
) -> Report:
    """Callback function for background report generation task."""
    return report_gen.generate(
        report_type=report_type,
        query=query,
        start_date=start_date,
        end_date=end_date,
        custom_prompt=custom_prompt
    )


def run_copilot_query(
    llm: LLMGateway,
    rag_pipeline: Optional[RAGPipeline],
    user_query: str,
    current_report_content: str
) -> tuple[str, List[Dict[str, Any]]]:
    """Retrieve document context and get LLM response for Copilot chat."""
    context = ""
    citations = []

    if rag_pipeline and rag_pipeline.retriever:
        try:
            # Use a larger top_k so that even when some low-quality chunks
            # rank highly, real content still has a chance to enter the context.
            results = rag_pipeline.retriever.retrieve(user_query, top_k=15)

            # Filter out near-empty / structural-only chunks before feeding
            # the LLM. Chunks with fewer than 50 characters carry no real data
            # and only confuse the model into hallucinating answers.
            MIN_CONTEXT_LEN = 50
            results = [r for r in results if len(r.get("content", "").strip()) >= MIN_CONTEXT_LEN]

            context_parts = []
            for i, r in enumerate(results):
                content = r.get("content", "")
                source = r.get("source", "Unknown")
                context_parts.append(f"[Doc Chunk {i+1} - Source: {source}]\n{content}")
                citations.append({
                    "source": source,
                    "score": r.get("score", 0.0),
                    "snippet": content[:300]
                })
            context = "\n\n---\n\n".join(context_parts)
        except Exception as e:
            st.warning(f"RAG retrieval failed: {e}")

    system_prompt = f"""You are an expert AI Report Copilot Assistant.
Your goal is to help the user review, improve, refine, or write technical reports.

The user is CURRENTLY working on the following report content on their Canvas:
```markdown
{current_report_content}
```

Instructions:
1. Help the user edit, write, or format sections of their report.
2. If the user's request requires updating, writing, or refining the report, you MUST provide the FULL updated report content inside a code block tagged with ```markdown-canvas
For example:
```markdown-canvas
# Report Title
Report content...
```
3. In your response outside of the ```markdown-canvas block, write only a short conversational message explaining what changes you made. Do NOT put the report content in your conversational message.
4. If the user's request is purely a question and does not require modifying the report on the canvas, do NOT include any ```markdown-canvas code block, and just answer the question in your conversational response.
5. Keep answers concise, technical, and highly actionable.
6. Refer to the provided document context below to extract real statistics, metrics, or factual statements if needed.
7. CRITICAL ANTI-HALLUCINATION RULE: If the document context does not contain the specific data the user is asking about, you MUST honestly say so. DO NOT invent, fabricate, estimate, or guess any numbers, metrics, dates, or table values. Only cite data that explicitly appears in the provided context chunks.
8. CHART GENERATION: To include a chart in the report, add a ```chart code block inside your ```markdown-canvas block. The chart block must contain valid JSON:
   {{ "type": "line|bar|doughnut|radar|polarArea", "title": "Title", "labels": ["A","B","C"], "datasets": [{{"label": "Series", "data": [1,2,3]}}] }}
   Example bar chart in ```markdown-canvas:
   ```chart
   {{"type": "bar", "title": "Monthly kWh", "labels": ["Jan","Feb","Mar"], "datasets": [{{"label": "kWh", "data": [352000, 426115, 390000]}}]}}
   ```"""

    user_prompt = f"""Document Context for Reference:
{context}

User Query/Request:
{user_query}

Please provide your helpful suggestion, refinement, or data generation:"""

    response = llm.chat(user_prompt, "", system_prompt)
    return response, citations


@st.dialog("➕ Add Custom Report / Template", width="large")
def manage_templates_dialog() -> None:
    """Popup modal dialog to generate custom reports directly or save custom templates."""
    templates = load_templates()

    tab_gen, tab_tpl = st.tabs(["Generate Custom Report", "Save as Template"])
    
    with tab_gen:
        st.markdown("##### Generate a custom report on-the-fly")
        custom_title = st.text_input("Report Title (报告标题)", placeholder="E.g., Chiller Efficiency Report", key="dlg_gen_title")
        custom_prompt = st.text_area("Custom Prompt / Instructions (生成指令)", placeholder="E.g., Summarize chiller COP values and system efficiency optimizations.", key="dlg_gen_prompt")
        
        if st.button("⚡ Generate Report", use_container_width=True, key="dlg_gen_btn"):
            if not custom_prompt:
                st.error("Prompt / Instructions are required to generate a report.")
            else:
                # Retrieve report generator and run background task
                report_gen = st.session_state.report_generator
                if report_gen:
                    task = BackgroundTask(
                        target=generate_report_job,
                        kwargs={
                            "report_gen": report_gen,
                            "report_type": "custom",
                            "query": "",
                            "start_date": None,
                            "end_date": None,
                            "custom_prompt": f"Title: {custom_title or 'Custom Report'}\n\n{custom_prompt}"
                        }
                    )
                    st.session_state.report_task = task
                    task.start()
                    st.toast("Generating custom report in the background...", icon="⚡")
                    st.rerun()
                    
    with tab_tpl:
        st.markdown("##### Add a template to the Report Generator list")
        t_name = st.text_input("Template Name (模板名称)", placeholder="E.g., Weekly_OSE", key="dlg_t_name")
        t_desc = st.text_input("Description (描述)", placeholder="E.g., Weekly Operation System Efficiency Report", key="dlg_t_desc")
        t_prompt = st.text_area("Template Prompt Instructions (模板生成指令)", placeholder="E.g., Summarize system efficiency metrics for the past week...", key="dlg_t_prompt")
        
        col_save, col_del = st.columns(2)
        with col_save:
            if st.button("Save Template", use_container_width=True, key="dlg_save_btn"):
                if not t_name or not t_prompt:
                    st.error("Name and Prompt instructions are required.")
                else:
                    save_template(t_name, t_desc, t_prompt)
                    st.toast("Saved template!")
                    st.rerun()

        with col_del:
            st.markdown("##### Delete Template")
            if templates:
                del_name = st.selectbox("Select Template to Delete", options=list(templates.keys()), key="dlg_del_select")
                if st.button("Delete Template", use_container_width=True, key="dlg_del_btn"):
                    delete_template(del_name)
                    st.toast(f"Deleted template '{del_name}'")
                    st.rerun()
            else:
                st.caption("No custom templates to delete.")


def render_report_generator(rag_pipeline: Optional[RAGPipeline], llm: Optional[LLMGateway]) -> None:
    """Render the split-column Reports & Copilot view."""
    init_report_state()
    is_dark = st.session_state.get("is_dark", True)

    # Copilot sidebar colors based on theme
    if is_dark:
        bg1 = "#1a1d2e"
        text0 = "#e4e6eb"
        text1 = "rgba(255,255,255,0.7)"
        border = "rgba(255,255,255,0.08)"
        bg2 = "rgba(255,255,255,0.03)"
        copilot_bg = "rgba(14, 16, 25, 0.98)"
        copilot_border = "rgba(255,255,255,0.09)"
        copilot_shadow = "rgba(0,0,0,0.5)"
        copilot_scrollbar = "rgba(255,255,255,0.15)"
        copilot_input_bg = "rgba(14, 16, 25, 0.98)"
        copilot_input_border = "rgba(255,255,255,0.09)"
    else:
        bg1 = "#ffffff"
        text0 = "#1a1a2e"
        text1 = "rgba(0,0,0,0.7)"
        border = "rgba(0,0,0,0.1)"
        bg2 = "rgba(0,0,0,0.02)"
        copilot_bg = "rgba(248, 249, 250, 0.98)"
        copilot_border = "rgba(0,0,0,0.1)"
        copilot_shadow = "rgba(0,0,0,0.12)"
        copilot_scrollbar = "rgba(0,0,0,0.15)"
        copilot_input_bg = "rgba(248, 249, 250, 0.98)"
        copilot_input_border = "rgba(0,0,0,0.1)"

    st.markdown(f"""
    <style>
        /* Restore stMain to its natural Streamlit scroll defaults */
        section[data-testid="stMain"],
        section.stMain {{
            overflow-y: auto !important;
        }}
        [data-testid="stMainBlockContainer"] {{
            /* Stretch block container to full width and right padding so canvas doesn't go under the 380px copilot sidebar */
            max-width: 100% !important;
            width: 100% !important;
            padding-left: 20px !important;
            padding-right: 400px !important;
            padding-top: 20px !important;
            height: auto !important;
            overflow: visible !important;
        }}

        /* Fixed position container inside Streamlit React tree */
        div[class*="st-key-copilot_sidebar"],
        div[class*="st-key-copilot-sidebar"] {{
            position: fixed !important;
            right: 0 !important;
            top: 0 !important;
            width: 380px !important;
            height: 100vh !important;
            background: {copilot_bg} !important;
            border-left: 1px solid {copilot_border} !important;
            padding: 20px 16px 16px 16px !important;
            z-index: 9990 !important;
            overflow-y: auto !important;
            box-shadow: -6px 0 28px {copilot_shadow} !important;
            margin: 0 !important;
            box-sizing: border-box !important;
        }}

        /* Ensure all text inside the Copilot sidebar adapts to light/dark mode */
        div[class*="st-key-copilot_sidebar"],
        div[class*="st-key-copilot-sidebar"],
        div[class*="st-key-copilot_sidebar"] .stMarkdown,
        div[class*="st-key-copilot-sidebar"] .stMarkdown,
        div[class*="st-key-copilot_sidebar"] p,
        div[class*="st-key-copilot-sidebar"] p,
        div[class*="st-key-copilot_sidebar"] h1,
        div[class*="st-key-copilot-sidebar"] h2,
        div[class*="st-key-copilot-sidebar"] h3,
        div[class*="st-key-copilot-sidebar"] h4,
        div[class*="st-key-copilot-sidebar"] label,
        div[class*="st-key-copilot-sidebar"] label,
        div[class*="st-key-copilot-sidebar"] span,
        div[class*="st-key-copilot-sidebar"] span {{
            color: {text0} !important;
        }}

        /* Ensure chat message contents and container follow theme colors */
        div[class*="st-key-copilot_sidebar"] [data-testid="stChatMessage"],
        div[class*="st-key-copilot-sidebar"] [data-testid="stChatMessage"] {{
            background-color: {bg2} !important;
            border: 1px solid {border} !important;
        }}

        div[class*="st-key-copilot_sidebar"] [data-testid="stChatMessageContent"],
        div[class*="st-key-copilot-sidebar"] [data-testid="stChatMessageContent"] {{
            color: {text0} !important;
        }}

        /* Customize scrollbar for the Copilot sidebar container */
        div[class*="st-key-copilot_sidebar"]::-webkit-scrollbar,
        div[class*="st-key-copilot-sidebar"]::-webkit-scrollbar {{
            width: 4px;
        }}
        div[class*="st-key-copilot_sidebar"]::-webkit-scrollbar-thumb,
        div[class*="st-key-copilot-sidebar"]::-webkit-scrollbar-thumb {{
            background: {copilot_scrollbar};
            border-radius: 2px;
        }}

        /* Pin chat input to bottom of viewport, aligned with copilot sidebar */
        div[class*="st-key-copilot_sidebar"] .stChatFloatingInputContainer,
        div[class*="st-key-copilot-sidebar"] .stChatFloatingInputContainer,
        div[class*="st-key-copilot_sidebar"] [data-testid="stChatInput"],
        div[class*="st-key-copilot-sidebar"] [data-testid="stChatInput"],
        div[class*="st-key-copilot_sidebar"] .stChatInput,
        div[class*="st-key-copilot-sidebar"] .stChatInput {{
            position: fixed !important;
            bottom: 0 !important;
            right: 0 !important;
            width: 380px !important;
            background: {copilot_input_bg} !important;
            border-top: 1px solid {copilot_input_border} !important;
            padding: 8px 16px !important;
            z-index: 9991 !important;
            margin: 0 !important;
            left: auto !important;
        }}

        /* Stretch chat input container children to fill width properly */
        div[class*="st-key-copilot_sidebar"] [data-testid="stChatInput"] > div,
        div[class*="st-key-copilot-sidebar"] [data-testid="stChatInput"] > div {{
            width: 100% !important;
            max-width: 100% !important;
        }}

        /* Add bottom padding to sidebar so content doesn't hide behind fixed input */
        div[class*="st-key-copilot_sidebar"],
        div[class*="st-key-copilot-sidebar"] {{
            padding-bottom: 80px !important;
        }}

        /* Source citation popup modal */
        #citation-modal {{
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 99999;
            justify-content: center;
            align-items: center;
        }}
        #citation-modal.show {{
            display: flex !important;
        }}
        #citation-modal .modal-content {{
            background: {bg1};
            color: {text0};
            border: 1px solid {border};
            border-radius: 12px;
            padding: 24px;
            max-width: 500px;
            width: 90%;
            max-height: 70vh;
            overflow-y: auto;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            position: relative;
        }}
        #citation-modal .modal-close {{
            position: absolute;
            top: 8px; right: 12px;
            cursor: pointer;
            font-size: 1.2em;
            color: {text1};
            background: none;
            border: none;
        }}
        #citation-modal .modal-close:hover {{ color: {text0}; }}
        #citation-modal .modal-source {{
            font-size: 1.1em; font-weight: 700; margin-bottom: 4px;
        }}
        #citation-modal .modal-score {{
            font-size: 0.85em; color: {text1}; margin-bottom: 12px;
        }}
        #citation-modal .modal-snippet {{
            font-size: 0.9em; line-height: 1.5; color: {text0};
            background: {bg2};
            padding: 12px;
            border-radius: 8px;
            border: 1px solid {border};
            white-space: pre-wrap;
            word-break: break-word;
        }}

        /* Floating top controls bar */
        div[class*="st-key-top_controls"],
        div[data-key="top_controls"] {{
            position: fixed !important;
            top: 15px !important;
            right: 400px !important;
            width: auto !important;
            left: auto !important;
            z-index: 9995 !important;
            background: transparent !important;
            margin: 0 !important;
            padding: 0 !important;
            display: flex !important;
            flex-direction: row !important;
            align-items: center !important;
            gap: 8px !important;
        }}
        /* Make the inner Streamlit block layout horizontal */
        div[class*="st-key-top_controls"] > div[data-testid="stVerticalBlock"],
        div[data-key="top_controls"] > div[data-testid="stVerticalBlock"] {{
            flex-direction: row !important;
            align-items: center !important;
            gap: 8px !important;
            display: flex !important;
        }}
        /* Reset margins/paddings on Streamlit wrappers inside top_controls */
        div[class*="st-key-top_controls"] [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-top_controls"] [data-testid="stVerticalBlock"] > div,
        div[data-key="top_controls"] [data-testid="stVerticalBlockBorderWrapper"],
        div[data-key="top_controls"] [data-testid="stVerticalBlock"] > div {{
            margin: 0 !important;
            padding: 0 !important;
        }}
        div[class*="st-key-top_controls"] [data-testid="stPopover"],
        div[data-key="top_controls"] [data-testid="stPopover"] {{
            display: inline-flex !important;
            margin: 0 !important;
        }}
        /* Style the actual buttons to be ultra-compact icon buttons */
        div[class*="st-key-top_controls"] div.stButton > button,
        div[class*="st-key-top_controls"] div.stPopover > button,
        div[class*="st-key-top_controls"] button,
        div[data-key="top_controls"] div.stButton > button,
        div[data-key="top_controls"] div.stPopover > button,
        div[data-key="top_controls"] button {{
            background: {bg2} !important;
            color: {text0} !important;
            border: 1px solid {border} !important;
            border-radius: 4px !important;
            width: 28px !important;
            height: 28px !important;
            min-width: 28px !important;
            max-width: 28px !important;
            min-height: 28px !important;
            max-height: 28px !important;
            padding: 0 !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-size: 14px !important;
            box-shadow: none !important;
            transition: all 0.15s ease !important;
            line-height: 1 !important;
        }}
        div[class*="st-key-top_controls"] div.stButton > button:hover,
        div[class*="st-key-top_controls"] div.stPopover > button:hover,
        div[class*="st-key-top_controls"] button:hover,
        div[data-key="top_controls"] div.stButton > button:hover,
        div[data-key="top_controls"] div.stPopover > button:hover,
        div[data-key="top_controls"] button:hover {{
            background: rgba(0, 120, 212, 0.15) !important;
            border-color: #0078d4 !important;
            color: #0078d4 !important;
            transform: scale(1.05) !important;
        }}
        /* Guarantee icon colors inside buttons stay high contrast */
        div[class*="st-key-top_controls"] button p,
        div[class*="st-key-top_controls"] button span,
        div[class*="st-key-top_controls"] button div,
        div[data-key="top_controls"] button p,
        div[data-key="top_controls"] button span,
        div[data-key="top_controls"] button div {{
            color: {text0} !important;
            font-size: 14px !important;
            margin: 0 !important;
            padding: 0 !important;
            line-height: 1 !important;
        }}

        /* Force the Canvas component to fill 100% width */
        div[data-testid="stHtml"],
        div[data-testid="stHtml"] > div,
        div[data-testid="stIFrame"],
        div[data-testid="stIFrame"] > iframe,
        iframe[data-testid="stIFrame"] {{
            width: 100% !important;
            max-width: 100% !important;
        }}
        /* Force the Canvas iframe to fill the height of the window and 100% width */
        div[data-testid="stHtml"] iframe,
        div[data-testid="stIFrame"] iframe,
        iframe[data-testid="stIFrame"] {{
            height: calc(100vh - 60px) !important;
            width: 100% !important;
            border: none !important;
            background: transparent !important;
        }}
    <script>
    function showCitationPopup(source, score, snippet) {{
        var modal = document.getElementById('citation-modal');
        if (!modal) return;
        modal.querySelector('.modal-source').textContent = source;
        modal.querySelector('.modal-score').textContent = 'Relevance score: ' + score.toFixed(3);
        modal.querySelector('.modal-snippet').textContent = snippet || '(No preview available)';
        modal.classList.add('show');
    }}
    document.addEventListener('click', function(e) {{
        var modal = document.getElementById('citation-modal');
        if (!modal) return;
        if (e.target === modal) modal.classList.remove('show');
    }});
    </script>
    <div id="citation-modal" onclick="this.classList.remove('show')">
        <div class="modal-content" onclick="event.stopPropagation()">
            <button class="modal-close" onclick="document.getElementById('citation-modal').classList.remove('show')">&times;</button>
            <div class="modal-source"></div>
            <div class="modal-score"></div>
            <div class="modal-snippet"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Settings dialog CSS — injected at page level so it reaches the stModal DOM
    st.markdown("""
    <style>
    /* ── Settings dialog: compact ghost buttons ── */
    div[data-testid="stModal"] button[kind="secondary"],
    div[data-testid="stModal"] button[kind="primary"] {
        padding: 4px 14px !important;
        font-size: 0.80rem !important;
        min-height: 30px !important;
        height: 30px !important;
        border-radius: 7px !important;
        font-weight: 500 !important;
    }
    div[data-testid="stModal"] button[kind="secondary"] {
        background: transparent !important;
        border: 1px solid rgba(128,128,128,0.28) !important;
        color: var(--text0, #e0e0e0) !important;
        width: auto !important;
        max-width: fit-content !important;
    }
    div[data-testid="stModal"] button[kind="secondary"]:hover {
        background: rgba(255,255,255,0.05) !important;
        border-color: rgba(128,128,128,0.50) !important;
    }
    /* Destructive: red ghost */
    div[data-testid="stModal"] div[class*="st-key-dlg_clear_index"] button,
    div[data-testid="stModal"] div[class*="st-key-dlg_del_folder"] button,
    div[data-testid="stModal"] div[class*="st-key-delete_prov_btn"] button {
        color: #e05555 !important;
        border-color: rgba(224,85,85,0.35) !important;
        background: transparent !important;
    }
    div[data-testid="stModal"] div[class*="st-key-dlg_clear_index"] button:hover,
    div[data-testid="stModal"] div[class*="st-key-dlg_del_folder"] button:hover,
    div[data-testid="stModal"] div[class*="st-key-delete_prov_btn"] button:hover {
        background: rgba(224,85,85,0.08) !important;
    }
    /* Primary save / add: accent colour, auto width */
    div[data-testid="stModal"] div[class*="st-key-save_chat_settings_btn"] button,
    div[data-testid="stModal"] div[class*="st-key-save_emb_settings_btn"] button,
    div[data-testid="stModal"] div[class*="st-key-save_rerank_settings_btn"] button,
    div[data-testid="stModal"] div[class*="st-key-save_edit_prov_btn"] button,
    div[data-testid="stModal"] div[class*="st-key-add_prov_btn"] button,
    div[data-testid="stModal"] div[class*="st-key-dlg_add_folder_path_btn"] button,
    div[data-testid="stModal"] div[class*="st-key-dlg_index_upload"] button {
        background: #4f8bea !important;
        border: none !important;
        color: #fff !important;
        width: auto !important;
        max-width: fit-content !important;
    }
    div[data-testid="stModal"] div[class*="st-key-save_chat_settings_btn"] button:hover,
    div[data-testid="stModal"] div[class*="st-key-save_emb_settings_btn"] button:hover,
    div[data-testid="stModal"] div[class*="st-key-save_rerank_settings_btn"] button:hover,
    div[data-testid="stModal"] div[class*="st-key-save_edit_prov_btn"] button:hover,
    div[data-testid="stModal"] div[class*="st-key-add_prov_btn"] button:hover,
    div[data-testid="stModal"] div[class*="st-key-dlg_add_folder_path_btn"] button:hover,
    div[data-testid="stModal"] div[class*="st-key-dlg_index_upload"] button:hover {
        opacity: 0.85 !important;
    }
    /* Tighten spacing */
    div[data-testid="stModal"] .stMarkdown p { margin: 0; }
    div[data-testid="stModal"] hr { margin: 8px 0 !important; }
    /* Status row */
    .dlg-status-row {
        display: flex; gap: 0; align-items: stretch; padding: 8px 0 12px;
    }
    .dlg-stat {
        display: flex; flex-direction: column; align-items: center; gap: 2px;
        padding: 0 18px; border-right: 1px solid rgba(128,128,128,0.18);
    }
    .dlg-stat:first-child { padding-left: 0; }
    .dlg-stat:last-child { border-right: none; }
    .dlg-stat-val { font-size: 1rem; font-weight: 700; color: var(--text0, #e0e0e0); line-height: 1.2; }
    .dlg-stat-lbl { font-size: 0.70rem; color: var(--text2, #888); text-transform: uppercase; letter-spacing: 0.05em; }
    /* Section label */
    .dlg-section-label {
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.08em;
        text-transform: uppercase; color: var(--text2, #888); margin: 12px 0 4px;
    }
    /* Provider card */
    .dlg-prov-card { padding: 8px 12px; border-radius: 8px; background: rgba(128,128,128,0.06);
        border-left: 3px solid #888; margin: 5px 0; font-size: 0.82rem; }
    .dlg-prov-card.ok { border-left-color: #3ecf8e; }
    .dlg-prov-card.err { border-left-color: #e05555; }
    .dlg-prov-name { font-weight: 600; color: var(--text0, #e0e0e0); }
    .dlg-prov-meta { color: var(--text2, #888); margin-top: 2px; font-size: 0.78rem; }
    </style>
    """, unsafe_allow_html=True)

    if not rag_pipeline or not llm:
        # System is not ready: render top bar with Settings and Dark Mode toggle only
        with st.container(key="top_controls"):
            from ui.api_settings import settings_dialog
            if st.button("⚙️", key="top_settings_btn", help="Settings"):
                st.session_state.settings_subpage = None
                settings_dialog()
            if st.button("☀️" if is_dark else "🌙", key="theme_toggle_btn", help="Toggle Theme"):
                st.session_state.is_dark = not is_dark
                st.rerun()

        # Show warning card
        st.markdown(f"""
        <div style="padding: 24px; background: rgba(255,184,0,0.08); border: 1px solid rgba(255,184,0,0.3); border-radius: 12px; margin-top: 20px;">
            <h3 style="color: #ffb800; margin: 0;">⚠️ System Not Ready</h3>
            <p style="color: var(--text1); margin: 12px 0;">
                Please configure your API keys and embedding model in <strong>Settings</strong> at the top right before using the system.
            </p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Initialize generator
    if not st.session_state.report_generator:
        st.session_state.report_generator = ReportGenerator(rag_pipeline, llm)

    report_gen = st.session_state.report_generator

    # Check background task status
    report_task = st.session_state.report_task
    if report_task and report_task.is_done:
        if report_task.error:
            st.error(f"Report generation failed: {report_task.error}")
        else:
            generated_report = report_task.result
            if generated_report:
                st.session_state.active_report_title = generated_report.title
                st.session_state.active_report_content = generated_report.to_markdown()
                st.success("Report generated! Loaded into the editor.")
        st.session_state.report_task = None
        st.rerun()

    templates = load_templates()

    # Top-right aligned actions row using key="top_controls" container
    with st.container(key="top_controls"):
        # Merged Report Generator Dropdown Popover
        with st.popover("📋", help="Report Generator"):
            st.markdown("##### Quick Templates")
            
            presets = [
                ("summary", "Executive Summary"),
                ("time_analysis", "Time-Based"),
                ("trend", "Trend Analysis"),
                ("comparison", "Comparison"),
                ("metrics", "Metrics"),
            ]
            
            # Quick Templates list
            for p_type, p_label in presets:
                if st.button(p_label, key=f"pop_preset_{p_type}", use_container_width=True):
                    prompt = f"Write a comprehensive {p_label} based on the indexed documents, summarizing key stats."
                    task = BackgroundTask(
                        target=generate_report_job,
                        kwargs={
                            "report_gen": report_gen,
                            "report_type": "custom",
                            "query": "",
                            "start_date": None,
                            "end_date": None,
                            "custom_prompt": prompt
                        }
                    )
                    st.session_state.report_task = task
                    task.start()
                    st.toast(f"⚡ Generating preset: {p_label}...", icon="🚀")
                    st.rerun()

            if templates:
                st.markdown("---")
                st.markdown("##### 🛠️ Custom Templates")
                for name, t_data in templates.items():
                    if st.button(f"🛠️ {name}", key=f"pop_custom_{name}", use_container_width=True):
                        task = BackgroundTask(
                            target=generate_report_job,
                            kwargs={
                                "report_gen": report_gen,
                                "report_type": "custom",
                                "query": "",
                                "start_date": None,
                                "end_date": None,
                                "custom_prompt": t_data["prompt"]
                            }
                        )
                        st.session_state.report_task = task
                        task.start()
                        st.toast(f"⚡ Generating template: {name}...", icon="🚀")
                        st.rerun()

            st.markdown("---")
            if st.button("Add Custom Report", use_container_width=True, key="pop_add_custom_report_btn"):
                manage_templates_dialog()

        # Settings
        from ui.api_settings import settings_dialog
        if st.button("⚙️", key="top_settings_btn", help="Settings"):
            st.session_state.settings_subpage = None
            settings_dialog()

        # Theme toggle
        if st.button("☀️" if is_dark else "🌙", key="theme_toggle_btn", help="Toggle Theme"):
            st.session_state.is_dark = not is_dark
            st.rerun()

    # Display background generation status if task is running
    task_running = report_task is not None and report_task.is_running
    if task_running:
        st.info("🔄 Report generation is in progress...")
        if st.button("🔄 Check Generation Status", key="chk_gen_btn"):
            st.rerun()

    # Canvas Preview with floating download buttons (renders directly at full width, no columns!)
    if st.session_state.active_report_content:
        content = st.session_state.active_report_content
        if not content.strip().startswith("#"):
            content = f"# {st.session_state.active_report_title}\n\n{content}"
        canvas_html = _build_canvas_html(
            st.session_state.active_report_title,
            content,
            st.session_state.is_dark,
        )
        components.html(canvas_html, height=800, scrolling=True)
    else:
        st.markdown("<p style='color: var(--text2); text-align: center; padding: 150px 0;'>No report content loaded. Select a template from the Report Generator dropdown or ask Copilot to generate a report!</p>", unsafe_allow_html=True)

    # 4. Report History / Library
    saved_reports = load_saved_reports()
    if saved_reports:
        st.markdown("<h4 style='color: var(--text0); margin-top: 24px;'>Saved Reports Library (保存的历史报告)</h4>", unsafe_allow_html=True)
        for r_idx, r_data in enumerate(saved_reports):
            saved_time = r_data.get("saved_at", "")[:19].replace("T", " ")
            r_title = r_data.get("title", "Untitled")
            r_path = r_data.get("file_path", "")
            
            col_item, col_load, col_del = st.columns([8, 2, 2])
            with col_item:
                st.markdown(f"**{r_title}**  \n<span style='color:var(--text2); font-size:0.85em;'>Saved: {saved_time}</span>", unsafe_allow_html=True)
            with col_load:
                if st.button("Load", key=f"load_r_{r_idx}", use_container_width=True):
                    st.session_state.active_report_title = r_title
                    st.session_state.active_report_content = r_data.get("content", "")
                    st.toast(f"Loaded '{r_title}' into canvas!")
                    st.rerun()
            with col_del:
                if st.button("Delete", key=f"del_r_{r_idx}", use_container_width=True):
                    delete_report(r_path)
                    st.warning("Report deleted.")
                    st.rerun()

    # ============================================================
    # Right Column: Edge Copilot Chat Assistant
    # ============================================================
    right_col = st.container()
    with right_col:
        # Wrap everything in a container with a custom key so we can target it in CSS
        with st.container(key="copilot_sidebar"):
            st.markdown("<h3 style='color: var(--text0); margin-top: 0;'>Copilot Assistant</h3>", unsafe_allow_html=True)
            st.markdown("<p style='color: var(--text1); font-size:0.85em; margin-top:0;'>Ask for content additions, data table creations, or report refinements.</p>", unsafe_allow_html=True)

            # Copilot Chat Container
            chat_container = st.container()

            with chat_container:
                # Top chat bubble: compact icon toolbar
                with st.chat_message("assistant"):
                    col_label, col_new, col_hist, col_plus = st.columns([2, 1, 1, 1])
                    with col_label:
                        st.markdown("<div class='chat-actions-label'>Chat actions</div>", unsafe_allow_html=True)
                    with col_new:
                        new_chat_clicked = st.button("🆕", help="New Chat", key="action_new_chat")
                    with col_hist:
                        with st.popover("🕐"):
                            _render_copilot_history()
                    with col_plus:
                        with st.popover("➕", help="Tools & presets"):
                            st.markdown("<div style='margin-top:0; font-weight:600;'>Tools</div>", unsafe_allow_html=True)
                            new_preset = st.text_input("Add preset", placeholder="e.g. Summarize EFF data", label_visibility="collapsed")
                            if st.button("Add", key="add_preset_btn"):
                                if new_preset and new_preset not in st.session_state.copilot_presets:
                                    st.session_state.copilot_presets.append(new_preset)
                                    st.toast("Preset added!")
                                    st.rerun()
                            st.markdown("<hr class='minimal-divider' style='margin: 8px 0;'>", unsafe_allow_html=True)
                            uploaded_file = st.file_uploader("Upload PDF to index", type=["pdf"], key="chat_pdf_uploader", label_visibility="collapsed")
                            if uploaded_file:
                                if st.button("Index PDF File", use_container_width=True, key="chat_index_upload_btn"):
                                    with st.spinner("Indexing PDF..."):
                                        upload_dir = PROJECT_ROOT / "data" / "uploads"
                                        upload_dir.mkdir(parents=True, exist_ok=True)
                                        file_path = upload_dir / uploaded_file.name
                                        with open(file_path, "wb") as f:
                                            f.write(uploaded_file.getbuffer())
                                        count = st.session_state.doc_manager.handle_upload(str(file_path))
                                        st.success(f"Indexed {count} chunks!")
                                        st.rerun()
                            st.markdown("<hr class='minimal-divider' style='margin: 8px 0;'>", unsafe_allow_html=True)
                            if st.button("Activate Canvas", use_container_width=True, key="chat_activate_canvas_btn"):
                                st.session_state.active_report_content = "# Active Report\n\nStart typing or request sections from the assistant..."
                                st.session_state.active_report_title = "Active Report"
                                st.toast("Canvas activated!")
                                st.rerun()
                            if st.button("Clear Canvas", use_container_width=True, key="chat_clear_canvas_btn"):
                                st.session_state.active_report_content = ""
                                st.session_state.active_report_title = "Untitled Report"
                                st.toast("Canvas cleared!")
                                st.rerun()
                    st.markdown("<div class='chat-actions-divider'></div>", unsafe_allow_html=True)

                if not st.session_state.copilot_messages:
                    st.markdown("<p style='color:var(--text2); text-align:center; margin-top:60px;'>No messages. Ask me to refine, extract tables, or write report sections!</p>", unsafe_allow_html=True)

                for msg_idx, msg in enumerate(st.session_state.copilot_messages):
                    role = msg["role"]
                    content = msg["content"]
                    citations = msg.get("citations")

                    # Render using native theme layout
                    with st.chat_message(role):
                        st.markdown(content, unsafe_allow_html=True)

                        # Copy button
                        content_escaped = json.dumps(content)
                        st.markdown(
                            f'<div style="text-align:right; margin-top:-6px; line-height:1;">'
                            f'<button class="msg-copy-btn" onclick="navigator.clipboard.writeText({content_escaped})" title="Copy message">📋</button>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                        # If assistant message, render apply actions and citations
                        if role == "assistant":
                            if citations:
                                with st.expander(f"📎 Citations ({len(citations)})"):
                                    for ci, c in enumerate(citations):
                                        source = c.get("source", "Unknown")
                                        score = c.get("score", 0.0)
                                        snippet = c.get("snippet", "")
                                        safe_snippet = snippet.replace("`", "\\`").replace("'", "\\'").replace("\n", "\\n")[:300]
                                        st.markdown(
                                            f'<div style="margin:4px 0;">'
                                            f'<a href="#" onclick="showCitationPopup(\'{source}\', {score:.3f}, \'{safe_snippet}\'); return false;" '
                                            f'style="color:var(--accent,#00bcf2); text-decoration:none; font-weight:600;">📄 {source}</a>'
                                            f'</div>',
                                            unsafe_allow_html=True,
                                        )

                            # Direct Canvas updates are automated; no manual copy buttons are needed

                # Custom Presets (inside chat container)
                presets = st.session_state.get("copilot_presets", [])
                if presets:
                    ncols = min(len(presets), 3)
                    for row_start in range(0, len(presets), ncols):
                        row_cols = st.columns(ncols)
                        for ci in range(ncols):
                            idx = row_start + ci
                            if idx < len(presets):
                                with row_cols[ci]:
                                    if st.button(presets[idx], key=f"preset_{idx}"):
                                        user_query = presets[idx]

                                        user_query = presets[idx]

            # Chat input (pinned to bottom of copilot column)
            query_input = st.chat_input("Ask Copilot helper...")

            # Process input
            user_query = ""
            if query_input:
                user_query = query_input
            elif new_chat_clicked:
                # Save current session before starting new one
                current_msgs = st.session_state.get("copilot_messages", [])
                if current_msgs:
                    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                    title = get_copilot_session_title(current_msgs)
                    save_copilot_session(session_id, title)
                st.session_state.copilot_messages = []
                st.toast("New chat started. Previous session saved.")
                st.rerun()

            if user_query:
                # Append User Message
                st.session_state.copilot_messages.append({"role": "user", "content": user_query})

                # Run query with Spinner
                with st.spinner("Copilot is thinking..."):
                    try:
                        response, citations = run_copilot_query(
                            llm=llm,
                            rag_pipeline=rag_pipeline,
                            user_query=user_query,
                            current_report_content=st.session_state.active_report_content
                        )

                        canvas_content = None
                        clean_response = response

                        import re
                        fences = list(re.finditer(r"^```(\S*)", response, re.MULTILINE))
                        canvas_open_idx = -1
                        for fi, fm in enumerate(fences):
                            if fm.group(1) == "markdown-canvas":
                                canvas_open_idx = fi
                                break

                        if canvas_open_idx >= 0:
                            content_start = fences[canvas_open_idx].end() + 1
                            depth = 0
                            for fi in range(canvas_open_idx + 1, len(fences)):
                                tag = fences[fi].group(1)
                                if tag:
                                    depth += 1
                                else:
                                    if depth == 0:
                                        end_pos = fences[fi].start()
                                        close_len = 3
                                        canvas_content = response[content_start:end_pos].strip()
                                        clean_response = (
                                            response[:fences[canvas_open_idx].start()] +
                                            response[end_pos + close_len:]
                                        ).strip()
                                        break
                                    depth -= 1

                        if canvas_content:
                            st.session_state.active_report_content = canvas_content
                            title_match = re.search(r"^#\s+(.+)$", canvas_content, re.MULTILINE)
                            if title_match:
                                st.session_state.active_report_title = title_match.group(1).strip()
                            st.toast("🎨 Canvas updated directly!", icon="✨")

                        if not clean_response:
                            clean_response = "I have updated the report on the canvas."

                        st.session_state.copilot_messages.append({
                            "role": "assistant",
                            "content": clean_response,
                            "citations": citations
                        })
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
