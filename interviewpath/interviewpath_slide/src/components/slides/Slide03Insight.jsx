import { motion } from 'framer-motion';

import SlideFrame, { fadeUp, stagger } from '../SlideFrame.jsx';

function Slide03Insight() {
  return (
    <SlideFrame tag="Key Insight" tagTone="purple" title="The Missing Memory Layer">
      <motion.div animate="show" className="insight-panel" initial="hidden" variants={stagger}>
        <motion.h3 variants={fadeUp}>
          "Hiring should not be based on a single CV or interview.
          <br />
          It requires an <span>AI Candidate Passport</span>."
        </motion.h3>
        <motion.p variants={fadeUp}>
          <strong>Breakthrough:</strong> InterviewPath creates a{' '}
          <strong>Candidate Digital Twin</strong> - a living AI profile that remembers each
          candidate's skills, interview answers, culture-fit signals, feedback history, and
          readiness progress.
        </motion.p>
      </motion.div>
    </SlideFrame>
  );
}

export default Slide03Insight;
