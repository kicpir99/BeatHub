from django.db.models import Prefetch, Q, Count
from .models import Genre, Playlist, LikedSong
from .utils import update_cover_seed

class MusicContextMixin:
    """
    Mixin dla widoków klasowych (CBV), który automatycznie wstrzykuje 
    podstawowe dane muzyczne i stan użytkownika do kontekstu.
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. Obsługa ziarna dla okładek (Cover Seed)
        seed = update_cover_seed(self.request)
        context['cover_seed'] = seed
        
        # 2. Dane specyficzne dla zalogowanego użytkownika
        if self.request.user.is_authenticated:
            profile = self.request.user.profile
            
            # Polubione utwory i albumy (często używane do ikon serduszek)
            context['liked_song_ids'] = list(profile.liked_songs.values_list('id', flat=True))
            context['liked_album_ids'] = list(profile.liked_albums.values_list('id', flat=True))
            
            # Playlisty użytkownika (do bocznego menu lub modali)
            context['user_playlists'] = self.request.user.playlists.all()
            
            # ID obserwowanych playlist
            context['followed_playlist_ids'] = list(profile.followed_playlists.values_list('id', flat=True))
            
            # ID obserwowanych osób (znajomych)
            context['following_ids'] = list(profile.following.values_list('id', flat=True))
            
        else:
            # Domyślne puste wartości dla niezalogowanych (zapobiega błędom w szablonach)
            context['liked_song_ids'] = []
            context['liked_album_ids'] = []
            context['user_playlists'] = []
            context['followed_playlist_ids'] = []
            context['following_ids'] = []
            
        # 3. Globalne dane (np. gatunki)
        context['genres'] = Genre.objects.all()
        
        return context

class ProfileSearchMixin:
    """
    Mixin wspierający filtrowanie i sortowanie list profili użytkowników.
    Wymaga zdefiniowania atrybutu 'default_sort' w klasie widoku.
    """
    def apply_profile_filters(self, queryset):
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(user__username__icontains=query) | 
                Q(bio__icontains=query) |
                Q(location__icontains=query)
            ).distinct()
        
        sort = self.request.GET.get('sort', self.default_sort)
        if sort == 'username':
            queryset = queryset.order_by('user__username')
        elif sort == '-playlists_count':
            queryset = queryset.order_by('-playlists_count', 'user__username')
        elif sort == '-followers_count':
            queryset = queryset.order_by('-followers_count', 'user__username')
        else:
            queryset = queryset.order_by(sort, 'user__username')
            
        return queryset

    def get_profile_context(self, context):
        context['query'] = self.request.GET.get('q', '')
        context['sort'] = self.request.GET.get('sort', self.default_sort)
        return context
