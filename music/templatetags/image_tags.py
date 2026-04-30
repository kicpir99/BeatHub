import os
from PIL import Image
from django import template
from django.conf import settings

register = template.Library()

@register.filter
def thumbnail(file, size):
    if not file:
        return ""
    
    try:
        # Parsowanie rozmiaru (np. "300x300")
        width, height = map(int, size.split('x'))
        
        # Pobieranie ścieżki względnej
        if hasattr(file, 'name'):
            rel_path = file.name
        else:
            rel_path = str(file)
            # Jeśli dostaliśmy pełny URL, próbujemy wyłuskać ścieżkę względną względem MEDIA_URL
            if rel_path.startswith(settings.MEDIA_URL):
                rel_path = rel_path[len(settings.MEDIA_URL):]
            elif rel_path.startswith('/media/'):
                rel_path = rel_path[len('/media/'):]
        
        # Ścieżka do pliku źródłowego
        source_path = os.path.join(settings.MEDIA_ROOT, rel_path)
        
        if not os.path.exists(source_path):
            # Jeśli plik nie istnieje, zwracamy oryginał (może to URL zewnętrzny)
            return file.url if hasattr(file, 'url') else file

        # Tworzenie nazwy i ścieżki miniatury
        ext = os.path.splitext(rel_path)[1]
        thumb_name = f"{os.path.splitext(os.path.basename(rel_path))[0]}_{width}x{height}{ext}"
        
        # Katalog cache
        thumb_rel_dir = os.path.join('cache', 'thumbnails')
        thumb_dir = os.path.join(settings.MEDIA_ROOT, thumb_rel_dir)
        
        if not os.path.exists(thumb_dir):
            os.makedirs(thumb_dir, exist_ok=True)
            
        thumb_path = os.path.join(thumb_dir, thumb_name)
        thumb_url = os.path.join(settings.MEDIA_URL, thumb_rel_dir, thumb_name).replace('\\', '/')

        # Sprawdzanie czy miniatura już istnieje i czy jest aktualna
        if os.path.exists(thumb_path):
            if os.path.getmtime(source_path) <= os.path.getmtime(thumb_path):
                return thumb_url

        # Generowanie miniatury
        img = Image.open(source_path)
        
        # Zachowujemy proporcje, ale dopasowujemy do podanego rozmiaru
        img.thumbnail((width, height), Image.Resampling.LANCZOS)
        
        # Zapisywanie
        img.save(thumb_path, quality=85, optimize=True)
        
        return thumb_url
    except Exception as e:
        # W razie błędu zwracamy oryginał
        if hasattr(file, 'url'):
            return file.url
        return str(file)
