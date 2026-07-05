"""LLM Gateway for Windows RAG System."""
import os
from typing import List, Dict, Any, Generator
from openai import OpenAI

from utils.logger import setup_logger
from utils.file_io import read_json
from llm.model_caps import get_capabilities
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

        # If the default_model is an embedding/rerank model it can't be used
        # for chat - scan enabled providers for the first usable chat model.
        _NON_CHAT = ("embed", "rerank", "rank", "bge", "gte", "e5-")
        if any(kw in self.model.lower() for kw in _NON_CHAT):
            providers = self.config.get("providers", {})
            for pname, pconf in providers.items():
                if not pconf.get("enabled", True):
                    continue
                models_raw = pconf.get("models", "")
                model_list = models_raw if isinstance(models_raw, list) else models_raw.split()
                for m in model_list:
                    if not any(kw in m.lower() for kw in _NON_CHAT):
                        self.provider = pname
                        self.model = m
                        logger.info(f"Auto-selected chat model: {pname}/{m}")
                        break
                else:
                    continue
                break
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

    def _provider_overrides(self):
        """Return per-model capability overrides for the current provider, if any.

        Reads providers[<name>].model_overrides from the config so users can
        manually pin reasoning/max_output for a model that the registry gets
        wrong. Returns None when no overrides are configured.
        """
        if not self.provider:
            return None
        pconf = self.config.get("providers", {}).get(self.provider, {})
        ov = pconf.get("model_overrides")
        return ov if isinstance(ov, dict) and ov else None

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

    # Sub-intent keyword lists for modify_canvas routing.
    # These steer the decision between targeted surgical edits, section-scoped
    # rewrites, and full-document transformations (translate / restructure).
    SURGICAL_EDIT_KEYWORDS = [
        # Chinese: small targeted changes
        "改成", "替换为", "改为", "修改", "修正", "改正", "插入", "删除",
        "添加一行", "去掉", "改掉", "换掉", "更新",
        # English: surgical indicators (must be specific to avoid false match)
        "fix the", "change the", "replace the", "update the",
        "insert ", "remove ", "delete ", "add a ", "fix ",
        "append a", "prepend a",
    ]
    WHOLE_TRANSFORM_KEYWORDS = [
        # Chinese: full-document transformations
        "翻译", "全文翻译", "整篇翻译", "整篇", "重写", "重构",
        "全面修改", "整体修改", "全部改写", "全文改写", "格式化全部",
        # English: whole-doc indicators
        "translate the whole", "translate this document",
        "rewrite the entire", "rewrite this document",
        "restructure the", "reformat all", "convert all",
        "translate to", "rewrite the whole",
    ]

    def classify_intent(self, query: str, canvas_content: str | None) -> str:
        """Classify user intent.

        Returns one of:
            - 'modify_canvas': user wants to edit/rewrite/append the canvas doc
            - 'read_canvas'  : user wants to read/summarize the canvas doc
            - 'search_kb'    : user wants to query the knowledge base
        """
        if not self.client:
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
        canvas_str = canvas_content or ""
        preview = canvas_str.strip()
        if len(preview) > 800:
            preview = preview[:400] + "\n... [truncated] ...\n" + preview[-400:]
        user_msg = (
            f"User query: {query}\n\n"
            f"Current canvas preview (first/last 400 chars, {len(canvas_str)} total):\n"
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

    def _scan_sub_intent(self, query: str) -> str | None:
        """Quick rule-based sub-intent scan. Returns one of the three sub-intent
        strings or None if rules are inconclusive."""
        import re as _re
        q = query.lower()

        # 1. whole_transform keywords
        for kw in self.WHOLE_TRANSFORM_KEYWORDS:
            if kw in q:
                return "whole_transform"

        # 2. section-level rewrite: query mentions a section number + section verb
        sec_pat = _re.search(r'\b§?\s*[1-9]\b|第[一二三四五六七八九1-9]章|section\s+\d', q, _re.IGNORECASE)
        sec_verb = any(v in q for v in ["重写", "润色", "改写", "rewrite", "polish", "更新该节", "更新本节", "rewrite section", "rewrite this section"])
        if sec_pat and sec_verb:
            return "section_rewrite"

        # 3. surgical edit keywords
        for kw in self.SURGICAL_EDIT_KEYWORDS:
            if kw in q:
                return "surgical_edit"

        return None

    def sub_classify_modify_intent(self, query: str, canvas_content: str) -> str:
        """Refine a 'modify_canvas' intent into one of three sub-intents:

        - 'surgical_edit'   small targeted change (fix a value, add a row, …)
        - 'section_rewrite' rewrite a single identified section
        - 'whole_transform' full-document transformation (translate, restructure, …)
        """
        if not self.client:
            logger.info("sub-intent: whole_transform (no client)")
            return "whole_transform"

        # Rule layer
        ruled = self._scan_sub_intent(query)
        if ruled:
            logger.info(f"sub-intent: {ruled} (keyword match)")
            return ruled

        # LLM fallback — same calling pattern as classify_intent
        import re as _re
        sp = (
            "You are a routing classifier for a document-editing app. "
            "Classify the user's query into EXACTLY one of three tokens:\n"
            "1. 'surgical_edit' — the user wants to change a specific value, "
            "row, word, or line (e.g. fix a typo, change May's number, add a column).\n"
            "2. 'section_rewrite' — the user wants to rewrite, polish, or "
            "reformat a single named/referenced section.\n"
            "3. 'whole_transform' — the user wants a full-document change: "
            "translate, restructure, rewrite everything, convert all.\n\n"
            "Reply with EXACTLY one token: surgical_edit / section_rewrite / whole_transform."
        )
        msgs = [{"role": "system", "content": sp}, {"role": "user", "content": f"Query: {query}"}]
        try:
            resp = self.client.chat.completions.create(
                model=self.model, messages=msgs,
                temperature=0.0, max_tokens=20,
            )
            raw = resp.choices[0].message.content
            if not raw:
                raw = getattr(resp.choices[0].message, "reasoning_content", None)
            if raw:
                txt = raw.strip().lower()
                for t in ("surgical_edit", "section_rewrite", "whole_transform"):
                    if t in txt:
                        logger.info(f"sub-intent: {t} (LLM)")
                        return t
        except Exception as e:
            logger.error(f"sub-intent LLM classify failed: {e}")

        # Safe default
        logger.info("sub-intent: whole_transform (fallback)")
        return "whole_transform"


    def chat(self, query: str, context: str, history: List[Dict[str, str]] = None, system_prompt: str | None = None, thinking_intensity: str | None = None, intent: str = "search_kb") -> tuple[str, str | None]:
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

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for h in history:
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"})

        kwargs = {}
        caps = get_capabilities(self.model, self._provider_overrides())
        is_reasoning = caps["reasoning"]
        # Never request more output tokens than the model supports.
        effective_max = min(self.max_tokens, caps["max_output"])

        if is_reasoning:
            kwargs["reasoning_effort"] = ti
            kwargs["max_completion_tokens"] = effective_max
        else:
            kwargs["temperature"] = self.temperature
            kwargs["max_tokens"] = effective_max

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
                    
                # During continuation, strip instruction/reasoning leak phrases
                # that the model may emit into the document body.
                if continuations > 0 and content:
                    _leak_patterns = [
                        r"The user wants me to continue.*?(?:\n|$)",
                        r"Looking at my previous response.*?(?:\n|$)",
                        r"Let me continue.*?(?:\n|$)",
                        r"I need to continue.*?(?:\n|$)",
                        r"continue from where.*?(?:\n|$)",
                        r"where I left off.*?(?:\n|$)",
                        r"The last text was:.*?(?:\n```|\n|$)",
                        r"I was in the middle of.*?(?:\n|$)",
                        r"Let me continue exactly.*?(?:\n|$)",
                        r"resume writing.*?(?:\n|$)",
                        r"continuing inside the SAME.*?(?:\n|$)",
                    ]
                    for _pat in _leak_patterns:
                        content = re.sub(_pat, "", content, flags=re.IGNORECASE).strip("\n")
                
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
                    # Temporarily close an unclosed markdown-canvas fence so the model sees a
                    # well-formed assistant turn and does not leak continuation instructions.
                    if "```markdown-canvas" in assistant_text:
                        fence_count = assistant_text.count("```")
                        if fence_count % 2 != 0:
                            assistant_text += "\n```"
                    
                    messages.append({"role": "assistant", "content": assistant_text})
                    messages.append({"role": "user", "content": 'CONTINUE the document. The previous code block was temporarily closed for transmission only. Resume writing EXACTLY from the last character you produced, continuing inside the SAME markdown-canvas block. Output ONLY the next characters of the document - no explanations, no apologies, no restating instructions, no re-opening of the fence, no conversational text.'})
                    
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

    def stream_section(self, full_document, section_index, total_sections, section_header, section_body, query, thinking_intensity=None):
        """Stream-generate ONE section of a document rewrite.

        Used by the segmented-rewrite pipeline (scheme C) to avoid the
        continuation-leak problem entirely: each section is produced in a
        single request that fits well within the model max_output, so no
        continuation is ever needed.

        Args:
            full_document: The complete original document (for context).
            section_index: 0-based index of this section.
            total_sections: Total number of sections.
            section_header: The heading line of this section.
            section_body: The full text of this section (header + body).
            query: The user instruction (e.g. translate to English).
            thinking_intensity: low/medium/high.

        Yields:
            Token strings (the rewritten section body, NO fences).
        """
        if not self.client:
            yield "Error: API not configured."
            return

        ti = (thinking_intensity or "medium").lower()
        caps = get_capabilities(self.model, self._provider_overrides())
        effective_max = min(self.max_tokens, caps["max_output"])

        system_prompt = (
            "You are a document editor. The user wants to apply an edit to a Markdown "
            "document, ONE section at a time. You are given the FULL original document "
            "for context, but you must ONLY output the rewritten version of the "
            "specified section.\n\n"
            f"User instruction: {query}\n\n"
            f"This is section {section_index + 1} of {total_sections}. "
            "Output ONLY the rewritten version of this section, starting with its "
            "heading. Do NOT include any other section. Do NOT wrap the output in "
            "code fences. Do NOT add explanations or conversational text. Just the "
            "section content.\n\n"
            "Preserve all data, numbers, and chart-config JSON exactly. Translate "
            "only natural-language text. Keep Markdown structure intact.\n\n"
            "FENCE PRESERVATION: Keep the EXACT fence markers from the original section. "
            "If the original uses ~~~chart-config, output ~~~chart-config. If it uses "
            "backticks, use backticks. Never change fence types or add extra fences."
        )

        user_msg = (
            "--- FULL ORIGINAL DOCUMENT (for context only, do NOT reproduce it) ---\n"
            f"{full_document}\n"
            "--- END FULL DOCUMENT ---\n\n"
            "--- SECTION TO REWRITE (output the rewritten version of ONLY this section) ---\n"
            f"{section_body}\n"
            "--- END SECTION ---"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]

        kwargs = {}
        if caps["reasoning"]:
            kwargs["reasoning_effort"] = ti
            kwargs["max_completion_tokens"] = effective_max
        else:
            kwargs["temperature"] = self.temperature
            kwargs["max_tokens"] = effective_max

        MAX_SECTION_CONT = 3
        section_cont = 0
        try:
          while True:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                **kwargs
            )
            in_thinking = False
            finish_reason = None
            section_acc = ""
            for chunk in stream:
                if not chunk.choices:
                    continue
                if hasattr(chunk.choices[0], "finish_reason") and chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
                delta = chunk.choices[0].delta
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    if not in_thinking:
                        yield "[THINK]"
                        in_thinking = True
                    yield delta.reasoning_content
                    continue
                text = delta.content
                if text:
                    if in_thinking:
                        yield "[/THINK]"
                        in_thinking = False
                    section_acc += text
                    yield text
            if in_thinking:
                yield "[/THINK]"
            if finish_reason in ("length", "max_tokens") and section_cont < MAX_SECTION_CONT and section_acc:
                section_cont += 1
                logger.info(f"stream_section truncated, continuing section ({section_cont}/{MAX_SECTION_CONT})")
                fence3_count = section_acc.count("```")
                tilde3_count = section_acc.count("~~~")
                closer = ""
                if fence3_count % 2 != 0:
                    closer += "\n```"
                if tilde3_count % 2 != 0:
                    closer += "\n~~~"
                messages.append({"role": "assistant", "content": section_acc + closer})
                messages.append({"role": "user", "content": "Continue this section exactly from where it stopped. The code block was temporarily closed for transmission only. Output ONLY the remaining content of this section - no other sections, no explanations, no re-opening of fences. Just the next characters."})
                continue
            break
        except Exception as e:
            logger.error(f"stream_section error: {e}")
            yield f"Error: {e}"

    def stream_chat(self, query: str, context: str, history: List[Dict[str, str]] = None, system_prompt: str | None = None, thinking_intensity: str | None = None, intent: str = "search_kb") -> Generator[str, None, None]:
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

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for h in history:
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"})

        kwargs = {}
        caps = get_capabilities(self.model, self._provider_overrides())
        is_reasoning = caps["reasoning"]
        # Never request more output tokens than the model supports.
        effective_max = min(self.max_tokens, caps["max_output"])

        if is_reasoning:
            kwargs["reasoning_effort"] = ti
            kwargs["max_completion_tokens"] = effective_max
        else:
            kwargs["temperature"] = self.temperature
            kwargs["max_tokens"] = effective_max

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
                        # During continuation, models may leak the continuation
                        # instruction / their own reasoning about where they left off
                        # into the document body. Strip these leak phrases so they
                        # do not corrupt the canvas output.
                        if continuations > 0:
                            import re as _re
                            _leak_patterns = [
                                r"The user wants me to continue.*?(?:\n|$)",
                                r"Looking at my previous response.*?(?:\n|$)",
                                r"Let me continue.*?(?:\n|$)",
                                r"I need to continue.*?(?:\n|$)",
                                r"continue from where.*?(?:\n|$)",
                                r"where I left off.*?(?:\n|$)",
                                r"The last text was:.*?(?:\n```|\n|$)",
                                r"I was in the middle of.*?(?:\n|$)",
                                r"Let me continue exactly.*?(?:\n|$)",
                                r"resume writing.*?(?:\n|$)",
                                r"continuing inside the SAME.*?(?:\n|$)",
                            ]
                            for _pat in _leak_patterns:
                                text = _re.sub(_pat, "", text, flags=_re.IGNORECASE).strip("\n")
                            if not text:
                                continue
                        # During continuation, detect if model restarts the markdown-canvas block.
                        # Skip the repeated opening fence rather than aborting the whole continuation.
                        if continuations > 0 and "```markdown-canvas" in text:
                            logger.warning("Model restarted markdown-canvas in stream. Attempting to skip repeated fence.")
                            parts = text.split("```markdown-canvas")
                            if len(parts) > 1:
                                text = "```markdown-canvas".join(parts[1:])
                                if text.startswith("\r\n"):
                                    text = text[2:]
                                elif text.startswith("\n"):
                                    text = text[1:]
                                # Deduplicate overlap with accumulated_content
                                if accumulated_content and text:
                                    overlap = 0
                                    max_ov = min(len(accumulated_content), len(text), 200)
                                    for i in range(max_ov, 0, -1):
                                        if accumulated_content.endswith(text[:i]):
                                            overlap = i
                                            break
                                    if overlap > 0:
                                        text = text[overlap:]
                                if not text:
                                    continue
                            
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
                    # Temporarily close an unclosed markdown-canvas fence so the model sees a
                    # well-formed assistant turn. Otherwise it treats the continuation prompt as
                    # part of the document body and leaks instruction text into the output.
                    if "```markdown-canvas" in assistant_text:
                        fence_count = assistant_text.count("```")
                        if fence_count % 2 != 0:
                            assistant_text += "\n```"
                    
                    messages.append({"role": "assistant", "content": assistant_text})
                    messages.append({"role": "user", "content": 'CONTINUE the document. The previous code block was temporarily closed for transmission only. Resume writing EXACTLY from the last character you produced, continuing inside the SAME markdown-canvas block. Output ONLY the next characters of the document - no explanations, no apologies, no restating instructions, no re-opening of the fence, no conversational text.'})
                    
                    continuations += 1
                    continue
                else:
                    break
                    
            except Exception as e:
                logger.error(f"LLM streaming error: {e}")
                yield f"Error: {e}"
                break
