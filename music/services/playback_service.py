import logging
from django.shortcuts import get_object_or_404
from ..models import Song, Album, Playlist, Artist

logger = logging.getLogger(__name__)

def get_playback_object(context_type, context_id, song_id=None):
    """
    Identyfikuje i zwraca obiekt, z którego pochodzi odtwarzanie.
    Zwraca (object, error_message).
    """
    try:
        if context_type == 'album' and context_id:
            return Album.objects.select_related('artist').get(id=context_id), None
        elif context_type == 'playlist' and context_id:
            return Playlist.objects.select_related('owner__profile').get(id=context_id), None
        elif context_type == 'artist' and context_id:
            return Artist.objects.get(id=context_id), None
        elif context_type == 'liked':
            return 'liked', None
        
        # Fallback do piosenki
        if song_id:
            return Song.objects.select_related('album', 'album__artist').get(id=song_id), None
            
        return None, "Nie rozpoznano kontekstu odtwarzania."
    except Exception as e:
        logger.warning(f"Could not find playback object: {e}")
        return None, str(e)

def get_context_songs_queryset(user, context_type, context_id, song_id=None):
    """
    Zwraca QuerySet lub listę utworów dla danego kontekstu.
    """
    songs = []
    
    if context_type == 'album' and context_id:
        songs = Song.objects.filter(album_id=context_id).select_related('album', 'album__artist').prefetch_related('featured_artists').order_by('id')
    
    elif context_type == 'playlist' and context_id:
        playlist = get_object_or_404(Playlist, id=context_id)
        positions = playlist.playlistposition_set.select_related(
            'song', 'song__album', 'song__album__artist'
        ).prefetch_related('song__featured_artists').all().order_by('order')
        songs = [pos.song for pos in positions]
        
    elif context_type == 'artist' and context_id:
        songs = Song.objects.filter(album__artist_id=context_id).select_related(
            'album', 'album__artist'
        ).prefetch_related('featured_artists').order_by('-play_count')[:15]
        
    elif context_type == 'liked':
        if user.is_authenticated:
            positions = user.profile.liked_positions.select_related(
                'song', 'song__album', 'song__album__artist'
            ).prefetch_related('song__featured_artists').all().order_by('order', '-added_at')
            songs = [pos.song for pos in positions]
        else:
            return None, "Wymagane logowanie do pobrania polubionych utworów."

    # Fallback do pojedynczego utworu
    if not songs and song_id:
        songs = Song.objects.filter(id=song_id).select_related('album', 'album__artist').prefetch_related('featured_artists')

    if not songs:
        return None, "Nie znaleziono utworów dla podanego kontekstu."
        
    return songs, None

def format_song_for_json(song, context_type=None, context_id=None):
    """Konwertuje obiekt Song na słownik gotowy do wysłania przez JSON."""
    try:
        featured = [
            {'nickname': a.nickname, 'slug': a.slug} 
            for a in song.featured_artists.all()
        ]
        
        return {
            'id': song.id,
            'title': song.title,
            'artist': song.album.artist.nickname if song.album and song.album.artist else "Nieznany",
            'artist_slug': song.album.artist.slug if song.album and song.album.artist else "",
            'featured_artists': featured,
            'url': song.audio_file.url if song.audio_file else "",
            'cover': song.album.cover.url if song.album and song.album.cover else '',
            'album_slug': song.album.slug if song.album else "unknown",
            'album_id': song.album.id if song.album else None,
            'playlist_id': context_id if context_type == 'playlist' else None,
        }
    except Exception as e:
        logger.error(f"Error formatting song {song.id}: {e}")
        return None
