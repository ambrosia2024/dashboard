# config/views.py
from django.http import JsonResponse, HttpResponseNotFound

def status_view(request):
    # Keep it DB-independent and very fast
    return JsonResponse({"status": "ok"})


def disabled_auth_view(request, *args, **kwargs):
    return HttpResponseNotFound("This feature is disabled.")
