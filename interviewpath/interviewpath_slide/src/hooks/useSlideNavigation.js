import { useCallback, useEffect, useState } from 'react';

function clampSlide(index, totalSlides) {
  return Math.min(Math.max(index, 0), totalSlides - 1);
}

function getInitialSlide(totalSlides) {
  if (typeof window === 'undefined') return 0;

  const params = new URLSearchParams(window.location.search);
  const requested = Number(params.get('slide') || window.location.hash.replace(/[^\d]/g, ''));

  if (!Number.isFinite(requested) || requested < 1) return 0;
  return clampSlide(requested - 1, totalSlides);
}

function isEditableTarget(target) {
  if (!(target instanceof Element)) return false;

  return Boolean(
    target.closest(
      'input, textarea, select, button, a, [contenteditable="true"], [data-interactive="true"]',
    ),
  );
}

export default function useSlideNavigation(totalSlides) {
  const [currentSlide, setCurrentSlide] = useState(() => getInitialSlide(totalSlides));
  const [direction, setDirection] = useState(1);

  const goToSlide = useCallback(
    (index) => {
      setCurrentSlide((previous) => {
        const next = clampSlide(index, totalSlides);
        if (next === previous) return previous;

        setDirection(next > previous ? 1 : -1);
        return next;
      });
    },
    [totalSlides],
  );

  const goNext = useCallback(() => {
    setCurrentSlide((previous) => {
      const next = clampSlide(previous + 1, totalSlides);
      if (next === previous) return previous;

      setDirection(1);
      return next;
    });
  }, [totalSlides]);

  const goPrev = useCallback(() => {
    setCurrentSlide((previous) => {
      const next = clampSlide(previous - 1, totalSlides);
      if (next === previous) return previous;

      setDirection(-1);
      return next;
    });
  }, [totalSlides]);

  useEffect(() => {
    function handleKeyDown(event) {
      if (isEditableTarget(event.target)) return;

      if (event.key === 'ArrowRight' || event.key === ' ') {
        event.preventDefault();
        goNext();
      }

      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        goPrev();
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [goNext, goPrev]);

  return {
    currentSlide,
    direction,
    goNext,
    goPrev,
    goToSlide,
  };
}
