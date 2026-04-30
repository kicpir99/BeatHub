from django import template

register = template.Library()

@register.filter
def compact_number(value):
    """
    Formatuje dużą liczbę do postaci kompaktowej:
    1500 -> 1.5k
    1200000 -> 1.2M
    """
    try:
        num = float(value)
        if num >= 1000000:
            return f"{num/1000000:.1f}M".replace('.0M', 'M')
        if num >= 1000:
            return f"{num/1000:.1f}k".replace('.0k', 'k')
        return str(int(num))
    except (ValueError, TypeError):
        return value

@register.filter
def to_string_list(queryset):
    """Zamienia listę/QuerySet ID na listę stringów dla łatwiejszego porównywania."""
    return [str(i) for i in queryset]

@register.filter
def is_in(value, collection):
    """Sprawdza czy wartość jest w kolekcji (obsługuje różne typy)."""
    try:
        return str(value) in [str(i) for i in collection]
    except:
        return False
