import os
from PIL import Image
from mutagen.mp3 import MP3
from mutagen import File as MutagenFile
from django.db import models

def resize_image(image_path, size=(800, 800)):
    """Zmienia rozmiar obrazu do podanych wymiarów."""
    if not os.path.exists(image_path):
        return
    try:
        img = Image.open(image_path)
        if img.height > size[0] or img.width > size[1]:
            img.thumbnail(size)
            img.save(image_path)
    except Exception as e:
        print(f"Błąd przy zmianie rozmiaru obrazu {image_path}: {e}")

def update_song_duration(song):
    """Odczytuje i aktualizuje czas trwania piosenki z pliku MP3."""
    if not song.audio_file:
        return 0
    
    try:
        audio = MP3(song.audio_file.path)
        if audio.info is None:
            audio = MutagenFile(song.audio_file.path)
        
        if audio and audio.info:
            new_duration = int(audio.info.length)
            return new_duration
    except Exception as e:
        print(f"Błąd odczytu metadanych dla utworu {song.title}: {e}")
    
    return 0
