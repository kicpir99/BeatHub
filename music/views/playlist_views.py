import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from django.views.generic import ListView, DetailView, UpdateView
from django.db.models import Count, Q, Sum, Max, F
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



def validate_playlist_data(name, description, is_public):
    """
    Sprawdza dane playlisty pod kątem wulgaryzmów i innych zasad.
    Zwraca (is_valid, error_message).
    """
    if profanity.contains_profanity(name):
        return False, "Nazwa playlisty zawiera niedozwolone słownictwo."
    
    if description and profanity.contains_profanity(description):
        return False, "Opis playlisty zawiera niedozwolone słownictwo."
        
    return True, ""

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
            # liked_song_ids są w mixinie
            context['is_followed'] = self.request.user.profile.followed_playlists.filter(id=self.object.id).exists()
        
        # Paginacja i sortowanie utworów wewnątrz playlisty
        all_positions = self.object.playlistposition_set.select_related(
            'song', 'song__album', 'song__album__artist'
        )
        
        query = self.request.GET.get('q')
        if query:
            all_positions = all_positions.filter(
                Q(song__title__icontains=query) |
                Q(song__album__artist__nickname__icontains=query) |
                Q(song__album__title__icontains=query)
            )
        context['query'] = query or ''
        
        sort_by = self.request.GET.get('sort', 'order')
        allowed_sorts = [
            'song__title', '-song__title', 
            'song__play_count', '-song__play_count', 
            'song__duration_sec', '-song__duration_sec', 
            'order', '-order', 
            'added_at', '-added_at',
            'song__album__title', '-song__album__title',
            'song__album__artist__genre__name', '-song__album__artist__genre__name'
        ]
        
        if sort_by in allowed_sorts:
            all_positions = all_positions.order_by(sort_by)
        else:
            all_positions = all_positions.order_by('order')

        context['current_sort'] = sort_by
        
        per_page = self.request.GET.get('per_page', '15')
        if per_page == 'all':
            items_per_page = 1000  # Duży limit dla widoku edycji
        else:
            try:
                items_per_page = max(5, min(int(per_page), 100))
            except (ValueError, TypeError):
                items_per_page = 15
            
        paginator = Paginator(all_positions, items_per_page)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context.update({
            'playlist_positions': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'per_page': per_page,
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
        base_condition = Q(is_public=True)
        visibility_condition = Q(owner__profile__visibility='public')
        
        if self.request.user.is_authenticated:
            following_ids = self.request.user.profile.following.values_list('id', flat=True)
            visibility_condition |= Q(
                owner__profile__visibility='followers',
                owner__profile__id__in=following_ids
            )
            visibility_condition |= Q(owner=self.request.user)
            
        queryset = Playlist.objects.filter(base_condition & visibility_condition).annotate(
            songs_count=Count('songs', distinct=True),
            followers_count=Count('followed_by', distinct=True),
            total_duration_db=Coalesce(Sum('songs__duration_sec'), 0)
        )
        
        query = self.request.GET.get('q')
        sort = self.request.GET.get('sort', '-created_at')
        genre_ids = self.request.GET.getlist('genre')
        s_min = self.request.GET.get('s_min')
        s_max = self.request.GET.get('s_max')
        d_min = self.request.GET.get('d_min')
        d_max = self.request.GET.get('d_max')

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | 
                Q(owner__username__icontains=query) |
                Q(songs__album__artist__nickname__icontains=query) |
                Q(songs__title__icontains=query)
            ).distinct()

        if genre_ids:
            queryset = queryset.filter(songs__album__artist__genre_id__in=genre_ids).distinct()

        if s_min: queryset = queryset.filter(songs_count__gte=s_min)
        if s_max: queryset = queryset.filter(songs_count__lte=s_max)
        
        if d_min: queryset = queryset.filter(total_duration_db__gte=int(d_min) * 60)
        if d_max: queryset = queryset.filter(total_duration_db__lte=int(d_max) * 60)

        if sort == '-recent_plays_count':
            time_range = self.request.GET.get('time_range', 'all')
            if time_range == 'week':
                cut_off = timezone.now() - timedelta(days=7)
                queryset = queryset.annotate(
                    range_plays=Count('playlist_plays__user', filter=Q(playlist_plays__played_at__gte=cut_off), distinct=True)
                ).order_by('-range_plays', '-created_at')
            elif time_range == 'month':
                cut_off = timezone.now() - timedelta(days=30)
                queryset = queryset.annotate(
                    range_plays=Count('playlist_plays__user', filter=Q(playlist_plays__played_at__gte=cut_off), distinct=True)
                ).order_by('-range_plays', '-created_at')
            else:
                queryset = queryset.annotate(
                    total_plays=Count('playlist_plays__user', distinct=True)
                ).order_by('-total_plays', '-created_at')
        elif sort == '-songs_count':
            queryset = queryset.order_by('-songs_count', '-created_at')
        elif sort == '-followers_count':
            queryset = queryset.order_by('-followers_count', '-created_at')
        elif sort == '-duration':
            queryset = queryset.order_by('-total_duration_db', '-created_at')
        elif sort == 'name':
            queryset = queryset.order_by('name')
        else:
            queryset = queryset.order_by('-created_at')

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        apply_cover_seed(context.get('playlists'), context['cover_seed'])
        stats = Playlist.objects.filter(is_public=True).annotate(
            s_count=Count('songs'),
            t_dur=Coalesce(Sum('songs__duration_sec'), 0)
        ).aggregate(
            max_s=Max('s_count'),
            max_d=Max('t_dur')
        )
        max_songs_limit = stats['max_s'] or 100
        max_duration_limit = (stats['max_d'] // 60) + 1 if stats['max_d'] else 180
        context.update({
            'query': self.request.GET.get('q', ''),
            'per_page': self.request.GET.get('per_page', '15'),
            'selected_genres': self.request.GET.getlist('genre'),
            'max_songs_limit': max_songs_limit,
            'max_duration_limit': max_duration_limit,
            's_min': self.request.GET.get('s_min', 0),
            's_max': self.request.GET.get('s_max', max_songs_limit),
            'd_min': self.request.GET.get('d_min', 0),
            'd_max': self.request.GET.get('d_max', max_duration_limit),
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
        seed = update_cover_seed(self.request)
        queryset = Playlist.objects.filter(followedplaylist__profile=self.request.user.profile).annotate(
            songs_count=Count('songs', distinct=True),
            followers_count=Count('followed_by', distinct=True),
            total_duration_db=Coalesce(Sum('songs__duration_sec'), 0),
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
        return context

@login_required
@require_POST
def toggle_playlist_follow_ajax(request):
    """Obserwuj lub przestań obserwować playlistę."""
    try:
        data = json.loads(request.body)
        playlist_id = data.get('playlist_id')
        playlist = get_object_or_404(Playlist, id=playlist_id)
        profile = request.user.profile

        if playlist.owner == request.user:
            return JsonResponse({'status': 'error', 'message': 'Nie możesz obserwować własnej playlisty'})

        if profile.followed_playlists.filter(id=playlist_id).exists():
            profile.followed_playlists.remove(playlist)
            is_followed = False
            message = f'Przestałeś obserwować playlistę: {playlist.name}'
        else:
            profile.followed_playlists.add(playlist)
            is_followed = True
            message = f'Obserwujesz teraz playlistę: {playlist.name}'

        return JsonResponse({
            'status': 'success',
            'is_followed': is_followed,
            'message': message,
            'followers_count': playlist.followed_by.count()
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def update_followed_playlists_order(request):
    """Aktualizuje manualną kolejność obserwowanych playlist."""
    try:
        data = json.loads(request.body)
        orders = data.get('orders', [])
        profile = request.user.profile
        for item in orders:
            p_id = item.get('id')
            new_order = item.get('order')
            FollowedPlaylist.objects.filter(profile=profile, playlist_id=p_id).update(order=new_order)
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def remove_from_playlist_ajax(request):
    """Usuwa utwór z playlisty."""
    try:
        data = json.loads(request.body)
        playlist_id = data.get('playlist_id')
        song_id = data.get('song_id')
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
        song = get_object_or_404(Song, id=song_id)
        PlaylistPosition.objects.filter(playlist=playlist, song=song).delete()
        return JsonResponse({'status': 'success', 'message': f'Usunięto z playlisty: {playlist.name}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def delete_playlist_ajax(request, playlist_id):
    """Usuwa całą playlistę."""
    try:
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
        name = playlist.name
        playlist.delete()
        return JsonResponse({'status': 'success', 'message': f'Usunięto playlistę: {name}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def add_to_playlist_ajax(request):
    """Dodaje utwór lub wiele utworów do playlisty lub tworzy nową."""
    try:
        data = json.loads(request.body)
        song_id = data.get('song_id')
        song_ids = data.get('song_ids') or []
        playlist_id = data.get('playlist_id')
        new_playlist_name = data.get('new_playlist_name')
        is_public = data.get('is_public', False)

        if new_playlist_name:
            is_valid, error_msg = validate_playlist_data(new_playlist_name, "", is_public)
            if not is_valid:
                return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
            playlist = Playlist.objects.create(name=new_playlist_name, owner=request.user, is_public=is_public)
        else:
            playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)

        # Ujednolicamy do listy song_ids
        final_song_ids = []
        if song_id: final_song_ids.append(song_id)
        if song_ids: final_song_ids.extend(song_ids)
        
        # Usuwamy duplikaty w żądaniu
        final_song_ids = list(dict.fromkeys(final_song_ids))

        if final_song_ids:
            last_position = PlaylistPosition.objects.filter(playlist=playlist).order_by('-order').first()
            next_order = (last_position.order + 1) if last_position else 1
            
            added_count = 0
            for s_id in final_song_ids:
                song = get_object_or_404(Song, id=s_id)
                if not PlaylistPosition.objects.filter(playlist=playlist, song=song).exists():
                    PlaylistPosition.objects.create(playlist=playlist, song=song, order=next_order)
                    next_order += 1
                    added_count += 1
            
            if len(final_song_ids) == 1 and added_count == 0:
                return JsonResponse({'status': 'error', 'message': f'Utwór jest już na liście: {playlist.name}'})
            
            msg = f'Dodano {added_count} utworów do playlisty: {playlist.name}' if added_count > 1 else f'Dodano do playlisty: {playlist.name}'
            return JsonResponse({'status': 'success', 'message': msg})

        return JsonResponse({'status': 'success', 'message': f'Utworzono playlistę: {playlist.name}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def edit_playlist_ajax(request, playlist_id):
    """Edytuje podstawowe dane playlisty przez AJAX."""
    try:
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
        data = json.loads(request.body)
        new_name = data.get('name')
        new_description = data.get('description', '')
        new_is_public = data.get('is_public', playlist.is_public)
        is_valid, error_msg = validate_playlist_data(new_name, new_description, new_is_public)
        if not is_valid:
            return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
        playlist.name = new_name
        playlist.description = new_description
        playlist.is_public = new_is_public
        playlist.save()
        return JsonResponse({'status': 'success', 'message': 'Playlista została pomyślnie zaktualizowana.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def get_user_playlists_ajax(request):
    """Zwraca listę playlist użytkownika do selektora 'Dodaj do'."""
    playlists = Playlist.objects.filter(owner=request.user).order_by('-created_at')
    data = [{'id': p.id, 'name': p.name} for p in playlists]
    return JsonResponse({'playlists': data})

@login_required
@require_POST
def bulk_add_to_playlist_ajax(request):
    """Masowe dodawanie utworów do playlisty."""
    try:
        data = json.loads(request.body)
        song_ids = data.get('song_ids', [])
        playlist_id = data.get('playlist_id')
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
        last_pos = PlaylistPosition.objects.filter(playlist=playlist).order_by('-order').first()
        next_order = last_pos.order + 1 if last_pos else 1
        added_count = 0
        for s_id in song_ids:
            song = Song.objects.get(id=s_id)
            if not PlaylistPosition.objects.filter(playlist=playlist, song=song).exists():
                PlaylistPosition.objects.create(playlist=playlist, song=song, order=next_order)
                next_order += 1
                added_count += 1
        return JsonResponse({'status': 'success', 'message': f'Dodano {added_count} utworów do playlisty {playlist.name}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def bulk_remove_from_playlist_ajax(request):
    """Masowe usuwanie utworów z playlisty."""
    try:
        data = json.loads(request.body)
        song_ids = data.get('song_ids', [])
        playlist_id = data.get('playlist_id')
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
        PlaylistPosition.objects.filter(playlist=playlist, song_id__in=song_ids).delete()
        return JsonResponse({'status': 'success', 'message': f'Usunięto {len(song_ids)} utworów z playlisty {playlist.name}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def copy_playlist_ajax(request):
    """Kopiuje cudzą playlistę jako własną (do nowej lub istniejącej)."""
    try:
        data = json.loads(request.body)
        source_id = data.get('source_playlist_id') or data.get('playlist_id')
        mode = data.get('mode', 'new')
        target_id = data.get('target_playlist_id')
        new_name = data.get('new_name')

        original = get_object_or_404(Playlist, id=source_id)
        positions = original.playlistposition_set.all().select_related('song')

        if mode == 'existing' and target_id:
            target_playlist = get_object_or_404(Playlist, id=target_id, owner=request.user)
            last_pos = PlaylistPosition.objects.filter(playlist=target_playlist).order_by('-order').first()
            next_order = (last_pos.order + 1) if last_pos else 1
            
            added_count = 0
            for pos in positions:
                if not PlaylistPosition.objects.filter(playlist=target_playlist, song=pos.song).exists():
                    PlaylistPosition.objects.create(playlist=target_playlist, song=pos.song, order=next_order)
                    next_order += 1
                    added_count += 1
            return JsonResponse({'status': 'success', 'message': f'Dodano {added_count} utworów do playlisty {target_playlist.name}'})
        else:
            final_name = new_name or f"Kopia - {original.name}"
            is_valid, error_msg = validate_playlist_data(final_name, "", False)
            if not is_valid:
                return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
                
            new_playlist = Playlist.objects.create(name=final_name, owner=request.user, is_public=False)
            for pos in positions:
                PlaylistPosition.objects.create(playlist=new_playlist, song=pos.song, order=pos.order)
            return JsonResponse({'status': 'success', 'message': f'Skopiowano playlistę jako: {new_playlist.name}'})
            
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def reorder_playlist_ajax(request):
    """Zmienia kolejność utworów wewnątrz playlisty (Drag & Drop)."""
    try:
        data = json.loads(request.body)
        playlist_id = data.get('playlist_id')
        position_ids = data.get('position_ids', [])
        playlist = get_object_or_404(Playlist, id=playlist_id, owner=request.user)
        
        # Pobieramy obiekty pozycji playlisty
        positions = PlaylistPosition.objects.filter(playlist=playlist, id__in=position_ids)
        pos_map = {str(p.id): p for p in positions}
        
        to_update = []
        for index, pos_id in enumerate(position_ids):
            p_obj = pos_map.get(str(pos_id))
            if p_obj:
                p_obj.order = index + 1
                to_update.append(p_obj)
        
        if to_update:
            PlaylistPosition.objects.bulk_update(to_update, ['order'])
            
        return JsonResponse({'status': 'success', 'message': 'Kolejność została zapisana.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

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
        new_name = form.cleaned_data.get('name')
        new_description = form.cleaned_data.get('description', '')
        new_is_public = form.cleaned_data.get('is_public', False)
        is_valid, error_msg = validate_playlist_data(new_name, new_description, new_is_public)
        if not is_valid:
            form.add_error(None, error_msg)
            messages.error(self.request, error_msg)
            return self.form_invalid(form)
        context = self.get_context_data()
        songs_formset = context['songs_formset']
        if songs_formset.is_valid():
            self.object = form.save()
            songs_formset.instance = self.object
            songs_formset.save()
            messages.success(self.request, "Playlista została pomyślnie zaktualizowana.")
            return redirect('music:playlist_detail', pk=self.object.id)
        return self.form_invalid(form)

    def form_invalid(self, form):
        response = super().form_invalid(form)
        response.status_code = 422
        return response

    def get_success_url(self):
        return reverse_lazy('music:playlist_detail', kwargs={'pk': self.object.id})
