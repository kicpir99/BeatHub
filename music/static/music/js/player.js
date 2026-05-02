window.BeatHub = window.BeatHub || {};

BeatHub.Player = {
    state: {
        isShuffle: false,
        originalQueue: [],
        currentSongId: null,
        currentQueue: [],
        playedHistory: [],
        currentQueueIndex: 0,
        currentSongCounted: false,
        repeatOne: false,
        currentPlaylistId: null,
        currentAlbumId: null,
        currentSongListenedTime: 0,
        lastReportedSongId: null,
        lastReportedPlaylistId: null,
        playbackContext: { type: 'queue', id: null }
    },

    init: function() {
        window.audio = document.getElementById('audio-element');
        this.restoreState();
        this.restoreVolume();
    },

    restoreVolume: function() {
        const savedVol = localStorage.getItem('beathub-volume');
        const vs = document.getElementById('volume-slider');
        if (savedVol !== null) {
            const vol = parseFloat(savedVol);
            if (window.audio) window.audio.volume = vol;
            if (vs) vs.value = vol;
        } else if (vs) {
            // First visit: sync audio volume FROM the slider's default HTML value
            if (window.audio) window.audio.volume = parseFloat(vs.value);
        }
        // Always update the green gradient line to match
        const currentVol = vs ? parseFloat(vs.value) : (window.audio ? window.audio.volume : 1);
        this.updateVolumeBackground(currentVol);
    },

    restoreState: function() {
        try {
            const savedContext = sessionStorage.getItem('currentPlaybackContext');
            this.state.playbackContext = savedContext ? JSON.parse(savedContext) : { type: 'queue', id: null };
        } catch (e) {
            this.state.playbackContext = { type: 'queue', id: null };
        }
        window.currentPlaybackContext = this.state.playbackContext;
    },

    visualizer: {
        audioCtx: null,
        analyser: null,
        source: null,
        dataArray: null,
        canvas: null,
        ctx: null,

        init: function() {
            if (this.audioCtx) return;
            try {
                this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                this.analyser = this.audioCtx.createAnalyser();
                this.source = this.audioCtx.createMediaElementSource(window.audio);
                this.source.connect(this.analyser);
                this.analyser.connect(this.audioCtx.destination);
                
                this.analyser.fftSize = 256; 
                this.analyser.smoothingTimeConstant = 0.85; 
                
                const bufferLength = this.analyser.frequencyBinCount;
                this.dataArray = new Uint8Array(bufferLength);
                this.canvas = document.getElementById('visualizer');
                if (this.canvas) {
                    this.ctx = this.canvas.getContext('2d');
                    this.draw();
                }
            } catch (e) {
                console.warn("Web Audio API not supported or blocked:", e);
            }
        },

        draw: function() {
            if (!this.canvas) return;
            requestAnimationFrame(() => this.draw());
            
            const width = this.canvas.width = this.canvas.clientWidth;
            const height = this.canvas.height = this.canvas.clientHeight;
            
            this.analyser.getByteFrequencyData(this.dataArray);
            this.ctx.clearRect(0, 0, width, height);
            
            let bassSum = 0;
            for(let i=0; i<5; i++) bassSum += this.dataArray[i];
            const bassLevel = bassSum / 5;
            const bassIntensity = bassLevel / 255;

            const barCount = this.dataArray.length / 2;
            const barWidth = (width / barCount) * 0.5;
            let barHeight;
            let x_right = width / 2;
            let x_left = width / 2 - barWidth;

            this.ctx.shadowBlur = 15 * bassIntensity;
            this.ctx.shadowColor = 'rgba(16, 185, 129, 0.5)';

            for (let i = 0; i < barCount; i++) {
                barHeight = (this.dataArray[i] / 255) * height * (0.4 + bassIntensity * 0.4);
                const hue = 160 + (i * 2);
                const opacity = 0.1 + (this.dataArray[i] / 255) * 0.5;
                this.ctx.fillStyle = `hsla(${hue}, 80%, 50%, ${opacity})`;
                const radius = 4;
                this.drawRoundedRect(x_right, height - barHeight, barWidth - 2, barHeight, radius);
                this.drawRoundedRect(x_left, height - barHeight, barWidth - 2, barHeight, radius);
                x_right += barWidth + 2;
                x_left -= (barWidth + 2);
            }
        },

        drawRoundedRect: function(x, y, w, h, r) {
            if (h < r) r = h/2;
            this.ctx.beginPath();
            this.ctx.moveTo(x, y + h);
            this.ctx.lineTo(x, y + r);
            this.ctx.quadraticCurveTo(x, y, x + r, y);
            this.ctx.lineTo(x + w - r, y);
            this.ctx.quadraticCurveTo(x + w, y, x + w, y + r);
            this.ctx.lineTo(x + w, y + h);
            this.ctx.closePath();
            this.ctx.fill();
        }
    },

    toggleShuffle: () => {
        const p = BeatHub.Player;
        p.state.isShuffle = !p.state.isShuffle;
        window.isShuffle = p.state.isShuffle; 
        const b = document.getElementById('shuffle-btn');
        if(p.state.isShuffle){ 
            b.classList.replace('text-gray-400','text-primary'); 
            p.state.originalQueue = [...p.state.currentQueue];
            window.originalQueue = p.state.originalQueue;
            let s = p.state.currentQueue.slice(1); 
            p.shuffleArr(s); 
            p.state.currentQueue = [p.state.currentQueue[0], ...s];
            window.currentQueue = p.state.currentQueue;
            if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Shuffle ON", true); 
        } else { 
            b.classList.replace('text-primary','text-gray-400'); 
            const cur = p.state.currentQueue[0];
            const idx = p.state.originalQueue.findIndex(s => s.id === cur.id); 
            if(idx !== -1) {
                p.state.currentQueue = [...p.state.originalQueue.slice(idx), ...p.state.originalQueue.slice(0, idx)];
                window.currentQueue = p.state.currentQueue;
            }
            if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Shuffle OFF", true); 
        }
        p.renderQueue();
    },

    shuffleArr: a => { for(let i=a.length-1;i>0;i--){ const j=Math.floor(Math.random()*(i+1)); [a[i],a[j]]=[a[j],a[i]]; } },

    playGlobalQueue: (q, i = 0, context = null) => {
        const p = BeatHub.Player;
        const ctx = context || { type: 'queue', id: null };
        p.state.playbackContext = ctx;
        window.currentPlaybackContext = ctx;
        sessionStorage.setItem('currentPlaybackContext', JSON.stringify(ctx));
        
        p.state.playedHistory = q.slice(0, i);
        window.playedHistory = p.state.playedHistory;
        p.state.currentQueue = q.slice(i);
        window.currentQueue = p.state.currentQueue;

        if(p.state.isShuffle){ 
            p.state.originalQueue = [...p.state.currentQueue]; 
            window.originalQueue = p.state.originalQueue;
            let s = p.state.currentQueue.slice(1); 
            p.shuffleArr(s); 
            p.state.currentQueue = [p.state.currentQueue[0], ...s]; 
            window.currentQueue = p.state.currentQueue;
        }
        p.state.currentQueueIndex = 0; 
        window.currentQueueIndex = 0;
        p.loadAndPlay(); 
        if(!document.getElementById('queue-panel').classList.contains('hidden')) p.renderQueue();
    },

    reportPlay: () => {
        const p = BeatHub.Player;
        const time = Math.floor(p.state.currentSongListenedTime);
        const songId = p.state.lastReportedSongId;
        const playlistId = p.state.lastReportedPlaylistId;

        if (songId && time > 0) {
            const data = { song_id: songId, playlist_id: playlistId, duration: time };
            const csrf = document.querySelector('[name=csrfmiddlewaretoken]').value;
            
            fetch(window.BEATHUB_CONFIG.urls.trackPlay, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
                body: JSON.stringify(data),
                keepalive: true
            });
        }
        p.state.currentSongListenedTime = 0;
    },

    loadAndPlay: function() {
        const p = BeatHub.Player;
        p.reportPlay();
        p.visualizer.init();
        
        const audioEl = document.getElementById('audio-element');
        if (!audioEl) return;
        
        if (p.visualizer.audioCtx && p.visualizer.audioCtx.state === 'suspended') p.visualizer.audioCtx.resume();
        
        const s = p.state.currentQueue[0]; 
        if(!s) return;
        if(!s.url) return p.playNext();
        
        p.state.lastReportedSongId = s.id;
        p.state.lastReportedPlaylistId = s.playlist_id || null;
        p.state.currentSongCounted = false; 
        p.state.currentPlaylistId = s.playlist_id || null;
        p.state.currentAlbumId = s.album_id || null;
        window.currentPlaylistId = p.state.currentPlaylistId;
        window.currentAlbumId = p.state.currentAlbumId;
        window.currentSongId = s.id;
        
        document.getElementById('player-title').textContent = s.title; 
        const artistContainer = document.getElementById('player-artist');
        artistContainer.innerHTML = ''; 
        
        const mainArtistLink = document.createElement('a');
        mainArtistLink.href = s.artist_slug ? `/artist/${s.artist_slug}/` : `/albums/?q=${encodeURIComponent(s.artist)}`;
        mainArtistLink.className = "hover:text-primary transition-colors";
        mainArtistLink.textContent = s.artist;
        artistContainer.appendChild(mainArtistLink);

        if (s.featured_artists && s.featured_artists.length > 0) {
            const ftSpan = document.createElement('span');
            ftSpan.className = "text-gray-500 font-medium mx-1";
            ftSpan.textContent = "ft.";
            artistContainer.appendChild(ftSpan);

            s.featured_artists.forEach((guest, index) => {
                const guestLink = document.createElement('a');
                guestLink.href = `/artist/${guest.slug}/`;
                guestLink.className = "hover:text-primary transition-colors";
                guestLink.textContent = guest.nickname;
                artistContainer.appendChild(guestLink);
                if (index < s.featured_artists.length - 1) artistContainer.appendChild(document.createTextNode(', '));
            });
        }

        const c = document.getElementById('player-cover'); 
        if(s.cover) { c.src = s.cover; c.classList.remove('hidden'); } else { c.classList.add('hidden'); }
        
        document.getElementById('player-album-link').href = document.getElementById('player-title-link').href = `/album/${s.album_slug}/`;
        document.getElementById('player-artist-link').href = `/albums/?q=${encodeURIComponent(s.artist)}`; 
        
        if (window.updatePlayerLikeIcon) window.updatePlayerLikeIcon(s.id);
        
        const shareBtn = document.getElementById('player-share-btn');
        if (shareBtn) {
            const shareTitle = `${s.title} - ${s.artist}`;
            const shareUrl = `/album/${s.album_slug}/?play=1&song_id=${s.id}`;
            shareBtn.onclick = (e) => {
                if (BeatHub.UI && BeatHub.UI.handleShare) BeatHub.UI.handleShare(e, shareTitle, shareUrl);
            };
        }

        document.body.classList.add('player-active');
        document.getElementById('global-player').classList.remove('translate-y-full'); 
        
        if(audioEl.src !== window.location.origin + s.url && audioEl.src !== s.url){
            audioEl.src = s.url; 
            audioEl.load();
        }
        audioEl.play().catch(err => console.error("[Player] Playback failed:", err));
        
        document.getElementById('icon-play').classList.add('hidden'); 
        document.getElementById('icon-pause').classList.remove('hidden'); 
        
        if(!document.getElementById('queue-panel').classList.contains('hidden')) p.renderQueue();
        
        p.syncListIcons();
        if (window.updatePlaylistIcons) window.updatePlaylistIcons();
        if (window.updateAlbumIcons) window.updateAlbumIcons();
        if (window.updateSongCardIcons) window.updateSongCardIcons();

        if (p.state.playbackContext && p.state.playbackContext.type) {
            fetch(window.BEATHUB_CONFIG.urls.savePlaybackState, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({
                    type: p.state.playbackContext.type,
                    id: p.state.playbackContext.id,
                    song_id: s.id,
                    index: 0
                })
            }).then(response => {
                if (response.ok && BeatHub.UI && BeatHub.UI.initLazySections) BeatHub.UI.initLazySections();
            });
        }
    },

    playNext: () => { 
        const p = BeatHub.Player;
        if(p.state.currentQueue.length > 0){ 
            const f = p.state.currentQueue.shift(); 
            p.state.playedHistory.push(f); 
            if(p.state.currentQueue.length > 0) p.loadAndPlay(); 
            else { 
                window.audio.pause(); 
                document.getElementById('global-player').classList.add('translate-y-full'); 
                document.body.classList.remove('player-active');
                const qp = document.getElementById('queue-panel');
                if(qp && !qp.classList.contains('hidden')) p.toggleQueue();
            } 
            p.renderQueue(); 
        } 
    },

    playPrev: () => { 
        const p = BeatHub.Player;
        if(window.audio.currentTime > 3){ 
            window.audio.currentTime = 0; 
            window.audio.play(); 
            return; 
        } 
        if(p.state.playedHistory.length > 0){ 
            const song = p.state.playedHistory.pop(); 
            p.state.currentQueue.unshift(song); 
            p.loadAndPlay(); 
            p.renderQueue(); 
        } 
    },

    toggleRepeat: () => { 
        const p = BeatHub.Player;
        p.state.repeatOne = !p.state.repeatOne; 
        const b = document.getElementById('repeat-btn'); 
        b.classList.toggle('text-primary', p.state.repeatOne); 
        b.classList.toggle('text-gray-400', !p.state.repeatOne); 
        if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast(`Repeat ${p.state.repeatOne?'ON':'OFF'}`, true); 
    },

    toggleGlobalPlay: function() { 
        const p = BeatHub.Player;
        if(window.audio.paused) {
            p.visualizer.init();
            if (p.visualizer.audioCtx && p.visualizer.audioCtx.state === 'suspended') p.visualizer.audioCtx.resume();
            window.audio.play().catch(() => {});
        } else {
            window.audio.pause();
        }
    },

    fmtTime: s => { 
        if (isNaN(s) || s === Infinity) return "0:00";
        const m = Math.floor(s/60), sc = Math.floor(s%60); 
        return m + ":" + (sc < 10 ? '0' : '') + sc; 
    },

    handleSeek: (e) => {
        const container = document.getElementById('progress-container');
        if (!container) return;
        
        const duration = window.audio.duration;
        const r = container.getBoundingClientRect();
        let pos = (e.clientX - r.left) / r.width;
        pos = Math.max(0, Math.min(1, pos));

        if (!duration || isNaN(duration) || duration === Infinity) {
            const onMetadata = () => {
                try { window.audio.currentTime = pos * window.audio.duration; } catch(err) {}
            };
            window.audio.addEventListener('loadedmetadata', onMetadata, { once: true });
            if (window.audio.readyState === 0) window.audio.load();
            return;
        }

        const bar = document.getElementById('progress-bar');
        if(bar) bar.style.width = (pos * 100) + '%';
        document.getElementById('time-current').textContent = BeatHub.Player.fmtTime(pos * duration);
        
        if (!BeatHub.Player.isDraggingSeek) {
            const seekTo = pos * duration;
            let attempts = 0;
            const trySeek = () => {
                try { window.audio.currentTime = seekTo; } catch (err) {
                    if (attempts < 10) { attempts++; setTimeout(trySeek, 100); }
                }
            };
            trySeek();
        }
    },

    toggleMute: () => {
        const vSlider = document.getElementById('volume-slider');
        if (!vSlider) return;
        
        if (window.audio.volume > 0) {
            BeatHub.Player.lastVolume = window.audio.volume;
            window.audio.volume = 0;
            vSlider.value = 0;
        } else {
            window.audio.volume = BeatHub.Player.lastVolume || 0.5;
            vSlider.value = window.audio.volume;
        }
        BeatHub.Player.updateVolumeBackground(window.audio.volume);
        localStorage.setItem('beathub-volume', window.audio.volume);
        
        if (window.discovery && window.discovery.audio) {
            const vol = window.audio.volume;
            window.discovery.audio.volume = vol;
            document.querySelectorAll('.volume-slider-discovery').forEach(s => {
                s.value = vol;
                s.style.background = `linear-gradient(to right, var(--primary) ${vol * 100}%, var(--border-main) ${vol * 100}%)`;
            });
        }
    },

    updateVolumeBackground: (val) => {
        const v = document.getElementById('volume-slider');
        if (v) {
            const percent = (val !== undefined ? val : v.value) * 100;
            v.style.background = `linear-gradient(to right, var(--primary) ${percent}%, #374151 ${percent}%)`;
            const high = document.getElementById('vol-icon-high');
            const mute = document.getElementById('vol-icon-mute');
            if (high && mute) {
                if (percent === 0) { high.classList.add('hidden'); mute.classList.remove('hidden'); }
                else { high.classList.remove('hidden'); mute.classList.add('hidden'); }
            }
        }
    },

    toggleQueue: e => { 
        if(e) e.stopPropagation(); 
        const p = document.getElementById('queue-panel'); 
        if(!p) return;
        if(p.classList.contains('hidden')){ 
            BeatHub.Player.renderQueue(); 
            p.classList.remove('hidden'); 
            setTimeout(() => { 
                p.classList.replace('opacity-0', 'opacity-100'); 
                p.classList.replace('translate-y-4', 'translate-y-0'); 
            }, 10); 
        } else { 
            p.classList.replace('opacity-100', 'opacity-0'); 
            p.classList.replace('translate-y-0', 'translate-y-4'); 
            setTimeout(() => p.classList.add('hidden'), 300); 
        } 
    },

    clearQueue: () => { 
        if(confirm("Czy na pewno chcesz wyczyścić kolejkę?")){ 
            const p = BeatHub.Player;
            p.state.currentQueue = []; 
            window.currentQueue = [];
            p.state.playedHistory = []; 
            window.playedHistory = [];
            p.state.currentPlaylistId = null; 
            p.state.currentAlbumId = null; 
            window.audio.pause(); 
            window.audio.src = ""; 
            document.body.classList.remove('player-active');
            document.getElementById('global-player').classList.add('translate-y-full'); 
            p.renderQueue(); 
            p.toggleQueue(); 
            p.syncListIcons(); 
            if (window.updatePlaylistIcons) window.updatePlaylistIcons(); 
            if (window.updateAlbumIcons) window.updateAlbumIcons(); 
            if (window.updateSongCardIcons) window.updateSongCardIcons();
            if (BeatHub.UI && BeatHub.UI.showToast) BeatHub.UI.showToast("Kolejka została wyczyszczona", true); 
        } 
    },

    removeFromQueue: (e, i) => { 
        e.stopPropagation(); 
        if(i === 0){ BeatHub.Player.playNext(); return; } 
        BeatHub.Player.state.currentQueue.splice(i, 1); 
        window.currentQueue = BeatHub.Player.state.currentQueue;
        BeatHub.Player.renderQueue(); 
    },

    reorderQueue: (f, t) => { 
        const p = BeatHub.Player;
        if(f === t) return; 
        const [m] = p.state.currentQueue.splice(f, 1); 
        p.state.currentQueue.splice(t, 0, m); 
        window.currentQueue = p.state.currentQueue;
        if(f === 0 || t === 0) p.loadAndPlay(); 
        else p.renderQueue(); 
    },

    renderQueue: function() {
        const p = BeatHub.Player;
        const l = document.getElementById('queue-list'); 
        if(!l) return;
        l.innerHTML = ''; 
        if(!p.state.currentQueue.length){ 
            l.innerHTML = '<div class="p-8 text-center text-gray-500 italic">Empty</div>'; 
            return; 
        }
        p.state.currentQueue.forEach((s, i) => {
            const act = i === 0; 
            const it = document.createElement('div'); 
            it.draggable = true; 
            it.className = `flex items-center gap-3 p-3 rounded-xl cursor-grab transition-all ${act?'bg-primary/20 border border-primary/30':'hover:bg-gray-800/50'}`;
            it.ondragstart = e => { e.dataTransfer.setData('text/plain', i); it.classList.add('dragging'); }; 
            it.ondragover = e => e.preventDefault(); 
            it.ondrop = e => { e.preventDefault(); p.reorderQueue(parseInt(e.dataTransfer.getData('text/plain')), i); }; 
            it.ondragend = () => it.classList.remove('dragging');
            it.onclick = () => { const sk = p.state.currentQueue.splice(0, i); p.state.playedHistory.push(...sk); p.loadAndPlay(); };
            it.innerHTML = `
                <div class="relative w-10 h-10 shrink-0 pointer-events-none">
                    <img src="${s.cover||''}" class="w-full h-full object-cover rounded-lg ${!s.cover?'hidden':''}"> 
                    ${act?'<div class="absolute inset-0 bg-primary/20 flex items-center justify-center rounded-lg"><div class="flex gap-0.5"><div class="w-0.5 h-3 bg-primary animate-bounce"></div><div class="w-0.5 h-4 bg-primary animate-bounce" style="animation-delay:0.2s"></div><div class="w-0.5 h-2 bg-primary animate-bounce" style="animation-delay:0.4s"></div></div></div>':''}
                </div>
                <div class="overflow-hidden flex-1 pointer-events-none">
                    <div class="text-sm font-bold ${act?'text-primary':'text-white'} truncate">${s.title}</div>
                    <div class="text-[11px] text-gray-500 truncate">${s.artist}</div>
                </div>
                <button onclick="BeatHub.Player.removeFromQueue(event,${i})" class="text-gray-500 hover:text-red-500 p-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>`; 
            l.appendChild(it);
        });
    },

    syncListIcons: () => {
        const currentSong = BeatHub.Player.state.currentQueue[0];
        const isPlaying = window.audio && !window.audio.paused;
        const ctx = BeatHub.Player.state.playbackContext || {};
        const norm = v => (!v || v === 'null' || v === 'None' || v === 'undefined' || v === '') ? null : String(v);
        const ctxType = norm(ctx.type);
        const ctxId = norm(ctx.id);

        document.querySelectorAll('.song-row').forEach(row => {
            const id = row.getAttribute('data-song-id');
            const rowCtxType = norm(row.getAttribute('data-context-type'));
            const rowCtxId = norm(row.getAttribute('data-context-id'));

            const songMatch = currentSong && String(id) === String(currentSong.id);
            // Strict context check only when both share the same type
            // (prevents highlighting wrong playlist/album/artist's row)
            // When types differ, song ID match is enough
            const sameType = ctxType && rowCtxType && ctxType === rowCtxType;
            const contextOk = !sameType || (ctxId === rowCtxId);

            if (songMatch && contextOk) {
                row.classList.add('is-current');
                if (isPlaying) row.classList.add('is-playing');
                else row.classList.remove('is-playing');
            } else {
                row.classList.remove('is-current', 'is-playing');
            }
        });
    },

    resumePlaybackDirectly: async (type, id, songId) => {
        if (!type || type === 'None' || type === 'null') return;
        const cleanId = (id && id !== 'None' && id !== 'null') ? id : '';
        const cleanSongId = (songId && songId !== 'None' && songId !== 'null') ? songId : '';
        try {
            const response = await fetch(`${window.BEATHUB_CONFIG.urls.getContextSongs}?type=${type}&id=${cleanId}&song_id=${cleanSongId}`);
            const data = await response.json();
            if (data.status === 'success' && data.songs && data.songs.length > 0) {
                let index = 0;
                if (cleanSongId) {
                    const foundIdx = data.songs.findIndex(s => String(s.id) === String(cleanSongId));
                    if (foundIdx !== -1) index = foundIdx;
                }
                BeatHub.Player.playGlobalQueue(data.songs, index, { type: type, id: cleanId || null });
            }
        } catch (err) { console.error("Błąd wznawiania odtwarzania:", err); }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    BeatHub.Player.init();
    
    window.audio.addEventListener('timeupdate', function() { 
        if(window.audio.duration && !BeatHub.Player.isDraggingSeek){ 
            const bar = document.getElementById('progress-bar');
            if(bar) bar.style.width = (window.audio.currentTime / window.audio.duration) * 100 + '%'; 
            const timeCurrent = document.getElementById('time-current');
            if(timeCurrent) timeCurrent.textContent = BeatHub.Player.fmtTime(window.audio.currentTime); 
            const timeTotal = document.getElementById('time-total');
            if(timeTotal) timeTotal.textContent = BeatHub.Player.fmtTime(window.audio.duration); 
        } 
    });
    
    window.audio.addEventListener('play', () => {
        BeatHub.Player.syncListIcons();
        if (window.updatePlaylistIcons) window.updatePlaylistIcons();
        if (window.updateAlbumIcons) window.updateAlbumIcons();
        if (window.updateSongCardIcons) window.updateSongCardIcons();
        document.getElementById('icon-play').classList.add('hidden');
        document.getElementById('icon-pause').classList.remove('hidden');
    });

    window.audio.addEventListener('pause', () => {
        BeatHub.Player.syncListIcons();
        if (window.updatePlaylistIcons) window.updatePlaylistIcons();
        if (window.updateAlbumIcons) window.updateAlbumIcons();
        if (window.updateSongCardIcons) window.updateSongCardIcons();
        document.getElementById('icon-play').classList.remove('hidden');
        document.getElementById('icon-pause').classList.add('hidden');
    });

    window.audio.addEventListener('playing', () => {
        const pc = document.getElementById('progress-container');
        if (pc) pc.classList.remove('is-buffering');
    });

    window.audio.addEventListener('ended', () => { 
        if(BeatHub.Player.state.repeatOne){ 
            BeatHub.Player.state.currentSongCounted = false; 
            window.audio.currentTime = 0; 
            window.audio.play(); 
        } else BeatHub.Player.playNext(); 
    });

    const pc = document.getElementById('progress-container');
    if (pc) {
        pc.addEventListener('mousedown', e => {
            BeatHub.Player.isDraggingSeek = true;
            pc.classList.add('is-dragging');
            BeatHub.Player.handleSeek(e);
        });
    }
    window.addEventListener('mousemove', e => { if (BeatHub.Player.isDraggingSeek) BeatHub.Player.handleSeek(e); });
    window.addEventListener('mouseup', e => {
        if (BeatHub.Player.isDraggingSeek) {
            const container = document.getElementById('progress-container');
            const r = container.getBoundingClientRect();
            let pos = (e.clientX - r.left) / r.width;
            pos = Math.max(0, Math.min(1, pos));
            window.audio.currentTime = pos * window.audio.duration;
            BeatHub.Player.isDraggingSeek = false;
            if (pc) pc.classList.remove('is-dragging');
        }
    });

    const vSlider = document.getElementById('volume-slider');
    if (vSlider) {
        vSlider.addEventListener('input', e => {
            const vol = e.target.value;
            window.audio.volume = vol;
            BeatHub.Player.updateVolumeBackground(vol);
            localStorage.setItem('beathub-volume', vol);
            
            if (window.discovery && window.discovery.audio) {
                window.discovery.audio.volume = vol;
                document.querySelectorAll('.volume-slider-discovery').forEach(s => {
                    s.value = vol;
                    s.style.background = `linear-gradient(to right, var(--primary) ${vol * 100}%, var(--border-main) ${vol * 100}%)`;
                });
            }
        });
    }

    if (!BeatHub.Player.playTicker) {
        BeatHub.Player.playTicker = setInterval(() => {
            if (window.audio && !window.audio.paused && BeatHub.Player.state.currentQueue && BeatHub.Player.state.currentQueue[0]) {
                BeatHub.Player.state.currentSongListenedTime += 1;
            }
        }, 1000);
        window.addEventListener('beforeunload', () => BeatHub.Player.reportPlay());
    }
});

document.addEventListener('turbo:load', () => {
    BeatHub.Player.init();
    const player = document.getElementById('global-player');
    if (player && !player.classList.contains('translate-y-full')) document.body.classList.add('player-active');

    // Auto-play from URL
    const params = new URLSearchParams(window.location.search);
    if (params.get('play') === '1') {
        const songId = params.get('song_id');
        const cType = params.get('c_type');
        const cId = params.get('c_id');
        
        setTimeout(() => {
            const queue = (cType === 'artist' && window.trendingArtistQueue) ? window.trendingArtistQueue : window.pageQueue;
            if (queue && queue.length > 0) {
                let index = 0;
                if (songId) {
                    const foundIdx = queue.findIndex(s => String(s.id) === String(songId));
                    if (foundIdx !== -1) index = foundIdx;
                }
                
                let context = null;
                if (cType) context = { type: cType, id: cId };
                
                window.playGlobalQueue(queue, index, context);
                
                const url = new URL(window.location);
                url.searchParams.delete('play');
                url.searchParams.delete('song_id');
                url.searchParams.delete('c_type');
                url.searchParams.delete('c_id');
                window.history.replaceState({}, '', url);
            }
        }, 400);
    }

    // Sync all playback indicators on the fresh DOM
    BeatHub.Player.syncListIcons();
    if (window.updatePlaylistIcons) window.updatePlaylistIcons();
    if (window.updateAlbumIcons) window.updateAlbumIcons();
    if (window.updateSongCardIcons) window.updateSongCardIcons();
});
window.playGlobalQueue = BeatHub.Player.playGlobalQueue;
window.toggleGlobalPlay = BeatHub.Player.toggleGlobalPlay;
window.playNext = BeatHub.Player.playNext;
window.playPrev = BeatHub.Player.playPrev;
window.toggleMute = BeatHub.Player.toggleMute;
window.toggleShuffle = BeatHub.Player.toggleShuffle;
window.toggleRepeat = BeatHub.Player.toggleRepeat;
window.toggleQueue = BeatHub.Player.toggleQueue;
window.resumePlaybackDirectly = BeatHub.Player.resumePlaybackDirectly;
window.clearQueue = BeatHub.Player.clearQueue;
window.removeFromQueue = BeatHub.Player.removeFromQueue;
window.reorderQueue = BeatHub.Player.reorderQueue;
window.handleSeek = BeatHub.Player.handleSeek;
