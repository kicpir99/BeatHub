import math
from django.db import models
from django.db.models import Count, Sum, OuterRef, Subquery
from django.db.models.functions import Coalesce
from ..models import Profile, Song, Playlist, Artist

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
            
            from ..models import PlaylistPosition
            from django.db.models import Max
            from django.db.models.functions import Coalesce
            
            discovery_playlist, created = Playlist.objects.get_or_create(
                owner=profile.user,
                is_discovery=True,
                defaults={
                    'name': 'Odkrycia 🪐', 
                    'is_public': False, 
                    'description': 'Automatyczna playlista z utworami polubionymi w trybie Odkrywaj.'
                }
            )
            
            if not PlaylistPosition.objects.filter(playlist=discovery_playlist, song=song).exists():
                last_order = PlaylistPosition.objects.filter(playlist=discovery_playlist).aggregate(
                    max_order=Coalesce(Max('order'), 0)
                )['max_order']
                PlaylistPosition.objects.create(
                    playlist=discovery_playlist, 
                    song=song, 
                    order=last_order + 1
                )
        else:
            message = "Utwór był już polubiony."
    elif action == 'skip':
        xp_gain = 2
        message = "Pominięto utwór."
    elif action == 'undo':
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
def get_profile_dashboard_context(profile_user):
    """
    Zbiera ujednolicony kontekst danych dla profilu użytkownika.
    Wykorzystywane zarówno w widoku publicznym, jak i panelu edycji.
    """
    profile = profile_user.profile
    
    duration_subquery = Song.objects.filter(
        playlists=OuterRef('pk')
    ).values('playlists').annotate(
        total=Sum('duration_sec')
    ).values('total')

    # 1. Publiczne playlisty z adnotacjami
    public_playlists = Playlist.objects.filter(owner=profile_user, is_public=True).annotate(
        songs_count=Count('songs', distinct=True),
        total_duration_db=Coalesce(Subquery(duration_subquery), 0)
    ).order_by('-created_at')
    
    # 2. Ostatnio polubione utwory
    liked_songs_qs = profile.liked_songs.select_related('album__artist').all()
    recent_liked_songs = liked_songs_qs.order_by('-id')[:5]
    
    artist_ids = liked_songs_qs.values_list('album__artist_id', flat=True).distinct()
    favorite_artists = Artist.objects.filter(id__in=artist_ids)[:5]
    
    return {
        'public_playlists': public_playlists,
        'recent_liked_songs': recent_liked_songs,
        'favorite_artists': favorite_artists,
    }
