import random
import os
from django.conf import settings
from django.http import Http404
from django.core.paginator import EmptyPage
from better_profanity import profanity

POLISH_BAD_WORDS = os.path.join(settings.BASE_DIR, 'cenzura.txt')

def load_bad_words():
    if os.path.exists(POLISH_BAD_WORDS):
        with open(POLISH_BAD_WORDS, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    return []

profanity.load_censor_words()
profanity.add_censor_words(load_bad_words())

class SafePaginationMixin:
    """Mixin zapobiegający błędom 404 przy nieistniejących stronach paginacji."""
    def paginate_queryset(self, queryset, page_size):
        try:
            return super().paginate_queryset(queryset, page_size)
        except (Http404, EmptyPage):
            paginator = self.get_paginator(queryset, page_size, allow_empty_first_page=self.get_allow_empty())
            page_number = paginator.num_pages if paginator.num_pages > 0 else 1
            page_obj = paginator.page(page_number)
            return (paginator, page_obj, page_obj.object_list, page_obj.has_other_pages())

def apply_cover_seed(playlists, seed):
    """Pomocnik do przypisywania ziarna (seed) do obiektów playlist w celu stabilizacji okładek."""
    if not playlists:
        return
    items = playlists
    if hasattr(playlists, 'object_list'):
        items = playlists.object_list
    
    if not hasattr(items, '__iter__'):
        items = [items]
        
    for p in items:
        if p:
            p.cover_seed = seed

def update_cover_seed(request):
    """
    Odświeża ziarno (seed) w sesji, jeśli nastąpiła nawigacja na inną stronę 
    lub twarde przeładowanie (F5). Pozostawia ziarno bez zmian przy AJAX/Turbo 
    na tej samej ścieżce (np. sortowanie, paginacja).
    """
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    is_turbo = 'X-Turbo-Request-Id' in request.headers
    current_path = request.path
    last_path = request.session.get('last_path_for_seed')
    
    refresh = False
    if not (is_ajax or is_turbo):
        refresh = True
    elif current_path != last_path:
        refresh = True
        
    if refresh or 'cover_seed' not in request.session:
        request.session['cover_seed'] = random.randint(1, 100000)
        request.session['last_path_for_seed'] = current_path
        
    return request.session.get('cover_seed', 1)
