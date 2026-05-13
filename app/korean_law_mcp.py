from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import shlex
import shutil
from dataclasses import dataclass
from typing import Any

from app.runtime_settings import get_law_oc


logger = logging.getLogger(__name__)

MCP_COMMAND_ENV = "KOREAN_LAW_MCP_COMMAND"
MCP_USE_NPX_ENV = "KOREAN_LAW_MCP_USE_NPX"
MCP_TIMEOUT_ENV = "KOREAN_LAW_MCP_TIMEOUT"
MCP_DOMAINS_ENV = "KOREAN_LAW_MCP_DOMAINS"

DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_RESULTS_LIMIT = 10
DEFAULT_DECISION_DOMAINS = ("interpretation", "tax_tribunal", "admin_appeal")

SOURCE_LABELS = {
    "admin_rule": "행정규칙",
    "ordinance": "자치법규",
    "treaty": "조약",
    "interpretation": "해석례",
    "tax_tribunal": "조세심판례",
    "customs": "관세해석",
    "nts": "국세청해석",
    "constitutional": "헌재결정",
    "admin_appeal": "행정심판례",
}

DIRECT_SEARCH_TOOLS = (
    ("search_admin_rule", "admin_rule"),
    ("search_ordinance", "ordinance"),
    ("search_treaties", "treaty"),
)

RESULT_START_RE = re.compile(r"^(?:(?P<number>\d+)\.\s+|\[(?P<bracket_id>[^\]]+)\]\s*)(?P<title>.+?)\s*$")
META_LINE_RE = re.compile(r"^-?\s*([^:：]+)[:：]\s*(.+?)\s*$")
NO_RESULT_MARKERS = ("검색 결과가 없습니다", "검색된 결과가 없습니다", "결과가 없습니다", "NOT_FOUND")


@dataclass(frozen=True)
class McpToolResponse:
    text: str
    is_error: bool = False


class KoreanLawMcpError(Exception):
    """Raised when the optional korean-law-mcp adapter cannot complete a call."""


def _normalize_max_results(max_results: int) -> int:
    return max(1, min(int(max_results or 5), MAX_RESULTS_LIMIT))


def _timeout_seconds() -> float:
    raw = os.getenv(MCP_TIMEOUT_ENV, "").strip()
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        return max(3.0, min(float(raw), 60.0))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _parse_command(value: str) -> list[str]:
    return shlex.split(value, posix=os.name != "nt")


def _resolve_command() -> list[str]:
    configured = os.getenv(MCP_COMMAND_ENV, "").strip()
    if configured:
        return _parse_command(configured)

    for candidate in ("korean-law-mcp.cmd", "korean-law-mcp") if os.name == "nt" else ("korean-law-mcp",):
        path = shutil.which(candidate)
        if path:
            return [path]

    use_npx = os.getenv(MCP_USE_NPX_ENV, "").strip().lower() in {"1", "true", "yes", "on"}
    if use_npx:
        npx = shutil.which("npx.cmd" if os.name == "nt" else "npx")
        if npx:
            return [npx, "-y", "korean-law-mcp@latest"]

    return []


async def _read_stderr(stderr: asyncio.StreamReader | None) -> str:
    if stderr is None:
        return ""

    chunks: list[str] = []
    while True:
        line = await stderr.readline()
        if not line:
            break
        if len(chunks) < 12:
            chunks.append(line.decode("utf-8", errors="replace").strip())
    return "\n".join(chunk for chunk in chunks if chunk)


async def _write_json(stdin: asyncio.StreamWriter | None, payload: dict[str, Any]) -> None:
    if stdin is None:
        raise KoreanLawMcpError("korean-law-mcp stdin is unavailable.")
    stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
    await stdin.drain()


async def _read_json_response(
    stdout: asyncio.StreamReader | None,
    request_id: int,
    *,
    timeout: float,
) -> dict[str, Any]:
    if stdout is None:
        raise KoreanLawMcpError("korean-law-mcp stdout is unavailable.")

    while True:
        line = await asyncio.wait_for(stdout.readline(), timeout=timeout)
        if not line:
            raise KoreanLawMcpError("korean-law-mcp process closed before sending a response.")
        try:
            message = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            continue
        if message.get("id") == request_id:
            return message


async def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> McpToolResponse:
    """Call a korean-law-mcp tool through stdio JSON-RPC.

    The adapter is optional by design. If the command is not installed, callers
    can skip extended public search while the existing law.go.kr XML search keeps
    working.
    """

    command = _resolve_command()
    if not command:
        raise KoreanLawMcpError(
            f"korean-law-mcp command is not available. Install it or set {MCP_COMMAND_ENV}."
        )

    law_oc = get_law_oc()
    if not law_oc:
        raise KoreanLawMcpError("LAW_OC is not configured.")

    env = {**os.environ, "LAW_OC": law_oc, "KOREAN_LAW_API_KEY": law_oc}
    timeout = _timeout_seconds()
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stderr_task = asyncio.create_task(_read_stderr(process.stderr))

    try:
        await _write_json(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "property-tax-qa", "version": "0.1.0"},
                },
            },
        )
        initialize_response = await _read_json_response(process.stdout, 1, timeout=timeout)
        if initialize_response.get("error"):
            raise KoreanLawMcpError(str(initialize_response["error"]))

        await _write_json(process.stdin, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        await _write_json(
            process.stdin,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
        )
        tool_response = await _read_json_response(process.stdout, 2, timeout=timeout)
        if tool_response.get("error"):
            raise KoreanLawMcpError(str(tool_response["error"]))

        result = tool_response.get("result") or {}
        content = result.get("content") or []
        text_parts = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text")
        ]
        return McpToolResponse(text="\n".join(text_parts).strip(), is_error=bool(result.get("isError")))
    finally:
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        stderr_text = await stderr_task
        if stderr_text:
            logger.debug("korean-law-mcp stderr: %s", stderr_text)


def _configured_decision_domains() -> tuple[str, ...]:
    configured = os.getenv(MCP_DOMAINS_ENV, "").strip()
    if not configured:
        return DEFAULT_DECISION_DOMAINS

    domains = tuple(domain.strip() for domain in configured.split(",") if domain.strip())
    return domains or DEFAULT_DECISION_DOMAINS


def _has_no_results(text: str) -> bool:
    return any(marker in text for marker in NO_RESULT_MARKERS)


def _split_result_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if RESULT_START_RE.match(line):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)

    if current:
        blocks.append(current)

    return blocks


def _parse_metadata(lines: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in lines:
        match = META_LINE_RE.match(line.strip())
        if not match:
            continue
        key = " ".join(match.group(1).split())
        value = " ".join(match.group(2).split())
        if key and value:
            metadata[key] = value
    return metadata


def _metadata_value(metadata: dict[str, str], candidates: tuple[str, ...]) -> str:
    for key in candidates:
        if metadata.get(key):
            return metadata[key]
    for key, value in metadata.items():
        if any(candidate in key for candidate in candidates):
            return value
    return ""


def _record_date(metadata: dict[str, str]) -> str:
    return _metadata_value(
        metadata,
        (
            "선고일",
            "선고일자",
            "공포일",
            "공포일자",
            "시행일",
            "시행일자",
            "체결일",
            "발효일",
            "회신일",
            "회신일자",
            "재결일",
            "의결일",
            "결정일",
        ),
    )


def _record_reference(metadata: dict[str, str]) -> str:
    return _metadata_value(
        metadata,
        (
            "사건번호",
            "안건번호",
            "청구번호",
            "조약번호",
            "행정규칙일련번호",
            "행정규칙ID",
            "자치법규ID",
            "일련번호",
            "ID",
        ),
    )


def _record_source(metadata: dict[str, str], fallback_label: str) -> str:
    return (
        _metadata_value(metadata, ("소관부처", "지자체", "처분청", "재결청", "회신기관", "기관", "구분"))
        or f"korean-law-mcp / {fallback_label}"
    )


def _stable_id(category: str, title: str, raw_text: str) -> str:
    digest = hashlib.sha1(f"{category}\n{title}\n{raw_text}".encode("utf-8")).hexdigest()[:16]
    return f"{category}-{digest}"


def _parse_tool_records(
    text: str,
    *,
    source_type: str,
    source_tool: str,
    source_domain: str | None = None,
) -> list[dict[str, Any]]:
    cleaned = text.strip()
    if not cleaned or _has_no_results(cleaned):
        return []

    label = SOURCE_LABELS.get(source_type, source_type)
    records: list[dict[str, Any]] = []
    blocks = _split_result_blocks(cleaned)
    if not blocks:
        blocks = [[line.strip() for line in cleaned.splitlines() if line.strip()]]

    for block in blocks:
        first_line = block[0]
        start_match = RESULT_START_RE.match(first_line)
        title = first_line
        bracket_id = ""
        if start_match:
            title = start_match.group("title").strip()
            bracket_id = (start_match.group("bracket_id") or "").strip()

        metadata = _parse_metadata(block[1:])
        reference = bracket_id or _record_reference(metadata)
        raw_text = "\n".join(block)
        record_id = reference or _stable_id(source_type, title, raw_text)
        detail_link = _metadata_value(metadata, ("링크", "상세링크", "URL"))

        records.append(
            {
                "source_type": source_type,
                "source_tool": source_tool,
                "source_domain": source_domain,
                "source_label": label,
                "id": record_id,
                "serial_no": reference,
                "title": title or label,
                "source": _record_source(metadata, label),
                "decision_date": _record_date(metadata),
                "case_no": reference,
                "metadata": metadata,
                "summary": raw_text,
                "raw_text": raw_text,
                "full_text": raw_text,
                "detail_link": detail_link,
            }
        )

    return records


async def _search_one_tool(
    *,
    tool_name: str,
    source_type: str,
    arguments: dict[str, Any],
    source_domain: str | None = None,
) -> list[dict[str, Any]]:
    try:
        response = await call_mcp_tool(tool_name, arguments)
    except KoreanLawMcpError as exc:
        logger.info("Extended public search skipped for %s: %s", tool_name, exc)
        return []
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Extended public search failed for %s: %s", tool_name, exc)
        return []

    if response.is_error:
        logger.info("Extended public search returned an error for %s: %s", tool_name, response.text)
        return []

    return _parse_tool_records(
        response.text,
        source_type=source_type,
        source_tool=tool_name,
        source_domain=source_domain,
    )


async def search_extended_public(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search optional korean-law-mcp sources beyond the built-in XML adapter."""

    normalized_query = query.strip()
    if not normalized_query:
        return []
    law_oc = get_law_oc()
    if not law_oc:
        return []

    display = _normalize_max_results(max_results)
    tasks: list[asyncio.Task[list[dict[str, Any]]]] = []

    for tool_name, source_type in DIRECT_SEARCH_TOOLS:
        tasks.append(
            asyncio.create_task(
                _search_one_tool(
                    tool_name=tool_name,
                    source_type=source_type,
                    arguments={"query": normalized_query, "display": display, "apiKey": law_oc},
                )
            )
        )

    for domain in _configured_decision_domains():
        tasks.append(
            asyncio.create_task(
                _search_one_tool(
                    tool_name="search_decisions",
                    source_type=domain,
                    source_domain=domain,
                    arguments={"query": normalized_query, "domain": domain, "display": display, "apiKey": law_oc},
                )
            )
        )

    batches = await asyncio.gather(*tasks, return_exceptions=True)
    results: list[dict[str, Any]] = []
    for batch in batches:
        if isinstance(batch, Exception):
            logger.warning("Extended public search task failed: %s", batch)
            continue
        results.extend(batch)
    return results


__all__ = [
    "McpToolResponse",
    "KoreanLawMcpError",
    "call_mcp_tool",
    "search_extended_public",
    "_parse_tool_records",
]
