"""LLM service — optional AI-powered suggestion for alert handling.

Uses OpenAI-compatible chat completion API (supports OpenAI, Anthropic via
proxy, local Ollama, etc.). Disabled when AT_LLM_PROVIDER=none.
"""

import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger("alert-tracker.llm")

SYSTEM_PROMPT = (
    "你是一位資深的 SRE (Site Reliability Engineer) 顧問。"
    "你的任務是根據過去同事的處理紀錄，為當前的 alert 產出一段簡潔的處理作法建議草稿。\n"
    "要求：\n"
    "1. 用繁體中文回應\n"
    "2. 100 字以內\n"
    "3. 直接給出可執行的步驟，不要廢話\n"
    "4. 如果歷史紀錄有多種不同作法，綜合最佳實務\n"
    "5. 如果歷史紀錄太少或不明確，誠實說明並給出一般性建議"
)


def _build_user_prompt(
    alert_name: str,
    severity: str,
    phenomenon: Optional[str],
    cluster_name: Optional[str],
    history_records: list[dict],
) -> str:
    """Build the user prompt with current alert context and historical records."""
    parts = [f"目前發生的告警：{alert_name}（severity: {severity}）"]
    if cluster_name:
        parts.append(f"Cluster: {cluster_name}")
    if phenomenon:
        parts.append(f"值班人員觀察到的現象：{phenomenon}")

    parts.append("")
    if history_records:
        parts.append(f"以下是過去 {len(history_records)} 筆同名/同源告警的處理紀錄：")
        for i, rec in enumerate(history_records, 1):
            entry = f"\n---\n紀錄 {i}（{rec.get('year')}-W{rec.get('week_number', 0):02d}）"
            if rec.get("operator_name"):
                entry += f"，值班: {rec['operator_name']}"
            if rec.get("action_taken"):
                entry += f"\n處理作法：{rec['action_taken']}"
            if rec.get("phenomenon"):
                entry += f"\n現象：{rec['phenomenon']}"
            parts.append(entry)
    else:
        parts.append("此告警無歷史處理紀錄。請根據告警名稱和 SRE 經驗給出一般性建議。")

    parts.append("\n請綜合以上資訊，寫出一段處理作法建議草稿。")
    return "\n".join(parts)


async def generate_suggestion(
    alert_name: str,
    severity: str,
    phenomenon: Optional[str] = None,
    cluster_name: Optional[str] = None,
    history_records: Optional[list[dict]] = None,
) -> str:
    """Call LLM to generate a handling suggestion.

    Returns the suggestion text, or raises an exception on failure.
    """
    if not settings.llm_enabled:
        raise ValueError("LLM feature is not enabled (AT_LLM_PROVIDER=none or missing API key)")

    user_prompt = _build_user_prompt(
        alert_name=alert_name,
        severity=severity,
        phenomenon=phenomenon,
        cluster_name=cluster_name,
        history_records=history_records or [],
    )

    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 500,
        "temperature": 0.3,
    }

    url = f"{settings.llm_api_base.rstrip('/')}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.llm_api_key}",
    }

    logger.info("LLM request for alert '%s' → %s (%s)", alert_name, url, settings.llm_model)

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, headers=headers, timeout=30.0)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        # Sanitize: never expose response body or auth headers in error messages
        raise ValueError(f"LLM API returned HTTP {e.response.status_code}") from None
    except httpx.RequestError as e:
        raise ValueError(f"LLM API connection error: {type(e).__name__}") from None

    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        raise ValueError("LLM returned no choices")

    suggestion = choices[0].get("message", {}).get("content", "").strip()
    logger.info("LLM suggestion for '%s': %d chars", alert_name, len(suggestion))
    return suggestion
