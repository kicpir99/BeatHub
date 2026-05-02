import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from django.views.generic import ListView, DetailView, UpdateView
from django.db.models import Count, Q, Sum, Max, F, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from better_profanity import profanity

from ..models import Playlist, Genre, Song, PlaylistPosition, FollowedPlaylist, LikedSong
from ..playlist_forms import PlaylistForm, PlaylistPositionFormSet
from ..utils import SafePaginationMixin, update_cover_seed, apply_cover_seed
from ..mixins import MusicContextMixin
from ..services import playlist_service
from ..decorators import ajax_error_handler




class PlaylistListView(MusicContextMixin, SafePaginationMixin, LoginRequiredMixin, ListView):
    """Widok listy wszystkich playlist zalogowanego użytkownika."""
    model = Playlist
    template_name = 'music/playlist_list.html'
    context_object_name = 'playlists'

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', '15')
        try:
            return max(5, min(int(per_page), 100))
        except ValueError:
            return 15

    def get_queryset(self):
        return Playlist.objects.filter(owner=self.request.user).annotate(
            songs_count=Count('songs', distinct=True),
            followers_count=Count('followed_by', distinct=True)
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        apply_cover_seed(context.get('playlists'), context['cover_seed'])
        context['per_page'] = self.request.GET.get('per_page', '15')
        if self.request.user.is_authenticated:
            context['followed_playlist_ids'] = list(self.request.user.profile.followed_playlists.values_list('id', flat=True))
        return context
    
class PlaylistDetailView(LoginRequiredMixin, MusicContextMixin, DetailView):
    """Widok szczegółów konkretnej playlisty."""
    model = Playlist
    template_name = 'music/playlist_detail.html'
    context_object_name = 'playlist'

    def get_queryset(self):
        return Playlist.objects.all().select_related('owner__profile').annotate(
            followers_count=Count('followed_by', distinct=True)
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        apply_cover_seed(self.object, context['cover_seed'])
        if self.request.user.is_authenticated:
            context['is_followed'] = self.request.user.profile.followed_playlists.filter(id=self.object.id).exists()
        
        playlist_data = playlist_service.get_playlist_detail_data(self.object, self.request.GET)
        
        per_page = self.request.GET.get('per_page', '15')
        items_per_page = 1000 if per_page == 'all' else max(5, min(int(per_page if per_page.isdigit() else 15), 100))
            
        paginator = Paginator(playlist_data['all_positions'], items_per_page)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context.update({
            'playlist_positions': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'per_page': per_page,
            'current_sort': playlist_data['current_sort'],
            'query': playlist_data['query'],
            'is_owner': self.object.owner == self.request.user,
            'back_url': reverse_lazy('music:playlist_list')
        })

        return context

class CommunityPlaylistView(MusicContextMixin, SafePaginationMixin, ListView):
    model = Playlist
    template_name = 'music/community_playlists.html'
    context_object_name = 'playlists'

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', '15')
        try:
            return max(5, min(int(per_page), 100))
        except ValueError:
            return 15

    def get_queryset(self):
        return playlist_service.get_community_playlists_queryset(self.request.user, self.request.GET)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        apply_cover_seed(context.get('playlists'), context['cover_seed'])
        
        comm_context = playlist_service.get_community_playlist_context()
        context.update(comm_context)
        
        context.update({
            'query': self.request.GET.get('q', ''),
            'per_page': self.request.GET.get('per_page', '15'),
            'selected_genres': self.request.GET.getlist('genre'),
            's_min': self.request.GET.get('s_min', 0),
            's_max': self.request.GET.get('s_max', comm_context['max_songs_limit']),
            'd_min': self.request.GET.get('d_min', 0),
            'd_max': self.request.GET.get('d_max', comm_context['max_duration_limit']),
            'time_range': self.request.GET.get('time_range', 'all'),
            'current_sort': self.request.GET.get('sort', '-created_at'),
        })
        return context

class FollowedPlaylistsListView(LoginRequiredMixin, MusicContextMixin, SafePaginationMixin, ListView):
    model = Playlist
    template_name = 'music/followed_playlists.html'
    context_object_name = 'playlists'

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', '15')
        try:
            return max(5, min(int(per_page), 100))
        except ValueError:
            return 15

    def get_queryset(self):
        duration_subquery = Song.objects.filter(
            playlists=OuterRef('pk')
        ).values('playlists').annotate(
            total=Sum('duration_sec')
        ).values('total')

        queryset = Playlist.objects.filter(followedplaylist__profile=self.request.user.profile).annotate(
            songs_count=Count('songs', distinct=True),
            followers_count=Count('followed_by', distinct=True),
            total_duration_db=Coalesce(Subquery(duration_subquery), 0),
            manual_order=F('followedplaylist__order')
        ).order_by('manual_order', '-followedplaylist__followed_at')
        
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(Q(name__icontains=query) | Q(owner__username__icontains=query)).distinct().order_by('-created_at')
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        apply_cover_seed(context.get('playlists'), context['cover_seed'])
        context['query'] = self.request.GET.get('q', '')
        context['per_page'] = self.request.GET.get('per_page', '15')
        if self.request.user.is_authenticated:
            context['followed_playlist_ids'] = list(self.request.user.profile.followed_playlists.values_list('id', flat=True))
        return context

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas obserwowania playlisty.')
def toggle_playlist_follow_ajax(request):
    """Obserwuj lub przestań obserwować playlistę."""
    data = json.loads(request.body)
    playlist_id = data.get('playlist_id')
    success, message, result = playlist_service.toggle_playlist_follow(request.user, playlist_id)
    if not success:
        return JsonResponse({'status': 'error', 'message': message})
    return JsonResponse({'status': 'success', 'message': message, **result})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas zmiany kolejności.')
def update_followed_playlists_order(request):
    """Aktualizuje manualną kolejność obserwowanych playlist."""
    data = json.loads(request.body)
    orders = data.get('orders', [])
    playlist_service.update_followed_order(request.user, orders)
    return JsonResponse({'status': 'success'})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas usuwania z playlisty.')
def remove_from_playlist_ajax(request):
    """Usuwa utwór z playlisty."""
    data = json.loads(request.body)
    playlist_id = data.get('playlist_id')
    song_id = data.get('song_id')
    message = playlist_service.remove_from_playlist(request.user, playlist_id, song_id)
    return JsonResponse({'status': 'success', 'message': message})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas usuwania playlisty.')
def delete_playlist_ajax(request, playlist_id):
    """Usuwa całą playlistę."""
    playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
    name = playlist.name
    playlist.delete()
    return JsonResponse({'status': 'success', 'message': f'Usunięto playlistę: {name}'})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas dodawania do playlisty.')
def add_to_playlist_ajax(request):
    """Dodaje utwór lub wiele utworów do playlisty lub tworzy nową."""
    data = json.loads(request.body)
    success, message, playlist = playlist_service.add_to_playlist(
        user=request.user,
        playlist_id=data.get('playlist_id'),
        song_id=data.get('song_id'),
        song_ids=data.get('song_ids'),
        new_name=data.get('new_playlist_name'),
        is_public=data.get('is_public', False)
    )
    if not success:
        return JsonResponse({'status': 'error', 'message': message}, status=400)
    return JsonResponse({'status': 'success', 'message': message})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas edycji playlisty.')
def edit_playlist_ajax(request, playlist_id):
    """Edytuje podstawowe dane playlisty przez AJAX."""
    playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
    data = json.loads(request.body)
    
    playlist.name = data.get('name', playlist.name)
    playlist.description = data.get('description', playlist.description)
    playlist.is_public = data.get('is_public', playlist.is_public)
    
    is_valid, error_msg = playlist_service.validate_playlist_data(playlist)
    if not is_valid:
        return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
        
    playlist.save()
    return JsonResponse({'status': 'success', 'message': 'Playlista została pomyślnie zaktualizowana.'})

@login_required
def get_user_playlists_ajax(request):
    """Zwraca listę playlist użytkownika do selektora 'Dodaj do'."""
    playlists = Playlist.objects.filter(owner=request.user).order_by('-created_at')
    data = [{'id': p.id, 'name': p.name} for p in playlists]
    return JsonResponse({'playlists': data})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas dodawania utworów.')
def bulk_add_to_playlist_ajax(request):
    """Masowe dodawanie utworów do playlisty."""
    data = json.loads(request.body)
    song_ids = data.get('song_ids', [])
    playlist_id = data.get('playlist_id')
    success, message, playlist = playlist_service.add_to_playlist(
        user=request.user,
        playlist_id=playlist_id,
        song_ids=song_ids
    )
    if not success:
        return JsonResponse({'status': 'error', 'message': message}, status=400)
    return JsonResponse({'status': 'success', 'message': message})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas usuwania utworów.')
def bulk_remove_from_playlist_ajax(request):
    """Masowe usuwanie utworów z playlisty."""
    data = json.loads(request.body)
    song_ids = data.get('song_ids', [])
    playlist_id = data.get('playlist_id')
    message = playlist_service.bulk_remove_from_playlist(request.user, playlist_id, song_ids)
    return JsonResponse({'status': 'success', 'message': message})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas kopiowania playlisty.')
def copy_playlist_ajax(request):
    """Kopiuje cudzą playlistę jako własną (do nowej lub istniejącej)."""
    data = json.loads(request.body)
    result = playlist_service.copy_playlist(
        user=request.user,
        source_id=data.get('source_playlist_id') or data.get('playlist_id'),
        mode=data.get('mode', 'new'),
        target_id=data.get('target_playlist_id'),
        new_name=data.get('new_name')
    )
    if isinstance(result, tuple) and not result[0]:
        return JsonResponse({'status': 'error', 'message': result[1]}, status=400)
    return JsonResponse({'status': 'success', 'message': result})

@login_required
@require_POST
@ajax_error_handler(error_msg='Wystąpił błąd podczas zmiany kolejności.')
def reorder_playlist_ajax(request):
    """Zmienia kolejność utworów wewnątrz playlisty (Drag & Drop)."""
    data = json.loads(request.body)
    playlist_id = data.get('playlist_id')
    position_ids = data.get('position_ids', [])
    start_index = data.get('start_index', 1)
    message = playlist_service.reorder_playlist(request.user, playlist_id, position_ids, start_index)
    return JsonResponse({'status': 'success', 'message': message})

class PlaylistEditView(LoginRequiredMixin, MusicContextMixin, generic.UpdateView):
    """Klasyczny widok edycji playlisty wykorzystujący Formsety."""
    model = Playlist
    form_class = PlaylistForm
    template_name = 'music/playlist_edit_form.html'
    pk_url_kwarg = 'playlist_id'

    def get_queryset(self):
        return Playlist.objects.filter(owner=self.request.user).prefetch_related('playlistposition_set__song__album__artist')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['songs_formset'] = PlaylistPositionFormSet(self.request.POST, instance=self.object)
        else:
            data['songs_formset'] = PlaylistPositionFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        playlist = form.save(commit=False)
        
        is_valid, error_msg = playlist_service.validate_playlist_data(playlist)
        if not is_valid:
            form.add_error(None, error_msg)
            messages.error(self.request, error_msg)
            return self.form_invalid(form)
        
        songs_formset = PlaylistPositionFormSet(self.request.POST, instance=playlist)
        if songs_formset.is_valid():
            playlist.save()
            songs_formset.save()
            messages.success(self.request, "Playlista została pomyślnie zaktualizowana.")
            return redirect('music:playlist_detail', pk=playlist.id)
        
        for err in songs_formset.non_form_errors():
            form.add_error(None, err)
        for s_form in songs_formset:
            for field, errors in s_form.errors.items():
                for error in errors:
                    form.add_error(None, f"Wiersz {s_form.prefix}: {error}")
        return self.form_invalid(form)

    def form_invalid(self, form):
        response = super().form_invalid(form)
        response.status_code = 422
        return response

    def get_success_url(self):
        return reverse_lazy('music:playlist_detail', kwargs={'pk': self.object.id})
