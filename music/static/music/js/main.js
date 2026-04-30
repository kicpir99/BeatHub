window.onerror = function(msg, url, lineNo, columnNo, error) {
    const errorMsg = `JS Error: ${msg} at ${lineNo}:${columnNo}`;
    console.error(errorMsg, error);
    if (window.showToast) window.showToast(errorMsg, 'error', 5000);
    return false;
};

/**
 * BeatHub Global Notification System (Toast)
 */
window.showToast = function(message, type = 'success', duration = 3000) {
    // Kompatybilność wsteczna: obsługa formatu (msg, boolean)
    if (typeof type === 'boolean') {
        type = type ? 'success' : 'error';
    }

    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    const colors = {
        success: 'bg-primary/90 border-primary',
        error: 'bg-red-600/90 border-red-500',
        info: 'bg-indigo-600/90 border-indigo-500',
        warning: 'bg-amber-600/90 border-amber-500'
    };

    const icons = {
        success: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>',
        error: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>',
        info: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>',
        warning: '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>'
    };

    toast.className = `flex items-center gap-3 px-6 py-4 rounded-2xl border backdrop-blur-xl shadow-2xl text-white pointer-events-auto min-w-[280px] toast-animation-in ${colors[type] || colors.success}`;
    toast.innerHTML = `
        <div class="shrink-0">${icons[type] || icons.success}</div>
        <div class="text-sm font-bold flex-1">${message}</div>
        <button class="ml-2 hover:opacity-70 transition-opacity" onclick="this.parentElement.remove()">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
        </button>
    `;

    container.appendChild(toast);

    // Automatyczne usuwanie
    setTimeout(() => {
        if (toast.parentNode) {
            toast.classList.replace('toast-animation-in', 'toast-animation-out');
            setTimeout(() => toast.remove(), 300);
        }
    }, duration);
};

// Alias dla kompatybilności wstecznej
window.showDynamicToast = window.showToast;
window.closeToast = (btn) => btn.closest('.toast-animation-in, .toast-animation-out')?.remove();

function checkDjangoMessages() {
    const script = document.getElementById('django-messages');
    if (script) {
        try {
            const messages = JSON.parse(script.textContent);
            messages.forEach(m => {
                let type = 'info';
                if (m.tags.includes('success')) type = 'success';
                if (m.tags.includes('error')) type = 'error';
                if (m.tags.includes('warning')) type = 'warning';
                window.showToast(m.message, type);
            });
            script.remove();
        } catch (e) {}
    }
}

function initLazySections() {
    const resumeContainer = document.getElementById('resume-section-container');
    if (resumeContainer) {
        fetch("/ajax/get-resume-section/")
            .then(r => r.text())
            .then(html => {
                if (html.trim()) {
                    resumeContainer.style.opacity = '0';
                    setTimeout(() => {
                        resumeContainer.innerHTML = html;
                        resumeContainer.style.transition = 'opacity 0.5s ease';
                        resumeContainer.style.opacity = '1';
                    }, 300);
                } else {
                    resumeContainer.remove();
                }
            })
            .catch(() => resumeContainer.remove());
    }
}

function initSearchAutocomplete() {
    const input = document.getElementById('search-input');
    const dropdown = document.getElementById('search-results-dropdown');
    if (!input || !dropdown || input.dataset.autocompleteBound) return;

    input.dataset.autocompleteBound = "true";
    let debounceTimer;
    let selectedIndex = -1;

    const showSkeletons = () => {
        dropdown.innerHTML = `
            <div class="p-3 space-y-4">
                <div class="space-y-2">
                    <div class="h-2 w-16 skeleton opacity-50 ml-2"></div>
                    <div class="flex items-center gap-3 p-2">
                        <div class="w-10 h-10 rounded-full skeleton shrink-0"></div>
                        <div class="h-4 skeleton w-1/2"></div>
                    </div>
                </div>
                <div class="space-y-2">
                    <div class="h-2 w-16 skeleton opacity-50 ml-2"></div>
                    <div class="flex items-center gap-3 p-2">
                        <div class="w-10 h-10 rounded-lg skeleton shrink-0"></div>
                        <div class="h-4 skeleton w-2/3"></div>
                    </div>
                </div>
            </div>
        `;
        dropdown.classList.remove('hidden');
    };

    const updateSelection = (items) => {
        items.forEach((item, index) => {
            if (index === selectedIndex) {
                item.classList.add('bg-white/10', 'border-primary/30');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('bg-white/10', 'border-primary/30');
            }
        });
    };

    input.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        const query = e.target.value.trim();
        selectedIndex = -1;

        if (query.length < 2) {
            dropdown.classList.add('hidden');
            return;
        }

        debounceTimer = setTimeout(async () => {
            showSkeletons();
            try {
                const baseUrl = input.dataset.url;
                const response = await fetch(`${baseUrl}?q=${encodeURIComponent(query)}`);
                const data = await response.json();
                
                let html = '';
                const hasResults = (data.artists?.length || 0) + (data.albums?.length || 0) + (data.songs?.length || 0) > 0;

                if (!hasResults) {
                    html = `
                        <div class="p-10 text-center flex flex-col items-center gap-3">
                            <div class="w-12 h-12 bg-white/5 rounded-full flex items-center justify-center text-text-muted">
                                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                            </div>
                            <span class="text-sm text-text-muted font-medium">Brak wyników dla "${query}"</span>
                        </div>`;
                } else {
                    const renderItem = (item, type) => `
                        <a href="${item.url}" class="search-result-item flex items-center gap-3 p-2.5 rounded-xl border border-transparent hover:bg-white/5 transition-all group">
                            <div class="w-10 h-10 ${type === 'artist' ? 'rounded-full' : 'rounded-lg'} overflow-hidden border border-white/10 group-hover:border-primary/50 transition-colors">
                                <img src="${item.photo || item.cover}" class="w-full h-full object-cover">
                            </div>
                            <div class="flex flex-col min-w-0">
                                <span class="text-sm font-bold text-text-main group-hover:text-primary transition-colors truncate">${item.name || item.title}</span>
                                ${item.artist ? `<span class="text-[10px] text-text-muted truncate">${item.artist}</span>` : `<span class="text-[10px] text-text-muted uppercase tracking-wider font-bold">Artysta</span>`}
                            </div>
                        </a>
                    `;

                    if (data.artists?.length) {
                        html += '<div class="p-2"><h3 class="text-[9px] font-black text-text-muted uppercase tracking-[0.2em] mb-2 ml-2">Artyści</h3>';
                        data.artists.forEach(a => html += renderItem(a, 'artist'));
                        html += '</div>';
                    }
                    if (data.albums?.length) {
                        html += `<div class="p-2 ${html ? 'border-t border-white/5' : ''}"><h3 class="text-[9px] font-black text-text-muted uppercase tracking-[0.2em] mb-2 ml-2">Albumy</h3>`;
                        data.albums.forEach(a => html += renderItem(a, 'album'));
                        html += '</div>';
                    }
                    if (data.songs?.length) {
                        html += `<div class="p-2 ${html ? 'border-t border-white/5' : ''}"><h3 class="text-[9px] font-black text-text-muted uppercase tracking-[0.2em] mb-2 ml-2">Utwory</h3>`;
                        data.songs.forEach(s => html += renderItem(s, 'song'));
                        html += '</div>';
                    }
                }
                dropdown.innerHTML = html;
            } catch (err) {
                dropdown.innerHTML = '<div class="p-4 text-center text-red-500 text-xs font-bold">Błąd połączenia</div>';
            }
        }, 300);
    });

    input.addEventListener('keydown', (e) => {
        const items = dropdown.querySelectorAll('.search-result-item');
        if (items.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = (selectedIndex + 1) % items.length;
            updateSelection(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = (selectedIndex - 1 + items.length) % items.length;
            updateSelection(items);
        } else if (e.key === 'Enter' && selectedIndex > -1) {
            e.preventDefault();
            items[selectedIndex].click();
        } else if (e.key === 'Escape') {
            dropdown.classList.add('hidden');
            input.blur();
        }
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('#search-input') && !e.target.closest('#search-results-dropdown')) {
            dropdown.classList.add('hidden');
        }
    });

    input.addEventListener('focus', () => {
        if (input.value.trim().length >= 2 && dropdown.innerHTML !== '') {
            dropdown.classList.remove('hidden');
        }
    });
}

class Modal {
    constructor(templateId) {
        this.template = document.getElementById(templateId);
        this.modalElement = null;
        this.bodyContent = null;
    }

    open(contentHtml) {
        if (!this.template) return;
        
        // Klonowanie szkieletu modala
        const clone = this.template.content.cloneNode(true);
        this.modalElement = clone.querySelector('.modal-overlay');
        this.bodyContent = this.modalElement.querySelector('#modal-body-content');
        
        if (contentHtml) this.bodyContent.innerHTML = contentHtml;
        
        document.body.appendChild(this.modalElement);
        
        // Obsługa zamykania
        this.modalElement.querySelectorAll('[data-close]').forEach(btn => {
            btn.addEventListener('click', () => this.close());
        });

        // Animacja wejścia
        requestAnimationFrame(() => {
            this.modalElement.classList.add('opacity-100');
            this.modalElement.querySelector('.modal-content').classList.replace('scale-95', 'scale-100');
        });

        return this.modalElement;
    }

    close() {
        if (!this.modalElement) return;
        
        this.modalElement.classList.replace('opacity-100', 'opacity-0');
        this.modalElement.querySelector('.modal-content').classList.replace('scale-100', 'scale-95');
        
        setTimeout(() => {
            this.modalElement.remove();
            this.modalElement = null;
        }, 300);
    }
}

// Globalny menedżer modali playlist
window.openPlaylistModal = async (songIdOrAction, title, playlistId = null) => {
    const modal = new Modal('playlist-modal-template');
    
    // Budujemy treść wewnętrzną
    const isCopy = songIdOrAction === 'copy';
    const isEdit = playlistId && !songIdOrAction;
    const isAdd = !!songIdOrAction && !isCopy && !isEdit;

    let modalHtml = `
        <h3 class="text-2xl font-black text-text-main mb-2 leading-tight">${isCopy ? 'Skopiuj playlistę' : (isEdit ? 'Edytuj playlistę' : (isAdd ? 'Dodaj do playlisty' : 'Nowa playlista'))}</h3>
        <p class="text-primary font-bold text-xs uppercase tracking-widest mb-8 truncate">${title || ''}</p>
        
        <div class="space-y-6">
            ${isCopy ? `
                <div id="copy-mode-selector" class="flex p-1 bg-white/5 rounded-2xl border border-white/10 mb-6">
                    <button onclick="window.setModalCopyMode('new')" id="mode-btn-new" class="flex-1 py-2.5 text-[10px] font-black uppercase tracking-widest rounded-xl transition-all bg-primary text-background-main shadow-lg">Nowa kopia</button>
                    <button onclick="window.setModalCopyMode('existing')" id="mode-btn-existing" class="flex-1 py-2.5 text-[10px] font-black uppercase tracking-widest rounded-xl transition-all text-text-muted hover:text-text-secondary">Moja lista</button>
                </div>
            ` : ''}

            <div class="space-y-4">
                <div id="existing-playlist-section" class="${(isAdd || isCopy) ? '' : 'hidden'}">
                    <label class="block text-[10px] text-text-muted font-black uppercase tracking-[0.2em] mb-3 ml-1">Wybierz playlistę:</label>
                    <div class="relative bg-white/5 border border-white/10 rounded-2xl focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/10 transition-all overflow-hidden">
                        <select id="playlist-select" class="w-full p-4 bg-transparent border-none text-text-main text-sm outline-none appearance-none cursor-pointer">
                            <option value="" class="bg-background-surface text-text-main">Ładowanie twoich playlist...</option>
                        </select>
                        <div class="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-text-muted">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M19 9l-7 7-7-7"></path></svg>
                        </div>
                    </div>
                </div>
                
                <div id="new-playlist-section" class="${isCopy ? '' : (isAdd ? '' : '')}">
                    <label class="block text-[10px] text-text-muted font-black uppercase tracking-[0.2em] mb-3 ml-1">${isEdit ? 'Nowa nazwa:' : 'Nazwa nowej playlisty:'}</label>
                    <input type="text" id="new-playlist-name" value="${isEdit || isCopy ? title : ''}" placeholder="Wpisz nazwę..." 
                        class="w-full p-4 bg-white/5 border border-white/10 rounded-2xl text-text-main text-sm outline-none focus:border-primary/50 focus:ring-4 focus:ring-primary/10 transition-all">
                </div>
            </div>
        </div>
        
        <button id="modal-submit-btn" class="w-full mt-10 bg-primary hover:bg-primary-hover text-background-main font-black text-xs uppercase tracking-[0.2em] py-4 rounded-2xl shadow-lg shadow-primary-glow/20 transition-all active:scale-95 flex items-center justify-center gap-2 group">
            <span>Zapisz zmiany</span>
            <svg class="w-4 h-4 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
        </button>
    `;

    const modalEl = modal.open(modalHtml);
    window.currentActiveModal = modal;
    
    // Stan globalny dla wysyłki
    window.modalState = {
        songId: Array.isArray(songIdOrAction) ? null : songIdOrAction,
        songIds: Array.isArray(songIdOrAction) ? songIdOrAction : null,
        editPlaylistId: playlistId && !isCopy ? playlistId : null,
        sourcePlaylistId: isCopy ? playlistId : null,
        copyMode: 'new'
    };

    // Obsługa przycisku zapisu
    modalEl.querySelector('#modal-submit-btn').addEventListener('click', () => window.submitModalPlaylist());

    // Ładowanie playlist jeśli potrzeba
    if (isAdd || isCopy) {
        try {
            const resp = await fetch(window.BEATHUB_CONFIG.urls.getUserPlaylists);
            const data = await resp.json();
            const select = modalEl.querySelector('#playlist-select');
            select.innerHTML = '<option value="" class="bg-background-surface text-white">-- Wybierz playlistę --</option>';
            data.playlists.forEach(p => {
                select.innerHTML += `<option value="${p.id}" class="bg-background-surface text-white">${p.name}</option>`;
            });
        } catch (e) {
            console.error("Failed to load playlists", e);
        }
    }
};

window.setModalCopyMode = (mode) => {
    window.modalState.copyMode = mode;
    const btnNew = document.getElementById('mode-btn-new');
    const btnExt = document.getElementById('mode-btn-existing');
    const secNew = document.getElementById('new-playlist-section');
    const secExt = document.getElementById('existing-playlist-section');

    if (mode === 'new') {
        btnNew.classList.add('bg-primary', 'text-background-main', 'shadow-lg');
        btnNew.classList.remove('text-text-muted');
        btnExt.classList.remove('bg-primary', 'text-background-main', 'shadow-lg');
        btnExt.classList.add('text-text-muted');
        secNew.classList.remove('hidden');
        secExt.classList.add('hidden');
    } else {
        btnExt.classList.add('bg-primary', 'text-background-main', 'shadow-lg');
        btnExt.classList.remove('text-text-muted');
        btnNew.classList.remove('bg-primary', 'text-background-main', 'shadow-lg');
        btnNew.classList.add('text-text-muted');
        secNew.classList.add('hidden');
        secExt.classList.remove('hidden');
    }
};

window.submitModalPlaylist = async () => {
    const name = document.getElementById('new-playlist-name').value.trim();
    const playlistId = document.getElementById('playlist-select')?.value;
    const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
    const state = window.modalState;
    const submitBtn = document.getElementById('modal-submit-btn');

    submitBtn.disabled = true;
    submitBtn.innerHTML = `<div class="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>`;

    let url, payload;

    if (state.sourcePlaylistId) {
        url = window.BEATHUB_CONFIG.urls.copyPlaylist;
        payload = {
            source_playlist_id: state.sourcePlaylistId,
            mode: state.copyMode,
            target_playlist_id: state.copyMode === 'existing' ? playlistId : null,
            new_name: state.copyMode === 'new' ? name : null
        };
    } else if (state.editPlaylistId) {
        url = `/playlist/edit/${state.editPlaylistId}/`;
        payload = { name: name };
    } else {
        url = window.BEATHUB_CONFIG.urls.addToPlaylist;
        payload = {
            song_id: state.songId,
            song_ids: state.songIds,
            playlist_id: playlistId,
            new_playlist_name: name
        };
    }

    try {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
            body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (data.status === 'success') {
            window.currentActiveModal?.close();
            sessionStorage.setItem('pendingToast', JSON.stringify({ msg: data.message, success: true }));
            window.visitPreservingScroll(window.location.href);
        } else {
            window.showToast(data.message, 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Zapisz zmiany';
        }
    } catch (err) {
        window.showToast("Błąd połączenia z serwerem", 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Zapisz zmiany';
    }
};

function initGlobalInteractions() {
    // Te funkcje muszą być wywoływane przy każdym turbo:load, jeśli elementy istnieją
    initLazySections();
    initSearchAutocomplete();

    // Zapobiegamy wielokrotnemu przypisaniu słuchaczy zdarzeń do document
    if (window.isInteractionsInitialized) return;
    window.isInteractionsInitialized = true;

    checkDjangoMessages();

    document.addEventListener('click', function(e) {
        // Szukamy najbliższego elementu z atrybutem data-action
        const actionElement = e.target.closest('[data-action]');
        console.log("[Main] Click detected. Target:", e.target, "ActionElement:", actionElement);
        if (!actionElement) return;

        const action = actionElement.getAttribute('data-action');
        const dataset = actionElement.dataset;

        // Jeśli kliknięty element to przycisk/link, zapobiegamy bąbelkowaniu, 
        // aby nie wywołać kliknięcia wiersza (row-click)
        if (actionElement.tagName === 'BUTTON' || actionElement.tagName === 'A') {
            e.stopPropagation();
        }

        switch (action) {
            case 'row-click':
                if (window.handleRowClick) {
                    window.handleRowClick(e, dataset.index, dataset.rowContext, actionElement);
                }
                break;

            case 'visit-album':
                e.stopPropagation();
                if (dataset.albumSlug) {
                    Turbo.visit(`/music/album/${dataset.albumSlug}/`);
                }
                break;

            case 'add-to-playlist':
                e.stopPropagation();
                if (window.openPlaylistModal) {
                    window.openPlaylistModal(dataset.songId, dataset.songTitle);
                }
                break;

            case 'share-song':
                e.stopPropagation();
                if (window.handleShare) {
                    window.handleShare(e, dataset.songTitle, dataset.shareUrl);
                } else {
                    // Fallback jeśli handleShare nie jest dostępny globalnie (np. stary kod)
                    if (window.copyToClipboard) {
                        window.copyToClipboard(window.location.origin + dataset.shareUrl, "Link do utworu skopiowany!");
                    }
                }
                break;

            case 'toggle-like':
                e.stopPropagation();
                if (window.handleToggleLike) {
                    window.handleToggleLike(e, actionElement, dataset.songId, dataset.isPlaylist === 'true')
                        .then(response => {
                            if (response && response.status === 'success') {
                                const msg = response.liked ? "Dodano do polubionych" : "Usunięto z polubionych";
                                window.showToast(msg, 'success');
                            }
                        })
                        .catch(err => {
                            window.showToast("Błąd podczas aktualizacji polubienia", "error");
                        });
                }
                break;

            case 'toggle-dropdown':
                e.stopPropagation();
                if (window.toggleDropdown) {
                    window.toggleDropdown(e, dataset.dropdownId);
                }
                break;

            case 'remove-from-playlist':
                e.stopPropagation();
                if (window.handleRemoveFromPlaylist) {
                    window.handleRemoveFromPlaylist(e, dataset.posId, dataset.songId);
                }
                break;
        }
    });
}

// Inicjalizacja przy ładowaniu strony (zarówno klasycznym jak i Turbo)
document.addEventListener('turbo:load', initGlobalInteractions);
document.addEventListener('DOMContentLoaded', initGlobalInteractions);
