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

from ..models import Genre, Song, SongPlay, Artist, Album, Profile, Playlist
from ..utils import update_cover_seed, apply_cover_seed

from ..services.discovery_service import get_home_page_data

from ..mixins import MusicContextMixin

class HomeView(MusicContextMixin, generic.TemplateView):
    template_name = 'music/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Pobieramy wszystkie dane ze specjalistycznego serwisu
        home_data = get_home_page_data(self.request, context['cover_seed'])
        context.update(home_data)
        
        return context

class DiscoveryView(LoginRequiredMixin, MusicContextMixin, generic.TemplateView):
    """Widok główny trybu odkrywania muzyki (Discovery Mode)."""
    template_name = 'music/discovery.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obliczanie liczby odkryć na dziś
        today = timezone.now().date()
        context['today_discovery_count'] = SongPlay.objects.filter(
            user=self.request.user,
            played_at__date=today
        ).count()
        
        return context

@login_required
def get_discovery_songs_ajax(request):
    """Widok AJAX zwracający zestaw utworów do trybu odkrywania."""
    genre_slugs = request.GET.getlist('genre')
    year_from = request.GET.get('year_from')
    year_to = request.GET.get('year_to')
    
    queryset = Song.objects.select_related('album', 'album__artist', 'album__artist__genre').prefetch_related('featured_artists')
    
    # Filtrowanie po gatunkach
    if genre_slugs and 'all' not in genre_slugs:
        queryset = queryset.filter(album__artist__genre__slug__in=genre_slugs)
    
    # Filtrowanie po latach
    if year_from:
        queryset = queryset.filter(album__release_date__year__gte=year_from)
    if year_to:
        queryset = queryset.filter(album__release_date__year__lte=year_to)
        
    # Pobieranie 15 losowych utworów
    songs = queryset.order_by('?')[:15]
    
    songs_data = []
    for s in songs:
        songs_data.append({
            'id': s.id,
            'title': s.title,
            'artist': s.album.artist.nickname,
            'artist_slug': s.album.artist.slug,
            'artist_photo': s.album.artist.photo.url if s.album.artist.photo else static('images/default_artist.png'),
            'artist_genre': s.album.artist.genre.name if s.album.artist.genre else "Inny",
            'artist_followers': s.album.artist.followers.count(),
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
def discovery_action_ajax(request):
    """Obsługuje akcje (polubienie/pominięcie) w trybie odkrywania i przyznaje XP."""
    try:
        data = json.loads(request.body)
        song_id = data.get('song_id')
        action = data.get('action') # 'like', 'skip', 'undo'
        
        profile = request.user.profile
        song = get_object_or_404(Song, id=song_id)
        
        xp_gain, message, status = handle_discovery_action(profile, song, action)
        
        return JsonResponse({
            'status': status, 
            'message': message,
            'xp_gained': xp_gain,
            'total_xp': profile.xp
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
