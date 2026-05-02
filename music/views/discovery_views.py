import json
import random
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from django.db.models import Count, Q, F
from django.utils import timezone
from django.templatetags.static import static

from ..models import Genre, Song, SongPlay, Artist, Album, Profile, Playlist, LikedSong
from ..utils import update_cover_seed, apply_cover_seed

from ..services.discovery_service import get_home_page_data, get_discovery_songs
from ..decorators import ajax_error_handler

from ..mixins import MusicContextMixin

class HomeView(MusicContextMixin, generic.TemplateView):
    template_name = 'music/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        home_data = get_home_page_data(self.request, context['cover_seed'])
        context.update(home_data)
        
        return context

class DiscoveryView(LoginRequiredMixin, MusicContextMixin, generic.TemplateView):
    """Widok główny trybu odkrywania muzyki (Discovery Mode)."""
    template_name = 'music/discovery.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Licznik tylko dla trybu discovery (sesja)
        today_str = timezone.now().date().isoformat()
        if self.request.session.get('discovery_today_date') != today_str:
            self.request.session['discovery_today_count'] = 0
            self.request.session['discovery_today_date'] = today_str
            
        context['today_discovery_count'] = self.request.session.get('discovery_today_count', 0)
        
        return context

@login_required
@ajax_error_handler(error_msg='Wystąpił błąd podczas pobierania utworów do odkrywania.')
def get_discovery_songs_ajax(request):
    """Widok AJAX zwracający zestaw utworów do trybu odkrywania."""
    songs = get_discovery_songs(request.GET)
    
    songs_data = []
    for s in songs:
        songs_data.append({
            'id': s.id,
            'title': s.title,
            'artist': s.album.artist.nickname,
            'artist_slug': s.album.artist.slug,
            'artist_photo': s.album.artist.photo.url if s.album.artist.photo else static('images/default_artist.png'),
            'artist_genre': s.album.artist.genre.name if s.album.artist.genre else "Inny",
            'artist_followers': s.artist_followers_count,
            'likes_count': s.likes_count,
            'cover': s.album.cover.url if s.album.cover else static('images/default_album.png'),
            'url': s.audio_file.url if s.audio_file else '',
            'album_id': s.album.id,
            'album_title': s.album.title,
            'album_slug': s.album.slug,
            'album_producer': s.album.produced_by or "Brak danych",
            'release_year': s.album.release_date.year if s.album.release_date else "Nieznany",
            'duration_sec': s.duration_sec,
        })
        
    return JsonResponse({'status': 'success', 'songs': songs_data})

from ..services.profile_service import handle_discovery_action

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas przetwarzania akcji odkrywania.')
def discovery_action_ajax(request):
    """Obsługuje akcje (polubienie/pominięcie) w trybie odkrywania i przyznaje XP."""
    data = json.loads(request.body)
    song_id = data.get('song_id')
    action = data.get('action') # 'like', 'skip', 'undo'
    
    profile = request.user.profile
    song = get_object_or_404(Song, id=song_id)
    
    was_liked = song in profile.liked_songs.all()
    xp_gain, message, status = handle_discovery_action(profile, song, action)
    
    today_str = timezone.now().date().isoformat()
    if request.session.get('discovery_today_date') != today_str:
        request.session['discovery_today_count'] = 0
        request.session['discovery_today_date'] = today_str
        
    if action == 'like' and xp_gain == 10:
        request.session['discovery_today_count'] = request.session.get('discovery_today_count', 0) + 1
    elif action == 'undo' and was_liked:
        request.session['discovery_today_count'] = max(0, request.session.get('discovery_today_count', 0) - 1)
        request.session.modified = True
    
    return JsonResponse({
        'status': status, 
        'message': message,
        'xp_gained': xp_gain,
        'total_xp': profile.xp
    })
