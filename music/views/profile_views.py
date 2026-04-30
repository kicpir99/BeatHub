import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from django.views.generic import ListView, DetailView, UpdateView
from django.db.models import Count, Q, Sum, Max, F
from django.db.models.functions import Coalesce, TruncDay, TruncWeek, TruncMonth
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta, datetime
from better_profanity import profanity

from ..models import Profile, Playlist, Song, SongPlay, LikedSong, Artist
from ..forms import ProfileForm
from ..utils import update_cover_seed, apply_cover_seed, SafePaginationMixin
from ..mixins import MusicContextMixin

def get_profile_stats(user, start_date=None, end_date=None):
    """Generuje dane statystyczne dla profilu użytkownika w podanym zakresie."""
    now = timezone.now()
    
    if not start_date:
        start_date = (now - timedelta(days=30)).date()
    if not end_date:
        end_date = now.date()
        
    # Konwersja stringów na daty jeśli trzeba
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

    # 1. Statystyki gatunków (Doughnut Chart)
    plays_genre = SongPlay.objects.filter(
        user=user,
        played_at__date__gte=start_date,
        played_at__date__lte=end_date
    ).select_related('song__album__artist__genre')

    genre_counts = {}
    for play in plays_genre:
        g_obj = play.song.album.artist.genre
        genre = g_obj.name if g_obj else "Nieznany"
        genre_counts[genre] = genre_counts.get(genre, 0) + 1

    sorted_genres = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)
    genre_labels = [g[0] for g in sorted_genres]
    genre_data = [g[1] for g in sorted_genres]
    
    # 2. Aktywność (Line Chart)
    delta = end_date - start_date
    
    if delta.days <= 45:
        trunc_func = TruncDay
        label_fmt = '%d.%m'
        delta_step = timedelta(days=1)
    elif delta.days <= 180:
        trunc_func = TruncWeek
        label_fmt = '%d.%m'
        delta_step = timedelta(weeks=1)
    else:
        trunc_func = TruncMonth
        label_fmt = '%m.%Y'
        delta_step = None
        
    stats_qs = SongPlay.objects.filter(
        user=user,
        played_at__date__gte=start_date,
        played_at__date__lte=end_date
    ).annotate(
        period=trunc_func('played_at')
    ).values('period').annotate(
        count=Count('id')
    ).order_by('period')
    
    stats_dict = {s['period'].date(): s['count'] for s in stats_qs if s['period']}
    
    activity_data = []
    activity_labels = []
    
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
            if curr.month == 12:
                curr = curr.replace(year=curr.year + 1, month=1, day=1)
            else:
                curr = curr.replace(month=curr.month + 1, day=1)
        else:
            curr += delta_step
        
    return {
        'mood_labels': json.dumps(genre_labels),
        'mood_data': json.dumps(genre_data),
        'activity_labels': json.dumps(activity_labels),
        'activity_data': json.dumps(activity_data),
    }

class UserProfileDetailView(MusicContextMixin, DetailView):
    """Widok publicznego profilu użytkownika."""
    model = User
    template_name = 'music/user_profile.html'
    context_object_name = 'profile_user'
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        seed = context['cover_seed']
        profile_user = self.object
        profile = profile_user.profile
        
        is_own_profile = self.request.user == profile_user
        context['is_own_profile'] = is_own_profile
        context['visibility'] = profile.visibility
        
        is_following = False
        if self.request.user.is_authenticated and not is_own_profile:
            is_following = self.request.user.profile.following.filter(pk=profile.pk).exists()
            context['is_following'] = is_following

        can_view = False
        if is_own_profile:
            can_view = True
        elif profile.visibility == 'public':
            can_view = True
        elif profile.visibility == 'followers' and is_following:
            can_view = True
            
        context['can_view'] = can_view

        if can_view:
            playlists_qs = Playlist.objects.filter(owner=profile_user, is_public=True).annotate(
                songs_count=Count('songs'),
                total_duration_db=Coalesce(Sum('songs__duration_sec'), 0)
            ).order_by('-created_at')


            playlists_paginator = Paginator(playlists_qs, 10)
            playlists_page_num = self.request.GET.get('playlists_page')
            public_playlists = playlists_paginator.get_page(playlists_page_num)
            
            context['public_playlists'] = public_playlists
            apply_cover_seed(public_playlists, seed)
            
            liked_songs = profile.liked_songs.select_related('album__artist').all()
            context['recent_liked_songs'] = liked_songs.order_by('-id')[:5]
            
            artist_ids = liked_songs.values_list('album__artist_id', flat=True).distinct()
            context['favorite_artists'] = Artist.objects.filter(id__in=artist_ids)[:5]

            # Statystyki nastroju (tylko jeśli publiczne lub jesteśmy właścicielem)
            if profile.show_profile_stats_publicly or is_own_profile:
                context['stats'] = get_profile_stats(profile_user)
                
                # Dodatkowe statystyki ogólne na profil
                all_plays = SongPlay.objects.filter(user=profile_user)
                context['total_plays_count'] = all_plays.count()
                agg_sec = all_plays.aggregate(s=Sum('listened_duration_sec'))['s'] or 0
                context['total_hours_all'] = round(agg_sec / 3600, 1)

        # liked IDs są w mixinie
        
        context['followers_count'] = profile.followers.count()
        context['following_count'] = profile.following.count()
        return context

class ProfileUpdateView(LoginRequiredMixin, MusicContextMixin, SuccessMessageMixin, UpdateView):
    """Widok do edycji danych profilu zalogowanego użytkownika."""
    model = Profile
    form_class = ProfileForm
    template_name = 'music/profile.html'
    success_url = reverse_lazy('music:profile')
    success_message = "Twój profil został pomyślnie zaktualizowany!"

    def get_object(self, queryset = None):
        """Zwraca profil przypisany do ZALOGOWANEGO użytkownika."""
        return self.request.user.profile
    
    def form_invalid(self, form):
        """Zwraca status 422 przy błędach walidacji dla poprawnej współpracy z Turbo."""
        response = super().form_invalid(form)
        response.status_code = 422
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        seed = context['cover_seed']
        user = self.request.user
        context['user_info'] = user
        profile = user.profile
        
        context['public_playlists'] = Playlist.objects.filter(owner=user, is_public=True).annotate(
            songs_count=Count('songs'),
            total_duration_db=Coalesce(Sum('songs__duration_sec'), 0)
        )
        
        liked_songs = profile.liked_songs.select_related('album__artist').all()
        context['recent_liked_songs'] = liked_songs.order_by('-id')[:5]
        
        artist_ids = liked_songs.values_list('album__artist_id', flat=True).distinct()
        context['favorite_artists'] = Artist.objects.filter(id__in=artist_ids)[:5]
        
        # liked IDs są w mixinie
        
        # Statystyki nastroju i aktywności
        context['stats'] = get_profile_stats(user)
        
        apply_cover_seed(context.get('public_playlists'), seed)
        return context

class DetailedStatsView(MusicContextMixin, DetailView):
    """Szczegółowy widok statystyk użytkownika."""
    model = User
    template_name = 'music/stats_detail.html'
    context_object_name = 'profile_user'
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = self.object
        profile = profile_user.profile
        is_own_profile = self.request.user == profile_user
        
        # Sprawdzanie uprawnień
        can_view_stats = profile.show_detailed_stats_publicly or is_own_profile
        context['can_view_stats'] = can_view_stats
        context['is_own_profile'] = is_own_profile
        
        if can_view_stats:
            # Agregacja po długościach utworów (Buckets)
            plays = SongPlay.objects.filter(user=profile_user).select_related('song', 'song__album')
            
            buckets = {
                'Mini (< 2:00)': {'min': 0, 'max': 120, 'count': 0, 'total_sec': 0},
                'Krótkie (2:00-3:30)': {'min': 120, 'max': 210, 'count': 0, 'total_sec': 0},
                'Standard (3:30-5:00)': {'min': 210, 'max': 300, 'count': 0, 'total_sec': 0},
                'Długie (5:00-8:00)': {'min': 300, 'max': 480, 'count': 0, 'total_sec': 0},
                'Epickie (> 8:00)': {'min': 480, 'max': 99999, 'count': 0, 'total_sec': 0},
            }
            
            for play in plays:
                if play.song:
                    song_len = play.song.duration_sec
                    listen_len = play.listened_duration_sec
                    for name, bounds in buckets.items():
                        if song_len >= bounds['min'] and song_len < bounds['max']:
                            bounds['count'] += 1
                            bounds['total_sec'] += listen_len
                            break
            
            labels = list(buckets.keys())
            counts = [b['count'] for b in buckets.values()]
            hours = [round(b['total_sec'] / 3600, 2) for b in buckets.values()]
            
            context['duration_labels'] = json.dumps(labels)
            context['duration_counts'] = json.dumps(counts)
            context['duration_hours'] = json.dumps(hours)
            
            # Statystyki po roku wydania
            year_stats = plays.filter(song__album__release_date__isnull=False).values('song__album__release_date__year').annotate(
                unique_songs=Count('song', distinct=True),
                total_duration=Sum('listened_duration_sec')
            ).order_by('song__album__release_date__year')
            
            if year_stats:
                years_raw = [item['song__album__release_date__year'] for item in year_stats]
                min_year = min(years_raw)
                max_year = max(years_raw)
                
                full_years = list(range(min_year, max_year + 1))
                year_counts_map = {item['song__album__release_date__year']: item['unique_songs'] for item in year_stats}
                year_hours_map = {item['song__album__release_date__year']: round(item['total_duration'] / 3600, 2) for item in year_stats}
                
                context['year_labels'] = json.dumps(full_years)
                context['year_counts'] = json.dumps([year_counts_map.get(y, 0) for y in full_years])
                context['year_hours'] = json.dumps([year_hours_map.get(y, 0) for y in full_years])
            else:
                context['year_labels'] = json.dumps([])
                context['year_counts'] = json.dumps([])
                context['year_hours'] = json.dumps([])

            # Statystyki po roku słuchania (Listening Year)
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
                
                context['listening_labels'] = json.dumps(l_full_years)
                context['listening_counts'] = json.dumps([l_counts_map.get(y, 0) for y in l_full_years])
                context['listening_hours'] = json.dumps([l_hours_map.get(y, 0) for y in l_full_years])
                
                # Dane do tabeli
                table_data = []
                for y in reversed(l_full_years):
                    table_data.append({
                        'year': y,
                        'count': l_counts_map.get(y, 0),
                        'unique': l_unique_map.get(y, 0),
                        'hours': l_hours_map.get(y, 0)
                    })
                context['listening_table'] = table_data
            else:
                context['listening_labels'] = json.dumps([])
                context['listening_counts'] = json.dumps([])
                context['listening_hours'] = json.dumps([])
                context['listening_table'] = []
            
            context['total_plays_count'] = plays.count()
            agg = plays.aggregate(s=Sum('listened_duration_sec'))['s'] or 0
            context['total_hours_all'] = round(agg / 3600, 1)
            
            context['unique_songs_count'] = plays.values('song').distinct().count()
            context['unique_artists_count'] = plays.values('song__album__artist').distinct().count()
            context['followed_artists_count'] = profile.following.count()

            # Gatunki
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
            context['genre_stats'] = final_genres

            # Artyści
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
            context['artist_stats'] = final_artists

            # Insights
            insights = []
            day_stats = plays.values('played_at__week_day').annotate(count=Count('id')).order_by('-count')
            if day_stats.exists():
                days_map = {
                    1: 'Niedzielę', 2: 'Poniedziałek', 3: 'Wtorek', 4: 'Środę',
                    5: 'Czwartek', 6: 'Piątek', 7: 'Sobotę'
                }
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
                
                insights.append({
                    'title': title,
                    'desc': desc,
                    'icon': icon
                })

            if context['unique_songs_count'] > 0:
                ratio = context['unique_artists_count'] / context['unique_songs_count']
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

            import random
            context['random_insight'] = random.choice(insights) if insights else None
            
        return context

@login_required
def get_stats_ajax(request):
    """Endpoint AJAX do pobierania statystyk dla wybranego zakresu."""
    start_date = request.GET.get('start')
    end_date = request.GET.get('end')
    target_user_id = request.GET.get('user_id')
    
    if target_user_id:
        target_user = get_object_or_404(User, id=target_user_id)
        if not target_user.profile.show_profile_stats_publicly and target_user != request.user:
            return JsonResponse({'status': 'error', 'message': 'Brak uprawnień'}, status=403)
    else:
        target_user = request.user

    stats = get_profile_stats(target_user, start_date, end_date)
    return JsonResponse({'status': 'success', 'stats': stats})

def get_monthly_stats_ajax(request, username, year):
    """Zwraca miesięczne statystyki słuchania dla podanego roku."""
    try:
        user = User.objects.get(username=username)
        is_own = request.user == user
        if not (user.profile.show_detailed_stats_publicly or is_own):
            return JsonResponse({'status': 'error', 'message': 'Brak uprawnień'}, status=403)
            
        plays = SongPlay.objects.filter(user=user, played_at__year=year)
        monthly_stats = plays.values('played_at__month').annotate(
            count=Count('id'),
            total_sec=Sum('listened_duration_sec')
        ).order_by('played_at__month')
        
        month_names = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
        counts_map = {item['played_at__month']: item['count'] for item in monthly_stats}
        hours_map = {item['played_at__month']: round(item['total_sec'] / 3600, 2) for item in monthly_stats}
        
        return JsonResponse({
            'status': 'success',
            'year': year,
            'labels': month_names,
            'counts': [counts_map.get(m, 0) for m in range(1, 13)],
            'hours': [hours_map.get(m, 0) for m in range(1, 13)]
        })
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Nie znaleziono użytkownika'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
def set_profile_visibility_ajax(request):
    """Zmienia widoczność profilu."""
    try:
        data = json.loads(request.body)
        visibility = data.get('visibility', 'private')
        bio = data.get('bio', '')

        if visibility in ['public', 'followers']:
            if profanity.contains_profanity(bio):
                return JsonResponse({'status': 'error', 'message': 'Opis profilu zawiera niedozwolone słownictwo.'})
            
            location = data.get('location')
            if location and profanity.contains_profanity(location):
                return JsonResponse({'status': 'error', 'message': 'Lokalizacja zawiera niedozwolone słownictwo.'})
        
        profile = request.user.profile
        profile.visibility = visibility
        profile.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Widoczność profilu została zmieniona na: {profile.get_visibility_display()}'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
@require_POST
def toggle_follow_ajax(request):
    """Przełączanie stanu obserwowania użytkownika."""
    try:
        data = json.loads(request.body)
        target_profile_id = data.get('profile_id')
        if not target_profile_id:
            return JsonResponse({'status': 'error', 'message': 'Brak ID profilu'})
        
        target_profile = Profile.objects.get(id=target_profile_id)
        my_profile = request.user.profile
        
        if target_profile == my_profile:
            return JsonResponse({'status': 'error', 'message': 'Nie możesz obserwować samego siebie'})
        
        if my_profile.following.filter(id=target_profile_id).exists():
            my_profile.following.remove(target_profile)
            is_following = False
            message = f'Przestałeś obserwować {target_profile.user.username}'
        else:
            my_profile.following.add(target_profile)
            is_following = True
            message = f'Obserwujesz teraz {target_profile.user.username}'
            
        return JsonResponse({
            'status': 'success',
            'is_following': is_following,
            'message': message,
            'followers_count': target_profile.followers.count()
        })
    except (Profile.DoesNotExist, Exception) as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

class ToggleStatsVisibilityView(LoginRequiredMixin, generic.View):
    """Przełącza publiczną widoczność SZCZEGÓŁOWYCH statystyk użytkownika."""
    def post(self, request, *args, **kwargs):
        profile = request.user.profile
        profile.show_detailed_stats_publicly = not profile.show_detailed_stats_publicly
        profile.save()
        
        status = "publiczne" if profile.show_detailed_stats_publicly else "prywatne"
        messages.success(request, f"Dostęp do Twoich statystyk jest teraz ustawiony jako: {status}.")
        return redirect('music:detailed_stats', username=request.user.username)

class UserSearchView(MusicContextMixin, SafePaginationMixin, ListView):
    """Widok wyszukiwania użytkowników."""
    model = Profile
    template_name = 'music/user_search.html'
    context_object_name = 'profiles'
    paginate_by = 20

    def get_queryset(self):
        queryset = Profile.objects.filter(visibility__in=['public', 'followers']).select_related('user').annotate(
            followers_count=Count('followers', distinct=True),
            playlists_count=Count('user__playlists', filter=Q(user__playlists__is_public=True), distinct=True)
        )
        
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(user__username__icontains=query) | 
                Q(bio__icontains=query) |
                Q(location__icontains=query)
            ).distinct()
        elif self.request.user.is_authenticated:
            # Ukrywamy siebie na liście startowej (bez zapytania), aby promować odkrywanie innych
            queryset = queryset.exclude(user=self.request.user)
        
        sort = self.request.GET.get('sort', '-followers_count')
        if sort == 'username':
            queryset = queryset.order_by('user__username')
        elif sort == '-playlists_count':
            queryset = queryset.order_by('-playlists_count', 'user__username')
        else:
            queryset = queryset.order_by('-followers_count', 'user__username')
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['sort'] = self.request.GET.get('sort', '-followers_count')
        return context

class FollowingListView(LoginRequiredMixin, MusicContextMixin, SafePaginationMixin, ListView):
    """Widok listy osób, które obserwuje zalogowany użytkownik."""
    model = Profile
    template_name = 'music/following_list.html'
    context_object_name = 'profiles'
    paginate_by = 20

    def get_queryset(self):
        queryset = self.request.user.profile.following.all().select_related('user').annotate(
            followers_count=Count('followers', distinct=True),
            playlists_count=Count('user__playlists', filter=Q(user__playlists__is_public=True), distinct=True)
        )
        
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(user__username__icontains=query) | 
                Q(bio__icontains=query) |
                Q(location__icontains=query)
            ).distinct()
            
        sort = self.request.GET.get('sort', 'user__username')
        if sort == '-followers_count':
            queryset = queryset.order_by('-followers_count', 'user__username')
        elif sort == '-playlists_count':
            queryset = queryset.order_by('-playlists_count', 'user__username')
        else:
            queryset = queryset.order_by('user__username')
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '')
        context['sort'] = self.request.GET.get('sort', 'user__username')
        return context
