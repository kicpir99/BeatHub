import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.templatetags.static import static
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import F

from ..models import Song, Album, SongPlay, Artist, LikedSong, Playlist, LikedAlbum
from ..utils import update_cover_seed, apply_cover_seed

@login_required
@require_POST
def save_playback_state(request):
    try:
        data = json.loads(request.body)
        profile = request.user.profile
        profile.last_playback = {
            'type': data.get('type'), # 'album', 'playlist', 'liked', 'artist', 'queue'
            'id': data.get('id'),
            'song_id': data.get('song_id'),
            'index': data.get('index', 0),
            'timestamp': timezone.now().isoformat()
        }
        profile.save(update_fields=['last_playback'])
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def toggle_like_ajax(request):
    try:
        data = json.loads(request.body)
        song_id = data.get('song_id')
        song = Song.objects.get(id=song_id)
        profile = request.user.profile
        album = song.album

        if song in profile.liked_songs.all():
            profile.liked_songs.remove(song)
            song.likes_count = max(0, song.likes_count - 1)
            album.likes_count = max(0, album.likes_count - 1)
            is_liked = False
            message = "Usunięto z ulubionych"
            profile.liked_albums.remove(album)
            album_liked_status = False
        else:
            profile.liked_songs.add(song)
            song.likes_count += 1 
            album.likes_count += 1
            is_liked = True
            message = "Dodano do ulubionych"
            all_songs_ids = set(album.songs.values_list('id', flat=True))
            user_liked_ids = set(profile.liked_songs.filter(album=album).values_list('id', flat=True))
            album_liked_status = False
            if all_songs_ids == user_liked_ids:
                profile.liked_albums.add(album)
                album_liked_status = True
        
        song.save()
        album.save()
        return JsonResponse({
            'status': 'success',
            'is_liked': is_liked,
            'album_id': album.id,
            'album_liked': album_liked_status,
            'message': "Zaktualizowano ulubione"
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Wystąpił błąd.'})

@login_required
@require_POST
def toggle_album_like_ajax(request):
    try:
        data = json.loads(request.body)
        album_id = data.get('album_id')
        album = get_object_or_404(Album, id=album_id)
        profile = request.user.profile
        songs = album.songs.all()
        
        if album in profile.liked_albums.all():
            profile.liked_albums.remove(album)
            for s in songs:
                if s in profile.liked_songs.all():
                    profile.liked_songs.remove(s)
                    s.likes_count = max(0, s.likes_count - 1)
                    album.likes_count = max(0, album.likes_count - 1)
                    s.save()
            is_liked = False
            message = "Usunięto album z kolekcji"
        else:
            profile.liked_albums.add(album)
            for s in songs:
                if s not in profile.liked_songs.all():
                    profile.liked_songs.add(s)
                    s.likes_count += 1
                    album.likes_count += 1
                    s.save()
            is_liked = True
            message = "Dodano album do kolekcji"
        
        album.save()
        return JsonResponse({
            'status': 'success', 
            'is_liked': is_liked, 
            'album_id': album.id,
            'song_ids': list(songs.values_list('id', flat=True)),
            'message': message
        })
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Błąd.'})

@login_required
@require_POST
def bulk_toggle_like_ajax(request):
    """Masowe polubienie lub odlubienie piosenek."""
    try:
        data = json.loads(request.body)
        song_ids = data.get('song_ids', [])
        action = data.get('action', 'like') # 'like' lub 'unlike'
        profile = request.user.profile
        
        songs = Song.objects.filter(id__in=song_ids)
        if action == 'like':
            for song in songs:
                if song not in profile.liked_songs.all():
                    profile.liked_songs.add(song)
                    song.likes_count += 1
                    song.save()
            message = f"Dodano {songs.count()} utworów do polubionych"
        else:
            for song in songs:
                if song in profile.liked_songs.all():
                    profile.liked_songs.remove(song)
                    song.likes_count = max(0, song.likes_count - 1)
                    song.save()
            message = f"Usunięto {songs.count()} utworów z polubionych"
            
        return JsonResponse({'status': 'success', 'message': message})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@require_POST
def track_play_ajax(request):
    """Zwiększa licznik odtworzeń utworu i albumu oraz zapisuje czas słuchania"""
    try:
        data = json.loads(request.body)
        song_id = data.get('song_id')
        playlist_id = data.get('playlist_id')
        duration = int(data.get('duration', 0))
        
        song = Song.objects.select_related('album').get(id=song_id)
        
        # Zapisujemy odtworzenie z rzeczywistym czasem
        SongPlay.objects.create(
            song=song,
            user=request.user if request.user.is_authenticated else None,
            playlist_id=playlist_id,
            listened_duration_sec=duration
        )

        # Inkrementujemy liczniki tylko jeśli przesłuchano min. 10 sekund
        if duration >= 10:
            Song.objects.filter(id=song_id).update(play_count=F('play_count') + 1)
            Album.objects.filter(id=song.album.id).update(play_count=F('play_count') + 1)

        return JsonResponse({'status': 'success'})
    except Exception as e:
        print(f"Błąd odtwarzania utworu: {e}") 
        return JsonResponse({'status': 'error'}, status=400)

@login_required
@require_POST
def toggle_artist_follow_ajax(request):
    """Widok AJAX do obserwowania/przestania obserwowania artysty."""
    try:
        data = json.loads(request.body)
        artist_id = data.get('artist_id')
        artist = get_object_or_404(Artist, id=artist_id)
        profile = request.user.profile
        
        if artist.followers.filter(id=profile.id).exists():
            artist.followers.remove(profile)
            action = 'unfollowed'
        else:
            artist.followers.add(profile)
            action = 'followed'
            
        return JsonResponse({
            'status': 'success',
            'action': action,
            'followers_count': artist.followers.count()
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def reorder_liked_songs_ajax(request):
    """Widok AJAX do zmiany kolejności polubionych utworów użytkownika."""
    try:
        data = json.loads(request.body)
        position_ids = data.get('position_ids', [])
        
        profile = request.user.profile
        # Pobieramy obiekty LikedSong należące do użytkownika
        liked_positions = LikedSong.objects.filter(profile=profile, id__in=position_ids)
        liked_map = {str(lp.id): lp for lp in liked_positions}
        
        to_update = []
        for index, pos_id in enumerate(position_ids):
            lp = liked_map.get(str(pos_id))
            if lp:
                lp.order = index
                to_update.append(lp)
        
        if to_update:
            LikedSong.objects.bulk_update(to_update, ['order'])
            
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def search_autocomplete_ajax(request):
    """Widok zwracający podpowiedzi wyszukiwania (artystów, albumy, utwory) w formacie JSON."""
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'artists': [], 'albums': [], 'songs': []})

    artists = Artist.objects.filter(nickname__icontains=query)[:3]
    albums = Album.objects.filter(title__icontains=query).select_related('artist')[:3]
    songs = Song.objects.filter(title__icontains=query).select_related('album', 'album__artist')[:4]

    data = {
        'artists': [{
            'id': a.id,
            'name': a.nickname,
            'photo': a.photo.url if a.photo else static('images/default_artist.png'),
            'url': reverse('music:artist_detail', args=[a.slug])
        } for a in artists],
        'albums': [{
            'id': a.id,
            'title': a.title,
            'artist': a.artist.nickname,
            'cover': a.cover.url if a.cover else static('images/default_album.png'),
            'url': reverse('music:album_detail', args=[a.slug])
        } for a in albums],
        'songs': [{
            'id': s.id,
            'title': s.title,
            'artist': s.album.artist.nickname,
            'cover': s.album.cover.url if s.album and s.album.cover else static('images/default_album.png'),
            'url': reverse('music:album_detail', args=[s.album.slug]) + f"?play={s.id}"
        } for s in songs]
    }
    return JsonResponse(data)

def get_context_songs_ajax(request):
    """
    Zwraca listę utworów dla podanego kontekstu (album, playlista, artysta, polubione) w formacie JSON.
    Wykorzystywane do natychmiastowego wznawiania odtwarzania bez przeładowania strony.
    """
    c_type = request.GET.get('type')
    c_id = request.GET.get('id')
    
    songs_list = []
    songs = []
    
    try:
        if c_type == 'album' and c_id:
            try:
                album = Album.objects.select_related('artist').get(id=c_id)
                songs = Song.objects.filter(album=album).select_related('album', 'album__artist').prefetch_related('featured_artists').order_by('id')
            except (Album.DoesNotExist, ValueError):
                pass
        elif c_type == 'playlist' and c_id:
            try:
                playlist = Playlist.objects.get(id=c_id)
                positions = playlist.playlistposition_set.select_related('song', 'song__album', 'song__album__artist').prefetch_related('song__featured_artists').all().order_by('order')
                songs = [pos.song for pos in positions]
            except (Playlist.DoesNotExist, ValueError):
                pass
        elif c_type == 'artist' and c_id:
            try:
                artist = Artist.objects.get(id=c_id)
                songs = Song.objects.filter(album__artist=artist).select_related('album', 'album__artist').prefetch_related('featured_artists').order_by('-play_count')[:15]
            except (Artist.DoesNotExist, ValueError):
                pass
        elif c_type == 'liked':
            if request.user.is_authenticated:
                positions = request.user.profile.liked_positions.select_related('song', 'song__album', 'song__album__artist').prefetch_related('song__featured_artists').all().order_by('order', '-added_at')
                songs = [pos.song for pos in positions]
            else:
                return JsonResponse({'status': 'error', 'message': 'Użytkownik nie jest zalogowany'}, status=401)
                
        # Fallback do pojedynczego utworu
        if not songs:
            song_id = request.GET.get('song_id')
            if song_id:
                try:
                    songs = [Song.objects.select_related('album', 'album__artist').prefetch_related('featured_artists').get(id=song_id)]
                except (Song.DoesNotExist, ValueError):
                    pass

        if not songs:
            return JsonResponse({'status': 'error', 'message': 'Nie znaleziono utworów dla podanego kontekstu'}, status=404)

        for s in songs:
            try:
                # Przygotowanie listy artystów gościnnych
                featured = [
                    {'nickname': a.nickname, 'slug': a.slug} 
                    for a in s.featured_artists.all()
                ]
                
                songs_list.append({
                    'id': s.id,
                    'title': s.title,
                    'artist': s.album.artist.nickname if s.album and s.album.artist else "Nieznany",
                    'artist_slug': s.album.artist.slug if s.album and s.album.artist else "",
                    'featured_artists': featured,
                    'url': s.audio_file.url if s.audio_file else "",
                    'cover': s.album.cover.url if s.album and s.album.cover else '',
                    'album_slug': s.album.slug if s.album else "unknown",
                    'album_id': s.album.id if s.album else None,
                    'playlist_id': c_id if c_type == 'playlist' else None,
                })
            except Exception:
                continue # Pomiń utwór z błędem danych
            
        return JsonResponse({'status': 'success', 'songs': songs_list})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def get_resume_section_ajax(request):
    """
    Renderuje i zwraca HTML sekcji 'Wróć do słuchania'.
    Umożliwia dynamiczne odświeżanie tej sekcji na stronie głównej.
    """
    if not request.user.is_authenticated:
        return HttpResponse('')
        
    last = request.user.profile.last_playback
    playback_obj = None
    
    if last:
        obj_type = last.get('type')
        obj_id = last.get('id')
        song_id = last.get('song_id')
        
        try:
            if obj_type == 'album' and obj_id:
                playback_obj = Album.objects.get(id=obj_id)
            elif obj_type == 'playlist' and obj_id:
                playback_obj = Playlist.objects.get(id=obj_id)
            elif obj_type == 'artist' and obj_id:
                playback_obj = Artist.objects.get(id=obj_id)
            elif obj_type == 'liked':
                playback_obj = 'liked'
        except:
            playback_obj = None
        
        if not playback_obj and song_id:
            try:
                playback_obj = Song.objects.get(id=song_id)
            except:
                pass
                
    seed = update_cover_seed(request)
    if playback_obj and hasattr(playback_obj, 'owner'):
        apply_cover_seed(playback_obj, seed)

    return render(request, 'music/partials/resume_section.html', {
        'last_playback_obj': playback_obj,
        'last_playback_json': last,
        'is_ajax': True
    })
@login_required
@require_POST
def reorder_liked_albums_ajax(request):
    """Widok AJAX do zmiany kolejności polubionych albumów użytkownika."""
    try:
        data = json.loads(request.body)
        album_ids = data.get('album_ids', [])
        
        profile = request.user.profile
        # Pobieramy obiekty LikedAlbum należące do użytkownika
        liked_positions = LikedAlbum.objects.filter(profile=profile, album_id__in=album_ids)
        liked_map = {str(la.album_id): la for la in liked_positions}
        
        to_update = []
        for index, alb_id in enumerate(album_ids):
            la = liked_map.get(str(alb_id))
            if la:
                la.order = index
                to_update.append(la)
        
        if to_update:
            LikedAlbum.objects.bulk_update(to_update, ['order'])
            
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
