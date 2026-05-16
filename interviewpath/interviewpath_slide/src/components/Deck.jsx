import { AnimatePresence, motion } from 'framer-motion';

import useSlideNavigation from '../hooks/useSlideNavigation.js';
import SlideNavigation from './SlideNavigation.jsx';
import Slide01Title from './slides/Slide01Title.jsx';
import Slide02Problem from './slides/Slide02Problem.jsx';
import Slide03Insight from './slides/Slide03Insight.jsx';
import Slide04Solution from './slides/Slide04Solution.jsx';
import Slide05CoreFlow from './slides/Slide05CoreFlow.jsx';
import Slide06Architecture from './slides/Slide06Architecture.jsx';
import Slide07HRExperience from './slides/Slide07HRExperience.jsx';
import Slide08LiveDemo from './slides/Slide08LiveDemo.jsx';
import Slide09WhyThisWins from './slides/Slide09WhyThisWins.jsx';
import Slide10ClosingQA from './slides/Slide10ClosingQA.jsx';

const slides = [
  Slide01Title,
  Slide02Problem,
  Slide03Insight,
  Slide04Solution,
  Slide05CoreFlow,
  Slide06Architecture,
  Slide07HRExperience,
  Slide08LiveDemo,
  Slide09WhyThisWins,
  Slide10ClosingQA,
];

const slideVariants = {
  enter: (direction) => ({
    x: direction > 0 ? 80 : -80,
    opacity: 0,
    scale: 0.98,
  }),
  center: {
    x: 0,
    opacity: 1,
    scale: 1,
  },
  exit: (direction) => ({
    x: direction > 0 ? -80 : 80,
    opacity: 0,
    scale: 0.98,
  }),
};

function isInteractiveTarget(target) {
  if (!(target instanceof Element)) return false;

  return Boolean(
    target.closest(
      'input, textarea, select, button, a, [role="button"], [contenteditable="true"], [data-interactive="true"]',
    ),
  );
}

function Deck() {
  const { currentSlide, direction, goNext, goPrev, goToSlide } = useSlideNavigation(slides.length);
  const ActiveSlide = slides[currentSlide];

  function handleDeckClick(event) {
    if (isInteractiveTarget(event.target)) return;

    const rect = event.currentTarget.getBoundingClientRect();
    const clickedRightHalf = event.clientX - rect.left > rect.width / 2;

    if (clickedRightHalf) goNext();
    else goPrev();
  }

  return (
    <main id="deck-root" onClick={handleDeckClick}>
      <div className="deck-stage">
        <AnimatePresence custom={direction} initial={false} mode="wait">
          <motion.section
            animate="center"
            className="slide-motion"
            custom={direction}
            exit="exit"
            initial="enter"
            key={currentSlide}
            transition={{ duration: 0.45, ease: 'easeInOut' }}
            variants={slideVariants}
          >
            <ActiveSlide />
          </motion.section>
        </AnimatePresence>

        <SlideNavigation
          currentSlide={currentSlide}
          goToSlide={goToSlide}
          totalSlides={slides.length}
        />
      </div>
    </main>
  );
}

export default Deck;
