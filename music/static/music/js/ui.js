window.BeatHub = window.BeatHub || {};
BeatHub.UI = BeatHub.UI || {};

// --- PROFILE & DROPDOWNS ---

BeatHub.UI.toggleProfileMenu = e => { 
    if (e) e.stopPropagation(); 
    const m = document.getElementById('profile-menu'); 
    if(!m) return; 
    if(m.classList.contains('hidden')){ 
        m.classList.remove('hidden'); 
        setTimeout(() => m.classList.replace('opacity-0', 'opacity-100'), 10); 
    } else { 
        m.classList.replace('opacity-100', 'opacity-0'); 
        setTimeout(() => m.classList.add('hidden'), 200); 
    } 
};

BeatHub.UI.toggleDropdown = (e, id) => {
    if (e && typeof e.stopPropagation === 'function') e.stopPropagation();
    const d = document.getElementById(id);
    if (!d) return;
    
    const isHidden = d.classList.contains('hidden');
    
    document.querySelectorAll('.song-dropdown').forEach(el => {
        if (el.id !== id) {
            el.classList.add('hidden');
            el.classList.replace('opacity-100', 'opacity-0');
        }
    });
    
    if (isHidden) {
        d.classList.remove('hidden');
        setTimeout(() => d.classList.replace('opacity-0', 'opacity-100'), 10);
    } else {
        d.classList.replace('opacity-100', 'opacity-0');
        setTimeout(() => d.classList.add('hidden'), 200);
    }
};

// --- NAVIGATION & PAGINATION ---

BeatHub.UI.visitPreservingScroll = function(url) {
    var scrollContainer = document.querySelector('main');
    if (scrollContainer) {
        sessionStorage.setItem('scrollPosition', scrollContainer.scrollTop);
    }
    if (window.Turbo) {
        window.Turbo.cache.clear();
        window.Turbo.visit(url, { action: "replace", scroll: false });
    } else {
        window.location.href = url;
    }
};

BeatHub.UI.goToPage = (input, paramName = 'page') => {
    let val = parseInt(input.value);
    const max = parseInt(input.max) || 1;
    const min = parseInt(input.min) || 1;
    if (isNaN(val)) val = 1;
    if (val > max) val = max;
    if (val < min) val = min;
    input.value = val;

    const p = new URLSearchParams(window.location.search);
    p.set(paramName, val);

    if ((window.location.pathname.includes('albums/') || window.location.pathname.includes('songs/')) && typeof window.fetchFilteredResults === 'function') {
        if (paramName === 'page_s') window.fetchFilteredResults(null, val);
        else window.fetchFilteredResults(val);
    } else if (window.location.pathname.includes('community-playlists/') && typeof window.fetchFilteredPlaylists === 'function') {
        window.fetchFilteredPlaylists(val);
    } else {
        const target = window.location.pathname.includes('artist/') ? ('?' + p.toString() + '#all-songs-section') : ('?' + p.toString());
        BeatHub.UI.visitPreservingScroll(target);
    }
};

// --- DRAGGABLE QUEUE ---

BeatHub.UI.initQueueDraggable = () => {
    const p = document.getElementById("queue-panel");
    const h = document.getElementById("queue-drag-handle");
    if(!p || !h) return;
    
    let x1=0, y1=0, x2=0, y2=0; 
    h.onmousedown = e => {
        e.preventDefault(); 
        const rect = p.getBoundingClientRect(); 
        p.style.top = rect.top + "px"; 
        p.style.left = rect.left + "px"; 
        p.style.bottom = "auto"; 
        p.style.right = "auto"; 
        p.style.margin = "0"; 
        x2 = e.clientX; 
        y2 = e.clientY;
        
        document.onmouseup = () => {
            document.onmouseup = null;
            document.onmousemove = null;
            p.style.transition = 'all 0.3s ease';
        };
        
        document.onmousemove = ev => { 
            ev.preventDefault(); 
            x1 = x2 - ev.clientX; 
            y1 = y2 - ev.clientY; 
            x2 = ev.clientX; 
            y2 = ev.clientY; 
            p.style.transition = 'none'; 
            p.style.top = (p.offsetTop - y1) + "px"; 
            p.style.left = (p.offsetLeft - x1) + "px"; 
        };
    };
};

// --- SELECTION MODE ---

BeatHub.UI.selectionState = {
    mode: false,
    selectedSongs: new Set(),
    lastSelectedIndex: null
};

BeatHub.UI.toggleSelectionMode = () => {
    BeatHub.UI.selectionState.mode = !BeatHub.UI.selectionState.mode;
    const btn = document.getElementById('selection-mode-btn');
    if (!btn) return;

    const isRed = window.location.pathname.includes('/liked-songs');
    const textClass = isRed ? 'text-red-500' : 'text-green-500';
    const borderClass = isRed ? 'border-red-500/50' : 'border-green-500/50';
    
    if (BeatHub.UI.selectionState.mode) {
        btn.classList.replace('text-text-secondary', textClass);
        btn.classList.replace('border-border-main', borderClass);
        btn.classList.add('bg-background-card');
        btn.querySelector('span').textContent = 'Zakończ wybieranie';
        if (BeatHub.UI.showToast) BeatHub.UI.showToast("Tryb wyboru aktywny. Klikaj w utwory, aby je zaznaczyć.", true);
    } else {
        BeatHub.UI.clearSelection();
        btn.classList.replace(textClass, 'text-text-secondary');
        btn.classList.replace(borderClass, 'border-border-main');
        btn.classList.remove('bg-background-card');
        btn.querySelector('span').textContent = 'Wybierz';
    }
};

BeatHub.UI.handleRowClick = (e, i, queueType, rowElement = null) => { 
    if(e.target.closest('a') || e.target.closest('button') || e.target.closest('.drag-handle')) return; 
    
    const row = rowElement || e.currentTarget;
    const songId = row.dataset.songId;
    const cType = row.dataset.contextType;
    const cId = row.dataset.contextId;
    const context = (cType && cType !== 'null') ? { type: cType, id: cId || null } : null;

    if (BeatHub.UI.selectionState.mode || e.ctrlKey || e.metaKey || e.shiftKey) {
        e.preventDefault();
        window.getSelection().removeAllRanges(); 

        if (e.shiftKey && BeatHub.UI.selectionState.lastSelectedIndex !== null) {
            const start = Math.min(BeatHub.UI.selectionState.lastSelectedIndex, i);
            const end = Math.max(BeatHub.UI.selectionState.lastSelectedIndex, i);
            const allRows = document.querySelectorAll('.song-row');
            for (let j = start; j <= end; j++) {
                const r = allRows[j];
                if (r) {
                    const sid = r.dataset.songId;
                    if (!BeatHub.UI.selectionState.selectedSongs.has(sid)) {
                        BeatHub.UI.toggleRowSelection(r, sid, true);
                    }
                }
            }
        } else {
            BeatHub.UI.toggleRowSelection(row, songId);
        }
        BeatHub.UI.selectionState.lastSelectedIndex = i;
        return;
    }

    BeatHub.UI.selectionState.lastSelectedIndex = i;

    // Normal play click
    const currentSong = window.currentQueue ? window.currentQueue[0] : null;
    const isSameSong = currentSong && String(songId) === String(currentSong.id);
    
    const getNormId = id => (id === null || id === undefined || id === '' || id === 'null' || id === 'None' || id === 'undefined') ? null : String(id);
    const getNormType = t => (t === null || t === undefined || t === '' || t === 'null') ? 'queue' : String(t).toLowerCase();
    
    const currCtxType = window.currentPlaybackContext ? window.currentPlaybackContext.type : null;
    const currCtxId = window.currentPlaybackContext ? window.currentPlaybackContext.id : null;
    const newCtxType = context ? context.type : null;
    const newCtxId = context ? context.id : null;

    const isSameContext = getNormType(currCtxType) === getNormType(newCtxType) &&
                          getNormId(currCtxId) === getNormId(newCtxId);

    if (isSameSong && isSameContext) {
        if (window.toggleGlobalPlay) window.toggleGlobalPlay();
        return;
    }

    let queue;
    if (queueType === 'trending_artist') queue = window.trendingArtistQueue;
    else if (queueType === 'artist_top') queue = window.artistTopQueue;
    else queue = window.pageQueue;
    
    if(!queue || !queue[i]) return;
    if (window.playGlobalQueue) window.playGlobalQueue(queue, i, context);
};

BeatHub.UI.toggleRowSelection = (row, id, forceSelect = null) => {
    const isRed = window.location.pathname.includes('/liked-songs');
    const selectClass = isRed ? 'bg-red-500/10' : 'bg-green-500/10';
    const borderClass = isRed ? 'border-red-500/30' : 'border-green-500/30';

    const shouldSelect = forceSelect !== null ? forceSelect : !BeatHub.UI.selectionState.selectedSongs.has(id);

    if (!shouldSelect) {
        BeatHub.UI.selectionState.selectedSongs.delete(id);
        row.classList.remove(selectClass, borderClass, 'selected-row', 'border-l-4');
    } else {
        BeatHub.UI.selectionState.selectedSongs.add(id);
        row.classList.add(selectClass, borderClass, 'selected-row', 'border-l-4');
    }
    BeatHub.UI.updateBulkActionBar();
};

BeatHub.UI.updateBulkActionBar = () => {
    const bar = document.getElementById('bulk-action-bar');
    const count = document.getElementById('selected-count');
    const removeBtn = document.getElementById('bulk-remove-btn');
    const likeBtn = document.getElementById('bulk-like-btn');
    const unlikeBtn = document.getElementById('bulk-unlike-btn');
    if (!bar || !count) return;

    const isRed = window.location.pathname.includes('/liked-songs');
    count.textContent = BeatHub.UI.selectionState.selectedSongs.size;
    
    if (BeatHub.UI.selectionState.selectedSongs.size > 0) {
        bar.classList.remove('hidden');
        
        if (isRed) {
            if(likeBtn) {
                likeBtn.classList.add('hidden');
                likeBtn.classList.remove('flex');
            }
            if(unlikeBtn) {
                unlikeBtn.classList.remove('hidden');
                unlikeBtn.classList.add('flex');
            }
        } else {
            if(likeBtn) {
                likeBtn.classList.remove('hidden');
                likeBtn.classList.add('flex');
            }
            if(unlikeBtn) {
                unlikeBtn.classList.remove('hidden');
                unlikeBtn.classList.add('flex');
            }
        }

        if (window.location.pathname.includes('/playlists/')) {
            removeBtn.classList.remove('hidden');
            removeBtn.classList.add('flex');
        } else {
            removeBtn.classList.add('hidden');
            removeBtn.classList.remove('flex');
        }
    } else {
        bar.classList.add('hidden');
    }
};

BeatHub.UI.clearSelection = () => {
    BeatHub.UI.selectionState.selectedSongs.clear();
    BeatHub.UI.selectionState.lastSelectedIndex = null;
    document.querySelectorAll('.selected-row').forEach(row => {
        row.classList.remove('bg-red-500/10', 'bg-green-500/10', 'border-red-500/30', 'border-green-500/30', 'selected-row', 'border-l-4');
    });
    BeatHub.UI.updateBulkActionBar();
};

// --- BULK ACTIONS ---

BeatHub.Interactions = BeatHub.Interactions || {};

BeatHub.Interactions.handleBulkLike = () => {
    if (!window.BEATHUB_CONFIG.isAuthenticated) {
        if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Zaloguj się, aby dodawać utwory do polubionych.", "warning");
        return;
    }
    const ids = Array.from(BeatHub.UI.selectionState.selectedSongs);
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
    fetch(window.BEATHUB_CONFIG.urls.bulkLike, {
        method: "POST", 
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrf},
        body: JSON.stringify({song_ids: ids, action: 'like'})
    }).then(r => r.json()).then(d => {
        if(d.status === 'success') {
            sessionStorage.setItem('pendingToast', JSON.stringify({ msg: d.message, success: true }));
            BeatHub.UI.clearSelection();
            if (window.visitPreservingScroll) window.visitPreservingScroll(window.location.pathname);
            else if (window.Turbo) window.Turbo.visit(window.location.pathname, { action: "replace" });
            else window.location.reload();
        }
    });
};

BeatHub.Interactions.handleBulkUnlike = () => {
    if (!window.BEATHUB_CONFIG.isAuthenticated) {
        if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Zaloguj się, aby usuwać utwory z polubionych.", "warning");
        return;
    }
    const ids = Array.from(BeatHub.UI.selectionState.selectedSongs);
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
    fetch(window.BEATHUB_CONFIG.urls.bulkLike, {
        method: "POST", 
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrf},
        body: JSON.stringify({song_ids: ids, action: 'unlike'})
    }).then(r => r.json()).then(d => {
        if(d.status === 'success') {
            sessionStorage.setItem('pendingToast', JSON.stringify({ msg: d.message, success: true }));
            BeatHub.UI.clearSelection();
            if (window.visitPreservingScroll) window.visitPreservingScroll(window.location.pathname);
            else if (window.Turbo) window.Turbo.visit(window.location.pathname, { action: "replace" });
            else window.location.reload();
        }
    });
};

BeatHub.Interactions.handleBulkAddToPlaylist = () => {
    if (!window.BEATHUB_CONFIG.isAuthenticated) {
        if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Zaloguj się, aby dodawać utwory do playlisty.", "warning");
        return;
    }
    const ids = Array.from(BeatHub.UI.selectionState.selectedSongs);
    if (BeatHub.Playlists && BeatHub.Playlists.openModal) {
        BeatHub.Playlists.openModal(ids, `${ids.length} wybranych utworów`);
    }
};

BeatHub.Interactions.handleBulkRemoveFromPlaylist = () => {
    if (!window.BEATHUB_CONFIG.isAuthenticated) {
        if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Zaloguj się, aby usuwać utwory z playlisty.", "warning");
        return;
    }
    const match = window.location.pathname.match(/\/playlists\/(\d+)\//);
    if (!match) return;
    const playlistId = match[1];
    const ids = Array.from(BeatHub.UI.selectionState.selectedSongs);
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    if (!confirm(`Czy na pewno chcesz usunąć ${ids.length} utworów z tej playlisty?`)) return;

    fetch(window.BEATHUB_CONFIG.urls.bulkRemoveFromPlaylist, {
        method: "POST", 
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrf},
        body: JSON.stringify({song_ids: ids, playlist_id: playlistId})
    }).then(r => r.json()).then(d => {
        if(d.status === 'success') {
            sessionStorage.setItem('pendingToast', JSON.stringify({ msg: d.message, success: true }));
            BeatHub.UI.clearSelection();
            if (window.visitPreservingScroll) window.visitPreservingScroll(window.location.pathname);
            else if (window.Turbo) window.Turbo.visit(window.location.pathname, { action: "replace" });
            else window.location.reload();
        }
    });
};

// --- UTILITIES ---

BeatHub.UI.handleShare = async (event, title, url) => {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    
    const shareUrl = url ? (url.startsWith('http') ? url : window.location.origin + url) : window.location.href;
    const shareData = {
        title: title || 'BeatHub',
        text: `Sprawdź to na BeatHub: ${title}`,
        url: shareUrl,
    };

    try {
        if (navigator.share) {
            await navigator.share(shareData);
        } else {
            await navigator.clipboard.writeText(shareData.url);
            if (BeatHub.UI.showToast) BeatHub.UI.showToast("Link został skopiowany do schowka!", true);
        }
    } catch (err) {
        if (err.name !== 'AbortError') {
            try {
                await navigator.clipboard.writeText(shareData.url);
                if (BeatHub.UI.showToast) BeatHub.UI.showToast("Link został skopiowany do schowka!", true);
            } catch (clipErr) {
                if (BeatHub.UI.showToast) BeatHub.UI.showToast("Nie udało się udostępnić linku.", false);
            }
        }
    }
};

BeatHub.UI.copyToClipboard = function(text, successMessage) {
    successMessage = successMessage || "Skopiowano do schowka!";
    navigator.clipboard.writeText(text).then(function() {
        if (BeatHub.UI.showToast) BeatHub.UI.showToast(successMessage, true);
    }).catch(function(err) {
        console.error('Błąd kopiowania: ', err);
        if (BeatHub.UI.showToast) BeatHub.UI.showToast("Błąd kopiowania.", false);
    });
};

BeatHub.UI.toggleSort = function(field) {
    var url = new URL(window.location.href);
    var currentSort = url.searchParams.get('sort');
    var newSort = field;
    
    if (field === 'order') {
        newSort = 'order';
    } else if (currentSort === field) {
        newSort = '-' + field;
    } else if (currentSort === '-' + field) {
        newSort = field;
    }
    
    url.searchParams.set('sort', newSort);
    url.searchParams.delete('page'); 
    
    BeatHub.UI.visitPreservingScroll(url.toString());
};

BeatHub.Interactions.togglePlaylistFollow = (event, playlistId) => {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }
    if (!window.BEATHUB_CONFIG.isAuthenticated) {
        if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Zaloguj się, aby obserwować playlisty.", "warning");
        return;
    }
    const btn = document.getElementById(`follow-btn-${playlistId}`);
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch(window.BEATHUB_CONFIG.urls.togglePlaylistFollow, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf
        },
        body: JSON.stringify({ playlist_id: playlistId })
    })
    .then(r => r.json())
    .then(data => {
        if (data.status === 'success') {
            if (BeatHub.UI.showToast) BeatHub.UI.showToast(data.message, true);
            
            if (btn) {
                const icon = btn.querySelector('svg');
                const text = btn.querySelector('.follow-text');
                
                if (data.is_followed) {
                    btn.classList.remove('text-text-secondary', 'bg-background-card');
                    btn.classList.add('text-rose-500', 'bg-rose-500/20', 'border-rose-500/50');
                    if(icon) icon.classList.add('fill-current');
                    if(text) text.textContent = btn.dataset.textUnfollow || 'Przestań obserwować';
                } else {
                    btn.classList.remove('text-rose-500', 'bg-rose-500/20', 'border-rose-500/50');
                    btn.classList.add('text-text-secondary', 'bg-background-card');
                    if(icon) icon.classList.remove('fill-current');
                    if(text) text.textContent = btn.dataset.textFollow || 'Obserwuj playlistę';
                    
                    if (window.location.pathname.includes('/followed-playlists/')) {
                        const card = document.getElementById(`playlist-card-${playlistId}`);
                        if (card) {
                            card.style.opacity = '0';
                            card.style.transform = 'scale(0.95)';
                            setTimeout(() => {
                                card.remove();
                                const container = document.getElementById('playlists-container');
                                if (container && container.children.length === 0) {
                                    if (window.Turbo) window.Turbo.visit(window.location.href);
                                    else window.location.reload();
                                }
                            }, 300);
                        }
                    }
                }
            }

            const cardCount = document.getElementById(`followers-count-${playlistId}`);
            if (cardCount) cardCount.textContent = `${data.followers_count} obs.`;
            
            const detailCount = document.getElementById('playlist-followers-count');
            if (detailCount && window.location.pathname.includes(`/playlists/${playlistId}/`)) {
                detailCount.textContent = data.followers_count;
            }
        } else {
            if (BeatHub.UI.showToast) BeatHub.UI.showToast(data.message, false);
        }
    })
    .catch(err => {
        console.error(err);
        if (BeatHub.UI.showToast) BeatHub.UI.showToast("Wystąpił błąd podczas próby obserwowania playlisty", false);
    });
};

// --- LISTENERS ---

document.addEventListener('click', e => { 
    const toggleBtn = e.target.closest('[data-dropdown-target]');
    if (toggleBtn) {
        e.preventDefault();
        e.stopPropagation();
        const targetId = toggleBtn.getAttribute('data-dropdown-target');
        BeatHub.UI.toggleDropdown(e, targetId);
        return;
    }

    const cardNav = e.target.closest('.playlist-card-nav');
    if (cardNav && !e.target.closest('.song-dropdown') && !e.target.closest('button') && !e.target.closest('[data-dropdown-target]') && !e.target.closest('[onclick]')) {
        const url = cardNav.getAttribute('data-card-link');
        if (url && window.Turbo) window.Turbo.visit(url);
        else if (url) window.location.href = url;
        return;
    }

    const pm = document.getElementById('profile-menu'); 
    if (pm && !pm.classList.contains('hidden') && !e.target.closest('button[onclick*="toggleProfileMenu"]')) {
        pm.classList.replace('opacity-100', 'opacity-0');
        setTimeout(() => pm.classList.add('hidden'), 200);
    } 
    
    const isClickInsideDropdown = e.target.closest('.song-dropdown');
    const isClickOnLegacyToggle = e.target.closest('[onclick*="toggleDropdown"]');

    if (!isClickInsideDropdown && !isClickOnLegacyToggle) {
        document.querySelectorAll('.song-dropdown').forEach(el => {
            if (!el.classList.contains('hidden')) {
                el.classList.replace('opacity-100', 'opacity-0');
                setTimeout(() => el.classList.add('hidden'), 200);
            }
        });
    }

    const resumeBtn = e.target.closest('[data-action="resume-playback"]');
    if (resumeBtn) {
        if (e.target.closest('a')) return;
        e.preventDefault();
        e.stopPropagation();
        const type = resumeBtn.getAttribute('data-type');
        const id = resumeBtn.getAttribute('data-id');
        const songId = resumeBtn.getAttribute('data-song-id');
        if (window.resumePlaybackDirectly) window.resumePlaybackDirectly(type, id, songId);
        return;
    }
});

document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    
    if (e.code === 'Space') {
        e.preventDefault();
        if (window.toggleGlobalPlay) window.toggleGlobalPlay();
    } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        const queuePanel = document.getElementById('queue-panel');
        const isQueueOpen = queuePanel && !queuePanel.classList.contains('hidden');
        
        if (isQueueOpen) {
            if (e.key === 'ArrowRight') { if (window.playNext) window.playNext(); }
            else { if (window.playPrev) window.playPrev(); }
        } else {
            if (window.audio && !isNaN(window.audio.duration)) {
                if (e.key === 'ArrowRight') window.audio.currentTime = Math.min(window.audio.duration, window.audio.currentTime + 5);
                else window.audio.currentTime = Math.max(0, window.audio.currentTime - 5);
            }
        }
    } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
        if (window.audio) {
            e.preventDefault();
            const step = 0.05;
            let newVol = e.key === 'ArrowUp' ? window.audio.volume + step : window.audio.volume - step;
            newVol = Math.max(0, Math.min(1, newVol));
            window.audio.volume = newVol;
            
            // Sync UI
            const vs = document.getElementById('volume-slider');
            if (vs) vs.value = newVol;
            if (BeatHub.Player && BeatHub.Player.updateVolumeBackground) {
                BeatHub.Player.updateVolumeBackground(newVol);
            }
            localStorage.setItem('beathub-volume', newVol);
        }
    } else if (e.key === 'm' || e.key === 'M') {
        if (window.toggleMute) window.toggleMute();
    } else if (e.key === 's' || e.key === 'S') {
        if (window.toggleShuffle) window.toggleShuffle();
    } else if (e.key === 'r' || e.key === 'R') {
        if (window.toggleRepeat) window.toggleRepeat();
    } else if (e.key === 'l' || e.key === 'L') {
        if (window.handlePlayerLike) window.handlePlayerLike();
    } else if (e.key === 'q' || e.key === 'Q') {
        if (window.toggleQueue) window.toggleQueue();
    }
});

document.addEventListener('turbo:load', () => {
    if (BeatHub.UI.initSearchAutocomplete) BeatHub.UI.initSearchAutocomplete();
    if (BeatHub.UI.initQueueDraggable) BeatHub.UI.initQueueDraggable();
    if (typeof BeatHub.UI.clearSelection === 'function') BeatHub.UI.clearSelection();

    const pending = sessionStorage.getItem('pendingToast');
    if (pending) {
        const { msg, success } = JSON.parse(pending);
        if (BeatHub.UI.showToast) BeatHub.UI.showToast(msg, success);
        sessionStorage.removeItem('pendingToast');
    }
});

BeatHub.UI.restoreScroll = function() {
    var scrollPos = sessionStorage.getItem('scrollPosition');
    if (scrollPos) {
        sessionStorage.removeItem('scrollPosition');
        requestAnimationFrame(function() {
            var scrollContainer = document.querySelector('main');
            if (scrollContainer) {
                scrollContainer.scrollTop = parseInt(scrollPos);
            }
        });
    }
};

document.addEventListener('turbo:render', BeatHub.UI.restoreScroll);
document.addEventListener('turbo:load', BeatHub.UI.restoreScroll);

document.addEventListener('turbo:before-cache', function() {
    if (window.moodChartInstance) {
        window.moodChartInstance.destroy();
        window.moodChartInstance = null;
    }
    if (window.activityChartInstance) {
        window.activityChartInstance.destroy();
        window.activityChartInstance = null;
    }
});

window.toggleProfileMenu = BeatHub.UI.toggleProfileMenu;
window.toggleDropdown = BeatHub.UI.toggleDropdown;
window.visitPreservingScroll = BeatHub.UI.visitPreservingScroll;
window.goToPage = BeatHub.UI.goToPage;
window.initQueueDraggable = BeatHub.UI.initQueueDraggable;
window.toggleSelectionMode = BeatHub.UI.toggleSelectionMode;
window.handleRowClick = BeatHub.UI.handleRowClick;
window.toggleRowSelection = BeatHub.UI.toggleRowSelection;
window.updateBulkActionBar = BeatHub.UI.updateBulkActionBar;
window.clearSelection = BeatHub.UI.clearSelection;
window.handleBulkLike = BeatHub.Interactions.handleBulkLike;
window.handleBulkUnlike = BeatHub.Interactions.handleBulkUnlike;
window.handleBulkAddToPlaylist = BeatHub.Interactions.handleBulkAddToPlaylist;
window.handleBulkRemoveFromPlaylist = BeatHub.Interactions.handleBulkRemoveFromPlaylist;
window.handleShare = BeatHub.UI.handleShare;
window.copyToClipboard = BeatHub.UI.copyToClipboard;
window.toggleSort = BeatHub.UI.toggleSort;
window.togglePlaylistFollow = BeatHub.Interactions.togglePlaylistFollow;
