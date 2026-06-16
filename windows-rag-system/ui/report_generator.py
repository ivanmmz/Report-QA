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
from utils.file_io import read_json, write_json
from utils.background_task import BackgroundTask
from core.report_generator import ReportGenerator, Report
from core.rag_pipeline import RAGPipeline
from llm.gateway import LLMGateway
from ui.theme import render_card, render_chat_message


def init_report_state() -> None:
    """Initialize report generator and editor session state."""
    if "active_report_title" not in st.session_state:
        st.session_state.active_report_title = "Untitled Report"
    if "active_report_content" not in st.session_state:
        st.session_state.active_report_content = ""
    if "copilot_messages" not in st.session_state:
        st.session_state.copilot_messages = []
    if "report_task" not in st.session_state:
        st.session_state.report_task = None
    if "selected_template_prompt" not in st.session_state:
        st.session_state.selected_template_prompt = ""
    if "report_generator" not in st.session_state:
        st.session_state.report_generator = None


def load_templates() -> Dict[str, Any]:
    """Load report templates from config/report_templates.json."""
    template_file = Path("config/report_templates.json")
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
    write_json("config/report_templates.json", templates)


def delete_template(name: str) -> None:
    """Delete a custom report template."""
    templates = load_templates()
    if name in templates:
        del templates[name]
        write_json("config/report_templates.json", templates)


def load_saved_reports() -> List[Dict[str, Any]]:
    """Load saved reports from data/reports/."""
    reports_dir = Path("data/reports")
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


def save_report(title: str, content: str) -> str:
    """Save active report to data/reports/."""
    reports_dir = Path("data/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = reports_dir / f"report_{timestamp}.json"
    data = {
        "title": title,
        "content": content,
        "saved_at": datetime.now().isoformat()
    }
    write_json(file_path, data)
    return str(file_path)


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
            results = rag_pipeline.retriever.retrieve(user_query, top_k=5)
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

    system_prompt = f"""You are an expert AI Report Copilot Assistant (Edge Copilot style).
Your goal is to help the user review, improve, refine, or write technical reports.

The user is CURRENTLY working on the following report content in their editor:
```markdown
{current_report_content}
```

Instructions:
1. Help the user edit, write, or format sections of their report.
2. If they ask to update or write report sections, provide the text clearly in Markdown.
3. Refer to the provided document context below to extract real statistics, metrics, or factual statements if needed.
4. Keep answers concise, technical, and highly actionable.
5. If you suggest changes, explain them clearly so the user can review them.
6. Make sure to output suggestions directly, so they can apply them easily."""

    user_prompt = f"""Document Context for Reference:
{context}

User Query/Request:
{user_query}

Please provide your helpful suggestion, refinement, or data generation:"""

    response = llm.chat(user_prompt, "", system_prompt)
    return response, citations


def render_report_generator(rag_pipeline: Optional[RAGPipeline], llm: Optional[LLMGateway]) -> None:
    """Render the split-column Reports & Copilot view."""
    init_report_state()

    # Title header
    st.markdown("<h1 style='color: #ffffff; margin-bottom: 8px;'>📊 Reports & Copilot</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color: rgba(255,255,255,0.6); margin-top: 0; margin-bottom: 24px;'>"
        "Generate structured reports from documents, edit content manually, and chat with AI Copilot for real-time writing assistance."
        "</p>",
        unsafe_allow_html=True,
    )

    if not rag_pipeline or not llm:
        render_card(
            "System Not Ready",
            "Please configure your API keys and index documents before generating reports.",
            accent=True,
        )
        return

    # Initialize generator
    if not st.session_state.report_generator:
        st.session_state.report_generator = ReportGenerator(rag_pipeline, llm)

    report_gen = st.session_state.report_generator

    # Check background task status
    report_task = st.session_state.report_task
    if report_task and report_task.is_done:
        if report_task.error:
            st.error(f"❌ Report generation failed: {report_task.error}")
        else:
            generated_report = report_task.result
            if generated_report:
                st.session_state.active_report_title = generated_report.title
                st.session_state.active_report_content = generated_report.to_markdown()
                st.success("🎉 Report generated successfully! Loaded into the editor.")
        st.session_state.report_task = None
        st.rerun()

    # Split page layout: Left Column (Report Editor/Generator) | Right Column (Copilot Chat)
    left_col, right_col = st.columns([7, 4])

    # ============================================================
    # Left Column: Report Generator & Editor
    # ============================================================
    with left_col:
        st.markdown("<h3 style='color: #e4e6eb; margin-top: 0;'>📝 Report Generator</h3>", unsafe_allow_html=True)

        # 1. Top Section: Presets & Custom Template buttons
        templates = load_templates()
        
        st.markdown("<h5 style='color: #e4e6eb; margin-bottom: 6px;'>一键生成统一格式报告 (Quick Templates):</h5>", unsafe_allow_html=True)
        
        # Display template buttons in horizontal rows
        presets = [
            ("summary", "📋 Executive Summary"),
            ("time_analysis", "📅 Time-Based"),
            ("trend", "📈 Trend Analysis"),
            ("comparison", "⚖️ Comparison"),
            ("metrics", "📊 Metrics"),
        ]
        
        # Row 1: Presets
        cols_preset = st.columns(len(presets))
        for idx, (p_type, p_label) in enumerate(presets):
            with cols_preset[idx]:
                if st.button(p_label, key=f"preset_btn_{p_type}", use_container_width=True):
                    st.session_state.selected_template_prompt = f"Write a comprehensive {p_label} based on the indexed documents, summarizing key stats."
                    st.toast(f"Selected preset: {p_label}")
        
        # Row 2: Custom Saved Templates
        if templates:
            st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
            cols_custom = st.columns(max(len(templates), 4))
            for idx, (name, t_data) in enumerate(templates.items()):
                col_idx = idx % len(cols_custom)
                with cols_custom[col_idx]:
                    if st.button(f"🛠️ {name}", key=f"custom_template_btn_{name}", use_container_width=True):
                        st.session_state.selected_template_prompt = t_data["prompt"]
                        st.toast(f"Loaded template: {name}")

        # Collapsible Custom Template Manager
        with st.expander("🛠️ Save / Manage Custom Templates", expanded=False):
            t_name = st.text_input("Template Name (e.g. OSE)", placeholder="OSE")
            t_desc = st.text_input("Description (描述)", placeholder="Operation System Efficiency Report")
            t_prompt = st.text_area("Template Instructions / Prompt (生成要求)", placeholder="Provide template layout requirements or prompting rules here...")
            
            col_t_save, col_t_del = st.columns(2)
            with col_t_save:
                if st.button("💾 Save Template Form", use_container_width=True, key="save_custom_temp_btn"):
                    if not t_name or not t_prompt:
                        st.error("Name and Prompt instructions are required.")
                    else:
                        save_template(t_name, t_desc, t_prompt)
                        st.success(f"Template '{t_name}' saved to top buttons!")
                        st.rerun()
            with col_t_del:
                # Delete option
                if templates:
                    del_name = st.selectbox("Select Template to Delete", options=list(templates.keys()), key="del_temp_select")
                    if st.button("🗑️ Delete Template", use_container_width=True, key="del_custom_temp_btn"):
                        delete_template(del_name)
                        st.warning(f"Deleted template '{del_name}'")
                        st.rerun()

        st.markdown("<hr class='minimal-divider'>", unsafe_allow_html=True)

        # 2. Generator parameters & Trigger
        with st.container():
            col_q, col_d = st.columns([2, 1])
            with col_q:
                report_query = st.text_input(
                    "Report Query / Focus (报告主题)",
                    placeholder="e.g. energy consumption optimization, system COP",
                    key="report_query_input"
                )
            with col_d:
                # Date filter expander
                date_filter = st.checkbox("Apply Date Filter", value=False)
                start_date_str = None
                end_date_str = None
                if date_filter:
                    col_ds, col_de = st.columns(2)
                    with col_ds:
                        start_date = st.date_input("Start", value=None)
                        start_date_str = start_date.strftime("%Y-%m-%d") if start_date else None
                    with col_de:
                        end_date = st.date_input("End", value=None)
                        end_date_str = end_date.strftime("%Y-%m-%d") if end_date else None

            # Custom prompt / prompt loaded from template
            st.session_state.selected_template_prompt = st.text_area(
                "Instructions (生成指令/提示词)",
                value=st.session_state.selected_template_prompt,
                placeholder="Select a template above or type custom instructions...",
                height=100,
                key="active_instructions_area"
            )

            # Trigger Button (Background run!)
            task_running = report_task is not None and report_task.is_running
            btn_label = "⚡ Generating report in background..." if task_running else "🚀 Generate Report (AI生成报告)"
            if st.button(btn_label, use_container_width=True, key="gen_report_btn", disabled=task_running):
                # Spawn background task
                task = BackgroundTask(
                    target=generate_report_job,
                    kwargs={
                        "report_gen": report_gen,
                        "report_type": "custom",
                        "query": report_query,
                        "start_date": start_date_str,
                        "end_date": end_date_str,
                        "custom_prompt": st.session_state.selected_template_prompt
                    }
                )
                st.session_state.report_task = task
                task.start()
                st.toast("⚡ Report generation started in background! You can navigate away.", icon="🚀")
                st.rerun()

        # Display background generation status
        if task_running:
            st.info("🔄 Report generation is in progress. You can switch to the 'Documents' page or continue editing. Check back here to load the result.")
            if st.button("🔄 Check Generation Status", key="chk_gen_btn"):
                st.rerun()

        st.markdown("<hr class='minimal-divider'>", unsafe_allow_html=True)

        # 3. Active Report Editor (Manual Edit & Persistence)
        st.markdown("<h4 style='color: #e4e6eb;'>📝 Active Report Editor (编辑报告)</h4>", unsafe_allow_html=True)
        
        st.session_state.active_report_title = st.text_input(
            "Report Title (报告标题)",
            value=st.session_state.active_report_title,
            key="report_title_edit"
        )
        
        st.session_state.active_report_content = st.text_area(
            "Report Content (Markdown) (报告正文内容)",
            value=st.session_state.active_report_content,
            height=400,
            key="report_content_edit"
        )

        col_save, col_dl_md, col_dl_json = st.columns(3)
        with col_save:
            if st.button("💾 Save Report (保存到历史)", use_container_width=True, key="save_report_btn"):
                filepath = save_report(st.session_state.active_report_title, st.session_state.active_report_content)
                st.success(f"Report saved to history!")
                st.rerun()
        with col_dl_md:
            st.download_button(
                "📄 Download Markdown",
                data=st.session_state.active_report_content,
                file_name=f"{st.session_state.active_report_title.replace(' ', '_')}.md",
                mime="text/markdown",
                use_container_width=True
            )
        with col_dl_json:
            json_str = json.dumps({
                "title": st.session_state.active_report_title,
                "content": st.session_state.active_report_content,
                "saved_at": datetime.now().isoformat()
            }, indent=2, ensure_ascii=False)
            st.download_button(
                "📄 Download JSON",
                data=json_str,
                file_name=f"{st.session_state.active_report_title.replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True
            )

        # 4. Report History / Library
        saved_reports = load_saved_reports()
        if saved_reports:
            st.markdown("<h4 style='color: #e4e6eb; margin-top: 24px;'>📂 Saved Reports Library (保存的历史报告)</h4>", unsafe_allow_html=True)
            for r_idx, r_data in enumerate(saved_reports):
                saved_time = r_data.get("saved_at", "")[:19].replace("T", " ")
                r_title = r_data.get("title", "Untitled")
                r_path = r_data.get("file_path", "")
                
                col_item, col_load, col_del = st.columns([4, 1, 1])
                with col_item:
                    st.markdown(f"**{r_title}**  \n<span style='color:rgba(255,255,255,0.4); font-size:0.85em;'>Saved: {saved_time}</span>", unsafe_allow_html=True)
                with col_load:
                    if st.button("Load", key=f"load_r_{r_idx}", use_container_width=True):
                        st.session_state.active_report_title = r_title
                        st.session_state.active_report_content = r_data.get("content", "")
                        st.toast(f"Loaded '{r_title}' into editor!")
                        st.rerun()
                with col_del:
                    if st.button("Delete", key=f"del_r_{r_idx}", use_container_width=True):
                        delete_report(r_path)
                        st.warning("Report deleted.")
                        st.rerun()

    # ============================================================
    # Right Column: Edge Copilot Chat Assistant
    # ============================================================
    with right_col:
        st.markdown("<h3 style='color: #e4e6eb; margin-top: 0;'>💬 Copilot Assistant</h3>", unsafe_allow_html=True)
        st.markdown("<p style='color: rgba(255,255,255,0.5); font-size:0.85em; margin-top:0;'>Edge Copilot-style assistant. Ask for content additions, data table creations, or report refinements.</p>", unsafe_allow_html=True)

        # Copilot Chat Container
        chat_container = st.container(height=500)
        
        with chat_container:
            if not st.session_state.copilot_messages:
                st.markdown("<p style='color:rgba(255,255,255,0.3); text-align:center; margin-top:100px;'>No messages. Ask me to refine, extract tables, or write report sections!</p>", unsafe_allow_html=True)
            
            for msg_idx, msg in enumerate(st.session_state.copilot_messages):
                role = msg["role"]
                content = msg["content"]
                citations = msg.get("citations")
                
                # Render using native theme layout
                with st.chat_message(role):
                    st.markdown(content)
                    
                    # If assistant message, render apply actions and citations
                    if role == "assistant":
                        if citations:
                            with st.expander(f"📎 Citations ({len(citations)})"):
                                for c in citations:
                                    st.markdown(f"**{c.get('source')}** (score: `{c.get('score'):.3f}`)")
                                    if c.get("snippet"):
                                        st.caption(c.get("snippet"))
                        
                        # Apply buttons
                        col_repl, col_app = st.columns(2)
                        with col_repl:
                            if st.button("📋 Replace Active Report", key=f"copilot_replace_{msg_idx}", use_container_width=True):
                                st.session_state.active_report_content = content
                                st.toast("Report editor updated (replaced)!")
                                st.rerun()
                        with col_app:
                            if st.button("➕ Append to Report", key=f"copilot_append_{msg_idx}", use_container_width=True):
                                st.session_state.active_report_content += f"\n\n{content}"
                                st.toast("AI content appended to editor!")
                                st.rerun()

        # Quick Assistant Actions
        st.markdown("<h5 style='color: #e4e6eb; margin-bottom:4px;'>Quick Actions:</h5>", unsafe_allow_html=True)
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            refine_clicked = st.button("✍️ Refine Active Section", use_container_width=True, key="action_refine")
            metrics_clicked = st.button("📊 Extract Metrics Table", use_container_width=True, key="action_table")
        with col_act2:
            summary_clicked = st.button("📝 Draft Exec Summary", use_container_width=True, key="action_exec_sum")
            clear_chat_clicked = st.button("🗑️ Clear Copilot Chat", use_container_width=True, key="action_clear_chat")

        # Input box
        query_input = st.chat_input("Ask Copilot helper...")

        # Process input
        user_query = ""
        if query_input:
            user_query = query_input
        elif refine_clicked:
            user_query = "Please review the active report content, clean up the grammar, refine the layout structure, and rewrite it for maximum clarity."
        elif metrics_clicked:
            user_query = "Search the documents, extract all numeric metrics (chiller system energy, COP values, flow rates, electricity load) and compile them into a neat Markdown metrics table."
        elif summary_clicked:
            user_query = "Draft a formal 3-paragraph Executive Summary based on the active report content and reference docs."
        elif clear_chat_clicked:
            st.session_state.copilot_messages = []
            st.toast("Copilot chat history cleared.")
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
                    
                    st.session_state.copilot_messages.append({
                        "role": "assistant",
                        "content": response,
                        "citations": citations
                    })
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
