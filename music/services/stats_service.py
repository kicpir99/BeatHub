import json
import random
from django.core.cache import cache
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Sum, Case, When, Value, IntegerField, CharField, Q
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth

from ..models import SongPlay

def get_profile_stats(user, start_date=None, end_date=None):
    """Generuje podstawowe dane statystyczne (wykresy aktywności i nastroju)."""
    now = timezone.now()
    if not start_date:
        start_date = (now - timedelta(days=30)).date()
    if not end_date:
        end_date = now.date()
        
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    cache_key = f"profile_stats_{user.id}_{start_date}_{end_date}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    genre_stats = SongPlay.objects.filter(
        user=user,
        played_at__date__gte=start_date,
        played_at__date__lte=end_date
    ).values('song__album__artist__genre__name').annotate(
        count=Count('id')
    ).order_by('-count')

    genre_labels = []
    genre_data = []
    for item in genre_stats:
        label = item['song__album__artist__genre__name'] or "Nieznany"
        genre_labels.append(label)
        genre_data.append(item['count'])
    
    delta = end_date - start_date
    if delta.days <= 45:
        trunc_func, label_fmt, delta_step = TruncDay, '%d.%m', timedelta(days=1)
    elif delta.days <= 180:
        trunc_func, label_fmt, delta_step = TruncWeek, '%d.%m', timedelta(weeks=1)
    else:
        trunc_func, label_fmt, delta_step = TruncMonth, '%m.%Y', None
        
    stats_qs = SongPlay.objects.filter(
        user=user, played_at__date__gte=start_date, played_at__date__lte=end_date
    ).annotate(period=trunc_func('played_at')).values('period').annotate(count=Count('id')).order_by('period')
    
    stats_dict = {s['period'].date(): s['count'] for s in stats_qs if s['period']}
    
    activity_data, activity_labels = [], []
    curr = start_date
    while curr <= end_date:
        target_date = curr
        if trunc_func == TruncMonth:
            target_date = curr.replace(day=1)
        elif trunc_func == TruncWeek:
            target_date = curr - timedelta(days=curr.weekday())
            
        count = stats_dict.get(target_date, 0)
        label = target_date.strftime(label_fmt)
        
        if not activity_labels or activity_labels[-1] != label:
            activity_labels.append(label)
            activity_data.append(count)
            
        if trunc_func == TruncMonth:
            curr = curr.replace(year=curr.year + 1, month=1, day=1) if curr.month == 12 else curr.replace(month=curr.month + 1, day=1)
        else:
            curr += delta_step
            
    result = {
        'mood_labels': json.dumps(genre_labels),
        'mood_data': json.dumps(genre_data),
        'activity_labels': json.dumps(activity_labels),
        'activity_data': json.dumps(activity_data),
    }
    
    # Zapis do cache na 15 minut
    cache.set(cache_key, result, 900)
    return result

def get_detailed_user_stats(profile_user):
    """
    Generuje i zwraca pełen pakiet szczegółowych statystyk (czas odtwarzania, 
    top artyści, gatunki, insights) dla widoku DetailedStatsView.
    """
    cache_key = f"detailed_stats_{profile_user.id}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    context_data = {}
    plays = SongPlay.objects.filter(user=profile_user).select_related('song', 'song__album', 'song__album__artist', 'song__album__artist__genre')
    profile = profile_user.profile
    
    bucket_stats = SongPlay.objects.filter(user=profile_user).annotate(
        bucket=Case(
            When(song__duration_sec__lt=120, then=Value('Mini (< 2:00)')),
            When(song__duration_sec__lt=210, then=Value('Krótkie (2:00-3:30)')),
            When(song__duration_sec__lt=300, then=Value('Standard (3:30-5:00)')),
            When(song__duration_sec__lt=480, then=Value('Długie (5:00-8:00)')),
            default=Value('Epickie (> 8:00)'),
            output_field=CharField(),
        )
    ).values('bucket').annotate(
        count=Count('id'),
        total_sec=Sum('listened_duration_sec')
    )
    
    ordered_buckets = [
        'Mini (< 2:00)', 'Krótkie (2:00-3:30)', 'Standard (3:30-5:00)', 
        'Długie (5:00-8:00)', 'Epickie (> 8:00)'
    ]
    bucket_map = {item['bucket']: item for item in bucket_stats}
    
    duration_counts = []
    duration_hours = []
    for b_name in ordered_buckets:
        data = bucket_map.get(b_name, {'count': 0, 'total_sec': 0})
        duration_counts.append(data['count'])
        duration_hours.append(round(data['total_sec'] / 3600, 2))

    context_data['duration_labels'] = json.dumps(ordered_buckets)
    context_data['duration_counts'] = json.dumps(duration_counts)
    context_data['duration_hours'] = json.dumps(duration_hours)
    
    year_stats = plays.filter(song__album__release_date__isnull=False).values('song__album__release_date__year').annotate(
        unique_songs=Count('song', distinct=True),
        total_duration=Sum('listened_duration_sec')
    ).order_by('song__album__release_date__year')
    
    if year_stats:
        years_raw = [item['song__album__release_date__year'] for item in year_stats]
        full_years = list(range(min(years_raw), max(years_raw) + 1))
        y_counts = {item['song__album__release_date__year']: item['unique_songs'] for item in year_stats}
        y_hours = {item['song__album__release_date__year']: round(item['total_duration'] / 3600, 2) for item in year_stats}
        
        context_data['year_labels'] = json.dumps(full_years)
        context_data['year_counts'] = json.dumps([y_counts.get(y, 0) for y in full_years])
        context_data['year_hours'] = json.dumps([y_hours.get(y, 0) for y in full_years])
    else:
        context_data.update({'year_labels': '[]', 'year_counts': '[]', 'year_hours': '[]'})

    listening_stats = plays.values('played_at__year').annotate(
        total_plays=Count('id'),
        unique_songs=Count('song', distinct=True),
        total_duration=Sum('listened_duration_sec')
    ).order_by('played_at__year')
    
    if listening_stats:
        l_years_raw = [item['played_at__year'] for item in listening_stats]
        l_min_year = min(l_years_raw)
        l_max_year = max(l_years_raw)
        l_full_years = list(range(l_min_year, l_max_year + 1))
        l_counts_map = {item['played_at__year']: item['total_plays'] for item in listening_stats}
        l_unique_map = {item['played_at__year']: item['unique_songs'] for item in listening_stats}
        l_hours_map = {item['played_at__year']: round(item['total_duration'] / 3600, 2) for item in listening_stats}
        
        context_data['listening_labels'] = json.dumps(l_full_years)
        context_data['listening_counts'] = json.dumps([l_counts_map.get(y, 0) for y in l_full_years])
        context_data['listening_hours'] = json.dumps([l_hours_map.get(y, 0) for y in l_full_years])
        
        table_data = []
        for y in reversed(l_full_years):
            table_data.append({
                'year': y,
                'count': l_counts_map.get(y, 0),
                'unique': l_unique_map.get(y, 0),
                'hours': l_hours_map.get(y, 0)
            })
        context_data['listening_table'] = table_data
    else:
        context_data.update({'listening_labels': '[]', 'listening_counts': '[]', 'listening_hours': '[]', 'listening_table': []})

    summary_stats = plays.aggregate(
        total_plays=Count('id'),
        total_sec=Sum('listened_duration_sec'),
        unique_songs=Count('song', distinct=True),
        unique_artists=Count('song__album__artist', distinct=True)
    )
    
    context_data['total_plays_count'] = summary_stats['total_plays']
    context_data['total_hours_all'] = round((summary_stats['total_sec'] or 0) / 3600, 1)
    context_data['unique_songs_count'] = summary_stats['unique_songs']
    context_data['unique_artists_count'] = summary_stats['unique_artists']
    context_data['followed_artists_count'] = profile.following.count()

    genre_data = plays.filter(song__album__artist__genre__isnull=False).values(
        'song__album__artist__genre__id', 'song__album__artist__genre__name'
    ).annotate(
        total_plays=Count('id'),
        unique_songs=Count('song', distinct=True),
        total_sec=Sum('listened_duration_sec')
    ).order_by('-total_plays')

    album_plays = plays.filter(
        song__album__artist__genre__isnull=False,
        song__album__slug__isnull=False
    ).exclude(song__album__slug='').values(
        'song__album__id', 'song__album__title', 'song__album__cover', 'song__album__artist__genre__id', 'song__album__slug'
    ).annotate(plays=Count('id')).order_by('-plays')

    genre_albums_map = {}
    for ap in album_plays:
        ga_id = ap['song__album__artist__genre__id']
        if ga_id not in genre_albums_map:
            genre_albums_map[ga_id] = []
        if len(genre_albums_map[ga_id]) < 4:
            genre_albums_map[ga_id].append({
                'title': ap['song__album__title'],
                'cover': ap['song__album__cover'],
                'slug': ap['song__album__slug']
            })

    final_genres = []
    for g in genre_data:
        sec = g['total_sec'] or 0
        days = sec // 86400
        hours = (sec % 86400) // 3600
        minutes = (sec % 3600) // 60
        
        time_parts = []
        if days > 0: time_parts.append(f"{days}d")
        if hours > 0: time_parts.append(f"{hours}godz")
        if minutes > 0 or (days == 0 and hours == 0): 
            time_parts.append(f"{minutes}min")
        
        current_genre_id = g['song__album__artist__genre__id']
        final_genres.append({
            'name': g['song__album__artist__genre__name'],
            'unique_count': g['unique_songs'],
            'total_sec': sec,
            'display_time': " ".join(time_parts),
            'top_albums': genre_albums_map.get(current_genre_id, [])
        })
    context_data['genre_stats'] = final_genres

    artist_data = plays.values(
        'song__album__artist__id', 
        'song__album__artist__nickname',
        'song__album__artist__photo',
        'song__album__artist__slug'
    ).annotate(
        total_plays=Count('id'),
        total_sec=Sum('listened_duration_sec')
    ).order_by('-total_plays')[:8]

    final_artists = []
    for a in artist_data:
        a_id = a['song__album__artist__id']
        top_songs_qs = plays.filter(song__album__artist__id=a_id).values(
            'song__id', 'song__title', 'song__album__cover', 'song__album__slug'
        ).annotate(p_count=Count('id')).order_by('-p_count')[:4]
        
        sec = a['total_sec'] or 0
        days = sec // 86400
        hours = (sec % 86400) // 3600
        minutes = (sec % 3600) // 60
        
        time_parts = []
        if days > 0: time_parts.append(f"{days}d")
        if hours > 0: time_parts.append(f"{hours}godz")
        if minutes > 0 or (days == 0 and hours == 0): 
            time_parts.append(f"{minutes}min")

        final_artists.append({
            'id': a_id,
            'nickname': a['song__album__artist__nickname'],
            'photo': a['song__album__artist__photo'],
            'slug': a['song__album__artist__slug'],
            'total_plays': a['total_plays'],
            'display_time': " ".join(time_parts),
            'top_songs': list(top_songs_qs)
        })
    context_data['artist_stats'] = final_artists

    # 5. Insights
    insights = []
    day_stats = plays.values('played_at__week_day').annotate(count=Count('id')).order_by('-count')
    if day_stats.exists():
        days_map = {1: 'Niedzielę', 2: 'Poniedziałek', 3: 'Wtorek', 4: 'Środę', 5: 'Czwartek', 6: 'Piątek', 7: 'Sobotę'}
        top_day = day_stats[0]
        insights.append({
            'title': f"Twój muzyczny dzień to {days_map.get(top_day['played_at__week_day'])}!",
            'desc': f"To wtedy najczęściej sięgasz po ulubione utwory. Wygląda na to, że to Twój czas na relaks.",
            'icon': 'calendar'
        })

    hour_stats = plays.values('played_at__hour').annotate(count=Count('id')).order_by('-count')
    if hour_stats.exists():
        top_hour = hour_stats[0]['played_at__hour']
        if 0 <= top_hour < 6:
            title, desc, icon = "Muzyczny Nocny Marek!", "Najwięcej słuchasz w środku nocy. Twoja pasja nie śpi.", "moon"
        elif 6 <= top_hour < 11:
            title, desc, icon = "Ranny Ptaszek?", "Muzyka to Twój sposób na dobry początek dnia. Uwielbiasz poranne sesje.", "sun"
        elif 11 <= top_hour < 18:
            title, desc, icon = "Popołudniowy Meloman", "Muzyka towarzyszy Ci głównie w ciągu dnia, podczas pracy lub nauki.", "clock"
        else:
            title, desc, icon = "Wieczorny Klimat", "Najchętniej słuchasz wieczorami, gdy świat nieco zwalnia.", "sparkles"
        
        insights.append({'title': title, 'desc': desc, 'icon': icon})

    if context_data.get('unique_songs_count', 0) > 0:
        ratio = context_data['unique_artists_count'] / context_data['unique_songs_count']
        if ratio > 0.5:
            insights.append({
                'title': "Prawdziwy Odkrywca!",
                'desc': "Uwielbiasz różnorodność. Rzadko słuchasz wielu piosenek tego samego artysty, szukasz nowości.",
                'icon': 'map'
            })
        else:
            insights.append({
                'title': "Lojalny Słuchacz",
                'desc': "Jeśli kogoś polubisz, zostajesz z nim na dłużej. Znasz dyskografie swoich ulubieńców na wylot.",
                'icon': 'heart'
            })

    context_data['random_insight'] = random.choice(insights) if insights else None

    # Zapis do cache
    cache.set(cache_key, context_data, 1800)
    return context_data
