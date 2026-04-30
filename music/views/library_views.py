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

class ArtistDetailView(MusicContextMixin, DetailView):
    model = Artist
    template_name = 'music/artist_detail.html'
    context_object_name = 'artist'
    slug_field = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        artist = self.object

        # Albumy artysty
        albums = Album.objects.filter(artist=artist).order_by('-release_date')
        context['albums'] = albums

        # Wszystkie piosenki artysty z paginacją i sortowaniem
        all_songs_list = Song.objects.filter(
            album__artist=artist
        ).select_related('album', 'album__artist', 'album__artist__genre').prefetch_related('featured_artists')
        
        sort_by = self.request.GET.get('sort', '-play_count')
        allowed_sorts = ['title', '-title', 'play_count', '-play_count', 'duration_sec', '-duration_sec', 'id', '-id']
        if sort_by in allowed_sorts:
            all_songs_list = all_songs_list.order_by(sort_by)
        else:
            all_songs_list = all_songs_list.order_by('-play_count')
        
        context['current_sort'] = sort_by
        
        paginator = Paginator(all_songs_list, 15)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context['all_songs'] = page_obj
        context['page_obj'] = page_obj
        context['is_paginated'] = page_obj.has_other_pages()
        context['all_songs_full_list'] = all_songs_list # Dla kolejki odtwarzacza

        # Top 5 utworów (Popularne - ostatnie 30 dni)
        cut_off_30 = timezone.now() - timedelta(days=30)
        top_songs = Song.objects.filter(
            album__artist=artist,
            individual_plays__played_at__gte=cut_off_30
        ).annotate(
            recent_plays=Count('individual_plays')
        ).order_by('-recent_plays')[:5]
        
        # Fallback: Jeśli brak odtworzeń w 30 dni, weź hity wszechczasów
        if not top_songs.exists():
            top_songs = Song.objects.filter(album__artist=artist).order_by('-play_count')[:5]
            
        context['top_songs'] = top_songs

        # Statystyki
        stats = all_songs_list.aggregate(
            total_plays=Sum('play_count'),
            total_songs=Count('id')
        )
        context['total_plays'] = stats['total_plays'] or 0
        context['total_songs'] = stats['total_songs'] or 0
        context['total_albums'] = albums.count()
        
        # Albumy na których artysta pojawia się gościnnie
        context['appears_on'] = Album.objects.filter(
            songs__featured_artists=artist
        ).exclude(artist=artist).distinct().order_by('-release_date')

        # Publiczne playlisty zawierające utwory tego artysty,
        # posortowane po ilości piosenek artysty w playliście
        artist_song_ids = all_songs_list.values_list('id', flat=True)
        playlists_with_artist = Playlist.objects.filter(
            is_public=True,
            songs__id__in=artist_song_ids
        ).annotate(
            artist_songs_count=Count('songs', filter=Q(songs__id__in=artist_song_ids))
        ).order_by('-artist_songs_count').distinct()[:10]
        context['related_playlists'] = playlists_with_artist

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
        queryset = Album.objects.select_related('artist', 'artist__genre').all()
        query = self.request.GET.get('q')
        artist_id = self.request.GET.get('artist_id')
        genre_ids = self.request.GET.getlist('genre')
        year = self.request.GET.get('year')
        year_min = self.request.GET.get('year_min')
        year_max = self.request.GET.get('year_max')
        sort_by = self.request.GET.get('sort', '-release_date')

        # Filtrowanie
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(artist__nickname__icontains=query)
            )
        if artist_id:
            queryset = queryset.filter(artist_id=artist_id)
        if genre_ids:
            queryset = queryset.filter(artist__genre_id__in=genre_ids)

        if year:
            queryset = queryset.filter(release_date__year=year)
        if year_min:
            queryset = queryset.filter(release_date__year__gte=year_min)
        if year_max:
            queryset = queryset.filter(release_date__year__lte=year_max)
        
        featured_artist_id = self.request.GET.get('featured_artist_id')
        if featured_artist_id:
            queryset = queryset.filter(songs__featured_artists__id=featured_artist_id).distinct()
        
        # POPRAWKA SORTOWANIA: Usunięto [] i dodano '-likes_count'
        allowed_sorts = ['-release_date', 'release_date', 'title', '-title', '-play_count', '-likes_count']
        
        if sort_by == '-play_count':
            time_range = self.request.GET.get('time_range', 'all')
            if time_range == 'week':
                cut_off = timezone.now() - timedelta(days=7)
                queryset = queryset.annotate(
                    range_plays=Count('songs__individual_plays', filter=Q(songs__individual_plays__played_at__gte=cut_off))
                ).order_by('-range_plays', '-release_date')
            elif time_range == 'month':
                cut_off = timezone.now() - timedelta(days=30)
                queryset = queryset.annotate(
                    range_plays=Count('songs__individual_plays', filter=Q(songs__individual_plays__played_at__gte=cut_off))
                ).order_by('-range_plays', '-release_date')
            else:
                queryset = queryset.order_by('-play_count', '-release_date')
        elif sort_by in allowed_sorts:
            queryset = queryset.order_by(sort_by, '-release_date')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q')
        artist_id = self.request.GET.get('artist_id')
        genre_ids = self.request.GET.getlist('genre')
        year = self.request.GET.get('year')
        year_min = self.request.GET.get('year_min')
        year_max = self.request.GET.get('year_max')
        sort_by = self.request.GET.get('sort', '-release_date')

        if artist_id:
            context['selected_artist'] = Artist.objects.filter(id=artist_id).first()

        # Liked IDs są teraz w MusicContextMixin

        if query:
            songs_qs = Song.objects.filter(
                Q(title__icontains=query) | Q(album__artist__nickname__icontains=query)
            ).select_related('album', 'album__artist', 'album__artist__genre')

            if genre_ids:
                songs_qs = songs_qs.filter(album__artist__genre_id__in=genre_ids)

            if year:
                songs_qs = songs_qs.filter(album__release_date__year=year)
            if year_min:
                songs_qs = songs_qs.filter(album__release_date__year__gte=year_min)
            if year_max:
                songs_qs = songs_qs.filter(album__release_date__year__lte=year_max)
            
            sort_map = {
                '-release_date': '-album__release_date',
                'release_date': 'album__release_date',
                'year': 'album__release_date',
                '-year': '-album__release_date',
                'title': 'title',
                '-title': '-title',
                'play_count': 'play_count',
                '-play_count': '-play_count',
                'album': 'album__title',
                '-album': '-album__title',
                'id': 'id',
                '-id': '-id',
                '-likes_count': '-likes_count'
            }
            songs_qs = songs_qs.order_by(sort_map.get(sort_by, '-album__release_date'))
            
            # Paginacja dla UTWORÓW w wynikach wyszukiwania
            per_page_s = self.request.GET.get('per_page_s', '10')
            try:
                items_per_page_s = max(5, min(int(per_page_s), 100))
            except ValueError:
                items_per_page_s = 10

            paginator_s = Paginator(songs_qs, items_per_page_s)
            page_s_number = self.request.GET.get('page_s')
            
            try:
                page_s_obj = paginator_s.page(page_s_number or 1)
            except (EmptyPage, PageNotAnInteger):
                page_s_obj = paginator_s.page(1)
                
            context['matching_songs'] = page_s_obj
            context['page_obj_s'] = page_s_obj
            context['is_paginated_s'] = page_s_obj.has_other_pages()
            context['per_page_s'] = items_per_page_s

        context.update({
            'query': query or '',
            'selected_genres': genre_ids,
            'selected_year': year,
            'year_min': year_min,
            'year_max': year_max,
            'current_sort': sort_by,
            'time_range': self.request.GET.get('time_range', 'all'),
            'page_s': self.request.GET.get('page_s', '1')
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
        queryset = Song.objects.select_related('album', 'album__artist', 'album__artist__genre').prefetch_related('featured_artists').all()
        query = self.request.GET.get('q')
        genre_ids = self.request.GET.getlist('genre')
        year_min = self.request.GET.get('year_min')
        year_max = self.request.GET.get('year_max')
        sort_by = self.request.GET.get('sort', '-play_count')

        if query and query.strip():
            queryset = queryset.filter(
                Q(title__icontains=query) | Q(album__artist__nickname__icontains=query)
            )
        
        if genre_ids:
            genre_ids = [gid for gid in genre_ids if gid]
            if genre_ids:
                queryset = queryset.filter(album__artist__genre_id__in=genre_ids)
        
        if year_min and year_min.isdigit():
            queryset = queryset.filter(album__release_date__year__gte=year_min)
        if year_max and year_max.isdigit():
            queryset = queryset.filter(album__release_date__year__lte=year_max)
        
        allowed_sorts = ['title', '-title', 'play_count', '-play_count', 'id', '-id', '-likes_count', 'album__release_date', '-album__release_date']
        
        if sort_by == '-play_count':
            time_range = self.request.GET.get('time_range', 'all')
            if time_range == 'week':
                cut_off = timezone.now() - timedelta(days=7)
                queryset = queryset.annotate(
                    range_plays=Count('individual_plays', filter=Q(individual_plays__played_at__gte=cut_off))
                ).order_by('-range_plays', '-play_count')
            elif time_range == 'month':
                cut_off = timezone.now() - timedelta(days=30)
                queryset = queryset.annotate(
                    range_plays=Count('individual_plays', filter=Q(individual_plays__played_at__gte=cut_off))
                ).order_by('-range_plays', '-play_count')
            else:
                queryset = queryset.order_by('-play_count', '-id')
        elif sort_by in allowed_sorts:
            queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('-play_count', '-id')
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        genre_ids = self.request.GET.getlist('genre')
        year_min = self.request.GET.get('year_min')
        year_max = self.request.GET.get('year_max')
        sort_by = self.request.GET.get('sort', '-play_count')
        time_range = self.request.GET.get('time_range', 'all')

        # Liked IDs są teraz w MusicContextMixin

        context.update({
            'query': query,
            'selected_genres': genre_ids,
            'year_min': year_min,
            'year_max': year_max,
            'current_sort': sort_by,
            'time_range': time_range,
            'per_page': self.request.GET.get('per_page', '30'),
        })
        return context

class AlbumDetailView(MusicContextMixin, DetailView):
    model = Album
    template_name = 'music/album_detail.html'
    context_object_name = 'album'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pobieranie piosenek tego samego artysty z INNYCH albumów w celu automatycznego zapełniania kolejki odtwarzania
        songs = Song.objects.filter(
            album=self.object
        ).select_related('album', 'album__artist').prefetch_related('featured_artists')

        sort_by = self.request.GET.get('sort', 'id')
        allowed_sorts = ['title', '-title', 'play_count', '-play_count', 'duration_sec', '-duration_sec', 'id', '-id']
        if sort_by in allowed_sorts:
            songs = songs.order_by(sort_by)
        else:
            songs = songs.order_by('id')
        
        context['songs'] = songs
        context['current_sort'] = sort_by

        context['other_artist_songs'] = Song.objects.filter(
            album__artist=self.object.artist
        ).exclude(
            album=self.object
        ).select_related('album', 'album__artist').prefetch_related('featured_artists')

        # Liked IDs są teraz w MusicContextMixin

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
        songs_list = LikedSong.objects.filter(profile=self.request.user.profile).select_related('song', 'song__album', 'song__album__artist')
        
        query = self.request.GET.get('q')
        if query:
            songs_list = songs_list.filter(
                Q(song__title__icontains=query) |
                Q(song__album__artist__nickname__icontains=query) |
                Q(song__album__title__icontains=query)
            )
        
        sort_by = self.request.GET.get('sort', 'order')
        allowed_sorts = [
            'song__title', '-song__title', 
            'song__play_count', '-song__play_count', 
            'song__duration_sec', '-song__duration_sec', 
            'song__album__title', '-song__album__title',
            'added_at', '-added_at',
            'order'
        ]
        if sort_by in allowed_sorts:
            songs_list = songs_list.order_by(sort_by)
        else:
            songs_list = songs_list.order_by('order')
        
        return songs_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile = user.profile
        context['current_sort'] = self.request.GET.get('sort', 'order')
        context['per_page'] = self.request.GET.get('per_page', '15')
        context['is_owner'] = True
        context['query'] = self.request.GET.get('q', '')
        
        # Paginacja dla ALBUMÓW
        query = self.request.GET.get('q')
        all_liked_albums = Album.objects.filter(liked_album_positions__profile=profile).select_related('artist', 'artist__genre').order_by('liked_album_positions__order', '-liked_album_positions__added_at')
        
        if query:
            all_liked_albums = all_liked_albums.filter(
                Q(title__icontains=query) |
                Q(artist__nickname__icontains=query) |
                Q(artist__genre__name__icontains=query)
            ).distinct()
        per_page_a = self.request.GET.get('per_page_a', '12')
        try:
            items_per_page_a = max(4, min(int(per_page_a), 60))
        except ValueError:
            items_per_page_a = 12
            
        paginator_a = Paginator(all_liked_albums, items_per_page_a)
        page_a_number = self.request.GET.get('page_a')
        page_a_obj = paginator_a.get_page(page_a_number)
        
        context.update({
            'liked_albums': page_a_obj,
            'page_a_obj': page_a_obj,
            'is_paginated_a': page_a_obj.has_other_pages(),
            'per_page': self.request.GET.get('per_page', '15'),
            'per_page_a': per_page_a,
            'liked_album_ids': context['liked_album_ids'],
            'liked_song_ids': context['liked_song_ids'],
            'all_liked_songs': self.get_queryset()
        })
            
        return context
