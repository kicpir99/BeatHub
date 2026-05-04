import random
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q, F, Sum, OuterRef, Subquery
from ..models import Genre, Song, SongPlay, Artist, Album, Profile, Playlist
from ..utils import apply_cover_seed
from . import playback_service

from django.core.cache import cache

def get_home_page_data(request, seed):
    """
    Zbiera wszystkie dane potrzebne do wyświetlenia strony głównej.
    Zoptymalizowane pod kątem keszowania (zapisujemy ID, nie obiekty).
    """
    period_of_days = 7
    cache_key = "home_page_trending_ids"
    cached_ids = cache.get(cache_key)
    
    if cached_ids:
        top_songs = list(Song.objects.filter(id__in=cached_ids['top_songs_ids']).select_related('album', 'album__artist').prefetch_related('featured_artists'))
        top_songs.sort(key=lambda x: cached_ids['top_songs_ids'].index(x.id))
        
        top_songs_ids = cached_ids['top_songs_ids']
        top_10_artists_ids = cached_ids['top_10_artists_ids']
        
        top_artists_list = list(Artist.objects.filter(id__in=cached_ids['top_artists_ids']))
        top_artists_list.sort(key=lambda x: cached_ids['top_artists_ids'].index(x.id))
        
        trending_artist = Artist.objects.filter(id=cached_ids['trending_artist_id']).first()
        trending_artist_songs = list(Song.objects.filter(id__in=cached_ids['trending_artist_songs_ids']).select_related('album', 'album__artist').prefetch_related('featured_artists'))
        
        album_duration_subquery = Song.objects.filter(
            album=OuterRef('pk')
        ).values('album').annotate(
            total=Sum('duration_sec')
        ).values('total')

        playlist_duration_subquery = Song.objects.filter(
            playlists=OuterRef('pk')
        ).values('playlists').annotate(
            total=Sum('duration_sec')
        ).values('total')

        featured_albums_pool = list(Album.objects.filter(
            id__in=cached_ids['featured_albums_ids']
        ).select_related('artist').annotate(
            total_duration_db=Subquery(album_duration_subquery),
            songs_count=Count('songs', distinct=True)
        ).prefetch_related('songs'))
        
        community_playlists = list(Playlist.objects.filter(
            id__in=cached_ids['community_playlists_ids']
        ).select_related('owner', 'owner__profile').prefetch_related(
            'playlistposition_set__song__album',
            'playlistposition_set__song__album__artist'
        ).annotate(
            total_duration_db=Subquery(playlist_duration_subquery),
            songs_count=Count('songs', distinct=True),
            followers_count=Count('followed_by', distinct=True)
        ))
    else:
        # 1. Trendy (Piosenki)
        trending_songs_qs = Song.objects.trending(days=period_of_days)
        top_songs = list(trending_songs_qs[:10])
        top_songs_ids = [s.id for s in top_songs]
        top_10_artists_ids = list(set(s.album.artist_id for s in top_songs))

        top_artists_qs = Artist.objects.top_by_plays(days=period_of_days, count=6)
        top_artists_list = list(top_artists_qs)
        
        needed_artists = 6 - len(top_artists_list)
        if needed_artists > 0:
            existing_ids = [artist.id for artist in top_artists_list]
            random_artists = Artist.objects.exclude(id__in=existing_ids).order_by('?')[:needed_artists]
            top_artists_list.extend(list(random_artists))
        
        top_artists_ids = [a.id for a in top_artists_list]

        # 3. Trending Artist
        cut_off_current = timezone.now() - timedelta(days=period_of_days)
        cut_off_previous_start = timezone.now() - timedelta(days=period_of_days * 2)
        
        previous_winner = Artist.objects.filter(
            albums__songs__individual_plays__played_at__gte=cut_off_previous_start,
            albums__songs__individual_plays__played_at__lt=cut_off_current
        ).annotate(
            total_plays=Count('albums__songs__individual_plays')
        ).order_by('-total_plays').first()

        if previous_winner and top_artists_list and top_artists_list[0].id == previous_winner.id and len(top_artists_list) > 1:
            trending_artist = top_artists_list[1]
        elif top_artists_list:
            trending_artist = top_artists_list[0]
        else:
            latest_album = Album.objects.select_related('artist').order_by('-release_date').first()
            trending_artist = latest_album.artist if latest_album else None

        trending_artist_songs = []
        if trending_artist:
            trending_artist_songs = list(Song.objects.filter(
                album__artist=trending_artist
            ).select_related('album', 'album__artist').prefetch_related('featured_artists').order_by('-play_count')[:3])

        trending_albums = Album.objects.trending(days=period_of_days)
        trending_album_ids = list(trending_albums[:20].values_list('id', flat=True))
        
        if len(trending_album_ids) < 20:
            needed = 20 - len(trending_album_ids)
            extra_album_ids = list(Album.objects.exclude(
                id__in=trending_album_ids
            ).order_by('-release_date')[:needed].values_list('id', flat=True))
            featured_albums_ids = trending_album_ids + extra_album_ids
        else:
            featured_albums_ids = trending_album_ids

        album_duration_subquery = Song.objects.filter(
            album=OuterRef('pk')
        ).values('album').annotate(
            total=Sum('duration_sec')
        ).values('total')

        featured_albums_pool = list(Album.objects.filter(
            id__in=featured_albums_ids
        ).select_related('artist').annotate(
            total_duration_db=Subquery(album_duration_subquery),
            songs_count=Count('songs', distinct=True)
        ).prefetch_related('songs'))
        
        # 6. Community Playlists
        community_playlists_qs = Playlist.objects.trending(days=period_of_days)[:5]
        community_playlists = list(community_playlists_qs)
        
        if not community_playlists:
            playlist_duration_subquery = Song.objects.filter(
                playlists=OuterRef('pk')
            ).values('playlists').annotate(
                total=Sum('duration_sec')
            ).values('total')

            community_playlists = list(Playlist.objects.filter(
                is_public=True
            ).select_related('owner', 'owner__profile').prefetch_related(
                'playlistposition_set__song__album',
                'playlistposition_set__song__album__artist'
            ).annotate(
                total_duration_db=Subquery(playlist_duration_subquery),
                songs_count=Count('songs', distinct=True),
                followers_count=Count('followed_by', distinct=True)
            ).order_by('?')[:5])

        # Zapisujemy TYLKO identyfikatory do cache
        cache.set(cache_key, {
            'top_songs_ids': top_songs_ids,
            'top_10_artists_ids': top_10_artists_ids,
            'top_artists_ids': top_artists_ids,
            'trending_artist_id': trending_artist.id if trending_artist else None,
            'trending_artist_songs_ids': [s.id for s in trending_artist_songs],
            'featured_albums_ids': [a.id for a in featured_albums_pool],
            'community_playlists_ids': [p.id for p in community_playlists]
        }, 3600)

    discovery_songs = Song.objects.filter(
        album__artist_id__in=top_10_artists_ids
    ).select_related('album', 'album__artist').prefetch_related('featured_artists').exclude(
        id__in=top_songs_ids
    ).order_by('?')[:20]

    featured_albums = list(featured_albums_pool)
    random.shuffle(featured_albums)
    featured_albums = featured_albums[:5]

    last_playback_obj = None
    last_playback_json = None
    if request.user.is_authenticated:
        last = request.user.profile.last_playback
        if last:
            obj_type = last.get('type')
            obj_id = last.get('id')
            song_id = last.get('song_id')
            
            last_playback_obj, _ = playback_service.get_playback_object(obj_type, obj_id, song_id)
            last_playback_json = last
            if last_playback_obj and hasattr(last_playback_obj, 'owner'):
                apply_cover_seed(last_playback_obj, seed)

    apply_cover_seed(community_playlists, seed)

    followed_artists_songs = []
    liked_song_ids = []
    liked_album_ids = []
    
    if request.user.is_authenticated:
        profile = request.user.profile
        followed_artists = Artist.objects.filter(followers=profile)
        
        if followed_artists.exists():
            followed_artists_songs = Song.objects.filter(
                album__artist__in=followed_artists
            ).select_related('album', 'album__artist').prefetch_related('featured_artists').order_by('-album__release_date', '-play_count')[:15]
        else:
            favorite_genres = SongPlay.objects.filter(user=request.user).values_list(
                'song__album__artist__genre', flat=True
            ).distinct()
            
            if favorite_genres:
                followed_artists_songs = Song.objects.filter(
                    album__artist__genre__id__in=favorite_genres
                ).select_related('album', 'album__artist').prefetch_related('featured_artists').exclude(
                    individual_plays__user=request.user
                ).order_by('?')[:15]
            else:
                followed_artists_songs = Song.objects.all().select_related('album', 'album__artist').prefetch_related('featured_artists').order_by('-play_count', '?')[:15]

        followed_artists_songs = list(followed_artists_songs)
        for i, s in enumerate(followed_artists_songs):
            s.suggest_queue_index = i
        
        liked_song_ids = list(profile.liked_songs.values_list('id', flat=True))
        liked_album_ids = list(profile.liked_albums.values_list('id', flat=True))

    album_duration_subquery = Song.objects.filter(
        album=OuterRef('pk')
    ).values('album').annotate(
        total=Sum('duration_sec')
    ).values('total')

    featured_album = Album.objects.select_related('artist').annotate(
        total_duration_db=Subquery(album_duration_subquery),
        songs_count=Count('songs', distinct=True)
    ).order_by('-release_date').first()

    latest_albums = Album.objects.select_related('artist').annotate(
        total_duration_db=Subquery(album_duration_subquery),
        songs_count=Count('songs', distinct=True)
    ).order_by('-release_date')[1:7]

    return {
        'top_songs': top_songs,
        'top_songs_json': [
            {
                'id': s.id,
                'url': s.audio_file.url if s.audio_file else "",
                'title': s.title,
                'artist': s.album.artist.nickname,
                'cover': s.album.cover.url if s.album.cover else "",
                'album_slug': s.album.slug
            } for s in top_songs
        ],
        'top_artists': top_artists_list,
        'trending_artist': trending_artist,
        'trending_artist_songs': trending_artist_songs,
        'trending_artist_songs_json': [
            {
                'id': s.id,
                'url': s.audio_file.url if s.audio_file else "",
                'title': s.title,
                'artist': s.album.artist.nickname,
                'cover': s.album.cover.url if s.album.cover else "",
                'album_slug': s.album.slug
            } for s in trending_artist_songs
        ],
        'featured_albums': featured_albums,
        'last_playback_obj': last_playback_obj,
        'last_playback_json': last_playback_json,
        'community_playlists': community_playlists,
        'queue_songs': list(top_songs[:30]) + list(discovery_songs),
        'chart_period': "tygodnia" if period_of_days == 7 else "miesiąca",
        'featured_album': featured_album,
        'latest_albums': latest_albums,
        'genres': Genre.objects.order_by('?'),
        'followed_artists_songs': followed_artists_songs,
        'liked_song_ids': liked_song_ids,
        'liked_album_ids': liked_album_ids,
    }

def get_discovery_songs(params):
    """
    Zwraca przefiltrowany zestaw utworów do trybu odkrywania.
    """
    genre_slugs_raw = params.getlist('genre')
    genre_slugs = []
    for gs in genre_slugs_raw:
        if gs:
            genre_slugs.extend(gs.split(','))
            
    year_from = params.get('year_from')
    year_to = params.get('year_to')
    
    queryset = Song.objects.select_related('album', 'album__artist', 'album__artist__genre').prefetch_related('featured_artists').annotate(
        artist_followers_count=Count('album__artist__followers', distinct=True)
    )
    
    # Filtrowanie po gatunkach
    if genre_slugs and 'all' not in genre_slugs:
        queryset = queryset.filter(album__artist__genre__slug__in=genre_slugs)
    
    # Filtrowanie po latach
    if year_from:
        queryset = queryset.filter(album__release_date__year__gte=year_from)
    if year_to:
        queryset = queryset.filter(album__release_date__year__lte=year_to)
        
    return queryset.order_by('?')[:15]
