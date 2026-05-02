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
from django.utils import timezone, dates
from django.core.exceptions import ValidationError
from datetime import timedelta, datetime

from ..models import Profile, Playlist, Song, SongPlay, LikedSong, Artist
from ..forms import ProfileForm
from ..utils import update_cover_seed, apply_cover_seed, SafePaginationMixin
from ..mixins import MusicContextMixin, ProfileSearchMixin
from ..services.stats_service import get_profile_stats, get_detailed_user_stats
from ..services.profile_service import get_profile_dashboard_context
from ..services import interaction_service
from ..decorators import ajax_error_handler


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
            dashboard_data = get_profile_dashboard_context(profile_user)
            context.update(dashboard_data)
            
            playlists_paginator = Paginator(dashboard_data['public_playlists'], 10)
            playlists_page_num = self.request.GET.get('playlists_page')
            public_playlists = playlists_paginator.get_page(playlists_page_num)
            
            context['public_playlists'] = public_playlists
            apply_cover_seed(public_playlists, seed)

            if profile.show_profile_stats_publicly or is_own_profile:
                context['stats'] = get_profile_stats(profile_user)
                
                all_plays = SongPlay.objects.filter(user=profile_user)
                context['total_plays_count'] = all_plays.count()
                agg_sec = all_plays.aggregate(s=Sum('listened_duration_sec'))['s'] or 0
                context['total_hours_all'] = round(agg_sec / 3600, 1)

        
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
        
        dashboard_data = get_profile_dashboard_context(user)
        context.update(dashboard_data)
        
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
        
        can_view_stats = profile.show_detailed_stats_publicly or is_own_profile
        context['can_view_stats'] = can_view_stats
        context['is_own_profile'] = is_own_profile
        
        if can_view_stats:
            detailed_stats = get_detailed_user_stats(profile_user)
            context.update(detailed_stats)
            
        return context

@login_required
@ajax_error_handler(error_msg='Wystąpił błąd podczas pobierania statystyk.')
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

@ajax_error_handler(error_msg='Wystąpił błąd podczas pobierania statystyk miesięcznych.')
def get_monthly_stats_ajax(request, username, year):
    """Zwraca miesięczne statystyki słuchania dla podanego roku."""
    user = User.objects.get(username=username)
    is_own = request.user == user
    if not (user.profile.show_detailed_stats_publicly or is_own):
        return JsonResponse({'status': 'error', 'message': 'Brak uprawnień'}, status=403)
        
    plays = SongPlay.objects.filter(user=user, played_at__year=year)
    monthly_stats = plays.values('played_at__month').annotate(
        count=Count('id'),
        total_sec=Sum('listened_duration_sec')
    ).order_by('played_at__month')
    
    month_names = [str(dates.MONTHS[m]) for m in range(1, 13)]
    counts_map = {item['played_at__month']: item['count'] for item in monthly_stats}
    hours_map = {item['played_at__month']: round(item['total_sec'] / 3600, 2) for item in monthly_stats}
    
    return JsonResponse({
        'status': 'success',
        'year': year,
        'labels': month_names,
        'counts': [counts_map.get(m, 0) for m in range(1, 13)],
        'hours': [hours_map.get(m, 0) for m in range(1, 13)]
    })

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas zmiany widoczności profilu.')
def set_profile_visibility_ajax(request):
    """Zmienia widoczność profilu."""
    data = json.loads(request.body)
    visibility = data.get('visibility', 'private')
    bio = data.get('bio', '')
    
    profile = request.user.profile
    profile.visibility = visibility
    profile.bio = bio
    profile.location = data.get('location', profile.location)
    
    try:
        profile.full_clean()
        profile.save()
    except ValidationError as e:
        msg = next(iter(e.message_dict.values()))[0]
        return JsonResponse({'status': 'error', 'message': msg})
    
    return JsonResponse({
        'status': 'success',
        'message': f'Widoczność profilu została zmieniona na: {profile.get_visibility_display()}'
    })

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas obserwowania użytkownika.')
def toggle_follow_ajax(request):
    """Przełączanie stanu obserwowania użytkownika."""
    data = json.loads(request.body)
    target_profile_id = data.get('profile_id')
    
    result = interaction_service.toggle_user_follow(request.user, target_profile_id)
    return JsonResponse({'status': 'success', **result})

class ToggleStatsVisibilityView(LoginRequiredMixin, generic.View):
    """Przełącza publiczną widoczność SZCZEGÓŁOWYCH statystyk użytkownika."""
    def post(self, request, *args, **kwargs):
        profile = request.user.profile
        profile.show_detailed_stats_publicly = not profile.show_detailed_stats_publicly
        profile.save()
        
        status = "publiczne" if profile.show_detailed_stats_publicly else "prywatne"
        messages.success(request, f"Dostęp do Twoich statystyk jest teraz ustawiony jako: {status}.")
        return redirect('music:detailed_stats', username=request.user.username)

class UserSearchView(MusicContextMixin, ProfileSearchMixin, SafePaginationMixin, ListView):
    """Widok wyszukiwania użytkowników."""
    model = Profile
    template_name = 'music/user_search.html'
    context_object_name = 'profiles'
    paginate_by = 20
    default_sort = '-followers_count'

    def get_queryset(self):
        if self.request.user.is_authenticated:
            base_filter = Q(visibility__in=['public', 'followers']) | Q(user=self.request.user)
        else:
            base_filter = Q(visibility__in=['public', 'followers'])
            
        queryset = Profile.objects.filter(base_filter).select_related('user').annotate(
            followers_count=Count('followers', distinct=True),
            playlists_count=Count('user__playlists', filter=Q(user__playlists__is_public=True), distinct=True)
        )
        
        if not self.request.GET.get('q') and self.request.user.is_authenticated:
            queryset = queryset.exclude(user=self.request.user)
        
        return self.apply_profile_filters(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return self.get_profile_context(context)

class FollowingListView(LoginRequiredMixin, MusicContextMixin, ProfileSearchMixin, SafePaginationMixin, ListView):
    """Widok listy osób, które obserwuje zalogowany użytkownik."""
    model = Profile
    template_name = 'music/following_list.html'
    context_object_name = 'profiles'
    paginate_by = 20
    default_sort = 'user__username'

    def get_queryset(self):
        queryset = self.request.user.profile.following.all().select_related('user').annotate(
            followers_count=Count('followers', distinct=True),
            playlists_count=Count('user__playlists', filter=Q(user__playlists__is_public=True), distinct=True)
        )
        return self.apply_profile_filters(queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return self.get_profile_context(context)
