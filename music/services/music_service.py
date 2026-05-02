import os
import io
from PIL import Image
from mutagen.mp3 import MP3
from mutagen import File as MutagenFile
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

def resize_image(image_field, size=(800, 800)):
    """
    Zmienia rozmiar obrazu do podanych wymiarów.
    Obsługuje Cloud Storage poprzez użycie default_storage.
    """
    if not image_field:
        return
    
    try:
        with default_storage.open(image_field.name, 'rb') as f:
            img = Image.open(f)
            
            if img.height > size[0] or img.width > size[1]:
                img.thumbnail(size)
                
                buffer = io.BytesIO()
                img_format = img.format or 'JPEG'
                img.save(buffer, format=img_format)
                
                # Nadpisujemy oryginalny plik w magazynie
                default_storage.save(image_field.name, ContentFile(buffer.getvalue()))
                # Ale standardowe S3 nadpisuje lub wersjonuje.
    except Exception as e:
        print(f"Błąd przy zmianie rozmiaru obrazu {image_field.name}: {e}")

def update_song_duration(song):
    """
    Odczytuje i aktualizuje czas trwania piosenki z pliku MP3.
    Wspiera Cloud Storage poprzez pobranie fragmentu pliku lub użycie strumienia.
    """
    if not song.audio_file:
        return 0
    
    try:
        with default_storage.open(song.audio_file.name, 'rb') as f:
            audio = MutagenFile(f)
            if audio and audio.info:
                return int(audio.info.length)
    except Exception as e:
        print(f"Błąd odczytu metadanych dla utworu {song.title}: {e}")
    
    return 0
