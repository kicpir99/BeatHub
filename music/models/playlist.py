import random
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from .base import BaseModel
from .catalog import Song

class PlaylistQuerySet(models.QuerySet):
    def trending(self, days=7):
        cut_off = timezone.now() - timedelta(days=days)
        return self.filter(
            is_public=True,
            playlist_plays__played_at__gte=cut_off
        ).select_related('owner__profile').prefetch_related(
            'playlistposition_set__song__album__artist'
        ).annotate(
            recent_plays_count=Count('playlist_plays__user', distinct=True)
        ).order_by('-recent_plays_count')

class PlaylistManager(models.Manager):
    def get_queryset(self):
        return PlaylistQuerySet(self.model, using=self._db)

    def trending(self, days=7):
        return self.get_queryset().trending(days)

class Playlist(BaseModel):
    """
    Reprezentuje kolekcję piosenek stworzoną przez użytkownika.
    """
    name = models.CharField(max_length=200, verbose_name="Nazwa playlisty")
    description = models.TextField(blank=True, verbose_name="Opis")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='playlists', verbose_name="Właściciel")
    songs = models.ManyToManyField(Song, through='PlaylistPosition', related_name='playlists', verbose_name="Piosenki")
    is_public = models.BooleanField(default=False, verbose_name='Publiczna')

    objects = PlaylistManager()

    def get_total_duration_sec(self):
        """Zwraca sumę sekund wszystkich piosenek na playliście."""
        return self.songs.aggregate(total=Sum('duration_sec'))['total'] or 0
    
    def get_total_duration_display(self):
        """Zwraca sformatowany czas."""
        total_seconds = self.get_total_duration_sec()
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours > 0:
            return f"{hours} h {minutes} min"
        return f"{minutes} min"

    def get_top_covers(self):
        """
        Pobiera okładki do kolarza 2x2. 
        """
        seed = getattr(self, 'cover_seed', None)
        positions = self.playlistposition_set.select_related('song__album').all()
        covers = []
        seen_urls = set()
        
        for pos in positions:
            if pos.song.album.cover:
                url = pos.song.album.cover.url
                if url not in seen_urls:
                    covers.append(url)
                    seen_urls.add(url)
        if len(covers) >= 4:
            if seed:
                r = random.Random(str(seed) + str(self.id))
                return r.sample(covers, 4)
            return random.sample(covers, 4)
        if covers:
            if seed:
                r = random.Random(str(seed) + str(self.id))
                return [r.choice(covers)]
            return [random.choice(covers)]
        return []

    def __str__(self):
        return f"{self.name} (od {self.owner.username})"

    class Meta:
        verbose_name = "Playlista"
        verbose_name_plural = "Playlisty"

class PlaylistPosition(models.Model):
    """
    Model pośredni dla relacji ManyToMany między playlistą a utworem.
    """
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, verbose_name="Playlista")
    song = models.ForeignKey(Song, on_delete=models.CASCADE, verbose_name="Piosenka")
    order = models.PositiveIntegerField(default=0, verbose_name="Kolejność")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Dodano dnia")

    class Meta:
        ordering = ['order']
        unique_together = ('playlist', 'song')
        verbose_name = "Pozycja na playliście"
        verbose_name_plural = "Pozycje na playliście"

    def __str__(self):
        return f"{self.order}. {self.song.title} na liście {self.playlist.name}"

class FollowedPlaylist(models.Model):
    profile = models.ForeignKey('music.Profile', on_delete=models.CASCADE)
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-followed_at']
        unique_together = ('profile', 'playlist')

    def save(self, *args, **kwargs):
        if not self.pk and self.order == 0:
            last = FollowedPlaylist.objects.filter(profile=self.profile).order_by('-order').first()
            if last:
                self.order = last.order + 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.profile.user.username} obserwuje {self.playlist.name} (poz. {self.order})"
