from django.shortcuts import get_object_or_404
from django.views.generic import ListView, DetailView
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse_lazy
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.mixins import LoginRequiredMixin

from ..models import Artist, Album, Song, Playlist, Genre, LikedSong
from ..utils import apply_cover_seed, SafePaginationMixin
from ..mixins import MusicContextMixin
from ..services import catalog_service

class ArtistDetailView(MusicContextMixin, DetailView):
    model = Artist
    template_name = 'music/artist_detail.html'
    context_object_name = 'artist'
    slug_field = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        artist_data = catalog_service.get_artist_detail_data(self.object, self.request.GET)
        context.update(artist_data)
        
        context['page_obj'] = artist_data['all_songs']
        context['is_paginated'] = context['page_obj'].has_other_pages()
        
        apply_cover_seed(context.get('related_playlists'), context['cover_seed'])
        return context

class AlbumListView(MusicContextMixin, SafePaginationMixin, ListView):
    model = Album
    template_name = 'music/album_list.html'
    context_object_name = 'albums'
    
    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', '15')
        try:
            return max(5, min(int(per_page), 100))
        except ValueError:
            return 15

    def get_queryset(self):
        return catalog_service.get_album_list_queryset(self.request.GET)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        query = params.get('q')
        
        if query:
            # Reusing song list queryset logic for matching songs in album list
            songs_qs = catalog_service.get_song_list_queryset(params)
            per_page_s = params.get('per_page_s', '10')
            try:
                items_per_page_s = max(5, min(int(per_page_s), 100))
            except ValueError:
                items_per_page_s = 10

            paginator_s = Paginator(songs_qs, items_per_page_s)
            page_s_number = params.get('page_s')
            page_s_obj = paginator_s.get_page(page_s_number)
                
            context.update({
                'matching_songs': page_s_obj,
                'page_obj_s': page_s_obj,
                'is_paginated_s': page_s_obj.has_other_pages(),
                'per_page_s': items_per_page_s
            })

        artist_id = params.get('artist_id')
        if artist_id:
            context['selected_artist'] = Artist.objects.filter(id=artist_id).first()

        context.update({
            'query': query or '',
            'selected_genres': params.getlist('genre'),
            'selected_year': params.get('year'),
            'year_min': params.get('year_min'),
            'year_max': params.get('year_max'),
            'current_sort': params.get('sort', '-release_date'),
            'time_range': params.get('time_range', 'all'),
            'page_s': params.get('page_s', '1')
        })
        return context

class SongListView(MusicContextMixin, SafePaginationMixin, ListView):
    model = Song
    template_name = 'music/song_list.html'
    context_object_name = 'songs'
    
    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', '30')
        try:
            return max(5, min(int(per_page), 100))
        except ValueError:
            return 30

    def get_queryset(self):
        return catalog_service.get_song_list_queryset(self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        context.update({
            'query': params.get('q', ''),
            'selected_genres': params.getlist('genre'),
            'year_min': params.get('year_min'),
            'year_max': params.get('year_max'),
            'current_sort': params.get('sort', '-play_count'),
            'time_range': params.get('time_range', 'all'),
            'per_page': params.get('per_page', '30'),
        })
        return context

class AlbumDetailView(MusicContextMixin, DetailView):
    model = Album
    template_name = 'music/album_detail.html'
    context_object_name = 'album'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        album_data = catalog_service.get_album_detail_data(self.object, self.request.GET)
        context.update(album_data)

        context['back_url'] = reverse_lazy('music:album_list')
        return context

class LikedSongsListView(MusicContextMixin, SafePaginationMixin, LoginRequiredMixin, ListView):
    """Widok wyświetlający wszystkie utwory polubione przez użytkownika."""
    model = Song
    template_name = 'music/liked_songs.html'
    context_object_name = 'liked_songs'

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', '15')
        if per_page == 'all':
            return 1000
        try:
            return max(5, min(int(per_page), 100))
        except (ValueError, TypeError):
            return 15

    def get_queryset(self):
        liked_data = catalog_service.get_liked_songs_data(self.request.user, self.request.GET)
        return liked_data['all_liked_songs']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET
        liked_data = catalog_service.get_liked_songs_data(self.request.user, params)
        
        page_a_obj = liked_data['liked_albums_page']
        
        context.update({
            'current_sort': params.get('sort', 'order'),
            'per_page': params.get('per_page', '15'),
            'is_owner': True,
            'query': params.get('q', ''),
            'liked_albums': page_a_obj,
            'page_a_obj': page_a_obj,
            'is_paginated_a': page_a_obj.has_other_pages(),
            'per_page_a': liked_data['per_page_a'],
            'all_liked_songs': self.get_queryset()
        })
            
        return context
