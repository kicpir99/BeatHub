from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Genre, Artist, Album, Song, Playlist, PlaylistPosition
import datetime

class BeatHubModelTests(TestCase):
    def setUp(self):
        self.genre = Genre.objects.create(name="Rock")
        self.artist = Artist.objects.create(nickname="Queen", genre=self.genre)
        self.album = Album.objects.create(
            title="A Night at the Opera",
            artist=self.artist,
            release_date=datetime.date(1975, 11, 21)
        )
        self.song = Song.objects.create(title="Bohemian Rhapsody", album=self.album)
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.playlist = Playlist.objects.create(name="Best of Rock", owner=self.user)

    def test_model_creation(self):
        """Testuje czy modele są poprawnie tworzone."""
        self.assertEqual(str(self.genre), "Rock")
        self.assertEqual(str(self.artist), "Queen")
        self.assertEqual(self.album.title, "A Night at the Opera")
        self.assertEqual(self.song.title, "Bohemian Rhapsody")
        self.assertEqual(self.playlist.name, "Best of Rock")

    def test_slug_generation(self):
        """Testuje automatyczne generowanie slugów."""
        self.assertEqual(self.genre.slug, "rock")
        self.assertEqual(self.artist.slug, "queen")
        self.album.save() # Wywołuje save() dla slug
        self.assertTrue(self.album.slug.startswith("a-night-at-the-opera"))

    def test_playlist_position(self):
        """Testuje relację ManyToMany z tabelą through."""
        pos = PlaylistPosition.objects.create(playlist=self.playlist, song=self.song, order=1)
        self.assertEqual(self.playlist.songs.count(), 1)
        self.assertEqual(self.playlist.songs.first(), self.song)
        self.assertEqual(pos.order, 1)

class BeatHubViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.genre = Genre.objects.create(name="Pop")
        self.artist = Artist.objects.create(nickname="Test Artist", genre=self.genre)
        self.album = Album.objects.create(
            title="Test Album",
            artist=self.artist,
            release_date=datetime.date.today()
        )
        self.user = User.objects.create_user(username="viewer", password="password123")

    def test_home_view(self):
        """Testuje czy strona główna zwraca kod 200."""
        response = self.client.get(reverse('music:home'))
        self.assertEqual(response.status_code, 200)

    def test_album_detail_view(self):
        """Testuje czy strona albumu zwraca kod 200."""
        response = self.client.get(reverse('music:album_detail', args=[self.album.slug]))
        self.assertEqual(response.status_code, 200)

    def test_artist_detail_view(self):
        """Testuje czy strona artysty zwraca kod 200."""
        response = self.client.get(reverse('music:artist_detail', args=[self.artist.slug]))
        self.assertEqual(response.status_code, 200)

    def test_login_required_redirect(self):
        """Testuje czy strony chronione przekierowują do logowania."""
        response = self.client.get(reverse('music:profile'))
        self.assertEqual(response.status_code, 302) # Przekierowanie do logowania
