import random
from django.db import models
from django.utils.text import slugify
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFit
from autoslug import AutoSlugField
from .base import BaseModel

class Genre(BaseModel):
    """
    Reprezentuje gatunek muzyczny.
    Automatycznie generuje slug z nazwy po utworzeniu.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nazwa gatunku")
    image = ProcessedImageField(upload_to='genres/',
                                processors=[ResizeToFit(800, 800)],
                                format='JPEG',
                                options={'quality': 85},
                                null=True, blank=True)
    slug = AutoSlugField(populate_from='name', unique=True)

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
    slug = AutoSlugField(populate_from='nickname', unique=True)
    photo = ProcessedImageField(upload_to='artists/',
                                 processors=[ResizeToFit(600, 600)],
                                 format='JPEG',
                                 options={'quality': 85},
                                 blank=True, null=True, verbose_name="Zdjęcie")
    genre = models.ForeignKey(Genre, on_delete=models.SET_NULL, null=True, related_name='artists', verbose_name="Gatunek")
    bio = models.TextField(blank=True, verbose_name="Biografia")
    followers = models.ManyToManyField('music.Profile', related_name='followed_artists', blank=True, verbose_name="Obserwujący")

    objects = ArtistManager()

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
    slug = AutoSlugField(populate_from='title', unique=True)
    release_date = models.DateField(verbose_name="Data wydania", db_index=True)
    cover = ProcessedImageField(upload_to='albums/',
                                 processors=[ResizeToFit(800, 800)],
                                 format='JPEG',
                                 options={'quality': 85},
                                 blank=True, null=True, verbose_name="Okładka")
    artist = models.ForeignKey(Artist, on_delete=models.PROTECT, related_name='albums', verbose_name="Artysta")
    produced_by = models.CharField(max_length=200, blank=True, null=True, verbose_name="Producent")
    play_count = models.PositiveIntegerField(default=0, verbose_name="Suma odtworzeń albumu", db_index=True)
    likes_count = models.PositiveIntegerField(default=0, verbose_name="Liczba polubień")

    objects = AlbumManager()

    def get_total_duration_sec(self):
        """Zwraca sumę sekund wszystkich piosenek na playliście."""
        if hasattr(self, 'total_duration_db'):
            return self.total_duration_db
        return self.songs.aggregate(total=Sum('duration_sec'))['total'] or 0
    
    def get_total_duration_display(self):
        total_seconds = self.get_total_duration_sec()
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours} h {minutes} min"
        return f"{minutes} min {seconds:02d} s"

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
        super().save(*args, **kwargs)
                
    def get_duration_display(self):
        minutes = self.duration_sec // 60
        seconds = self.duration_sec % 60
        return f"{minutes}:{seconds:02d}"

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Piosenka"
        verbose_name_plural = "Piosenki"
