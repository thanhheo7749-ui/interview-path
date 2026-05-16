import { motion } from 'framer-motion';
import { UserRoundX, Users } from 'lucide-react';

import FeatureCard from '../FeatureCard.jsx';
import SlideFrame, { stagger } from '../SlideFrame.jsx';

function Slide02Problem() {
  return (
    <SlideFrame tag="The Problem" title="Recruitment is Fragmented">
      <motion.div animate="show" className="grid-2 problem-grid" initial="hidden" variants={stagger}>
        <FeatureCard icon={Users} title="For HR Teams" tone="red">
          One open role can attract 500-1,000 CVs. HR teams must screen under time pressure,
          shortlist quickly, schedule interviews, and still keep feedback from every round organized.
        </FeatureCard>
        <FeatureCard icon={UserRoundX} title="For Candidates" tone="amber">
          They don't know if they truly fit the job. They are unprepared for specific corporate
          cultures, receive zero feedback after failing, and cannot track their own progress.
        </FeatureCard>
      </motion.div>
    </SlideFrame>
  );
}

export default Slide02Problem;
