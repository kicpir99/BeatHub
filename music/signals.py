from django.db.models.signals import post_save
from django.dispatch import receiver
from .models.catalog import Song

@receiver(post_save, sender=Song)
def update_song_metadata(sender, instance, created, **kwargs):
    """
    Sygnał aktualizujący czas trwania piosenki po zapisie.
    Separuje logikę binarną od modelu.
    """
    if instance.audio_file:
        from .services.music_service import update_song_duration
        
        new_duration = update_song_duration(instance)
        
        # Używamy .update(), aby uniknąć ponownego wywołania sygnału
        if new_duration and instance.duration_sec != new_duration:
            Song.objects.filter(pk=instance.pk).update(duration_sec=new_duration)
