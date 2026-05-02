import json
import logging
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.templatetags.static import static
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import F

from ..models import Song, Album, SongPlay, Artist, LikedSong, Playlist, LikedAlbum
from ..utils import update_cover_seed, apply_cover_seed
from ..services import interaction_service, playback_service
from ..decorators import ajax_error_handler

logger = logging.getLogger(__name__)

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas zapisywania stanu.')
def save_playback_state(request):
    data = json.loads(request.body)
    interaction_service.update_playback_state(request.user, data)
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas polubienia utworu.')
def toggle_like_ajax(request):
    data = json.loads(request.body)
    song_id = data.get('song_id')
    result = interaction_service.toggle_song_like(request.user, song_id)
    return JsonResponse({'status': 'success', **result})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas polubienia albumu.')
def toggle_album_like_ajax(request):
    data = json.loads(request.body)
    album_id = data.get('album_id')
    result = interaction_service.toggle_album_like(request.user, album_id)
    return JsonResponse({'status': 'success', **result})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas masowej operacji.')
def bulk_toggle_like_ajax(request):
    """Masowe polubienie lub odlubienie piosenek."""
    data = json.loads(request.body)
    song_ids = data.get('song_ids', [])
    action = data.get('action', 'like')
    message = interaction_service.bulk_toggle_likes(request.user, song_ids, action)
    return JsonResponse({'status': 'success', 'message': message})

@require_POST
@ajax_error_handler(error_msg='Błąd podczas rejestrowania odtworzenia.')
def track_play_ajax(request):
    """Zwiększa licznik odtworzeń utworu i albumu oraz zapisuje czas słuchania"""
    data = json.loads(request.body)
    song_id = data.get('song_id')
    playlist_id = data.get('playlist_id')
    duration = int(data.get('duration', 0))
    
    interaction_service.record_song_play(request.user, song_id, duration, playlist_id)
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas obserwowania artysty.')
def toggle_artist_follow_ajax(request):
    """Widok AJAX do obserwowania/przestania obserwowania artysty."""
    data = json.loads(request.body)
    artist_id = data.get('artist_id')
    result = interaction_service.toggle_artist_follow(request.user, artist_id)
    return JsonResponse({'status': 'success', **result})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas zmiany kolejności utworów.')
def reorder_liked_songs_ajax(request):
    """Zmienia kolejność polubionych utworów (Drag & Drop)."""
    data = json.loads(request.body)
    position_ids = data.get('position_ids', [])
    start_index = data.get('start_index', 1)
    interaction_service.reorder_liked_songs(request.user, position_ids, start_index)
    return JsonResponse({'status': 'success', 'message': 'Kolejność została zapisana.'})

@ajax_error_handler(error_msg='Wystąpił błąd podczas wyszukiwania.')
def search_autocomplete_ajax(request):
    """Widok zwracający podpowiedzi wyszukiwania (artystów, albumy, utwory) w formacie JSON."""
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'artists': [], 'albums': [], 'songs': []})

    artists = Artist.objects.filter(nickname__icontains=query)[:3]
    albums = Album.objects.filter(title__icontains=query).select_related('artist')[:3]
    songs = Song.objects.filter(title__icontains=query).select_related('album', 'album__artist')[:4]

    data = {
        'artists': [{
            'id': a.id,
            'name': a.nickname,
            'photo': a.photo.url if a.photo else static('images/default_artist.png'),
            'url': reverse('music:artist_detail', args=[a.slug])
        } for a in artists],
        'albums': [{
            'id': a.id,
            'title': a.title,
            'artist': a.artist.nickname,
            'cover': a.cover.url if a.cover else static('images/default_album.png'),
            'url': reverse('music:album_detail', args=[a.slug])
        } for a in albums],
        'songs': [{
            'id': s.id,
            'title': s.title,
            'artist': s.album.artist.nickname,
            'cover': s.album.cover.url if s.album and s.album.cover else static('images/default_album.png'),
            'url': reverse('music:album_detail', args=[s.album.slug]) + f"?play={s.id}"
        } for s in songs]
    }
    return JsonResponse(data)

@ajax_error_handler(error_msg='Wystąpił błąd podczas pobierania utworów.')
def get_context_songs_ajax(request):
    """
    Zwraca listę utworów dla podanego kontekstu (album, playlista, artysta, polubione) w formacie JSON.
    Wykorzystywane do natychmiastowego wznawiania odtwarzania bez przeładowania strony.
    """
    c_type = request.GET.get('type')
    c_id = request.GET.get('id')
    song_id = request.GET.get('song_id')
    
    songs, error = playback_service.get_context_songs_queryset(request.user, c_type, c_id, song_id)
    if error:
        status_code = 401 if "logowanie" in error else (404 if "Nie znaleziono" in error else 500)
        return JsonResponse({'status': 'error', 'message': error}, status=status_code)

    songs_list = []
    for s in songs:
        formatted = playback_service.format_song_for_json(s, c_type, c_id)
        if formatted:
            songs_list.append(formatted)
            
    return JsonResponse({'status': 'success', 'songs': songs_list})

def get_resume_section_ajax(request):
    """
    Renderuje i zwraca HTML sekcji 'Wróć do słuchania'.
    Umożliwia dynamiczne odświeżanie tej sekcji na stronie głównej.
    """
    if not request.user.is_authenticated:
        return HttpResponse('')
        
    last = request.user.profile.last_playback
    playback_obj = None
    
    if last:
        obj_type = last.get('type')
        obj_id = last.get('id')
        song_id = last.get('song_id')
        
        playback_obj, _ = playback_service.get_playback_object(obj_type, obj_id, song_id)
                
    seed = update_cover_seed(request)
    if playback_obj and hasattr(playback_obj, 'owner'):
        apply_cover_seed(playback_obj, seed)

    return render(request, 'music/partials/resume_section.html', {
        'last_playback_obj': playback_obj,
        'last_playback_json': last,
        'is_ajax': True
    })
@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas zmiany kolejności albumów.')
def reorder_liked_albums_ajax(request):
    """Zmienia kolejność polubionych albumów (Drag & Drop)."""
    data = json.loads(request.body)
    album_ids = data.get('album_ids', [])
    start_index = data.get('start_index', 1)
    interaction_service.reorder_liked_albums(request.user, album_ids, start_index)
    return JsonResponse({'status': 'success', 'message': 'Kolejność została zapisana.'})
