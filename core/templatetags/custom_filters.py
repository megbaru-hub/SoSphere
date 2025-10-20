# core/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def times(value, arg):
    "Multiplies the value by the argument"
    try:
        return value * arg
    except:
        return ''
