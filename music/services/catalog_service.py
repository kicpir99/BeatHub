from django.db.models import Count, Sum, Q, OuterRef, Subquery
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models.functions import Coalesce
from ..models import Artist, Album, Song, Playlist, LikedSong

from django.core.cache import cache

def get_artist_detail_data(artist, request_params):
    """
    Zbiera wszystkie dane potrzebne do widoku detali artysty.
    Zoptymalizowane pod kątem keszowania (zapisujemy ID, nie obiekty).
    """
    version_key = f"artist_v_{artist.id}"
    version = cache.get(version_key, 1)

    page_num = request_params.get('page', '1')
    sort_by = request_params.get('sort', '-play_count')
    cache_key = f"artist_detail_{artist.id}_v{version}_p{page_num}_s{sort_by}"
    
    cached_ids = cache.get(cache_key)
    if cached_ids:
        data = {
            'current_sort': cached_ids['current_sort'],
            'total_plays': cached_ids['total_plays'],
            'total_songs': cached_ids['total_songs'],
            'total_albums': cached_ids['total_albums'],
        }
        
        # 1. Albumy
        albums = list(Album.objects.filter(id__in=cached_ids['albums_ids']).order_by('-release_date'))
        data['albums'] = albums
        
        # 2. Piosenki (Strona)
        page_songs = list(Song.objects.filter(id__in=cached_ids['page_songs_ids']).select_related('album', 'album__artist').prefetch_related('featured_artists'))
        # Przywracamy sortowanie
        page_songs.sort(key=lambda x: cached_ids['page_songs_ids'].index(x.id))
        
        class PageMock:
            def __init__(self, items, has_next, has_prev, number, total_pages):
                self.object_list = items
                self.has_next_val = has_next
                self.has_previous_val = has_prev
                self.number = number
                self.paginator = type('PaginatorMock', (), {'num_pages': total_pages, 'per_page': 15})
            def has_next(self): return self.has_next_val
            def has_previous(self): return self.has_previous_val
            def has_other_pages(self): return self.has_next_val or self.has_previous_val
            def start_index(self): return (self.number - 1) * 15 + 1 if self.object_list else 0
            def __iter__(self): return iter(self.object_list)
            def __len__(self): return len(self.object_list)

        data['all_songs'] = PageMock(
            page_songs, 
            cached_ids['has_next'], 
            cached_ids['has_prev'], 
            int(page_num if str(page_num).isdigit() else 1),
            cached_ids['total_pages']
        )
        
        full_list = list(Song.objects.filter(id__in=cached_ids['all_songs_ids']).select_related('album', 'album__artist').prefetch_related('featured_artists'))
        full_list.sort(key=lambda x: cached_ids['all_songs_ids'].index(x.id))
        data['all_songs_full_list'] = full_list
        
        # 4. Top Songs
        top_songs = list(Song.objects.filter(id__in=cached_ids['top_songs_ids']).select_related('album', 'album__artist').prefetch_related('featured_artists'))
        top_songs.sort(key=lambda x: cached_ids['top_songs_ids'].index(x.id))
        data['top_songs'] = top_songs
        
        # 5. Appears on
        data['appears_on'] = Album.objects.filter(id__in=cached_ids['appears_on_ids']).select_related('artist').order_by('-release_date')
        
        playlist_duration_subquery = Song.objects.filter(
            playlists=OuterRef('pk')
        ).values('playlists').annotate(
            total=Sum('duration_sec')
        ).values('total')

        data['related_playlists'] = Playlist.objects.filter(
            id__in=cached_ids['related_playlists_ids']
        ).select_related(
            'owner', 'owner__profile'
        ).prefetch_related(
            'playlistposition_set__song__album',
            'playlistposition_set__song__album__artist'
        ).annotate(
            total_duration_db=Subquery(playlist_duration_subquery),
            songs_count=Count('songs', distinct=True),
            followers_count=Count('followed_by', distinct=True)
        )
        
        return data

    data = {}
    albums_qs = Album.objects.filter(artist=artist).order_by('-release_date')
    data['albums'] = albums_qs

    all_songs_qs = Song.objects.filter(
        album__artist=artist
    ).select_related('album', 'album__artist', 'album__artist__genre').prefetch_related('featured_artists')
    
    artist_song_ids = list(all_songs_qs.values_list('id', flat=True))
    
    allowed_sorts = [
        'title', '-title', 'play_count', '-play_count', 
        'duration_sec', '-duration_sec', 'id', '-id',
        'album__title', '-album__title'
    ]
    if sort_by in allowed_sorts:
        all_songs_qs = all_songs_qs.order_by(sort_by)
    else:
        all_songs_qs = all_songs_qs.order_by('-play_count')
    
    paginator = Paginator(all_songs_qs, 15)
    page_number = request_params.get('page')
    page_obj = paginator.get_page(page_number)
    
    data['all_songs'] = page_obj
    data['current_sort'] = sort_by

    cut_off_30 = timezone.now() - timedelta(days=30)
    top_songs_qs = Song.objects.filter(
        album__artist=artist,
        individual_plays__played_at__gte=cut_off_30
    ).select_related('album', 'album__artist').prefetch_related('featured_artists').annotate(
        recent_plays=Count('individual_plays')
    ).order_by('-recent_plays')[:5]
    
    if not top_songs_qs.exists():
        top_songs_qs = Song.objects.filter(album__artist=artist).select_related('album', 'album__artist').prefetch_related('featured_artists').order_by('-play_count')[:5]
    
    data['top_songs'] = list(top_songs_qs)

    stats = all_songs_qs.aggregate(
        total_plays_sum=Sum('play_count'),
        total_songs_count=Count('id')
    )
    data['total_plays'] = stats['total_plays_sum'] or 0
    data['total_songs'] = stats['total_songs_count'] or 0
    data['total_albums'] = albums_qs.count()
    
    appears_on_qs = Album.objects.filter(
        songs__featured_artists=artist
    ).select_related('artist').exclude(artist=artist).distinct().order_by('-release_date')
    data['appears_on'] = appears_on_qs

    playlist_duration_subquery = Song.objects.filter(
        playlists=OuterRef('pk')
    ).values('playlists').annotate(
        total=Sum('duration_sec')
    ).values('total')

    related_playlists_qs = Playlist.objects.filter(
        is_public=True,
        songs__id__in=artist_song_ids
    ).select_related(
        'owner', 'owner__profile'
    ).prefetch_related(
        'playlistposition_set__song__album',
        'playlistposition_set__song__album__artist'
    ).annotate(
        artist_songs_count=Count('songs', filter=Q(songs__id__in=artist_song_ids)),
        total_duration_db=Subquery(playlist_duration_subquery),
        songs_count=Count('songs', distinct=True),
        followers_count=Count('followed_by', distinct=True)
    ).order_by('-artist_songs_count').distinct()[:10]
    data['related_playlists'] = related_playlists_qs

    data['all_songs_full_list'] = list(all_songs_qs)

    cache_payload = {
        'current_sort': sort_by,
        'total_plays': data['total_plays'],
        'total_songs': data['total_songs'],
        'total_albums': data['total_albums'],
        'albums_ids': list(albums_qs.values_list('id', flat=True)),
        'all_songs_ids': list(all_songs_qs.values_list('id', flat=True)),
        'page_songs_ids': [s.id for s in page_obj.object_list],
        'has_next': page_obj.has_next(),
        'has_prev': page_obj.has_previous(),
        'total_pages': paginator.num_pages,
        'top_songs_ids': [s.id for s in data['top_songs']],
        'appears_on_ids': list(appears_on_qs.values_list('id', flat=True)),
        'related_playlists_ids': list(related_playlists_qs.values_list('id', flat=True)),
    }
    cache.set(cache_key, cache_payload, 600)
    return data

def get_album_list_queryset(request_params):
    """Zwraca przefiltrowany i posortowany QuerySet albumów."""
    album_duration_subquery = Song.objects.filter(
        album=OuterRef('pk')
    ).values('album').annotate(
        total=Sum('duration_sec')
    ).values('total')

    queryset = Album.objects.select_related('artist', 'artist__genre').annotate(
        total_duration_db=Subquery(album_duration_subquery),
        songs_count=Count('songs', distinct=True)
    ).all()
    query = request_params.get('q')
    artist_id = request_params.get('artist_id')
    genre_ids = request_params.getlist('genre')
    year = request_params.get('year')
    year_min = request_params.get('year_min')
    year_max = request_params.get('year_max')
    sort_by = request_params.get('sort', '-release_date')

    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(artist__nickname__icontains=query))
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
    
    featured_artist_id = request_params.get('featured_artist_id')
    if featured_artist_id:
        queryset = queryset.filter(songs__featured_artists__id=featured_artist_id).distinct()
    
    # Aliasy sortowania
    if sort_by == 'album': sort_by = 'title'
    elif sort_by == '-album': sort_by = '-title'
    elif sort_by == 'year': sort_by = 'release_date'
    elif sort_by == '-year': sort_by = '-release_date'

    allowed_sorts = ['-release_date', 'release_date', 'title', '-title', '-play_count', '-likes_count']
    
    if sort_by == '-play_count':
        time_range = request_params.get('time_range', 'all')
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

def get_song_list_queryset(request_params):
    """Zwraca przefiltrowany i posortowany QuerySet utworów."""
    queryset = Song.objects.select_related(
        'album', 'album__artist', 'album__artist__genre'
    ).prefetch_related('featured_artists').all()
    query = request_params.get('q')
    genre_ids = request_params.getlist('genre')
    year_min = request_params.get('year_min')
    year_max = request_params.get('year_max')
    sort_by = request_params.get('sort', '-play_count')

    if query and query.strip():
        queryset = queryset.filter(Q(title__icontains=query) | Q(album__artist__nickname__icontains=query))
    
    if genre_ids:
        genre_ids = [gid for gid in genre_ids if gid]
        if genre_ids:
            queryset = queryset.filter(album__artist__genre_id__in=genre_ids)
    
    if year_min and year_min.isdigit():
        queryset = queryset.filter(album__release_date__year__gte=year_min)
    if year_max and year_max.isdigit():
        queryset = queryset.filter(album__release_date__year__lte=year_max)
    
    if sort_by == 'album': sort_by = 'album__title'
    elif sort_by == '-album': sort_by = '-album__title'
    elif sort_by in ['year', 'release_date']: sort_by = 'album__release_date'
    elif sort_by in ['-year', '-release_date']: sort_by = '-album__release_date'

    allowed_sorts = ['title', '-title', 'play_count', '-play_count', 'id', '-id', '-likes_count', 'album__release_date', '-album__release_date', 'album__title', '-album__title']
    
    if sort_by == '-play_count':
        time_range = request_params.get('time_range', 'all')
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

def get_liked_songs_data(user, request_params):
    """Zbiera dane dla widoku polubionych utworów i albumów."""
    profile = user.profile
    data = {}
    
    # 1. Polubione utwory
    songs_list = LikedSong.objects.filter(profile=profile).select_related('song', 'song__album', 'song__album__artist')
    
    query = request_params.get('q')
    if query:
        songs_list = songs_list.filter(
            Q(song__title__icontains=query) |
            Q(song__album__artist__nickname__icontains=query) |
            Q(song__album__title__icontains=query)
        )
    
    sort_by = request_params.get('sort', 'order')
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
    
    data['all_liked_songs'] = songs_list
    
    album_duration_subquery = Song.objects.filter(
        album=OuterRef('pk')
    ).values('album').annotate(
        total=Sum('duration_sec')
    ).values('total')

    all_liked_albums = Album.objects.filter(
        liked_album_positions__profile=profile
    ).select_related('artist', 'artist__genre').annotate(
        total_duration_db=Subquery(album_duration_subquery),
        songs_count=Count('songs', distinct=True)
    ).order_by(
        'liked_album_positions__order', '-liked_album_positions__added_at'
    )
    
    if query:
        all_liked_albums = all_liked_albums.filter(
            Q(title__icontains=query) |
            Q(artist__nickname__icontains=query) |
            Q(artist__genre__name__icontains=query)
        ).distinct()
        
    per_page_a = request_params.get('per_page_a', '12')
    try:
        items_per_page_a = max(4, min(int(per_page_a), 60))
    except ValueError:
        items_per_page_a = 12
        
    paginator_a = Paginator(all_liked_albums, items_per_page_a)
    page_a_number = request_params.get('page_a')
    data['liked_albums_page'] = paginator_a.get_page(page_a_number)
    data['per_page_a'] = items_per_page_a

    return data
def get_album_detail_data(album, request_params):
    """Zbiera dane potrzebne do widoku detali albumu."""
    songs_qs = Song.objects.filter(
        album=album
    ).select_related('album', 'album__artist').prefetch_related('featured_artists')

    sort_by = request_params.get('sort', 'id')
    allowed_sorts = ['title', '-title', 'play_count', '-play_count', 'duration_sec', '-duration_sec', 'id', '-id']
    if sort_by in allowed_sorts:
        songs_qs = songs_qs.order_by(sort_by)
    else:
        songs_qs = songs_qs.order_by('id')
    
    # Inne utwory tego samego artysty (rekomendacje)
    other_artist_songs = Song.objects.filter(
        album__artist=album.artist
    ).exclude(
        album=album
    ).select_related('album', 'album__artist').prefetch_related('featured_artists')[:15]
    
    return {
        'songs': songs_qs,
        'current_sort': sort_by,
        'other_artist_songs': other_artist_songs
    }
