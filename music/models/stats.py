from django.db import models
from django.contrib.auth.models import User
from .catalog import Song
from .playlist import Playlist

class SongPlay(models.Model):
    """Rejestruje pojedyncze odtworzenie utworu dla statystyk czasowych."""
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='individual_plays')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    playlist = models.ForeignKey(Playlist, on_delete=models.SET_NULL, null=True, blank=True, related_name='playlist_plays')
    played_at = models.DateTimeField(auto_now_add=True, verbose_name="Data odtworzenia", db_index=True)
    listened_duration_sec = models.PositiveIntegerField(default=0, verbose_name="Przesłuchany czas (s)")

    class Meta:
        verbose_name = "Odtwarzanie"
        verbose_name_plural = "Odtwarzania"
        ordering = ['-played_at']
