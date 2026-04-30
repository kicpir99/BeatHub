import random
from django.db import models
from django.utils.text import slugify
from PIL import Image
from mutagen.mp3 import MP3
from mutagen import File as MutagenFile
from django.db.models import Sum, Count
from .base import BaseModel

class Genre(BaseModel):
    """
    Reprezentuje gatunek muzyczny.
    Automatycznie generuje slug z nazwy po utworzeniu.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nazwa gatunku")
    image = models.ImageField(upload_to='genres/', null=True, blank=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        if self.image:
            from ..services.music_service import resize_image
            resize_image(self.image.path, (800, 800))

    def __str__(self):
        return self.name

    def get_mood(self):
        """Mapuje gatunek na muzyczny nastrój."""
        mapping = {
            'Rock': 'Intensywny',
            'Pop': 'Energetyczny',
            'Hip-Hop': 'Dynamiczny',
            'Jazz': 'Relaksujący',
            'Elektronika': 'Energetyczny',
            'Klasyka': 'Relaksujący',
            'Metal': 'Intensywny',
            'Blues': 'Nostalgiczny',
            'Reggae': 'Chillout',
            'Country': 'Sielankowy',
            'Indie': 'Marzycielski'
        }
        return mapping.get(self.name, 'Neutralny')

    class Meta:
        verbose_name = "Gatunek"
        verbose_name_plural = "Gatunki"

from django.utils import timezone
from datetime import timedelta

class ArtistQuerySet(models.QuerySet):
    def top_by_plays(self, days=7, count=6):
        cut_off = timezone.now() - timedelta(days=days)
        return self.filter(
            albums__songs__individual_plays__played_at__gte=cut_off
        ).annotate(
            total_plays=Count('albums__songs__individual_plays')
        ).order_by('-total_plays')[:count]

class ArtistManager(models.Manager):
    def get_queryset(self):
        return ArtistQuerySet(self.model, using=self._db)

    def top_by_plays(self, days=7, count=6):
        return self.get_queryset().top_by_plays(days, count)

class Artist(BaseModel):
    """
    Reprezentuje artystę lub zespół muzyczny.
    """
    nickname = models.CharField(max_length=100, verbose_name="Pseudonim")
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    photo = models.ImageField(upload_to='artists/', blank=True, null=True, verbose_name="Zdjęcie")
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True, related_name='artists', verbose_name="Gatunek")
    bio = models.TextField(blank=True, verbose_name="Biografia")
    followers = models.ManyToManyField('music.Profile', related_name='followed_artists', blank=True, verbose_name="Obserwujący")

    objects = ArtistManager()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nickname)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nickname

    class Meta:
        verbose_name = "Artysta"
        verbose_name_plural = "Artyści"

class AlbumQuerySet(models.QuerySet):
    def trending(self, days=7):
        cut_off = timezone.now() - timedelta(days=days)
        return self.filter(
            songs__individual_plays__played_at__gte=cut_off
        ).annotate(
            recent_plays=Count('songs__individual_plays')
        ).filter(recent_plays__gt=0).order_by('-recent_plays')

class AlbumManager(models.Manager):
    def get_queryset(self):
        return AlbumQuerySet(self.model, using=self._db)

    def trending(self, days=7):
        return self.get_queryset().trending(days)

class Album(BaseModel):
    """
    Reprezentuje album muzyczny wydany przez artystę.
    """
    title = models.CharField(max_length=200, verbose_name="Tytuł albumu")
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    release_date = models.DateField(verbose_name="Data wydania", db_index=True)
    cover = models.ImageField(upload_to='albums/', blank=True, null=True, verbose_name="Okładka")
    artist = models.ForeignKey(Artist, on_delete=models.PROTECT, related_name='albums', verbose_name="Artysta")
    produced_by = models.CharField(max_length=200, blank=True, null=True, verbose_name="Producent")
    play_count = models.PositiveIntegerField(default=0, verbose_name="Suma odtworzeń albumu", db_index=True)
    likes_count = models.PositiveIntegerField(default=0, verbose_name="Liczba polubień")

    objects = AlbumManager()

    def get_total_duration_sec(self):
        return self.songs.aggregate(total=Sum('duration_sec'))['total'] or 0
    
    def get_total_duration_display(self):
        total_seconds = self.get_total_duration_sec()
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours} h {minutes} min"
        return f"{minutes} min {seconds:02d} s"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Album.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1 
            self.slug = slug
        super().save(*args, **kwargs)
        if self.cover:
            from ..services.music_service import resize_image
            resize_image(self.cover.path, (800, 800))

    def __str__(self):
        return f"{self.title} ({self.artist.nickname})"

    class Meta:
        verbose_name = "Album"
        verbose_name_plural = "Albumy"

class SongQuerySet(models.QuerySet):
    def trending(self, days=7):
        cut_off = timezone.now() - timedelta(days=days)
        return self.filter(
            individual_plays__played_at__gte=cut_off
        ).select_related('album__artist').prefetch_related('featured_artists').annotate(
            trending_count=Count('individual_plays')
        ).order_by('-trending_count')

class SongManager(models.Manager):
    def get_queryset(self):
        return SongQuerySet(self.model, using=self._db)

    def trending(self, days=7):
        return self.get_queryset().trending(days)

class Song(BaseModel):
    """
    Reprezentuje pojedynczy utwór należący do albumu.
    """
    title = models.CharField(max_length=200, verbose_name="Tytuł piosenki")
    duration_sec = models.PositiveIntegerField(default=0, editable=False, help_text="Czas trwania (automatycznie z pliku)", verbose_name="Czas trwania (s)")
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='songs', verbose_name="Album")
    featured_artists = models.ManyToManyField(Artist, blank=True, related_name='featured_songs', verbose_name="Artyści gościnni")
    audio_file = models.FileField(upload_to='songs', null=True, blank=True, verbose_name="Plik Audio")
    play_count = models.PositiveIntegerField(default=0, verbose_name="Liczba odtworzeń", db_index=True)
    likes_count = models.PositiveIntegerField(default=0, verbose_name="Liczba polubień")

    objects = SongManager()

    def save(self, *args, **kwargs):
        skip_metadata = kwargs.pop('skip_metadata', False)
        super().save(*args, **kwargs)
        if not skip_metadata and self.audio_file:
            from ..services.music_service import update_song_duration
            new_duration = update_song_duration(self)
            if new_duration and self.duration_sec != new_duration:
                Song.objects.filter(pk=self.pk).update(duration_sec=new_duration)
                self.duration_sec = new_duration
        else:
            if not skip_metadata and self.duration_sec != 0:
                Song.objects.filter(pk=self.pk).update(duration_sec=0)
                self.duration_sec = 0
                
    def get_duration_display(self):
        minutes = self.duration_sec // 60
        seconds = self.duration_sec % 60
        return f"{minutes}:{seconds:02d}"

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Piosenka"
        verbose_name_plural = "Piosenki"
