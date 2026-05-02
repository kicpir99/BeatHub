from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Max, Q, Count, Sum, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from ..models import Playlist, Song, PlaylistPosition, FollowedPlaylist

def validate_playlist_data(playlist):
    """
    Wymusza walidację modelu Playlist.
    Zwraca (is_valid, error_message).
    """
    try:
        playlist.full_clean()
        return True, ""
    except ValidationError as e:
        msg = next(iter(e.message_dict.values()))[0]
        return False, msg

def toggle_playlist_follow(user, playlist_id):
    """Obserwuj lub przestań obserwować playlistę."""
    playlist = get_object_or_404(Playlist, id=playlist_id)
    profile = user.profile

    if playlist.owner == user:
        return False, "Nie możesz obserwować własnej playlisty", 0

    if profile.followed_playlists.filter(id=playlist_id).exists():
        profile.followed_playlists.remove(playlist)
        is_followed = False
        message = f'Przestałeś obserwować playlistę: {playlist.name}'
    else:
        profile.followed_playlists.add(playlist)
        is_followed = True
        message = f'Obserwujesz teraz playlistę: {playlist.name}'

    return True, message, {
        'is_followed': is_followed,
        'followers_count': playlist.followed_by.count()
    }

@transaction.atomic
def add_to_playlist(user, playlist_id=None, song_id=None, song_ids=None, new_name=None, is_public=False):
    """Dodaje utwór lub wiele utworów do playlisty lub tworzy nową."""
    if song_ids is None:
        song_ids = []
    
    if new_name:
        playlist = Playlist(name=new_name, owner=user, is_public=is_public)
        is_valid, error_msg = validate_playlist_data(playlist)
        if not is_valid:
            return False, error_msg, None
        playlist.save()
    else:
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=user)

    # Ujednolicamy do listy song_ids
    final_song_ids = []
    if song_id: final_song_ids.append(song_id)
    if song_ids: final_song_ids.extend(song_ids)
    
    final_song_ids = list(dict.fromkeys(final_song_ids))

    if final_song_ids:
        last_position = PlaylistPosition.objects.filter(playlist=playlist).order_by('-order').first()
        next_order = (last_position.order + 1) if last_position else 1
        
        existing_song_ids = set(PlaylistPosition.objects.filter(
            playlist=playlist, 
            song_id__in=final_song_ids
        ).values_list('song_id', flat=True))
        
        songs_to_add_objs = Song.objects.filter(id__in=final_song_ids).exclude(id__in=existing_song_ids)
        
        new_positions = []
        added_count = 0
        
        for song in songs_to_add_objs:
            new_positions.append(PlaylistPosition(
                playlist=playlist,
                song=song,
                order=next_order
            ))
            next_order += 1
            added_count += 1
            
        if new_positions:
            PlaylistPosition.objects.bulk_create(new_positions)
        
        if len(final_song_ids) == 1 and added_count == 0:
            return False, f'Utwór jest już na liście: {playlist.name}', None
        
        msg = f'Dodano {added_count} utworów do playlisty: {playlist.name}' if added_count > 1 else f'Dodano do playlisty: {playlist.name}'
        return True, msg, playlist

    return True, f'Utworzono playlistę: {playlist.name}', playlist

def remove_from_playlist(user, playlist_id, song_id):
    """Usuwa utwór z playlisty."""
    playlist = get_object_or_404(Playlist, id=playlist_id, owner=user)
    song = get_object_or_404(Song, id=song_id)
    PlaylistPosition.objects.filter(playlist=playlist, song=song).delete()
    return f'Usunięto z playlisty: {playlist.name}'

def bulk_remove_from_playlist(user, playlist_id, song_ids):
    """Masowe usuwanie utworów z playlisty."""
    playlist = get_object_or_404(Playlist, id=playlist_id, owner=user)
    PlaylistPosition.objects.filter(playlist=playlist, song_id__in=song_ids).delete()
    return f'Usunięto {len(song_ids)} utworów z playlisty {playlist.name}'

@transaction.atomic
def reorder_playlist(user, playlist_id, position_ids, start_index=1):
    """Zmienia kolejność utworów wewnątrz playlisty (Drag & Drop)."""
    playlist = get_object_or_404(Playlist, id=playlist_id, owner=user)
    
    all_items = list(PlaylistPosition.objects.filter(playlist=playlist).order_by('order', '-added_at'))
    item_map = {str(item.id): item for item in all_items}
    
    indices = [i for i, item in enumerate(all_items) if str(item.id) in position_ids]
    
    for new_pos_id, slot_idx in zip(position_ids, indices):
        if new_pos_id in item_map:
            all_items[slot_idx] = item_map[new_pos_id]
            
    to_update = []
    for i, item in enumerate(all_items):
        if item.order != i + 1:
            item.order = i + 1
            to_update.append(item)
            
    if to_update:
        PlaylistPosition.objects.bulk_update(to_update, ['order'], batch_size=500)
    
    return 'Kolejność została zapisana.'

@transaction.atomic
def copy_playlist(user, source_id, mode='new', target_id=None, new_name=None):
    """Kopiuje cudzą playlistę jako własną (do nowej lub istniejącej)."""
    original = get_object_or_404(Playlist, id=source_id)
    positions = original.playlistposition_set.all().select_related('song')

    if mode == 'existing' and target_id:
        target_playlist = get_object_or_404(Playlist, id=target_id, owner=user)
        last_pos = PlaylistPosition.objects.filter(playlist=target_playlist).order_by('-order').first()
        next_order = (last_pos.order + 1) if last_pos else 1
        
        existing_ids = set(PlaylistPosition.objects.filter(
            playlist=target_playlist,
            song__in=[pos.song for pos in positions]
        ).values_list('song_id', flat=True))
        
        new_positions = []
        added_count = 0
        for pos in positions:
            if pos.song_id not in existing_ids:
                new_positions.append(PlaylistPosition(
                    playlist=target_playlist, 
                    song=pos.song, 
                    order=next_order
                ))
                next_order += 1
                added_count += 1
        
        if new_positions:
            PlaylistPosition.objects.bulk_create(new_positions)
            
        return f'Dodano {added_count} utworów do playlisty {target_playlist.name}'
    else:
        final_name = new_name or f"Kopia - {original.name}"
        new_playlist = Playlist(name=final_name, owner=user, is_public=False)
        
        is_valid, error_msg = validate_playlist_data(new_playlist)
        if not is_valid:
            return False, error_msg
            
        new_playlist.save()
        
        # Optymalizacja: Bulk create dla nowej playlisty
        new_positions = [
            PlaylistPosition(playlist=new_playlist, song=pos.song, order=pos.order)
            for pos in positions
        ]
        PlaylistPosition.objects.bulk_create(new_positions)
        
        return f'Skopiowano playlistę jako: {new_playlist.name}'

def update_followed_order(user, orders):
    """Aktualizuje manualną kolejność obserwowanych playlist."""
    profile = user.profile
    for item in orders:
        p_id = item.get('id')
        new_order = item.get('order')
        FollowedPlaylist.objects.filter(profile=profile, playlist_id=p_id).update(order=new_order)
    return True

def get_community_playlists_queryset(user, params):
    """
    Zwraca przefiltrowany i posortowany QuerySet publicznych playlist społeczności.
    """
    base_condition = Q(is_public=True)
    visibility_condition = Q(owner__profile__visibility='public')
    
    if user.is_authenticated:
        following_ids = user.profile.following.values_list('id', flat=True)
        visibility_condition |= Q(
            owner__profile__visibility='followers',
            owner__profile__id__in=following_ids
        )
        visibility_condition |= Q(owner=user)
        
    playlist_duration_subquery = Song.objects.filter(
        playlists=OuterRef('pk')
    ).values('playlists').annotate(
        total=Sum('duration_sec')
    ).values('total')

    queryset = Playlist.objects.filter(base_condition & visibility_condition).annotate(
        songs_count=Count('songs', distinct=True),
        followers_count=Count('followed_by', distinct=True),
        total_duration_db=Coalesce(Subquery(playlist_duration_subquery), 0)
    )
    
    query = params.get('q')
    sort = params.get('sort', '-created_at')
    genre_ids = params.getlist('genre')
    s_min = params.get('s_min')
    s_max = params.get('s_max')
    d_min = params.get('d_min')
    d_max = params.get('d_max')

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) | 
            Q(owner__username__icontains=query) |
            Q(songs__album__artist__nickname__icontains=query) |
            Q(songs__title__icontains=query)
        ).distinct()

    if genre_ids:
        queryset = queryset.filter(songs__album__artist__genre_id__in=genre_ids).distinct()

    if s_min: queryset = queryset.filter(songs_count__gte=s_min)
    if s_max: queryset = queryset.filter(songs_count__lte=s_max)
    
    if d_min: queryset = queryset.filter(total_duration_db__gte=int(d_min) * 60)
    if d_max: queryset = queryset.filter(total_duration_db__lte=int(d_max) * 60)

    if sort == '-recent_plays_count':
        time_range = params.get('time_range', 'all')
        if time_range == 'week':
            cut_off = timezone.now() - timedelta(days=7)
            queryset = queryset.annotate(
                range_plays=Count('playlist_plays__user', filter=Q(playlist_plays__played_at__gte=cut_off), distinct=True)
            ).order_by('-range_plays', '-created_at')
        elif time_range == 'month':
            cut_off = timezone.now() - timedelta(days=30)
            queryset = queryset.annotate(
                range_plays=Count('playlist_plays__user', filter=Q(playlist_plays__played_at__gte=cut_off), distinct=True)
            ).order_by('-range_plays', '-created_at')
        else:
            queryset = queryset.annotate(
                total_plays=Count('playlist_plays__user', distinct=True)
            ).order_by('-total_plays', '-created_at')
    elif sort == '-songs_count':
        queryset = queryset.order_by('-songs_count', '-created_at')
    elif sort == '-followers_count':
        queryset = queryset.order_by('-followers_count', '-created_at')
    elif sort == '-duration':
        queryset = queryset.order_by('-total_duration_db', '-created_at')
    elif sort == 'name':
        queryset = queryset.order_by('name')
    else:
        queryset = queryset.order_by('-created_at')

    return queryset
def get_playlist_detail_data(playlist, request_params):
    """
    Pobiera i filtruje utwory wewnątrz konkretnej playlisty.
    """
    all_positions = playlist.playlistposition_set.select_related(
        'song', 'song__album', 'song__album__artist'
    )
    
    query = request_params.get('q')
    if query:
        all_positions = all_positions.filter(
            Q(song__title__icontains=query) |
            Q(song__album__artist__nickname__icontains=query) |
            Q(song__album__title__icontains=query)
        )
    
    sort_by = request_params.get('sort', 'order')
    allowed_sorts = [
        'song__title', '-song__title', 
        'song__play_count', '-song__play_count', 
        'song__duration_sec', '-song__duration_sec', 
        'order', '-order', 
        'added_at', '-added_at',
        'song__album__title', '-song__album__title',
        'song__album__artist__genre__name', '-song__album__artist__genre__name'
    ]
    
    if sort_by in allowed_sorts:
        all_positions = all_positions.order_by(sort_by)
    else:
        all_positions = all_positions.order_by('order')
        
    return {
        'all_positions': all_positions,
        'current_sort': sort_by,
        'query': query or ''
    }

def get_community_playlist_context():
    """
    Oblicza limity i statystyki dla widoku playlist społeczności.
    """
    duration_subquery = Song.objects.filter(
        playlists=OuterRef('pk')
    ).values('playlists').annotate(
        total=Sum('duration_sec')
    ).values('total')

    qs = Playlist.objects.filter(is_public=True).annotate(
        s_count=Count('songs', distinct=True),
        t_dur=Subquery(duration_subquery)
    )
    
    stats = qs.aggregate(
        max_s=Max('s_count'),
        max_d=Max('t_dur')
    )
    
    max_songs_limit = stats['max_s'] or 100
    max_duration_limit = (stats['max_d'] // 60) + 1 if stats['max_d'] else 180
    
    return {
        'max_songs_limit': max_songs_limit,
        'max_duration_limit': max_duration_limit
    }
