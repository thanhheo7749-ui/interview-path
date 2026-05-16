import { useEffect, useState } from 'react';
import { Maximize2, Minimize2 } from 'lucide-react';

function formatSlideNumber(index) {
  return String(index + 1).padStart(2, '0');
}

function SlideNavigation({ currentSlide, totalSlides, goToSlide }) {
  const [isFullscreen, setIsFullscreen] = useState(Boolean(document.fullscreenElement));
  const progress = ((currentSlide + 1) / totalSlides) * 100;
  const FullscreenIcon = isFullscreen ? Minimize2 : Maximize2;

  useEffect(() => {
    function handleFullscreenChange() {
      setIsFullscreen(Boolean(document.fullscreenElement));
    }

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  async function toggleFullscreen() {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      return;
    }

    await document.documentElement.requestFullscreen();
  }

  return (
    <div className="deck-controls" data-interactive="true">
      <div className="deck-progress" aria-hidden="true">
        <div style={{ width: `${progress}%` }} />
      </div>

      <div className="slide-counter" aria-live="polite">
        <span>{formatSlideNumber(currentSlide)}</span>
        <span>/</span>
        <span>{formatSlideNumber(totalSlides - 1)}</span>
      </div>

      <div className="slide-dots" aria-label="Slide navigation">
        {Array.from({ length: totalSlides }, (_, index) => (
          <button
            aria-label={`Go to slide ${index + 1}`}
            aria-current={index === currentSlide ? 'step' : undefined}
            className={index === currentSlide ? 'active' : ''}
            key={index}
            onClick={() => goToSlide(index)}
            type="button"
          />
        ))}
      </div>

      <button
        aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
        className="fullscreen-button"
        onClick={toggleFullscreen}
        type="button"
      >
        <FullscreenIcon aria-hidden="true" />
        <span>{isFullscreen ? 'Exit' : 'Fullscreen'}</span>
      </button>
    </div>
  );
}

export default SlideNavigation;
