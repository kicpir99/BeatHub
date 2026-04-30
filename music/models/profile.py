import base64
import math
import datetime
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from PIL import Image
from multiavatar.multiavatar import multiavatar
from .catalog import Song, Album
from .playlist import Playlist

class LikedAlbum(models.Model):
    profile = models.ForeignKey('Profile', on_delete=models.CASCADE, related_name='liked_album_positions')
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='liked_album_positions')
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Data polubienia")
    order = models.PositiveIntegerField(default=0, verbose_name="Kolejność")

    class Meta:
        ordering = ['order', '-added_at']
        unique_together = ('profile', 'album')
        verbose_name = "Polubiony album"
        verbose_name_plural = "Polubione albumy"

    def save(self, *args, **kwargs):
        if not self.pk and self.order == 0:
            last = LikedAlbum.objects.filter(profile=self.profile).order_by('-order').first()
            if last:
                self.order = last.order + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.profile.user.username} polubił album {self.album.title}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True, help_text="Napisz coś o sobie i swoim guście muzycznym")
    liked_songs = models.ManyToManyField(Song, blank=True, related_name='liked_by', through='LikedSong')
    liked_albums = models.ManyToManyField(Album, blank=True, through='LikedAlbum')
    VISIBILITY_CHOICES = [
        ('public', 'Publiczny (widoczny dla wszystkich)'),
        ('followers', 'Tylko dla obserwujących'),
        ('private', 'Prywatny'),
    ]
    visibility = models.CharField(
        max_length=10, 
        choices=VISIBILITY_CHOICES, 
        default='private', 
        verbose_name="Widoczność profilu"
    )
    show_profile_stats_publicly = models.BooleanField(default=True, verbose_name="Pokazuj wykresy na profilu publicznie")
    show_detailed_stats_publicly = models.BooleanField(default=True, verbose_name="Dostęp do szczegółowych statystyk publiczny")
    location = models.CharField(max_length=100, blank=True, null=True, verbose_name="Lokalizacja")
    instagram_url = models.URLField(max_length=200, blank=True, null=True, verbose_name="Instagram URL")
    twitter_url = models.URLField(max_length=200, blank=True, null=True, verbose_name="Twitter URL")
    website_url = models.URLField(max_length=200, blank=True, null=True, verbose_name="Strona WWW")
    following = models.ManyToManyField('self', symmetrical=False, related_name='followers', blank=True)
    followed_playlists = models.ManyToManyField(Playlist, blank=True, related_name='followed_by', through='music.FollowedPlaylist')
    
    GENDER_CHOICES = [
        ('M', 'Mężczyzna'),
        ('F', 'Kobieta'),
        ('O', 'Nie chcę podawać / Inna'),
    ]
    gender = models.CharField(
        max_length=1, 
        choices=GENDER_CHOICES, 
        default='O', 
        verbose_name="Płeć"
    )

    xp = models.PositiveIntegerField(default=0, verbose_name="Doświadczenie (XP)", db_index=True)
    last_playback = models.JSONField(null=True, blank=True, verbose_name="Ostatnie odtwarzanie")
    last_activity = models.DateTimeField(null=True, blank=True, verbose_name="Ostatnia aktywność")

    def get_level_data(self):
        """
        Zwraca dane o poziomie.
        Logika obliczeń została przeniesiona do services/profile_service.py.
        """
        from ..services.profile_service import get_user_level_info
        return get_user_level_info(self.xp)

    def is_online(self):
        if self.last_activity:
            return self.last_activity > timezone.now() - datetime.timedelta(minutes=5)
        return False

    def __str__(self):
        return f"Profil użytkownika: {self.user.username}"
    
    @property
    def avatar_url(self):
        if self.avatar:
            return self.avatar.url
        return self.avatar_svg_b64

    @property
    def avatar_svg_b64(self):
        if not hasattr(self, '_avatar_svg_cache'):
            svg_code = multiavatar(self.user.username, None, None)
            svg_b64 = base64.b64encode(svg_code.encode('utf-8')).decode('utf-8')
            self._avatar_svg_cache = f"data:image/svg+xml;base64,{svg_b64}"
        return self._avatar_svg_cache

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.avatar:
            from ..services.music_service import resize_image
            resize_image(self.avatar.path, (300, 300))

class LikedSong(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='liked_positions')
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='liked_positions')
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Data polubienia")
    order = models.PositiveIntegerField(default=0, verbose_name="Kolejność")

    class Meta:
        ordering = ['order', '-added_at']
        unique_together = ('profile', 'song')
        verbose_name = "Polubiony utwór"
        verbose_name_plural = "Polubione utwory"

    def save(self, *args, **kwargs):
        if not self.pk and self.order == 0:
            last = LikedSong.objects.filter(profile=self.profile).order_by('-order').first()
            if last:
                self.order = last.order + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.profile.user.username} polubił {self.song.title}"
