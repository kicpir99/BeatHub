from django.db.models import Prefetch
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
            
        # 3. Globalne dane (np. gatunki)
        context['genres'] = Genre.objects.all()
        
        return context
