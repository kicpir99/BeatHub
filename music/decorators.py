import json
import logging
from functools import wraps
from django.http import JsonResponse

logger = logging.getLogger(__name__)

def ajax_error_handler(error_msg='Wystąpił nieoczekiwany błąd.'):
    """
    Dekorator do standaryzacji obsługi błędów w widokach AJAX.
    Automatycznie loguje wyjątek i zwraca ujednoliconą odpowiedź JSON.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)
            except Exception as e:
                # Logujemy pełny błąd dla programisty
                logger.error(f"Error in {view_func.__name__}: {str(e)}", exc_info=True)
                
                # Zwracamy bezpieczny komunikat dla użytkownika
                return JsonResponse({
                    'status': 'error',
                    'message': error_msg
                }, status=400)
        return _wrapped_view
    return decorator
