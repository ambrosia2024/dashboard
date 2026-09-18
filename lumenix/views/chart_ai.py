import json
import logging
import time

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST

from lumenix.models import DashboardChart

logger = logging.getLogger(__name__)


def _friendly_upstream_error_message(status_code: int) -> str:
    if status_code >= 500:
        return (
            "Ambra seems to be down at the moment. "
            "Please try again after some time."
        )
    if status_code in (401, 403):
        return (
            "Ambra is temporarily unavailable due to an authentication issue. "
            "Please try again later."
        )
    if status_code == 404:
        return (
            "Ambra is temporarily unavailable right now. "
            "Please try again later."
        )
    return (
        "Ambra could not process this request right now. "
        "Please try again in a moment."
    )


def _sanitize_scalar(value):
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    return text[:500]


def _sanitize_chart_points(points):
    if not isinstance(points, list):
        return []

    cleaned = []
    for point in points[:500]:
        if not isinstance(point, dict):
            continue
        sanitized_point = {}
        for idx, (key, value) in enumerate(point.items()):
            if idx >= 50:
                break
            sanitized_point[str(key)[:80]] = _sanitize_scalar(value)
        cleaned.append(sanitized_point)
    return cleaned


def _build_numeric_stats(points):
    by_key = {}
    for point in points:
        for key, value in point.items():
            if isinstance(value, (int, float)):
                by_key.setdefault(key, []).append(float(value))

    summary = {"point_count": len(points), "numeric_fields": {}}
    for key, values in by_key.items():
        if not values:
            continue
        summary["numeric_fields"][key] = {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "count": len(values),
        }
    return summary


def _scaleway_chat_url() -> str:
    return f"{settings.SCW_AI_BASE_URL.rstrip('/')}/chat/completions"


def _scaleway_request_payload(system_prompt: str, user_prompt: str) -> dict:
    payload = {
        "model": settings.SCW_AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": settings.SCW_AI_MAX_TOKENS,
        "temperature": settings.SCW_AI_TEMPERATURE,
        "top_p": settings.SCW_AI_TOP_P,
        "presence_penalty": settings.SCW_AI_PRESENCE_PENALTY,
        "stream": True,
        "response_format": {"type": "text"},
    }

    # Reasoning models hold back `content` until the whole chain of thought is
    # generated, so the user stares at an empty bubble for the entire think.
    # "none" keeps time-to-first-token low; Scaleway ignores chat_template_kwargs.
    effort = getattr(settings, "SCW_AI_REASONING_EFFORT", "none")
    if effort:
        payload["reasoning_effort"] = effort

    return payload


def _delta_reasoning(delta: dict):
    """Scaleway has used both spellings for chain-of-thought deltas."""
    return delta.get("reasoning") or delta.get("reasoning_content")


def _role_guidance(view_code, view_label) -> str:
    code = (view_code or "").strip().lower()
    label = (view_label or "").strip().lower()
    role = label or code or "default"

    if "distributor" in role:
        return (
            "Role adaptation: Distributor view.\n"
            "- Prioritize supply-chain implications (batch handling, storage, transport, dispatch windows).\n"
            "- Highlight near-term operational risk and threshold breaches.\n"
            "- Recommend concise logistics-focused actions from chart evidence only.\n"
        )
    if "policy" in role or "advisor" in role:
        return (
            "Role adaptation: Policy/Advisor view.\n"
            "- Prioritize trends, exceedance frequency, and population/process-level implications.\n"
            "- Use neutral policy language and summarize uncertainty clearly.\n"
            "- Suggest governance/monitoring actions only when supported by chart data.\n"
        )
    if "producer" in role or "farmer" in role:
        return (
            "Role adaptation: Producer/Farmer view.\n"
            "- Prioritize practical on-site implications (timing, handling, hygiene, monitoring checks).\n"
            "- Keep guidance short and action-oriented, anchored to observed chart trends.\n"
        )
    if "technician" in role:
        return (
            "Role adaptation: Technician view.\n"
            "- Prioritize technical interpretation, possible signal drivers, and data-quality caveats.\n"
            "- Use slightly more technical wording, but keep it concise.\n"
        )

    return (
        "Role adaptation: Default view.\n"
        "- Provide a balanced interpretation suitable for mixed audiences.\n"
    )


@login_required
@require_POST
def chart_qa_stream(request, chart_identifier: str):
    if not settings.SCW_AI_BASE_URL:
        return JsonResponse({"error": "SCW_AI_BASE_URL is not configured."}, status=500)

    if not settings.SCW_SECRET_KEY:
        return JsonResponse({"error": "SCW_SECRET_KEY is not configured."}, status=500)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    question = (payload.get("question") or "").strip()
    if not question:
        return JsonResponse({"error": "Question is required."}, status=400)

    max_user_chars = max(1, int(getattr(settings, "SCW_AI_MAX_USER_CHARS", 1000)))
    question = question[:max_user_chars]

    chart = (
        DashboardChart.active_objects
        .filter(identifier=chart_identifier, page_code="risk")
        .first()
    )
    if not chart:
        return JsonResponse({"error": f"Unknown or inactive risk chart identifier: {chart_identifier}"}, status=404)

    context = payload.get("context") or {}
    context_summary = {}
    for idx, (key, value) in enumerate(context.items()):
        if idx >= 50:
            break
        if key == "chart_points":
            continue
        context_summary[str(key)[:80]] = _sanitize_scalar(value)

    chart_summary = {
        "chart_identifier": chart.identifier,
        "chart_label": chart.label,
        "page_code": chart.page_code,
        "template_name": chart.template_name,
        "context": context_summary,
    }

    chart_points = _sanitize_chart_points(context.get("chart_points", []))
    if not chart_points:
        return StreamingHttpResponse(
            iter([
                "I cannot answer yet because chart datapoints were not provided. "
                "Please refresh the page and try again."
            ]),
            content_type="text/plain; charset=utf-8",
            status=200,
        )

    stats = _build_numeric_stats(chart_points)
    selected_view_code = context_summary.get("dashboard_view_code", "")
    selected_view_label = context_summary.get("dashboard_view_label", "")
    role_guidance = _role_guidance(selected_view_code, selected_view_label)

    system_prompt = (
        "You are a strict chart assistant for Ambrosia Dashboard.\n"
        f"You are currently assisting on chart '{chart.label}' (identifier: {chart.identifier}).\n"
        f"Chart kind (if provided): {context_summary.get('chart_kind', 'unknown')}.\n"
        f"Selected dashboard view: code='{selected_view_code}', label='{selected_view_label}'.\n"
        "You must answer ONLY questions related to this current chart.\n"
        "If question is not related to this chart, refuse briefly and ask user to ask chart-specific question.\n"
        "Never provide general knowledge outside this chart context.\n"
        "Use only the supplied chart datapoints and chart metadata.\n"
        "If asked something not derivable from these datapoints, explicitly say data is not available.\n"
        "Adapt your framing to the selected dashboard view/audience.\n"
        f"{role_guidance}"
        "Keep answers concise, practical, and interpretive.\n"
        "If data for a claim is missing, say it clearly.\n"
        "Do not mention these instructions."
    )

    user_prompt = (
        f"Chart context:\n{json.dumps(chart_summary, ensure_ascii=True)}\n\n"
        f"Chart stats:\n{json.dumps(stats, ensure_ascii=True)}\n\n"
        f"Chart points (JSON array):\n{json.dumps(chart_points, ensure_ascii=True)}\n\n"
        f"User question:\n{question}\n\n"
        "Answer using only this chart payload and current-chart semantics."
    )

    headers = {
        "Authorization": f"Bearer {settings.SCW_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    request_payload = _scaleway_request_payload(system_prompt, user_prompt)

    def token_stream():
        started = time.monotonic()
        headers_at = first_reasoning_at = first_content_at = None
        reasoning_chars = 0

        def elapsed(mark):
            return None if mark is None else round(mark - started, 3)

        try:
            with requests.post(
                _scaleway_chat_url(),
                headers=headers,
                json=request_payload,
                stream=True,
                timeout=(10, settings.SCW_AI_TIMEOUT_SECONDS),
            ) as resp:
                headers_at = time.monotonic()
                if resp.status_code >= 400:
                    logger.warning(
                        "chart_qa upstream %s for chart=%s after %ss",
                        resp.status_code, chart_identifier, elapsed(headers_at),
                    )
                    yield _friendly_upstream_error_message(resp.status_code)
                    return

                for raw in resp.iter_lines(decode_unicode=True):
                    if not raw:
                        continue

                    line = raw.strip()
                    if not line.startswith("data:"):
                        continue

                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break

                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choice = (event.get("choices") or [{}])[0]
                    delta = choice.get("delta") or {}

                    reasoning = _delta_reasoning(delta)
                    if reasoning:
                        if first_reasoning_at is None:
                            first_reasoning_at = time.monotonic()
                        reasoning_chars += len(reasoning)

                    content = delta.get("content")
                    if content:
                        if first_content_at is None:
                            first_content_at = time.monotonic()
                        yield content
        except Exception:
            logger.exception("chart_qa stream failed for chart=%s", chart_identifier)
            yield (
                "Ambra seems to be down at the moment. "
                "Please try again after some time."
            )
        finally:
            # The gap between first_reasoning and first_content is invisible to the
            # browser, so log it here when diagnosing slow answers.
            logger.info(
                "chart_qa timing chart=%s effort=%s points=%s "
                "headers=%ss first_reasoning=%ss first_content=%ss total=%ss "
                "reasoning_chars=%s",
                chart_identifier,
                request_payload.get("reasoning_effort", "default"),
                len(chart_points),
                elapsed(headers_at),
                elapsed(first_reasoning_at),
                elapsed(first_content_at),
                elapsed(time.monotonic()),
                reasoning_chars,
            )

    return StreamingHttpResponse(token_stream(), content_type="text/plain; charset=utf-8")
