window.BeatHub = window.BeatHub || {};
BeatHub.Playlists = BeatHub.Playlists || {};

BeatHub.Playlists.handlePlayerPlaylist = e => { 
    if(window.currentQueue && window.currentQueue[0]) {
        if (BeatHub.Playlists.openModal) {
            BeatHub.Playlists.openModal(window.currentQueue[0].id, window.currentQueue[0].title); 
        }
    }
};

BeatHub.Playlists.handlePlaylistSubmit = (e) => {
    if (e) e.preventDefault();
    const p = document.getElementById('playlist-select')?.value;
    const n = document.getElementById('new-playlist-name')?.value;
    const c = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    if (window.currentCopyMode === 'copy' && window.sourcePlaylistId) {
        fetch(window.BEATHUB_CONFIG.urls.copyPlaylist, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": c },
            body: JSON.stringify({ 
                source_id: window.sourcePlaylistId,
                new_name: n,
                is_public: true
            })
        }).then(r => r.json()).then(d => {
            if (d.status === 'success') {
                if (BeatHub.Playlists.closeModal) BeatHub.Playlists.closeModal();
                if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast(d.message, true);
                
                if (d.redirect_url && window.Turbo) window.Turbo.visit(d.redirect_url);
                else if (d.redirect_url) window.location.href = d.redirect_url;
            } else {
                if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast(d.message, false);
            }
        });
    } else {
        if (!p && !n) {
            if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Podaj nazwę lub wybierz playlistę!", false);
            return;
        }
        
        const url = window.currentSongIds ? window.BEATHUB_CONFIG.urls.bulkAddToPlaylist : window.BEATHUB_CONFIG.urls.addToPlaylist;
        const payload = window.currentSongIds ? 
            { song_ids: window.currentSongIds, playlist_id: p, new_playlist_name: n } : 
            { song_id: window.currentSongId, playlist_id: p, new_playlist_name: n };

        fetch(url, {
            method: "POST", 
            headers: { "Content-Type": "application/json", "X-CSRFToken": c },
            body: JSON.stringify(payload)
        }).then(r => r.json()).then(d => {
            if (d.status === 'success') { 
                if (BeatHub.Playlists.closeModal) BeatHub.Playlists.closeModal(); 
                const shouldVisit = window.location.pathname.includes('/playlists/') || window.location.pathname.includes('/liked-songs');
                
                if (shouldVisit) {
                    sessionStorage.setItem('pendingToast', JSON.stringify({ msg: d.message, success: true }));
                    if (window.Turbo) window.Turbo.visit(window.location.href, { action: "replace" });
                    else window.location.reload();
                } else {
                    if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast(d.message, true);
                }
                if (BeatHub.UI && BeatHub.UI.clearSelection) BeatHub.UI.clearSelection();
            } else { 
                if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast(d.message, false); 
            }
        });
    }
};

BeatHub.Playlists.togglePlaylistPrivacy = (playlistId, elementOrState) => {
    let isCheckbox = (typeof elementOrState === 'object');
    let newPublicState = isCheckbox ? elementOrState.checked : !elementOrState;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    fetch(`/playlist/edit/${playlistId}/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ is_public: newPublicState }) 
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            let msg = newPublicState ? "Playlista jest teraz publiczna" : "Playlista jest teraz prywatna";
            if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast(msg, true);
            const label = document.getElementById('detail-privacy-label');
            if (label) {
                label.textContent = newPublicState ? 'Playlista publiczna' : 'Playlista prywatna';
                label.classList.remove('text-primary', 'text-text-muted');
                label.classList.add(newPublicState ? 'text-primary' : 'text-text-muted');
            }
            document.querySelectorAll('.song-dropdown').forEach(el => {
                el.classList.add('hidden');
                el.classList.replace('opacity-100', 'opacity-0');
            });
        } else {
            if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast(data.message, false);
            if (isCheckbox) elementOrState.checked = !newPublicState;
        }
    })
    .catch(error => {
        if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Wystąpił błąd podczas zmiany statusu.", false);
        if (isCheckbox) elementOrState.checked = !newPublicState; 
    });
};

BeatHub.Playlists.handleDeletePlaylist = (e, playlistId) => {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    if (!confirm("Czy na pewno chcesz usunąć tę playlistę? Tej operacji nie można cofnąć.")) return;

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    fetch(`/playlist/delete/${playlistId}/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast(data.message || "Playlista została usunięta", true);
            
            document.querySelectorAll('.song-dropdown').forEach(el => {
                el.classList.add('hidden');
                el.classList.replace('opacity-100', 'opacity-0');
            });

            const redirectUrl = window.location.pathname.includes(`/playlists/${playlistId}`) 
                ? window.BEATHUB_CONFIG.urls.playlistList 
                : window.location.href;

            sessionStorage.setItem('pendingToast', JSON.stringify({ msg: data.message || "Playlista została usunięta", success: true }));
            if (window.Turbo) window.Turbo.visit(redirectUrl, { action: "replace" });
            else window.location.href = redirectUrl;
        } else {
            if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast(data.message || "Wystąpił błąd podczas usuwania", false);
        }
    })
    .catch(error => {
        if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Wystąpił błąd serwera.", false);
    });
};

// --- PLAYBACK TRIGGERS ---

BeatHub.Playlists.handlePlaylistToggle = (playlistId, songs) => {
    const isSameContext = window.currentPlaybackContext && 
                         window.currentPlaybackContext.type === 'playlist' && 
                         String(window.currentPlaybackContext.id) === String(playlistId);
    
    const hasSource = window.audio && window.audio.src && window.audio.src !== window.location.href;

    if (isSameContext && hasSource) {
        if (window.toggleGlobalPlay) window.toggleGlobalPlay();
    } else {
        if (window.playGlobalQueue) window.playGlobalQueue(songs, 0, {type: 'playlist', id: playlistId});
    }
};

BeatHub.Playlists.handleAlbumToggle = (albumId, songs) => {
    const isSameContext = window.currentPlaybackContext && 
                         window.currentPlaybackContext.type === 'album' && 
                         String(window.currentPlaybackContext.id) === String(albumId);

    const hasSource = window.audio && window.audio.src && window.audio.src !== window.location.href;

    if (isSameContext && hasSource) {
        if (window.toggleGlobalPlay) window.toggleGlobalPlay();
    } else {
        if (window.playGlobalQueue) window.playGlobalQueue(songs, 0, {type: 'album', id: albumId});
    }
};

// --- ICON UPDATES ---

BeatHub.Playlists.updatePlaylistIcons = () => {
    if (!window.audio) return;
    const isPlaying = !window.audio.paused;
    const activeId = String(window.currentPlaylistId);

    document.querySelectorAll('.playlist-play-trigger').forEach(btn => {
        const btnId = String(btn.getAttribute('data-playlist-id'));
        const playIcon = btn.querySelector('.play-icon');
        const pauseIcon = btn.querySelector('.pause-icon');
        const card = document.getElementById(`playlist-card-${btnId}`);

        if (btnId === activeId && isPlaying) {
            if (playIcon) playIcon.classList.add('hidden');
            if (pauseIcon) pauseIcon.classList.remove('hidden');
            btn.classList.add('active-playing'); 
            if(card) card.classList.add('playing-card-glow');
        } else {
            if (playIcon) playIcon.classList.remove('hidden');
            if (pauseIcon) pauseIcon.classList.add('hidden');
            btn.classList.remove('active-playing');
            if(card) card.classList.remove('playing-card-glow');
        }
    });
};

BeatHub.Playlists.updateAlbumIcons = () => {
    if (!window.audio) return;
    const isPlaying = !window.audio.paused;
    const activeId = String(window.currentAlbumId);

    document.querySelectorAll('.album-play-trigger').forEach(btn => {
        const btnId = String(btn.getAttribute('data-album-id'));
        const playIcon = btn.querySelector('.play-icon');
        const pauseIcon = btn.querySelector('.pause-icon');
        const card = document.getElementById(`album-card-${btnId}`);

        if (btnId === activeId && isPlaying) {
            if (playIcon) playIcon.classList.add('hidden');
            if (pauseIcon) pauseIcon.classList.remove('hidden');
            btn.classList.add('active-playing'); 
            if(card) {
                card.classList.add('playing-card-glow');
                const badge = card.querySelector('.playing-badge');
                if(badge) badge.classList.replace('hidden', 'flex');
            }
        } else {
            if (playIcon) playIcon.classList.remove('hidden');
            if (pauseIcon) pauseIcon.classList.add('hidden');
            btn.classList.remove('active-playing');
            if(card) {
                card.classList.remove('playing-card-glow');
                const badge = card.querySelector('.playing-badge');
                if(badge) badge.classList.replace('flex', 'hidden');
            }
        }
    });
};

BeatHub.Playlists.updateSongCardIcons = () => {
    if (!window.audio) return;
    const isPlaying = !window.audio.paused;
    const currentSong = window.currentQueue ? window.currentQueue[0] : null;
    const activeId = currentSong ? String(currentSong.id) : null;

    document.querySelectorAll('.song-card-play-trigger').forEach(btn => {
        const btnId = String(btn.getAttribute('data-song-id'));
        const playIcon = btn.querySelector('.play-icon');
        const pauseIcon = btn.querySelector('.pause-icon');
        const card = document.getElementById(`song-card-${btnId}`);

        if (activeId && btnId === activeId && isPlaying) {
            if(playIcon) playIcon.classList.add('hidden');
            if(pauseIcon) pauseIcon.classList.remove('hidden');
            btn.classList.add('active-playing'); 
            if(card) {
                card.classList.add('playing-card-glow');
                const badge = card.querySelector('.playing-badge');
                if(badge) badge.classList.replace('hidden', 'flex');
            }
        } else {
            if(playIcon) playIcon.classList.remove('hidden');
            if(pauseIcon) pauseIcon.classList.add('hidden');
            btn.classList.remove('active-playing');
            if(card) {
                card.classList.remove('playing-card-glow');
                const badge = card.querySelector('.playing-badge');
                if(badge) badge.classList.replace('flex', 'hidden');
            }
        }
    });
};

window.handlePlayerPlaylist = BeatHub.Playlists.handlePlayerPlaylist;
window.handlePlaylistSubmit = BeatHub.Playlists.handlePlaylistSubmit;
window.togglePlaylistPrivacy = BeatHub.Playlists.togglePlaylistPrivacy;
window.handleDeletePlaylist = BeatHub.Playlists.handleDeletePlaylist;
window.handlePlaylistToggle = BeatHub.Playlists.handlePlaylistToggle;
window.handleAlbumToggle = BeatHub.Playlists.handleAlbumToggle;
window.updatePlaylistIcons = BeatHub.Playlists.updatePlaylistIcons;
window.updateAlbumIcons = BeatHub.Playlists.updateAlbumIcons;
window.updateSongCardIcons = BeatHub.Playlists.updateSongCardIcons;
