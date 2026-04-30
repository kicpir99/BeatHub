from django.contrib import admin
from django.utils.html import format_html
from .models import Genre, Artist, Album, Song, Playlist, PlaylistPosition, Profile, SongPlay

class SongInline(admin.TabularInline):
    """Pozwala dodawać i edytować piosenki bezpośrednio na stronie edycji Albumu."""
    model = Song
    extra = 1
    readonly_fields = ('play_count', 'likes_count', 'duration_sec')

class PlaylistPositionInline(admin.TabularInline):
    """Pozwala zarządzać piosenkami i ich kolejnością na stronie edycji Playlisty."""
    model = PlaylistPosition
    extra = 1

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('get_image_thumbnail', 'name', 'created_at', 'updated_at')
    search_fields = ('name',)
    readonly_fields = ('slug',)

    def get_image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="40" height="40" style="border-radius: 8px; object-fit: cover; border: 1px solid #444;" />', 
                obj.image.url
            )
        return format_html('<span style="color: #666; font-size: 10px;">Brak foto</span>')
    
    get_image_thumbnail.short_description = "Zdjęcie"

@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'genre', 'created_at')
    list_filter = ('genre',)
    search_fields = ('nickname',)
    readonly_fields = ('slug',)

@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('get_cover_thumbnail', 'title', 'artist', 'release_date', 'play_count', 'likes_count')
    list_filter = ('artist', 'release_date')
    search_fields = ('title', 'artist__nickname') # Podwójne podkreślenie (artist__nickname) pozwala szukać po polach klucza obcego!
    readonly_fields = ('slug', 'play_count', 'likes_count')
    inlines = [SongInline]

    def get_cover_thumbnail(self, obj):
        if obj.cover:
            return format_html('<img src="{}" width="40" height="40" style="border-radius: 4px; object-fit: cover;" />', obj.cover.url)
        return "Brak okładki"
    get_cover_thumbnail.short_description = "Okładka"

@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ('title', 'album', 'format_duration', 'play_count', 'likes_count')
    list_filter = ('album__artist', 'album')
    search_fields = ('title',)
    readonly_fields = ('play_count', 'likes_count', 'duration_sec')

    def format_duration(self, obj):
        minutes = obj.duration_sec // 60
        seconds = obj.duration_sec % 60
        return f"{minutes}:{seconds:02d}"
    format_duration.short_description = "Czas trwania"

@admin.register(Playlist)
class PlaylistAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'created_at')
    list_filter = ('owner',)
    search_fields = ('name', 'owner__username')
    inlines = [PlaylistPositionInline]

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'bio')
    search_fields = ('user__username',)

@admin.register(SongPlay)
class SongPlayAdmin(admin.ModelAdmin):
    list_display = ('song', 'user', 'played_at', 'get_artist')
    list_filter = ('played_at', 'song__album__artist__genre', 'song')
    search_fields = ('song__title', 'user__username')
    readonly_fields = ('song', 'user', 'played_at')
   
    def get_artist(self, obj):
        return obj.song.album.artist.nickname
    get_artist.short_description = "Artysta"

    def has_add_permission(self, request):
        return False