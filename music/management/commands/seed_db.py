import random
import requests 
import os
import glob
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction 
from django.conf import settings 
from django.contrib.auth.models import User
from faker import Faker
from music.models import Genre, Artist, Album, Song, SongPlay, Playlist, PlaylistPosition, Profile, LikedSong, FollowedPlaylist
from mutagen.mp3 import MP3
from mutagen import File as MutagenFile

class Command(BaseCommand):
    help = 'Seeder z diagnostyką czasu trwania'

    def _download_image(self, width, height, prefix, keyword=None):
        try:
            url = f"https://source.unsplash.com/featured/{width}x{height}/?{keyword}" if keyword else f"https://picsum.photos/{width}/{height}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return ContentFile(response.content, name=f"{prefix}_{random.randint(1,100000)}.jpg")
        except:
            try:
                response = requests.get(f"https://picsum.photos/{width}/{height}", timeout=5)
                if response.status_code == 200:
                    return ContentFile(response.content, name=f"{prefix}_fb_{random.randint(1,100000)}.jpg")
            except: return None
        return None

    def _get_local_genre_image(self, genre_name):
        for ext in ['.png', '.jpg', '.jpeg']:
            path = os.path.join(settings.MEDIA_ROOT, 'genres', f"{genre_name}{ext}")
            if os.path.exists(path):
                with open(path, 'rb') as f: return ContentFile(f.read(), name=f"{genre_name}{ext}")
        return None

    def _get_audio_templates(self):
        songs_dir = os.path.join(settings.MEDIA_ROOT, 'songs')
        all_files = glob.glob(os.path.join(songs_dir, "*.mp3"))
        templates = [f for f in all_files if not os.path.basename(f).startswith(('s_', 'song_'))]
        self.stdout.write(f"Zaleziono {len(templates)} oryginalnych szablonów audio.")
        return templates

    def _get_duration(self, file_path):
        if not file_path: return random.randint(120, 240)
        try:
            audio = MP3(file_path)
            if audio.info is not None: return int(audio.info.length)
            
            audio = MutagenFile(file_path)
            if audio and audio.info: return int(audio.info.length)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Błąd Mutagen dla {os.path.basename(file_path)}: {e}"))
        return random.randint(120, 240)

    def handle(self, *args, **kwargs):
        if not settings.DEBUG: return 
                
        SUPPORTED_LANGUAGES = {'pl': 'pl_PL', 'en': 'en_US', 'es': 'es_ES', 'fr': 'fr_FR', 'de': 'de_DE', 'it': 'it_IT'}
        fakers = {lang: Faker(loc) for lang, loc in SUPPORTED_LANGUAGES.items()}

        self.stdout.write(self.style.WARNING('Czyszczenie...'))
        PlaylistPosition.objects.all().delete()
        FollowedPlaylist.objects.all().delete()
        LikedSong.objects.all().delete()
        Playlist.objects.all().delete()
        SongPlay.objects.all().delete()
        Song.objects.all().delete()
        Album.objects.all().delete()
        Artist.objects.all().delete()
        Genre.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

        audio_templates = self._get_audio_templates()
        if not audio_templates:
            self.stdout.write(self.style.ERROR('ALARM: Brak plików MP3 w media/songs!'))

        GENRES_CONFIG = {
            'Rock': 'rock-music', 'Pop': 'pop-music', 'Hip-Hop': 'hip-hop', 'Jazz': 'jazz',
            'Elektronika': 'techno', 'Klasyka': 'orchestra', 'Metal': 'heavy-metal',
            'Blues': 'blues', 'Reggae': 'reggae', 'Country': 'country-music', 'Indie': 'indie-rock'
        }
        
        NUM_ARTISTS, NUM_ALBUMS, NUM_SONGS, NUM_USERS, NUM_PLAYLISTS = 40, 80, 500, 15, 25

        # Obrazki
        genres_to_dl, genre_local_images = {}, {}
        for name, kw in GENRES_CONFIG.items():
            local = self._get_local_genre_image(name)
            if local: genre_local_images[name] = local
            else: genres_to_dl[name] = kw

        self.stdout.write('Pobieranie obrazków...')
        dl_genre_names = list(genres_to_dl.keys())
        tasks = [(600,400,"genre",genres_to_dl[n]) for n in dl_genre_names] + \
                [(400,400,"artist",None) for _ in range(NUM_ARTISTS)] + \
                [(500,500,"album",None) for _ in range(NUM_ALBUMS)] + \
                [(300,300,"avatar",None) for _ in range(NUM_USERS)]
        
        downloaded = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._download_image, *t) for t in tasks]
            for f in futures: downloaded.append(f.result())

        curr = 0
        genre_dl_map = {n: downloaded[curr+i] for i, n in enumerate(dl_genre_names)}; curr += len(dl_genre_names)
        artist_imgs = downloaded[curr : curr + NUM_ARTISTS]; curr += NUM_ARTISTS
        album_imgs = downloaded[curr : curr + NUM_ALBUMS]; curr += NUM_ALBUMS
        user_imgs = downloaded[curr : curr + NUM_USERS]

        try:
            with transaction.atomic():
                self.stdout.write('Generowanie Gatunków...')
                genre_objs = []
                for name in GENRES_CONFIG.keys():
                    img = genre_local_images.get(name) or genre_dl_map.get(name)
                    genre_objs.append(Genre.objects.create(name=name, image=img))

                self.stdout.write('Tworzenie Artystów...')
                artist_data = []
                for i in range(NUM_ARTISTS):
                    lang = random.choice(list(fakers.keys()))
                    fake = fakers[lang]
                    pl_fake = fakers['pl']
                    bio = pl_fake.paragraph(nb_sentences=random.randint(3, 8)) if random.random() < 0.8 else ""
                    artist = Artist.objects.create(
                        nickname=f"{fake.first_name()} {fake.last_name()}",
                        genre=random.choice(genre_objs),
                        photo=artist_imgs[i],
                        bio=bio
                    )
                    artist_data.append({'obj': artist, 'lang': lang})

                self.stdout.write('Tworzenie Albumów...')
                producer_names = [f"{fakers['en'].first_name()} {fakers['en'].last_name()}" for _ in range(20)]
                album_data = []
                for i in range(NUM_ALBUMS):
                    a_dict = random.choice(artist_data)
                    fake = fakers[a_dict['lang']]
                    produced_by = random.choice(producer_names) if random.random() < 0.7 else None
                    album = Album.objects.create(
                        title=" ".join(fake.words(nb=random.randint(1,3))).title(),
                        artist=a_dict['obj'],
                        cover=album_imgs[i],
                        release_date=fake.date_between(start_date='-20y'),
                        produced_by=produced_by
                    )
                    album_data.append({'obj': album, 'lang': a_dict['lang']})

                self.stdout.write('Tworzenie Piosenek i Audio...')
                all_songs = []
                now = timezone.now()
                for i in range(NUM_SONGS):
                    alb_dict = random.choice(album_data)
                    fake = fakers[alb_dict['lang']]
                    
                    template = random.choice(audio_templates) if audio_templates else None
                    duration = self._get_duration(template)

                    song = Song(
                        title=" ".join(fake.words(nb=random.randint(1, 4))).title(),
                        duration_sec=duration,
                        album=alb_dict['obj'],
                        play_count=random.randint(50, 5000)
                    )
                    song.save()
                    all_songs.append(song)

                    if template:
                        with open(template, 'rb') as f:
                            song.audio_file.save(f"song_{song.id}.mp3", ContentFile(f.read()), save=False)
                        
                        Song.objects.filter(pk=song.pk).update(duration_sec=duration)
                        song.save()

                    if random.random() < 0.2:
                        song.featured_artists.add(*random.sample([d['obj'] for d in artist_data if d['obj'].id != alb_dict['obj'].artist.id], random.randint(1,2)))

                self.stdout.write('Użytkownicy i Społeczność...')
                user_objs = []
                for i in range(NUM_USERS):
                    fake = fakers[random.choice(list(fakers.keys()))]
                    user = User.objects.create_user(username=fake.user_name()+str(random.randint(1,99)), password='password123', email=fake.email())
                    p = user.profile
                    p.bio, p.location = fake.text(max_nb_chars=200), fake.city()
                    
                    p.visibility = random.choice(['public', 'followers', 'private'])
                    p.show_profile_stats_publicly = random.choice([True, False])
                    p.show_detailed_stats_publicly = random.choice([True, False])
                    
                    if random.random() < 0.7: p.instagram_url = f"https://instagram.com/{fake.user_name()}"
                    if random.random() < 0.6: p.twitter_url = f"https://x.com/{fake.user_name()}"
                    if random.random() < 0.5: p.website_url = fake.url()
                    
                    p.gender = random.choice(['M', 'F', 'O'])
                    
                    # Losowa ostatnia aktywność (od kilku minut do kilku tygodni temu)
                    activity_ago = random.choice([
                        timedelta(minutes=random.randint(1, 4)),     # online
                        timedelta(minutes=random.randint(10, 59)),   # niedawno
                        timedelta(hours=random.randint(1, 23)),      # dziś
                        timedelta(days=random.randint(1, 7)),        # ten tydzień
                        timedelta(days=random.randint(8, 30)),       # dawniej
                    ])
                    p.last_activity = now - activity_ago
                    
                    # Losowe dane ostatniego odtwarzania dla sekcji "Wznów"
                    if random.random() < 0.6 and all_songs:
                        resume_song = random.choice(all_songs)
                        p.last_playback = {
                            'song_id': str(resume_song.id),
                            'song_title': resume_song.title,
                            'artist': resume_song.album.artist.nickname,
                            'cover': resume_song.album.cover.url if resume_song.album.cover else '',
                            'position': random.randint(10, max(11, resume_song.duration_sec - 30)),
                        }
                    
                    if random.random() < 0.6: p.avatar = user_imgs[i]
                    p.save()
                    user_objs.append(user)

                self.stdout.write('Generowanie relacji obserwowania (Użytkownicy i Artyści)...')
                all_artist_objs = [d['obj'] for d in artist_data]
                for user in user_objs:
                    # Obserwowanie innych użytkowników
                    other_users = [u for u in user_objs if u != user]
                    targets = random.sample(other_users, min(len(other_users), random.randint(2, 8)))
                    user.profile.following.add(*[t.profile for t in targets])
                    
                    # Obserwowanie artystów (nowe!)
                    fav_artists = random.sample(all_artist_objs, random.randint(3, 12))
                    for artist in fav_artists:
                        artist.followers.add(user.profile)

                self.stdout.write('Playlisty i Polubienia...')
                playlist_objs = []
                for i in range(NUM_PLAYLISTS):
                    fake = fakers[random.choice(list(fakers.keys()))]
                    # Szansa na opis (nowe!)
                    desc = fake.paragraph(nb_sentences=2) if random.random() > 0.4 else ""
                    playlist = Playlist.objects.create(
                        name=fake.catch_phrase(), 
                        description=desc,
                        owner=random.choice(user_objs), 
                        is_public=random.random() < 0.8  # 80% publicznych, 20% prywatnych
                    )
                    for idx, s in enumerate(random.sample(all_songs, random.randint(5, 20))):
                        PlaylistPosition.objects.create(playlist=playlist, song=s, order=idx)
                    playlist_objs.append(playlist)

                self.stdout.write('Generowanie historii odtworzeń (SongPlay) - rozpiętość 3 lata...')
                plays = []
                # Zwiększamy liczbę odtworzeń dla lepszych statystyk
                for song in all_songs:
                    # Każda piosenka ma od 10 do 100 odtworzeń w historii
                    for _ in range(random.randint(10, 100)):
                        # Rozkładamy daty: 20% szans na ostatnie 7 dni, 80% na resztę z 3 lat
                        if random.random() < 0.2:
                            played_at = now - timedelta(
                                days=random.randint(0, 7), 
                                hours=random.randint(0, 23),
                                minutes=random.randint(0, 59)
                            )
                        else:
                            played_at = now - timedelta(
                                days=random.randint(8, 1095), 
                                hours=random.randint(0, 23),
                                minutes=random.randint(0, 59)
                            )
                        
                        # Losujemy czy odtworzenie było z playlisty społeczności (nowe!)
                        # aby wypełnić sekcję "Najchętniej słuchane" na stronie głównej
                        play_playlist = None
                        if random.random() < 0.3: # 30% szans na odtworzenie z playlisty
                            play_playlist = random.choice(playlist_objs)
                        
                        # Losujemy przesłuchany czas (od 10s do pełnego czasu trwania)
                        listened = random.randint(10, song.duration_sec) if song.duration_sec > 10 else song.duration_sec
                        
                        plays.append(SongPlay(
                            song=song, 
                            user=random.choice(user_objs),
                            playlist=play_playlist,
                            played_at=played_at,
                            listened_duration_sec=listened
                        ))

                liked_bulk, followed_bulk = [], []
                for user in user_objs:
                    # Polubione utwory
                    for idx, s in enumerate(random.sample(all_songs, random.randint(10, 40))):
                        liked_bulk.append(LikedSong(profile=user.profile, song=s, order=idx))
                    # Obserwowane playlisty innych
                    for idx, p in enumerate(random.sample([pl for pl in playlist_objs if pl.owner != user], random.randint(2, 5))):
                        followed_bulk.append(FollowedPlaylist(profile=user.profile, playlist=p, order=idx))
                
                LikedSong.objects.bulk_create(liked_bulk)
                FollowedPlaylist.objects.bulk_create(followed_bulk)
                
                # Masowe tworzenie odtworzeń (może być ich dużo, więc dzielimy na paczki)
                self.stdout.write(f'Zapisywanie {len(plays)} odtworzeń...')
                for i in range(0, len(plays), 5000):
                    SongPlay.objects.bulk_create(plays[i:i+5000])

                self.stdout.write('Generowanie polubień albumów...')
                for user in user_objs:
                    liked_albums = random.sample(list(Album.objects.all()), random.randint(2, 8))
                    user.profile.liked_albums.add(*liked_albums)

                self.stdout.write('Aktualizacja statystyk albumów i piosenek...')
                from django.db.models import Sum, Count
                for album in Album.objects.all():
                    # Suma odtworzeń piosenek w albumie (na podstawie SongPlay)
                    album_plays = SongPlay.objects.filter(song__album=album).count()
                    # Liczba polubień albumu
                    total_likes = album.profile_set.count()
                    
                    Album.objects.filter(pk=album.pk).update(
                        play_count=album_plays,
                        likes_count=total_likes
                    )
                    
                    # Aktualizujemy też play_count i likes_count pojedynczych piosenek w albumie
                    for song in album.songs.all():
                        s_plays = SongPlay.objects.filter(song=song).count()
                        s_likes = LikedSong.objects.filter(song=song).count()
                        Song.objects.filter(pk=song.pk).update(play_count=s_plays, likes_count=s_likes)

                self.stdout.write('Aktualizacja XP użytkowników...')
                for user in user_objs:
                    total_xp = SongPlay.objects.filter(user=user).aggregate(total=Sum('listened_duration_sec'))['total'] or 0
                    Profile.objects.filter(user=user).update(xp=total_xp)

                self.stdout.write(self.style.SUCCESS('GOTOWE! Seeder zakończony sukcesem.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'BŁĄD: {e}')); import traceback; traceback.print_exc()