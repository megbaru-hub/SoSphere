from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplies value by arg (e.g., price * quantity)."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
