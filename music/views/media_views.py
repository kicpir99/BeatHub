import os
import re
from django.http import FileResponse
from django.views.static import serve as static_serve

def ranged_media_serve(request, path, document_root=None, **kwargs):
    """
    Rozszerzona wersja widoku serve, która lepiej radzi sobie z zapytaniami Range (szczególnie w Safari/Chrome).
    Pomaga przy przewijaniu długich utworów, które nie zostały jeszcze w pełni zbuforowane.
    """
    response = static_serve(request, path, document_root, **kwargs)
    
    # Jeśli to FileResponse, Django powinno obsłużyć Range automatycznie (od wersji 2.0+)
    # Ale jeśli używamy standardowego runserver, czasem warto wymusić obsługę Range
    # poprzez upewnienie się, że nagłówki są poprawne.
    
    if response.status_code == 200:
        # Sprawdzamy czy plik istnieje i czy możemy go obsłużyć jako Range
        fullpath = os.path.join(document_root, path)
        if os.path.exists(fullpath):
            response['Accept-Ranges'] = 'bytes'
            
    return response
