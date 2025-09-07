# config/views.py
from django.http import JsonResponse

def status_view(request):
    # Keep it DB-independent and very fast
    return JsonResponse({"status": "ok"})
