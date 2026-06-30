"""LLM Gateway for Windows RAG System."""
import os
from typing import List, Dict, Any, Generator
from openai import OpenAI

from utils.logger import setup_logger
from utils.file_io import read_json
from utils.paths import API_KEYS_LOCAL_PATH, API_KEYS_PATH

logger = setup_logger("llm_gateway")


class LLMGateway:
    """Unified LLM gateway supporting multiple providers."""

    def __init__(self, config_path=API_KEYS_LOCAL_PATH, fallback_path=API_KEYS_PATH):
        """Initialize gateway with provider configs.

        Args:
            config_path: Primary config path (local/persistent).
            fallback_path: Fallback config path.
        """
        self.config = self._load_config(config_path, fallback_path)
        self.provider = self.config.get("default_provider", "")
        self.model = self.config.get("default_model", "")
        self.temperature = 0.3
        self.max_tokens = 8192
        self.client = None
        self._init_client()

    def _load_config(self, primary: str, fallback: str) -> Dict[str, Any]:
        """Load configuration with fallback chain.

        Args:
            primary: Primary config path.
            fallback: Fallback config path.

        Returns:
            Merged configuration dict.
        """
        config = read_json(primary)
        if not config.get("providers"):
            config = read_json(fallback)
        
        # Override with environment variables for all providers
        for provider_name in config.get("providers", {}):
            env_key = os.getenv(f"{provider_name.upper().replace('-', '_')}_API_KEY")
            if env_key:
                config["providers"][provider_name]["api_key"] = env_key
        
        # Legacy OpenAI env var
        env_key = os.getenv("OPENAI_API_KEY")
        if env_key and "providers" in config and "openai" in config["providers"]:
            config["providers"]["openai"]["api_key"] = env_key
        
        return config

    def _init_client(self) -> None:
        """Initialize OpenAI-compatible client."""
        if not self.provider or not self.model:
            logger.info("No provider configured, skipping client initialization")
            return

        providers = self.config.get("providers", {})
        pconf = providers.get(self.provider, {})
        
        base_url = pconf.get("base_url", "")
        api_key = pconf.get("api_key", "")
        
        # Check if provider needs API key
        is_key_optional = self.provider in ("local",) or api_key in ("not-needed", "")
        
        if not api_key and not is_key_optional:
            logger.warning(f"No API key configured for {self.provider}")
        
        if not base_url:
            logger.warning(f"No base URL configured for {self.provider}")
            return
        
        # Ensure base_url ends with /v1 for OpenAI-compatible APIs
        if base_url and not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
            # Some providers like Gemini already include the full path
            if "googleapis.com" not in base_url and "anthropic.com" not in base_url:
                base_url = base_url.rstrip("/") + "/v1"
        
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key or "dummy",
        )

    # Phrases that strongly suggest the user wants to mutate the canvas.
    CANVAS_EDIT_KEYWORDS = [
        "修改", "更新", "编辑", "改成", "改为", "翻译", "替换", "重写", "格式化",
        "润色", "改一下", "调整", "添加", "加入", "插入", "补充", "删除", "去掉",
        "删掉", "移除", "改动", "优化", "改写", "整理", "改调", "扩充", "拓展",
        "填入", "去除", "添加到", "加到", "写入", "追加", "融合", "拼接",
        "在canvas", "canvas里", "canvas中", "文档里", "文档中", "报表里",
        "报告里", "里面", "本文", "本章", "此文档",
        "edit", "modify", "update", "rewrite", "translate", "change", "fix",
        "format", "append", "insert", "remove", "delete", "refine", "polish",
        "expand", "shorten", "replace", "add to", "put in", "fill in", "merge",
        "canvas",
        "in the doc", "in the report", "in this file", "in the document",
        "into the report",
    ]

    # Phrases that signal the user wants to *read* / summarize the canvas
    # without mutating it. Treated as a separate intent so the LLM is not
    # forced to return a full rewritten document.
    CANVAS_READ_KEYWORDS = [
        # Keep phrases SPECIFIC so a modify query that just happens to contain a
        # summary noun (e.g. "在canvas里加入一段总结") is not misrouted. The bare
        # Chinese noun "总结" is intentionally absent - we only match the verb
        # form ("总结一下") where ambiguity is low.
        "总结一下", "概括一下", "归纳一下", "摘要一下",
        "说一下", "讲一下", "阐述一下", "讲讲", "说说", "读读", "看看",
        "总结这份", "总结这份文档", "总结当前", "总结当前文档",
        "what is in the canvas", "what is in the doc", "what is in the report",
        "what's in the canvas", "what's in the doc", "what's in the report",
        "summarize the canvas", "summarize the doc", "summarize the report",
        "summarise the canvas", "summarise the doc", "summarise the report",
        "summarize this canvas", "summarize this doc", "summarize this report",
        "summarize what is in", "summarise what is in",
        "give me an overview of the", "give me a summary of the",
        "tldr", "recap of the", "describe the canvas", "describe the doc",
        "explain the canvas", "explain the doc", "outline the canvas",
        "show me what is in", "show me the canvas", "show me what the canvas",
        "read the canvas", "read this canvas", "review the canvas",
        "概要", "梗概", "大意",
    ]

    def classify_intent(self, query: str, canvas_content: str | None) -> str:
        """Classify user intent.

        Returns one of:
            - 'modify_canvas': user wants to edit/rewrite/append the canvas doc
            - 'read_canvas'  : user wants to read/summarize the canvas doc
            - 'search_kb'    : user wants to query the knowledge base
        """
        if not canvas_content or not self.client:
            return "search_kb"

        query_lower = query.lower()
        is_edit = any(kw in query_lower for kw in self.CANVAS_EDIT_KEYWORDS)
        is_read = any(kw in query_lower for kw in self.CANVAS_READ_KEYWORDS)

        # Unambiguous edit signal: only edit keywords matched.
        if is_edit and not is_read:
            logger.info("Intent: modify_canvas (keyword match)")
            return "modify_canvas"

        # Unambiguous read signal: only read keywords matched.
        if is_read and not is_edit:
            logger.info("Intent: read_canvas (keyword match)")
            return "read_canvas"

        # If BOTH matched (e.g. "summarize the canvas and add a new section"),
        # the query is ambiguous - fall through to the LLM classifier below
        # rather than guessing. Same if neither matched.

        # Ask the LLM to classify, but show it a canvas preview so it can
        # decide based on both the query AND the document the user is editing.
        system_prompt = (
            "You are an intent classifier for a report-editing assistant. "
            "The user is working inside an app with a 'canvas' pane (a Markdown "
            "document they are viewing and editing) and a knowledge base of "
            "uploaded documents. Decide which of the following three intents "
            "the user's query expresses:\n"
            "1. 'modify_canvas' - the user wants to change, rewrite, edit, "
            "append, translate, format, or otherwise mutate the canvas document.\n"
            "2. 'read_canvas' - the user wants to read, summarize, or "
            "understand the canvas document as it is, without changing it.\n"
            "3. 'search_kb' - the user is asking a question about the knowledge "
            "base (uploaded files / reports) or making a general request "
            "unrelated to the canvas.\n\n"
            "Reply with EXACTLY one of those three tokens, with no extra text."
        )

        # Short preview (first/last 400 chars) so the LLM has enough context
        # to disambiguate. The keyword heuristics above already cover the
        # obvious cases; this LLM call resolves the genuinely ambiguous ones.
        preview = canvas_content.strip()
        if len(preview) > 800:
            preview = preview[:400] + "\n... [truncated] ...\n" + preview[-400:]
        user_msg = (
            f"User query: {query}\n\n"
            f"Current canvas preview (first/last 400 chars, {len(canvas_content)} total):\n"
            f"---BEGIN CANVAS---\n{preview}\n---END CANVAS---"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,
                max_tokens=20,
            )
            msg = response.choices[0].message
            # Some thinking models (mimo, DeepSeek R1) return None for content
            # and put the answer in reasoning_content instead.
            raw = msg.content
            if not raw:
                raw = getattr(msg, "reasoning_content", None)
            if raw:
                intent_text = raw.strip().lower()
                if "modify_canvas" in intent_text:
                    logger.info("Intent: modify_canvas (LLM)")
                    return "modify_canvas"
                if "read_canvas" in intent_text:
                    logger.info("Intent: read_canvas (LLM)")
                    return "read_canvas"
                if "search_kb" in intent_text:
                    logger.info("Intent: search_kb (LLM)")
                    return "search_kb"
        except Exception as e:
            logger.error(f"Intent classification failed: {e}")

        # Final fallback: if the canvas is non-empty and the query mentions
        # 'canvas' anywhere, lean toward modify_canvas rather than KB search.
        if "canvas" in query_lower:
            logger.info("Intent: modify_canvas (canvas-mention fallback)")
            return "modify_canvas"

        return "search_kb"


    def chat(self, query: str, context: str, system_prompt: str | None = None, thinking_intensity: str | None = None, intent: str = "search_kb") -> tuple[str, str | None]:
        """Send chat completion request.

        Args:
            query: User question.
            context: Retrieved context.
            system_prompt: Optional custom system prompt.
            thinking_intensity: Optional intensity ('low', 'medium', 'high').
            intent: User query intent ('search_kb' or 'modify_canvas').

        Returns:
            Generated response text and optional thinking text.
        """
        if not self.client:
            return "Error: API not configured. Please configure your API in Settings.", None

        ti = (thinking_intensity or "medium").lower()

        # Build dynamic CoT instructions based on thinking intensity for standard models
        cot_instruction = ""
        if ti == "low":
            cot_instruction = (
                "\nTHINKING INTENSITY: LOW.\n"
                "Provide direct, concise answers with minimal explanation. Skip background analysis."
            )
        elif ti == "high":
            cot_instruction = (
                "\nTHINKING INTENSITY: HIGH.\n"
                "You MUST perform a deep step-by-step chain-of-thought analysis before giving your final answer.\n"
                "Carefully dissect the query, analyze the provided context documents, plan the layout, "
                "and explain your reasoning clearly. Start your response with a detailed, structured "
                "analysis of your thoughts (e.g., in a 'Thinking Process:' or similar section) "
                "before giving the final output."
            )
        else: # medium
            cot_instruction = (
                "\nTHINKING INTENSITY: MEDIUM.\n"
                "Think step-by-step and show brief reasoning for complex parts of the answer."
            )

        if not system_prompt:
            if intent == "modify_canvas":
                # NOTE: The full canvas document is included in the user message
                # (the context field). The LLM CAN and MUST read it.
                system_prompt = (
                    "You are a document editor working inside a report-writing app. "
                    "The user is currently viewing and editing a Markdown document in a canvas pane. "
                    "You CAN read the current canvas document in full - it is provided "
                    "to you in the user message under the heading CURRENT CANVAS CONTENT. "
                    "Treat that block as the document the user wants you to change.\n\n"
                    "HOW TO USE THE CANVAS:\n"
                    "- Read the entire CURRENT CANVAS CONTENT block before making changes. "
                    "- Preserve the existing structure (headings, sections, tables, charts) "
                    "unless the user explicitly asks you to restructure it.\n"
                    "- Make the SMALLEST change that satisfies the request. If the user asks "
                    "to fix a typo, fix the typo. If they ask to translate, translate the whole "
                    "document but keep section order.\n"
                    "- When in doubt, return the full document unchanged plus a short chat note.\n\n"
                    "CRITICAL OUTPUT FORMAT - CANVAS BLOCK:\n"
                    "You MUST wrap the complete updated/new document inside a SINGLE fenced "
                    "code block whose info string is exactly markdown-canvas (three backticks "
                    "followed by the literal text markdown-canvas, a newline, the document, "
                    "a newline, then three closing backticks). The application looks for this "
                    "exact marker to write your output back to the canvas.\n"
                    "- Put a brief 1-3 sentence explanation OUTSIDE the block (in chat).\n"
                    "- Inside the block, output the FULL updated document - do not use diffs "
                    "or placeholders like ... rest unchanged.\n"
                    "- Use Markdown tables for tabular data.\n"
                    "FOR CHARTS: include an interactive Chart.js JSON configuration block "
                    "inside a NESTED fence using THREE tildes (~~~) with info string chart-config:\n"
                    "~~~chart-config\n"
                    "{\n"
                    "  \"type\": \"bar\",\n"
                    "  \"data\": {\n"
                    "    \"labels\": [\"Month1\", \"Month2\"],\n"
                    "    \"datasets\": [{\n"
                    "      \"label\": \"EFF\",\n"
                    "      \"data\": [0.61, 0.62],\n"
                    "      \"backgroundColor\": \"rgba(0, 188, 242, 0.2)\",\n"
                    "      \"borderColor\": \"#00bcf2\",\n"
                    "      \"borderWidth\": 1.5\n"
                    "    }]\n"
                    "  },\n"
                    "  \"options\": {\n"
                    "    \"responsive\": true,\n"
                    "    \"scales\": {\n"
                    "      \"y\": { \"min\": 0.5, \"max\": 0.7 }\n"
                    "    }\n"
                    "  }\n"
                    "}\n"
                    "~~~\n"
                    "Always use three tildes (~~~ ... ~~~) for ANY nested code or configuration "
                    "block inside the markdown-canvas block to avoid parsing conflicts."
                )
            elif intent == "read_canvas":
                # User wants to read/summarize the canvas without changing it.
                # No markdown-canvas block is required; respond directly in chat.
                system_prompt = (
                    "You are a helpful document analysis assistant. "
                    "The user is asking about the document they are currently editing in the canvas. "
                    "You CAN read the full canvas document - it is provided to you in the user message "
                    "under the heading CURRENT CANVAS CONTENT. "
                    "Answer their question about it (summarize, describe, explain, etc.) based on that "
                    "content. Do NOT rewrite or modify the canvas - they only want to read it. "
                    "Respond directly in chat with a clear answer."
                )
            else: # search_kb
                system_prompt = (
                    "You are a helpful document analysis assistant. "
                    "You CAN read the current canvas document - it is provided in the user message "
                    "under the heading CURRENT CANVAS CONTENT. The provided context below may "
                    "also include retrieved knowledge-base passages.\n\n"
                    "ANSWERING RULES:\n"
                    "- For pure knowledge-base questions, answer based on the retrieved context. "
                    "If the answer is not in the context, say so. Cite sources using [1], [2] format.\n"
                    "- For questions about the canvas (summarize it, what does it say, etc.), "
                    "answer based on the CURRENT CANVAS CONTENT block.\n\n"
                    "CANVAS-EDIT OVERRIDE:\n"
                    "If the user asks to extract, compile, or organize data into tables/charts, "
                    "or to modify, rewrite, edit, append, translate, or format the current canvas, "
                    "you MUST wrap the complete updated/new document inside a SINGLE fenced "
                    "code block marked ```markdown-canvas\\n...\\n```. The application looks for "
                    "that exact marker to write your output back to the canvas.\n"
                    "- Put a brief 1-3 sentence explanation OUTSIDE the block (in chat).\n"
                    "- Inside the block, output the FULL updated document - no diffs, no placeholders.\n"
                    "- Use Markdown tables for tabular data.\n"
                    "FOR CHARTS: include an interactive Chart.js JSON config inside a NESTED "
                    "fence with THREE tildes (~~~) and info string chart-config:\n"
                    "~~~chart-config\n"
                    "{\n"
                    "  \"type\": \"bar\",\n"
                    "  \"data\": {\n"
                    "    \"labels\": [\"Month1\", \"Month2\"],\n"
                    "    \"datasets\": [{\n"
                    "      \"label\": \"EFF\",\n"
                    "      \"data\": [0.61, 0.62],\n"
                    "      \"backgroundColor\": \"rgba(0, 188, 242, 0.2)\",\n"
                    "      \"borderColor\": \"#00bcf2\",\n"
                    "      \"borderWidth\": 1.5\n"
                    "    }]\n"
                    "  },\n"
                    "  \"options\": {\n"
                    "    \"responsive\": true,\n"
                    "    \"scales\": {\n"
                    "      \"y\": { \"min\": 0.5, \"max\": 0.7 }\n"
                    "    }\n"
                    "  }\n"
                    "}\n"
                    "~~~\n"
                    "Always use three tildes (~~~ ... ~~~) for any nested code or configuration "
                    "block inside the markdown-canvas block to prevent parsing conflicts."
                )

        system_prompt += cot_instruction

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ]

        kwargs = {}
        is_openai_reasoning = self.model and (
            "o1" in self.model.lower() or 
            "o3-mini" in self.model.lower()
        )

        if is_openai_reasoning:
            kwargs["reasoning_effort"] = ti
            kwargs["max_completion_tokens"] = self.max_tokens
        else:
            kwargs["temperature"] = self.temperature
            kwargs["max_tokens"] = self.max_tokens

        MAX_CONTINUATIONS = 3
        continuations = 0
        
        full_content = ""
        full_thinking = ""
        
        while True:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    **kwargs
                )
                message_obj = response.choices[0].message
                content = message_obj.content or ""
                finish_reason = response.choices[0].finish_reason
                
                # Extract reasoning/thinking content
                thinking = None
                if hasattr(message_obj, "reasoning_content") and message_obj.reasoning_content:
                    thinking = message_obj.reasoning_content
                elif isinstance(message_obj, dict) and message_obj.get("reasoning_content"):
                    thinking = message_obj["reasoning_content"]
                elif hasattr(message_obj, "model_extra") and message_obj.model_extra and "reasoning_content" in message_obj.model_extra:
                    thinking = message_obj.model_extra["reasoning_content"]
                    
                # Also extract from <think> tags in the main content if present
                import re
                think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
                if think_match:
                    extracted_think = think_match.group(1).strip()
                    if thinking:
                        thinking = thinking + "\n" + extracted_think
                    else:
                        thinking = extracted_think
                    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                    
                if continuations > 0 and "```markdown-canvas" in content:
                    logger.warning("Model restarted the document instead of continuing. Aborting auto-continuation.")
                    # Revert full_content to before this chunk
                    break
                    
                full_content += content
                if thinking:
                    if full_thinking:
                        full_thinking += "\n" + thinking
                    else:
                        full_thinking = thinking
                        
                if finish_reason in ("length", "max_tokens") and continuations < MAX_CONTINUATIONS and (content or full_thinking):
                    logger.info(f"Response truncated (finish_reason={finish_reason}). Auto-continuing ({continuations+1}/{MAX_CONTINUATIONS})...")
                    assistant_text = ""
                    if full_thinking:
                        assistant_text += f"<think>\n{full_thinking}\n</think>\n"
                    assistant_text += full_content
                    
                    messages.append({"role": "assistant", "content": assistant_text})
                    messages.append({"role": "user", "content": "Please continue exactly from where you left off. Do not repeat anything you already said. Do not add any conversational filler. Just continue the text or code block seamlessly."})
                    
                    continuations += 1
                    continue
                else:
                    if not full_content and not full_thinking:
                        logger.warning(f"LLM returned empty content. finish_reason={finish_reason}, usage={response.usage}")
                    break
                    
            except Exception as e:
                logger.error(f"LLM error: {e}")
                if not full_content and not full_thinking:
                    return f"Error: {e}", None
                break
                
        return full_content, full_thinking

    def stream_chat(self, query: str, context: str, system_prompt: str | None = None, thinking_intensity: str | None = None, intent: str = "search_kb") -> Generator[str, None, None]:
        """Stream chat completion.

        Args:
            query: User question.
            context: Retrieved context.
            system_prompt: Optional custom system prompt.
            thinking_intensity: Optional intensity ('low', 'medium', 'high').
            intent: User query intent ('search_kb' or 'modify_canvas').

        Yields:
            Token strings.
        """
        if not self.client:
            yield "Error: API not configured. Please configure your API in Settings."
            return

        ti = (thinking_intensity or "medium").lower()

        # Build dynamic CoT instructions based on thinking intensity for standard models
        cot_instruction = ""
        if ti == "low":
            cot_instruction = (
                "\nTHINKING INTENSITY: LOW.\n"
                "Provide direct, concise answers with minimal explanation. Skip background analysis."
            )
        elif ti == "high":
            cot_instruction = (
                "\nTHINKING INTENSITY: HIGH.\n"
                "You MUST perform a deep step-by-step chain-of-thought analysis before giving your final answer.\n"
                "Carefully dissect the query, analyze the provided context documents, plan the layout, "
                "and explain your reasoning clearly. Start your response with a detailed, structured "
                "analysis of your thoughts (e.g., in a 'Thinking Process:' or similar section) "
                "before giving the final output."
            )
        else: # medium
            cot_instruction = (
                "\nTHINKING INTENSITY: MEDIUM.\n"
                "Think step-by-step and show brief reasoning for complex parts of the answer."
            )

        if not system_prompt:
            if intent == "modify_canvas":
                # NOTE: The full canvas document is included in the user message
                # (the context field). The LLM CAN and MUST read it.
                system_prompt = (
                    "You are a document editor working inside a report-writing app. "
                    "The user is currently viewing and editing a Markdown document in a canvas pane. "
                    "You CAN read the current canvas document in full - it is provided "
                    "to you in the user message under the heading CURRENT CANVAS CONTENT. "
                    "Treat that block as the document the user wants you to change.\n\n"
                    "You MUST wrap the complete updated/new document inside a SINGLE fenced "
                    "code block whose info string is exactly markdown-canvas (three backticks "
                    "followed by the literal text markdown-canvas, a newline, the document, "
                    "a newline, then three closing backticks). The application looks for this "
                    "exact marker to write your output back to the canvas.\n"
                    "- Put a brief 1-3 sentence explanation OUTSIDE the block.\n"
                    "- Inside the block, output the FULL updated document - no diffs/placeholders.\n"
                    "- Use Markdown tables for tabular data."
                )
            elif intent == "read_canvas":
                system_prompt = (
                    "You are a helpful document analysis assistant. "
                    "The user is asking about the document they are currently editing in the canvas. "
                    "You CAN read the full canvas document - it is provided to you in the user message "
                    "under the heading CURRENT CANVAS CONTENT. "
                    "Answer their question (summarize, describe, explain) based on that content. "
                    "Do NOT rewrite or modify the canvas - they only want to read it. "
                    "Respond directly in chat."
                )
            else: # search_kb
                system_prompt = (
                    "You are a helpful document analysis assistant. "
                    "You CAN read the current canvas document - it is provided in the user message "
                    "under the heading CURRENT CANVAS CONTENT.\n\n"
                    "For pure knowledge-base questions, answer based on the retrieved context. "
                    "If the answer is not in the context, say so. Cite sources using [1], [2] format.\n\n"
                    "If the user asks to modify, rewrite, edit, append, translate, or format the "
                    "current canvas, you MUST wrap the complete updated/new document inside a "
                    "SINGLE fenced code block marked ```markdown-canvas\\n...\\n```."
                )

        system_prompt += cot_instruction

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ]

        kwargs = {}
        is_openai_reasoning = self.model and (
            "o1" in self.model.lower() or 
            "o3-mini" in self.model.lower()
        )

        if is_openai_reasoning:
            kwargs["reasoning_effort"] = ti
            kwargs["max_completion_tokens"] = self.max_tokens
        else:
            kwargs["temperature"] = self.temperature
            kwargs["max_tokens"] = self.max_tokens

        MAX_CONTINUATIONS = 3
        continuations = 0
        
        while True:
            try:
                stream = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    **kwargs
                )
                
                accumulated_content = ""
                accumulated_thinking = ""
                finish_reason = None
                in_thinking = False
                
                for chunk in stream:
                    if not chunk.choices:
                        continue
                        
                    delta = chunk.choices[0].delta
                    if hasattr(chunk.choices[0], "finish_reason") and chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason
                    
                    # Yield reasoning_content if present (DeepSeek-R1 style)
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        if not in_thinking:
                            yield "<think>\n"
                            in_thinking = True
                        accumulated_thinking += delta.reasoning_content
                        yield delta.reasoning_content
                        continue
                        
                    text = delta.content
                    if text:
                        if continuations > 0 and "```markdown" in text:
                            # We can't easily retract streamed tokens, but we can stop the stream
                            logger.warning("Model restarted the document instead of continuing in stream. Aborting auto-continuation.")
                            finish_reason = "stop" # Force stop continuation
                            
                        if in_thinking:
                            yield "\n</think>\n"
                            in_thinking = False
                        accumulated_content += text
                        yield text
                        
                if in_thinking:
                    yield "\n</think>\n"
                    
                if finish_reason in ("length", "max_tokens") and continuations < MAX_CONTINUATIONS and (accumulated_content or accumulated_thinking):
                    logger.info(f"Stream truncated (finish_reason={finish_reason}). Auto-continuing ({continuations+1}/{MAX_CONTINUATIONS})...")
                    assistant_text = ""
                    if accumulated_thinking:
                        assistant_text += f"<think>\n{accumulated_thinking}\n</think>\n"
                    assistant_text += accumulated_content
                    
                    messages.append({"role": "assistant", "content": assistant_text})
                    messages.append({"role": "user", "content": "Please continue exactly from where you left off. Do not repeat anything you already said. Do not add any conversational filler. Just continue the text or code block seamlessly."})
                    
                    continuations += 1
                    continue
                else:
                    break
                    
            except Exception as e:
                logger.error(f"LLM streaming error: {e}")
                yield f"Error: {e}"
                break
