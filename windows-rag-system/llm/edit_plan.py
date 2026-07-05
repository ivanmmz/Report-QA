"""SEARCH/REPLACE block parser, applier, and validation for surgical canvas edits."""
import re
import json
from dataclasses import dataclass, field
from typing import List, Tuple

from utils.logger import setup_logger
logger = setup_logger("edit_plan")


# ── Data types ──────────────────────────────────────────────────────────────

@dataclass
class EditOp:
    kind: str            # "replace" | "insert_before" | "insert_after"
    search: str
    replacement: str
    source_index: int    # 0-based block order in the LLM output


@dataclass
class ApplyResult:
    document: str
    applied: int
    failed_ops: List[Tuple[int, str]] = field(default_factory=list)


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ExecuteResult:
    ok: bool
    document: str
    sub_intent: str             # caller-set, not changed here
    applied: int
    failed_ops: List[Tuple[int, str]]
    validation: ValidationResult
    fallback_reason: str | None


# ── Parser ───────────────────────────────────────────────────────────────────

_BLOCK_PAT = re.compile(
    r"<<<< SEARCH\n"
    r"(.*?)"
    r"\n==== (REPLACE|INSERT_BEFORE|INSERT_AFTER)\n"
    r"(.*?)"
    r"\n>>>> (REPLACE|INSERT_BEFORE|INSERT_AFTER)",
    re.DOTALL,
)


def parse_plan(text: str) -> list[EditOp]:
    """Parse LLM output into a list of EditOp.

    Expected block format (one or more per plan):

        <<<< SEARCH
        <exact original text>
        ==== REPLACE
        <replacement text>
        >>>> REPLACE

    Also INSERT_BEFORE and INSERT_AFTER variants.  Each occurrence of SEARCH
    must be a verbatim substring of the document; the applier uses ``str.find``
    so casing and whitespace are significant.
    """
    ops: list[EditOp] = []
    for idx, m in enumerate(_BLOCK_PAT.finditer(text)):
        kind_open  = m.group(2)          # e.g. "REPLACE"
        kind_close = m.group(4)          # e.g. "REPLACE"
        if kind_open != kind_close:
            logger.warning(
                "block %d: opening kind %r != closing kind %r — skipping",
                idx, kind_open, kind_close,
            )
            continue

        search = m.group(1)
        repl   = m.group(3)

        # Strip exactly one leading / trailing newline (LLMs often add one)
        if search.startswith("\n"):
            search = search[1:]
        if search.endswith("\n"):
            search = search[:-1]
        if repl.startswith("\n"):
            repl = repl[1:]
        if repl.endswith("\n"):
            repl = repl[:-1]

        # Map delimiter kind to our internal name
        kind_map = {"REPLACE": "replace", "INSERT_BEFORE": "insert_before", "INSERT_AFTER": "insert_after"}
        ops.append(EditOp(kind=kind_map[kind_open], search=search, replacement=repl, source_index=idx))

    if not ops:
        logger.info("parse_plan: 0 ops parsed from %d chars", len(text))
    else:
        logger.info("parse_plan: %d ops parsed", len(ops))
    return ops


# ── Applier ───────────────────────────────────────────────────────────────────

def apply_plan(document: str, ops: list[EditOp]) -> ApplyResult:
    """Apply EditOps in order to *document*.

    Each op operates on the result of the **previous** op, so later ops see
    the already-edited document.  On failure the op is recorded in
    ``failed_ops`` and the next op continues.
    """
    doc = document
    applied = 0
    failed: list[tuple[int, str]] = []

    for op in ops:
        try:
            if not op.search:
                failed.append((op.source_index, "empty search"))
                continue

            if op.kind == "replace":
                idx = doc.find(op.search)
                if idx == -1:
                    failed.append((op.source_index, "search not found"))
                    continue
                doc = doc[:idx] + op.replacement + doc[idx + len(op.search):]
                applied += 1

            elif op.kind == "insert_before":
                cnt = doc.count(op.search)
                if cnt == 0:
                    failed.append((op.source_index, "anchor not found"))
                    continue
                if cnt > 1:
                    failed.append((op.source_index, f"non-unique anchor ({cnt} matches)"))
                    continue
                idx = doc.find(op.search)
                doc = doc[:idx] + op.replacement + doc[idx:]
                applied += 1

            elif op.kind == "insert_after":
                cnt = doc.count(op.search)
                if cnt == 0:
                    failed.append((op.source_index, "anchor not found"))
                    continue
                if cnt > 1:
                    failed.append((op.source_index, f"non-unique anchor ({cnt} matches)"))
                    continue
                idx = doc.find(op.search) + len(op.search)
                doc = doc[:idx] + op.replacement + doc[idx:]
                applied += 1

            else:
                failed.append((op.source_index, f"unknown kind {op.kind!r}"))
        except Exception as e:
            failed.append((op.source_index, f"exception: {e}"))

    return ApplyResult(document=doc, applied=applied, failed_ops=failed)


# ── Validator ─────────────────────────────────────────────────────────────────

def _iter_sections(text: str) -> int:
    """Count top-level ``## `` sections (same definition as query_rag.py)."""
    count = 0
    for line in text.split("\n"):
        if line.startswith("## "):
            count += 1
    return count


def _table_row_count(text: str) -> list[tuple[str, int]]:
    """Return list of (header_snippet, row_count) for each markdown table."""
    tables: list[tuple[str, int]] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        # Find a table header row (starts with |---| )
        if line.startswith("|") and "---" in line:
            # header is the line before the separator
            header = lines[i - 1] if i > 0 else ""
            hdr_snippet = header[:30] if header else "(no header)"
            sep = line
            # Count data rows after separator
            row_cnt = 0
            j = i + 1
            while j < len(lines) and lines[j].startswith("|") and "---" not in lines[j]:
                row_cnt += 1
                j += 1
            tables.append((hdr_snippet, row_cnt))
            i = j
        else:
            i += 1
    return tables


def _find_chart_blocks(text: str) -> list[str]:
    """Return list of JSON strings inside ~~~chart-config ... ~~~ blocks."""
    blocks: list[str] = []
    pattern = re.compile(r"~~~chart-config\n(.*?)\n~~~", re.DOTALL)
    for m in pattern.finditer(text):
        blocks.append(m.group(1))
    return blocks


def validate(original: str, result: str) -> ValidationResult:
    """Compare structural integrity of *result* against *original*."""
    errors: list[str] = []
    warnings: list[str] = []

    # Section count
    orig_secs = _iter_sections(original)
    res_secs  = _iter_sections(result)
    if orig_secs != res_secs:
        errors.append(
            f"section count mismatch: original={orig_secs} result={res_secs}"
        )

    # Table rows
    try:
        orig_tables = _table_row_count(original)
        res_tables  = _table_row_count(result)
        for o_hdr, o_cnt in orig_tables:
            found = False
            for r_hdr, r_cnt in res_tables:
                if r_hdr == o_hdr:
                    found = True
                    if o_cnt != r_cnt:
                        errors.append(
                            f"table row count mismatch: original={o_cnt} result={r_cnt} "
                            f"for table starting {o_hdr!r}"
                        )
                    break
            if not found:
                errors.append(f"table missing (header {o_hdr!r})")
    except Exception as e:
        warnings.append(f"table validation exception: {e}")

    # chart-config JSON integrity
    try:
        orig_charts = _find_chart_blocks(original)
        res_charts  = _find_chart_blocks(result)
        for ci, oc in enumerate(orig_charts):
            # Try parsing original (to know baseline)
            try:
                json.loads(oc)
            except json.JSONDecodeError:
                continue  # original was already invalid — skip this block
            # Check corresponding result block
            if ci >= len(res_charts):
                errors.append(f"chart-config block #{ci} missing")
            else:
                rc = res_charts[ci]
                try:
                    json.loads(rc)
                except json.JSONDecodeError:
                    errors.append(f"chart-config JSON invalid at block #{ci}")
    except Exception as e:
        warnings.append(f"chart-config validation exception: {e}")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


# ── Orchestrator ──────────────────────────────────────────────────────────────

def execute_plan(document: str, plan_text: str, sub_intent: str = "") -> ExecuteResult:
    """Parse *plan_text*, apply to *document*, validate, and return outcome."""
    ops = parse_plan(plan_text)
    if not ops:
        return ExecuteResult(
            ok=False, document=document, sub_intent=sub_intent,
            applied=0, failed_ops=[], validation=ValidationResult(False, [], ["no ops parsed"]),
            fallback_reason="empty_plan",
        )

    ar = apply_plan(document, ops)
    vr = validate(document, ar.document)

    ok = vr.ok and not ar.failed_ops and ar.applied > 0
    if not ok:
        reasons: list[str] = []
        if ar.applied == 0:
            reasons.append("no ops applied")
        if ar.failed_ops:
            reasons.append("ops failed: " + "; ".join(reason for _, reason in ar.failed_ops[:3]))
        if not vr.ok:
            reasons.append("validation: " + "; ".join(vr.errors[:3]))
        fallback_reason = "; ".join(reasons) if reasons else "unknown"
    else:
        fallback_reason = None

    return ExecuteResult(
        ok=ok, document=ar.document, sub_intent=sub_intent,
        applied=ar.applied, failed_ops=ar.failed_ops,
        validation=vr, fallback_reason=fallback_reason,
    )
