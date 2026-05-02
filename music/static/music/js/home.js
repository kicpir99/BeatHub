window.BeatHub = window.BeatHub || {};
BeatHub.Home = BeatHub.Home || {};

// --- HERO SLIDER ---

BeatHub.Home.initHeroSlider = () => {
    const wrapper = document.getElementById('slider-wrapper');
    if (!wrapper) return;

    const slidesCount = parseInt(wrapper.getAttribute('data-slides-count') || 0);
    if (slidesCount === 0) return;

    let currentSlide = 0; 
    const dots = document.querySelectorAll('.slider-dot');
    
    const updateSlider = () => {
        wrapper.style.transform = `translateX(-${currentSlide * 100}%)`;
        dots.forEach((dot, index) => {
            dot.classList.toggle('bg-green-500', index === currentSlide);
            dot.classList.toggle('w-8', index === currentSlide); 
            dot.classList.toggle('bg-white/20', index !== currentSlide);
        });
    };

    BeatHub.Home.moveSlider = d => { 
        currentSlide = (currentSlide + d + slidesCount) % slidesCount; 
        updateSlider(); 
        resetAutoSlide(); 
    };
    
    BeatHub.Home.goToSlide = i => { 
        currentSlide = i; 
        updateSlider(); 
        resetAutoSlide(); 
    };
    
    if (BeatHub.Home.heroSliderInterval) {
        clearInterval(BeatHub.Home.heroSliderInterval);
    }
    
    BeatHub.Home.heroSliderInterval = setInterval(() => BeatHub.Home.moveSlider(1), 8000);
    
    const resetAutoSlide = () => { 
        clearInterval(BeatHub.Home.heroSliderInterval); 
        BeatHub.Home.heroSliderInterval = setInterval(() => BeatHub.Home.moveSlider(1), 8000); 
    };
    
    updateSlider();
};

BeatHub.Home.handleAlbumToggle = (albumId, songs) => {
    const isSameContext = window.currentPlaybackContext && 
                         window.currentPlaybackContext.type === 'album' && 
                         String(window.currentPlaybackContext.id) === String(albumId);

    if (isSameContext) {
        if (window.toggleGlobalPlay) window.toggleGlobalPlay();
    } else {
        if (window.playGlobalQueue) window.playGlobalQueue(songs, 0, {type: 'album', id: albumId});
    }
};

BeatHub.Home.handleSongCardToggle = (songs, index, context, songId) => {
    const currentSong = window.currentQueue && window.currentQueue[0];
    const isSameSong = currentSong && String(currentSong.id) === String(songId);
    
    if (isSameSong) {
        if (window.toggleGlobalPlay) window.toggleGlobalPlay();
    } else {
        if (window.playGlobalQueue) window.playGlobalQueue(songs, index, context);
    }
};

// --- GENRES TOGGLE ---

BeatHub.Home.toggleGenres = () => {
    const grid = document.getElementById('genres-grid');
    const btn = document.getElementById('toggle-genres');
    if (!grid || !btn) return;
    
    const cards = grid.querySelectorAll('.genre-card');
    const isExp = btn.textContent === 'Pokaż mniej';
    cards.forEach((c, i) => { if (i >= 5) c.classList.toggle('hidden', isExp); });
    btn.textContent = isExp ? 'Pokaż wszystkie' : 'Pokaż mniej';
};

// --- RECOMMENDATION CAROUSEL ---

BeatHub.Home.updateCarouselArrows = () => {
    const container = document.getElementById('smart-suggest-carousel');
    const prevBtn = document.getElementById('prev-btn-smart');
    const nextBtn = document.getElementById('next-btn-smart');
    
    if (!container || !prevBtn || !nextBtn) return;
    
    const scrollLeft = container.scrollLeft;
    const maxScroll = container.scrollWidth - container.clientWidth;
    
    if (scrollLeft <= 5) {
        prevBtn.style.visibility = 'hidden';
        prevBtn.style.opacity = '0';
    } else {
        prevBtn.style.visibility = 'visible';
        prevBtn.style.opacity = '';
    }
    
    if (scrollLeft >= maxScroll - 5) {
        nextBtn.style.visibility = 'hidden';
        nextBtn.style.opacity = '0';
    } else {
        nextBtn.style.visibility = 'visible';
        nextBtn.style.opacity = '';
    }
};

BeatHub.Home.scrollCarousel = (containerId, direction) => {
    const container = document.getElementById(containerId);
    if (container) {
        const gap = 24; 
        const scrollAmount = container.clientWidth + gap;
        container.scrollBy({ left: scrollAmount * direction, behavior: 'smooth' });
        setTimeout(BeatHub.Home.updateCarouselArrows, 400);
    }
};

BeatHub.Home.initCarouselArrows = () => {
    const container = document.getElementById('smart-suggest-carousel');
    if (container) {
        container.removeEventListener('scroll', BeatHub.Home.updateCarouselArrows);
        container.addEventListener('scroll', BeatHub.Home.updateCarouselArrows);
        window.removeEventListener('resize', BeatHub.Home.updateCarouselArrows);
        window.addEventListener('resize', BeatHub.Home.updateCarouselArrows);
        setTimeout(BeatHub.Home.updateCarouselArrows, 150);
    }
};

// --- LIFECYCLE ---

BeatHub.Home.init = () => {
    BeatHub.Home.initHeroSlider();
    BeatHub.Home.initCarouselArrows();
};

document.addEventListener('turbo:load', BeatHub.Home.init);
document.addEventListener('DOMContentLoaded', BeatHub.Home.init);

window.handleAlbumToggle = BeatHub.Home.handleAlbumToggle;
window.handleSongCardToggle = BeatHub.Home.handleSongCardToggle;
window.moveSlider = d => BeatHub.Home.moveSlider(d);
window.goToSlide = i => BeatHub.Home.goToSlide(i);
window.toggleGenres = BeatHub.Home.toggleGenres;
window.updateCarouselArrows = BeatHub.Home.updateCarouselArrows;
window.scrollCarousel = BeatHub.Home.scrollCarousel;
