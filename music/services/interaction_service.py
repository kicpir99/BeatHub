import json
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from ..models import Song, Album, SongPlay, Artist, LikedSong, Playlist, LikedAlbum

def update_playback_state(user, data):
    """Zapisuje ostatni stan odtwarzania użytkownika."""
    profile = user.profile
    profile.last_playback = {
        'type': data.get('type'), # 'album', 'playlist', 'liked', 'artist', 'queue'
        'id': data.get('id'),
        'song_id': data.get('song_id'),
        'index': data.get('index', 0),
        'timestamp': timezone.now().isoformat()
    }
    profile.save(update_fields=['last_playback'])
    return True

@transaction.atomic
def toggle_song_like(user, song_id):
    """Przełącza polubienie utworu i synchronizuje status albumu."""
    song = Song.objects.get(id=song_id)
    profile = user.profile
    album = song.album
    
    is_liked = False
    if song in profile.liked_songs.all():
        profile.liked_songs.remove(song)
        song.likes_count = max(0, song.likes_count - 1)
        album.likes_count = max(0, album.likes_count - 1)
        profile.liked_albums.remove(album)
        album_liked_status = False
    else:
        profile.liked_songs.add(song)
        song.likes_count += 1 
        album.likes_count += 1
        is_liked = True
        
        all_songs_count = album.songs.count()
        user_liked_count = profile.liked_songs.filter(album=album).count()
        album_liked_status = (all_songs_count == user_liked_count)
        
        if album_liked_status:
            profile.liked_albums.add(album)
            
    song.save()
    album.save()
    
    message = "Dodano do ulubionych" if is_liked else "Usunięto z ulubionych"
    return {
        'is_liked': is_liked,
        'album_id': album.id,
        'album_liked': album_liked_status,
        'message': message
    }

@transaction.atomic
def toggle_album_like(user, album_id):
    """Przełącza polubienie albumu i wszystkich jego utworów."""
    album = get_object_or_404(Album, id=album_id)
    profile = user.profile
    songs = album.songs.all()
    
    is_liked = False
    if album in profile.liked_albums.all():
        profile.liked_albums.remove(album)
        songs_to_unlike = songs.filter(id__in=profile.liked_songs.values_list('id', flat=True))
        count = songs_to_unlike.count()
        if count > 0:
            profile.liked_songs.remove(*songs_to_unlike)
            songs_to_unlike.update(likes_count=F('likes_count') - 1)
            album.likes_count = F('likes_count') - count
        message = "Usunięto album z kolekcji"
    else:
        profile.liked_albums.add(album)
        songs_to_like = songs.exclude(id__in=profile.liked_songs.values_list('id', flat=True))
        count = songs_to_like.count()
        if count > 0:
            profile.liked_songs.add(*songs_to_like)
            songs_to_like.update(likes_count=F('likes_count') + 1)
            album.likes_count = F('likes_count') + count
        is_liked = True
        message = "Dodano album do kolekcji"
    
    album.save()
    return {
        'is_liked': is_liked, 
        'album_id': album.id,
        'song_ids': list(songs.values_list('id', flat=True)),
        'message': message
    }

@transaction.atomic
def bulk_toggle_likes(user, song_ids, action='like'):
    """Masowe polubienie lub odlubienie piosenek."""
    profile = user.profile
    songs = Song.objects.filter(id__in=song_ids)
    
    if action == 'like':
        songs_to_like = songs.exclude(id__in=profile.liked_songs.values_list('id', flat=True))
        count = songs_to_like.count()
        if count > 0:
            # Dodajemy wszystkie naraz do M2M
            profile.liked_songs.add(*songs_to_like)
            songs_to_like.update(likes_count=F('likes_count') + 1)
            message = f"Dodano {count} utworów do polubionych"
        else:
            message = "Wybrane utwory są już w polubionych"
    else:
        songs_to_unlike = songs.filter(id__in=profile.liked_songs.values_list('id', flat=True))
        count = songs_to_unlike.count()
        if count > 0:
            # Usuwamy wszystkie naraz z M2M
            profile.liked_songs.remove(*songs_to_unlike)
            songs_to_unlike.update(likes_count=F('likes_count') - 1)
            message = f"Usunięto {count} utworów z polubionych"
        else:
            message = "Wybrane utwory nie były w polubionych"
        
    return message

from django.core.cache import cache

@transaction.atomic
def record_song_play(user, song_id, duration, playlist_id=None):
    """Rejestruje odtworzenie utworu."""
    if user.is_authenticated:
        cache.delete(f"detailed_stats_{user.id}")
        now = timezone.now().date()
        start = (timezone.now() - timezone.timedelta(days=30)).date()
        cache.delete(f"profile_stats_{user.id}_{start}_{now}")
    song = Song.objects.select_related('album').get(id=song_id)
    
    # Zapisujemy odtworzenie
    SongPlay.objects.create(
        song=song,
        user=user if user.is_authenticated else None,
        playlist_id=playlist_id if playlist_id else None,
        listened_duration_sec=duration
    )

    if duration >= 10:
        Song.objects.filter(id=song_id).update(play_count=F('play_count') + 1)
        Album.objects.filter(id=song.album.id).update(play_count=F('play_count') + 1)
    
    return True

def toggle_artist_follow(user, artist_id):
    """Przełącza obserwowanie artysty."""
    artist = get_object_or_404(Artist, id=artist_id)
    profile = user.profile
    
    if artist.followers.filter(id=profile.id).exists():
        artist.followers.remove(profile)
        version_key = f"artist_v_{artist.id}"
        try:
            cache.incr(version_key)
        except ValueError:
            cache.set(version_key, 2, None)
            
        message = f"Nie obserwujesz już {artist.nickname}"
        is_following = False
    else:
        artist.followers.add(profile)
        version_key = f"artist_v_{artist.id}"
        try:
            cache.incr(version_key)
        except ValueError:
            cache.set(version_key, 2, None)
        
        message = f"Obserwujesz teraz {artist.nickname}"
        is_following = True
        
    return {
        'is_following': is_following,
        'message': message,
        'followers_count': artist.followers.count()
    }
@transaction.atomic
def reorder_liked_songs(user, position_ids, start_index=1):
    """Zmienia kolejność polubionych utworów użytkownika (Drag & Drop)."""
    profile = user.profile
    all_items = list(LikedSong.objects.filter(profile=profile).order_by('order', '-added_at'))
    item_map = {str(item.id): item for item in all_items}
    
    indices = [i for i, item in enumerate(all_items) if str(item.id) in position_ids]
    
    for new_pos_id, slot_idx in zip(position_ids, indices):
        if new_pos_id in item_map:
            all_items[slot_idx] = item_map[new_pos_id]
            
    to_update = []
    for i, item in enumerate(all_items):
        if item.order != i:
            item.order = i
            to_update.append(item)
            
    if to_update:
        LikedSong.objects.bulk_update(to_update, ['order'], batch_size=500)
        
    return True

@transaction.atomic
def reorder_liked_albums(user, album_ids, start_index=1):
    """Zmienia kolejność polubionych albumów użytkownika (Drag & Drop)."""
    profile = user.profile
    all_items = list(LikedAlbum.objects.filter(profile=profile).order_by('order', '-added_at'))
    item_map = {str(item.album_id): item for item in all_items}
    
    indices = [i for i, item in enumerate(all_items) if str(item.album_id) in album_ids]
    
    for new_alb_id, slot_idx in zip(album_ids, indices):
        if new_alb_id in item_map:
            all_items[slot_idx] = item_map[new_alb_id]
            
    to_update = []
    for i, item in enumerate(all_items):
        if item.order != i:
            item.order = i
            to_update.append(item)
            
    if to_update:
        LikedAlbum.objects.bulk_update(to_update, ['order'], batch_size=500)
        
    return True

@transaction.atomic
def toggle_user_follow(user, target_profile_id):
    """Przełącza obserwowanie innego użytkownika."""
    target_profile = get_object_or_404(Profile, id=target_profile_id)
    my_profile = user.profile
    
    if target_profile == my_profile:
        raise ValueError("Nie możesz obserwować samego siebie")
    
    if my_profile.following.filter(id=target_profile_id).exists():
        my_profile.following.remove(target_profile)
        is_following = False
        message = f'Przestałeś obserwować {target_profile.user.username}'
    else:
        my_profile.following.add(target_profile)
        is_following = True
        message = f'Obserwujesz teraz {target_profile.user.username}'
        
    return {
        'is_following': is_following,
        'message': message,
        'followers_count': target_profile.followers.count()
    }
