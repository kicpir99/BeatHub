window.BeatHub = window.BeatHub || {};

BeatHub.Interactions = BeatHub.Interactions || {};

BeatHub.Interactions.toggleLike = (e, b, id, rem = false) => {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    if (!window.BEATHUB_CONFIG.isAuthenticated) {
        if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Zaloguj się, aby dodawać utwory do polubionych.", "warning");
        return Promise.resolve({status: 'error', message: 'Not authenticated'});
    }
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
    return fetch(window.BEATHUB_CONFIG.urls.toggleLike, {
        method: "POST", 
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrf},
        body: JSON.stringify({song_id: id})
    })
    .then(r => r.json()).then(d => {
        if(d.status === 'success') {
            const isLikedSongsPage = window.location.pathname.includes('/liked-songs');

            // Update player icon if the current song is the one being liked
            if(window.currentQueue && window.currentQueue[0] && String(window.currentQueue[0].id) === String(id)) {
                const pIcon = document.getElementById('player-like-btn')?.querySelector('svg');
                if (pIcon) {
                    if(d.is_liked) { 
                        pIcon.classList.add('text-rose-500', 'fill-current'); 
                        pIcon.classList.remove('text-text-muted', 'text-gray-500'); 
                    } else { 
                        pIcon.classList.remove('text-rose-500', 'fill-current'); 
                        pIcon.classList.add('text-text-muted'); 
                    }
                }
            }

            // Handle UI row removal on Liked Songs page
            const row = document.getElementById(`song-row-${id}`);
            if (isLikedSongsPage) {
                if (row) {
                    if (!d.is_liked) {
                        row.style.transition = 'all 0.4s ease'; 
                        row.style.opacity = '0'; 
                        row.style.transform = 'translateX(-20px)';
                        setTimeout(() => { 
                            row.style.display = 'none';
                            const visibleRows = Array.from(document.querySelectorAll('tr[id^="song-row-"]')).filter(r => r.style.display !== 'none');
                            if(visibleRows.length === 0) {
                                if (window.Turbo) window.Turbo.visit(window.location.pathname, { action: "replace" }); 
                                else window.location.reload();
                            }
                        }, 400);
                    } else {
                        if (row.style.display === 'none') {
                            row.style.display = '';
                            setTimeout(() => {
                                row.style.opacity = '1'; 
                                row.style.transform = 'translateX(0)';
                            }, 10);
                        }
                    }
                } else if (d.is_liked) {
                    if (window.visitPreservingScroll) window.visitPreservingScroll(window.location.href);
                    else window.location.reload();
                }
            }

            // Sync album icons if provided
            if(d.album_id) {
                document.querySelectorAll(`button[onclick*='handleToggleAlbumLike'][onclick*='${d.album_id}'], button[onclick*='BeatHub.Interactions.toggleAlbumLike'][onclick*='${d.album_id}'] svg`).forEach(svg => {
                    if (d.album_liked) { 
                        svg.classList.add('text-rose-500', 'fill-current'); 
                        svg.classList.remove('text-text-muted', 'text-white'); 
                    } else { 
                        svg.classList.remove('text-rose-500', 'fill-current'); 
                        svg.classList.add('text-text-muted'); 
                    }
                });
                
                if(isLikedSongsPage) {
                    const card = document.getElementById(`album-card-${d.album_id}`);
                    if (d.album_liked) {
                        if (card) {
                            if (card.style.display === 'none') {
                                card.style.display = '';
                                setTimeout(() => {
                                    card.style.opacity = '1';
                                    card.style.transform = 'translateY(0)';
                                }, 10);
                            }
                        } else {
                            if (window.visitPreservingScroll) window.visitPreservingScroll(window.location.pathname);
                            else window.location.reload();
                        }
                    } else {
                        if(card) {
                            card.style.transition = 'all 0.4s ease';
                            card.style.opacity = '0';
                            card.style.transform = 'translateY(20px)';
                            setTimeout(() => card.style.display = 'none', 400);
                        }
                    }
                }
            }

            // Update Global Config
            if (d.is_liked) {
                if (!window.BEATHUB_CONFIG.user.liked_song_ids.includes(parseInt(id))) {
                    window.BEATHUB_CONFIG.user.liked_song_ids.push(parseInt(id));
                }
            } else {
                window.BEATHUB_CONFIG.user.liked_song_ids = window.BEATHUB_CONFIG.user.liked_song_ids.filter(sid => sid !== parseInt(id));
            }

            // Sync all song row icons
            document.querySelectorAll(`[data-song-id='${id}'][data-action='toggle-like'] svg, [data-song-id='${id}'] .liked-icon, button[onclick*='handleToggleLike'][onclick*='${id}'] svg, button[onclick*='BeatHub.Interactions.toggleLike'][onclick*='${id}'] svg`).forEach(svg => {
                if (d.is_liked) { 
                    svg.classList.add('text-rose-500', 'fill-current'); 
                    svg.classList.remove('text-text-muted', 'text-white', 'text-gray-500'); 
                } else { 
                    svg.classList.remove('text-rose-500', 'fill-current'); 
                    svg.classList.add('text-text-muted');
                }
            });
            
            BeatHub.Interactions.updatePlayerLikeIcon(id);
            if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast(d.message, true);
        }
        return d;
    });
};

BeatHub.Interactions.toggleAlbumLike = (e, btn, id) => {
    if (e) {
        e.stopPropagation(); 
        e.preventDefault();
    }
    if (!window.BEATHUB_CONFIG.isAuthenticated) {
        if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Zaloguj się, aby dodawać albumy do polubionych.", "warning");
        return;
    }
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
    fetch(window.BEATHUB_CONFIG.urls.toggleAlbumLike, {
        method: "POST", 
        headers: {"Content-Type": "application/json", "X-CSRFToken": csrf},
        body: JSON.stringify({album_id: id})
    })
    .then(r => r.json()).then(d => {
        if(d.status === 'success') {
            if (d.is_liked) {
                if (!window.BEATHUB_CONFIG.user.liked_album_ids.includes(parseInt(id))) {
                    window.BEATHUB_CONFIG.user.liked_album_ids.push(parseInt(id));
                }
            } else {
                window.BEATHUB_CONFIG.user.liked_album_ids = window.BEATHUB_CONFIG.user.liked_album_ids.filter(aid => aid !== parseInt(id));
            }

            if(d.is_liked && window.location.pathname.includes('/liked-songs')) { 
                if (window.visitPreservingScroll) window.visitPreservingScroll(window.location.pathname);
                else window.location.reload();
                return; 
            }

            // Player Like Sync
            if(window.currentQueue && window.currentQueue[0] && d.song_ids.map(String).includes(String(window.currentQueue[0].id))) {
                const pIcon = document.getElementById('player-like-btn')?.querySelector('svg');
                if (pIcon) {
                    if(d.is_liked) { 
                        pIcon.classList.add('text-rose-500', 'fill-current'); 
                        pIcon.classList.remove('text-text-muted', 'text-gray-500'); 
                    } else { 
                        pIcon.classList.remove('text-rose-500', 'fill-current'); 
                        pIcon.classList.add('text-text-muted'); 
                    }
                }
            }

            // Remove cards on Liked Songs page if unliked
            if(!d.is_liked && window.location.pathname.includes('/liked-songs')) {
                const card = document.getElementById(`album-card-${id}`);
                if(card) { card.style.opacity = '0'; setTimeout(() => card.remove(), 400); }
                d.song_ids.forEach(sId => {
                    const row = document.getElementById(`song-row-${sId}`);
                    if(row) { 
                        row.style.transition = 'all 0.4s ease'; 
                        row.style.opacity = '0'; 
                        row.style.transform = 'translateX(-20px)'; 
                        setTimeout(() => row.remove(), 400); 
                    }
                });
            }

            // Sync current button
            const svg = btn.querySelector('svg');
            if (svg) {
                if (d.is_liked) { 
                    svg.classList.add('text-rose-500', 'fill-current'); 
                    svg.classList.remove('text-text-muted', 'text-white'); 
                } else { 
                    svg.classList.remove('text-rose-500', 'fill-current'); 
                    svg.classList.add('text-text-muted'); 
                }
            }

            // Sync all song row icons for songs in this album
            d.song_ids.forEach(sId => {
                document.querySelectorAll(`tr[data-song-id='${sId}'] .liked-icon, button[onclick*='handleToggleLike'][onclick*='${sId}'], button[onclick*='BeatHub.Interactions.toggleLike'][onclick*='${sId}'] svg`).forEach(sSvg => {
                    if (d.is_liked) { 
                        sSvg.classList.add('text-rose-500', 'fill-current'); 
                        sSvg.classList.remove('text-text-muted', 'text-white', 'text-gray-500'); 
                    } else { 
                        sSvg.classList.remove('text-rose-500', 'fill-current'); 
                        sSvg.classList.add('text-text-muted');
                    }
                });
            });

            if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast(d.message, true);
        }
    });
};

BeatHub.Interactions.handlePlayerLike = e => { 
    if(e) e.preventDefault();
    if(window.currentQueue && window.currentQueue[0]) {
        BeatHub.Interactions.toggleLike(e, document.getElementById('player-like-btn'), window.currentQueue[0].id); 
    }
};

BeatHub.Interactions.updatePlayerLikeIcon = id => {
    const pIcon = document.getElementById('player-like-btn')?.querySelector('svg');
    if (!pIcon) return;
    
    const isLiked = window.BEATHUB_CONFIG.user.liked_song_ids.includes(parseInt(id));
    
    if(isLiked) { 
        pIcon.classList.add('text-rose-500', 'fill-current'); 
        pIcon.classList.remove('text-text-muted', 'text-gray-500'); 
    } else { 
        pIcon.classList.remove('text-rose-500', 'fill-current'); 
        pIcon.classList.add('text-text-muted'); 
    }
};

window.handleToggleLike = BeatHub.Interactions.toggleLike;
window.handleToggleAlbumLike = BeatHub.Interactions.toggleAlbumLike;
window.handlePlayerLike = BeatHub.Interactions.handlePlayerLike;
window.updatePlayerLikeIcon = BeatHub.Interactions.updatePlayerLikeIcon;
