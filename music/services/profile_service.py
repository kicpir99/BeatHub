import math
from django.db import models
from ..models import Profile, Song

def add_xp(profile, amount):
    """
    Dodaje XP użytkownikowi i zapisuje profil.
    Można tu w przyszłości dodać logikę powiadomień o awansie.
    """
    profile.xp += amount
    profile.save(update_fields=['xp'])
    return profile.xp

def get_user_level_info(xp_amount):
    """
    Oblicza dane o poziomie na podstawie ilości XP.
    Logika wyciągnięta z modelu Profile.
    """
    level = math.floor(0.1 * math.sqrt(xp_amount)) + 1
    xp_current_lvl_start = (10 * (level - 1)) ** 2
    xp_next_lvl_start = (10 * level) ** 2
    
    xp_in_level = xp_amount - xp_current_lvl_start
    xp_required_for_level = xp_next_lvl_start - xp_current_lvl_start
    
    progress = (xp_in_level / xp_required_for_level) * 100 if xp_required_for_level > 0 else 0
    
    return {
        'level': level,
        'current_xp_in_level': int(xp_in_level),
        'required_xp_for_level': int(xp_required_for_level),
        'progress': min(100, max(0, progress)),
        'total_xp': xp_amount
    }

def handle_discovery_action(profile, song, action):
    """
    Obsługuje logikę akcji w trybie odkrywania (like/skip/undo).
    Zwraca (xp_gained, message, status).
    """
    xp_gain = 0
    message = ""
    status = 'success'

    if action == 'like':
        if song not in profile.liked_songs.all():
            profile.liked_songs.add(song)
            song.likes_count += 1
            song.save(update_fields=['likes_count'])
            xp_gain = 10
            message = "Polubiono utwór!"
        else:
            message = "Utwór był już polubiony."
    elif action == 'skip':
        xp_gain = 2
        message = "Pominięto utwór."
    elif action == 'undo':
        # Specjalna logika dla cofania
        if song in profile.liked_songs.all():
            profile.liked_songs.remove(song)
            song.likes_count = max(0, song.likes_count - 1)
            song.save(update_fields=['likes_count'])
            profile.xp = max(0, profile.xp - 10)
        else:
            profile.xp = max(0, profile.xp - 2)
        profile.save(update_fields=['xp'])
        return 0, "Cofnięto akcję", 'success'

    if xp_gain > 0:
        add_xp(profile, xp_gain)
        
    return xp_gain, message, status
