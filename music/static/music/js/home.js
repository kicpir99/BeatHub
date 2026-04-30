// --- KARUZELA HERO ---
(function() {
    const wrapper = document.getElementById('slider-wrapper');
    if (!wrapper) return;

    const slidesCount = parseInt(wrapper.getAttribute('data-slides-count') || 0);
    if (slidesCount === 0) return;

    let currentSlide = 0; 
    const dots = document.querySelectorAll('.slider-dot');
    
    function updateSlider() {
        wrapper.style.transform = `translateX(-${currentSlide * 100}%)`;
        dots.forEach((dot, index) => {
            dot.classList.toggle('bg-green-500', index === currentSlide);
            dot.classList.toggle('w-8', index === currentSlide); 
            dot.classList.toggle('bg-white/20', index !== currentSlide);
        });
    }

    window.handleAlbumToggle = (albumId, songs) => {
        const isSameContext = window.currentPlaybackContext && 
                             window.currentPlaybackContext.type === 'album' && 
                             String(window.currentPlaybackContext.id) === String(albumId);

        if (isSameContext) {
            window.toggleGlobalPlay();
        } else {
            window.playGlobalQueue(songs, 0, {type: 'album', id: albumId});
        }
    };

    window.handleSongCardToggle = (songs, index, context, songId) => {
        const currentSong = window.currentQueue && window.currentQueue[0];
        const isSameSong = currentSong && String(currentSong.id) === String(songId);
        
        if (isSameSong) {
            window.toggleGlobalPlay();
        } else {
            window.playGlobalQueue(songs, index, context);
        }
    };

    window.moveSlider = d => { 
        currentSlide = (currentSlide + d + slidesCount) % slidesCount; 
        updateSlider(); 
        resetAutoSlide(); 
    };
    
    window.goToSlide = i => { 
        currentSlide = i; 
        updateSlider(); 
        resetAutoSlide(); 
    };
    
    if (window.heroSliderInterval) {
        clearInterval(window.heroSliderInterval);
    }
    
    window.heroSliderInterval = setInterval(() => window.moveSlider(1), 8000);
    
    function resetAutoSlide() { 
        clearInterval(window.heroSliderInterval); 
        window.heroSliderInterval = setInterval(() => window.moveSlider(1), 8000); 
    }
    
    updateSlider();
})();

// --- GATUNKI TOGGLE ---
window.toggleGenres = function() {
    const grid = document.getElementById('genres-grid');
    const btn = document.getElementById('toggle-genres');
    if (!grid || !btn) return;
    
    const cards = grid.querySelectorAll('.genre-card');
    const isExp = btn.textContent === 'Pokaż mniej';
    cards.forEach((c, i) => { if (i >= 5) c.classList.toggle('hidden', isExp); });
    btn.textContent = isExp ? 'Pokaż wszystkie' : 'Pokaż mniej';
}

// --- KARUZELA REKOMENDACJI ---
window.updateCarouselArrows = function() {
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
}

window.scrollCarousel = function(containerId, direction) {
    const container = document.getElementById(containerId);
    if (container) {
        const gap = 24; 
        const scrollAmount = container.clientWidth + gap;
        container.scrollBy({ left: scrollAmount * direction, behavior: 'smooth' });
        setTimeout(window.updateCarouselArrows, 400);
    }
}

function initCarouselArrows() {
    const container = document.getElementById('smart-suggest-carousel');
    if (container) {
        container.removeEventListener('scroll', window.updateCarouselArrows);
        container.addEventListener('scroll', window.updateCarouselArrows);
        window.removeEventListener('resize', window.updateCarouselArrows);
        window.addEventListener('resize', window.updateCarouselArrows);
        setTimeout(window.updateCarouselArrows, 150);
    }
}

document.addEventListener('turbo:load', initCarouselArrows);
document.addEventListener('DOMContentLoaded', initCarouselArrows);
