import json
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from music.models import Profile, LikedSong, Song

with open('likes_backup.json') as f:
    data = json.load(f)

for item in data:
    try:
        profile = Profile.objects.get(user_id=item['user_id'])
        for song_id in item['song_ids']:
            LikedSong.objects.get_or_create(profile=profile, song_id=song_id)
        print(f"Restored {len(item['song_ids'])} likes for user {profile.user.username}")
    except Profile.DoesNotExist:
        print(f"Profile for user_id {item['user_id']} not found")
