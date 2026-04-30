import random
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q, F
from ..models import Genre, Song, SongPlay, Artist, Album, Profile, Playlist
from ..utils import apply_cover_seed

def get_home_page_data(request, seed):
    """
    Zbiera wszystkie dane potrzebne do wyświetlenia strony głównej.
    Logika została uproszczona dzięki użyciu Custom Managers w modelach.
    """
    # 1. Trendy (Piosenki)
    period_of_days = 7
    trending_songs = Song.objects.trending(days=period_of_days)
    top_songs = trending_songs[:10]

    # 2. Top Artyści
    top_artists_qs = Artist.objects.top_by_plays(days=period_of_days, count=6)
    
    # Do określenia "poprzedniego zwycięzcy" nadal potrzebujemy logiki (lub kolejnej metody managera)
    cut_off_current = timezone.now() - timedelta(days=period_of_days)
    cut_off_previous_start = timezone.now() - timedelta(days=period_of_days * 2)
    
    previous_winner = Artist.objects.filter(
        albums__songs__individual_plays__played_at__gte=cut_off_previous_start,
        albums__songs__individual_plays__played_at__lt=cut_off_current
    ).annotate(
        total_plays=Count('albums__songs__individual_plays')
    ).order_by('-total_plays').first()

    top_artists_list = list(top_artists_qs)
    needed = 6 - len(top_artists_list)
    if needed > 0:
        existing_ids = [artist.id for artist in top_artists_list]
        random_artists = Artist.objects.exclude(id__in=existing_ids).order_by('?')[:needed]
        top_artists_list.extend(list(random_artists))
    
    # 3. Trending Artist
    trending_artist = None
    if top_artists_list:
        if previous_winner and top_artists_list[0].id == previous_winner.id and len(top_artists_list) > 1:
            trending_artist = top_artists_list[1]
        else:
            trending_artist = top_artists_list[0]
    else:
        latest_album = Album.objects.order_by('-release_date').first()
        if latest_album:
            trending_artist = latest_album.artist

    trending_artist_songs = []
    if trending_artist:
        trending_artist_songs = Song.objects.filter(
            album__artist=trending_artist
        ).select_related('album__artist').prefetch_related('featured_artists').order_by('-play_count')[:3]

    # 4. Discovery Songs
    top_10_artists_ids = trending_songs[:10].values_list('album__artist_id', flat=True)
    discovery_songs = Song.objects.filter(
        album__artist_id__in=top_10_artists_ids
    ).select_related('album__artist').prefetch_related('featured_artists').exclude(
        id__in=trending_songs[:10].values_list('id', flat=True)
    ).order_by('?')[:20]

    # 5. Featured Albums
    trending_albums = Album.objects.trending(days=period_of_days)
    trending_album_ids = list(trending_albums[:20].values_list('id', flat=True))
    
    if len(trending_album_ids) >= 5:
        selected_ids = random.sample(trending_album_ids, 5)
    else:
        needed = 5 - len(trending_album_ids)
        extra_album_ids = list(Album.objects.exclude(
            id__in=trending_album_ids
        ).order_by('-release_date')[:needed].values_list('id', flat=True))
        selected_ids = trending_album_ids + extra_album_ids
    
    final_featured = list(Album.objects.filter(id__in=selected_ids).select_related('artist').prefetch_related('songs'))
    random.shuffle(final_featured)
    featured_albums = final_featured[:5]

    # 6. Wróć do słuchania
    # ... (bez zmian)
    last_playback_obj = None
    last_playback_json = None
    if request.user.is_authenticated:
        last = request.user.profile.last_playback
        if last:
            obj_type = last.get('type')
            obj_id = last.get('id')
            song_id = last.get('song_id')
            
            try:
                if obj_type == 'album' and obj_id:
                    last_playback_obj = Album.objects.get(id=obj_id)
                elif obj_type == 'playlist' and obj_id:
                    last_playback_obj = Playlist.objects.get(id=obj_id)
                elif obj_type == 'artist' and obj_id:
                    last_playback_obj = Artist.objects.get(id=obj_id)
                elif obj_type == 'liked':
                    last_playback_obj = 'liked'
            except:
                last_playback_obj = None
            
            if not last_playback_obj and song_id:
                try:
                    last_playback_obj = Song.objects.get(id=song_id)
                except:
                    pass
            
            last_playback_json = last
            if last_playback_obj and hasattr(last_playback_obj, 'owner'):
                apply_cover_seed(last_playback_obj, seed)

    # 7. Community Playlists
    community_playlists = Playlist.objects.trending(days=period_of_days)[:5]
    
    if not community_playlists.exists():
        community_playlists = Playlist.objects.filter(is_public=True).select_related('owner__profile').prefetch_related(
            'playlistposition_set__song__album__artist'
        ).order_by('?')[:5]

    apply_cover_seed(community_playlists, seed)

    # 8. Rekomendacje (Może Ci się spodobać)
    followed_artists_songs = []
    liked_song_ids = []
    liked_album_ids = []
    
    if request.user.is_authenticated:
        profile = request.user.profile
        followed_artists = Artist.objects.filter(followers=profile)
        
        if followed_artists.exists():
            followed_artists_songs = Song.objects.filter(
                album__artist__in=followed_artists
            ).select_related('album', 'album__artist').order_by('-album__release_date', '-play_count')[:15]
        else:
            favorite_genres = SongPlay.objects.filter(user=request.user).values_list(
                'song__album__artist__genre', flat=True
            ).distinct()
            
            if favorite_genres:
                followed_artists_songs = Song.objects.filter(
                    album__artist__genre__id__in=favorite_genres
                ).select_related('album', 'album__artist').exclude(
                    individual_plays__user=request.user
                ).order_by('?')[:15]
            else:
                followed_artists_songs = Song.objects.all().select_related('album', 'album__artist').order_by('-play_count', '?')[:15]

        followed_artists_songs = list(followed_artists_songs)
        for i, s in enumerate(followed_artists_songs):
            s.suggest_queue_index = i
        
        liked_song_ids = list(profile.liked_songs.values_list('id', flat=True))
        liked_album_ids = list(profile.liked_albums.values_list('id', flat=True))

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
        'featured_album': Album.objects.select_related('artist').order_by('-release_date').first(),
        'latest_albums': Album.objects.select_related('artist').order_by('-release_date')[1:7],
        'genres': Genre.objects.order_by('?'),
        'followed_artists_songs': followed_artists_songs,
        'liked_song_ids': liked_song_ids,
        'liked_album_ids': liked_album_ids,
    }
