# lumenix/views/ambra.py
"""
Ask Ambra for an assessment run: a persisted, per-user conversation.

The question is saved, the chart context is built server-side from the run's
stored snapshot (the browser never supplies datapoints), the answer streams
through the existing chart_qa_stream view, and the completed answer is saved.
"""

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.views import View

from lumenix.models import AmbraMessage, AssessmentRun
from lumenix.views.chart_ai import chart_qa_stream

CHART_FOR_AMBRA = "c2_pathogen_over_time"
MAX_QUESTION = 1000


def _run_context(run):
    snap = run.snapshot or {}
    series = (snap.get("series") or [])[:500]
    return {
        "assessment": run.run_code,
        "name": run.name,
        "crop": run.crop_label,
        "hazard": run.hazard_label,
        "region": f"{run.nuts2_name} ({run.nuts2_code})",
        "period": f"{run.start_date.isoformat()} to {run.end_date.isoformat()}",
        "time_scale": run.resolution,
        "model": run.model_name,
        "unit": snap.get("unit", "model output"),
        "uncertainty": "not supplied by the model; do not present variability as uncertainty",
        "variability_of_output": snap.get("variability") or "not computed",
        "note": "model output, not a validated risk prediction",
        "chart_kind": "line: model output over time",
        "chart_points": [{"date": r.get("date"), "value": r.get("value"), "temperature_c": r.get("temperature_c")} for r in series],
    }


class _OwnedRun(LoginRequiredMixin, View):
    def get_run(self):
        return get_object_or_404(AssessmentRun.active_objects, pk=self.kwargs["run_id"], user=self.request.user)


class AmbraMessagesView(_OwnedRun):
    """GET the conversation; POST {"action": "clear"} deletes it."""

    def get(self, request, *args, **kwargs):
        run = self.get_run()
        msgs = AmbraMessage.objects.filter(run=run, user=request.user)
        return JsonResponse({"messages": [{"id": m.id, "role": m.role, "content": m.content, "at": m.created_at.isoformat()} for m in msgs]})

    def post(self, request, *args, **kwargs):
        run = self.get_run()
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        if payload.get("action") == "clear":
            deleted, _ = AmbraMessage.objects.filter(run=run, user=request.user).delete()
            return JsonResponse({"cleared": deleted})
        return JsonResponse({"error": "Unknown action."}, status=400)


class AmbraAskView(_OwnedRun):
    """POST {"question": ...} → text/plain token stream; both turns are persisted."""

    def post(self, request, *args, **kwargs):
        run = self.get_run()
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "Invalid JSON payload."}, status=400)
        question = (payload.get("question") or "").strip()[:MAX_QUESTION]
        if not question:
            return JsonResponse({"error": "Question is required."}, status=400)

        AmbraMessage.objects.create(run=run, user=request.user, role=AmbraMessage.Role.USER, content=question)

        # Hand the existing view a body built from the stored snapshot, not from the client.
        request._body = json.dumps({"question": question, "context": _run_context(run)}).encode("utf-8")
        upstream = chart_qa_stream(request, CHART_FOR_AMBRA)
        if not isinstance(upstream, StreamingHttpResponse):
            return upstream  # configuration/validation error passthrough

        def capture():
            parts = []
            try:
                for chunk in upstream.streaming_content:
                    text = chunk.decode("utf-8", "ignore") if isinstance(chunk, bytes) else str(chunk)
                    parts.append(text)
                    yield text
            finally:
                answer = "".join(parts).strip()
                if answer:
                    AmbraMessage.objects.create(run=run, user=request.user, role=AmbraMessage.Role.AMBRA, content=answer)

        return StreamingHttpResponse(capture(), content_type="text/plain; charset=utf-8")


class AmbraDownloadView(_OwnedRun):
    def get(self, request, *args, **kwargs):
        run = self.get_run()
        lines = [
            f"Ask Ambra — {run.run_code} {run.name}",
            f"{run.crop_label} · {run.hazard_label} · {run.nuts2_name} ({run.nuts2_code}) · {run.start_date} to {run.end_date}",
            "Ambra answers only from this assessment's data. Ambra can make mistakes; verify before relying on it.",
            "",
        ]
        for m in AmbraMessage.objects.filter(run=run, user=request.user):
            who = "You" if m.role == AmbraMessage.Role.USER else "Ambra"
            lines.append(f"[{m.created_at:%Y-%m-%d %H:%M}] {who}:\n{m.content}\n")
        response = HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="ambra-{run.run_code}.txt"'
        return response
