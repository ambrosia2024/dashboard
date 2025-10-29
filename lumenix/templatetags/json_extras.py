# lumenix/templatetags/json_extras.py

from django import template

register = template.Library()

@register.filter
def get(value, key):
    if isinstance(value, dict):
        return value.get(key) or value.get("en") or next(iter(value.values()), "")
    return ""
