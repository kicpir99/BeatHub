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
def is_in(value, collection):
    """Sprawdza czy wartość jest w kolekcji, minimalizując narzut pamięciowy."""
    if not collection:
        return False
    
    # Najpierw sprawdzamy oryginalne typy (bardzo szybkie O(1) jeśli collection to set)
    try:
        if value in collection:
            return True
    except (TypeError, ValueError):
        pass
    
    # Awaryjnie używamy generatora zamiast tworzyć całą nową listę w pamięci RAM
    try:
        return str(value) in map(str, collection)
    except:
        return False
