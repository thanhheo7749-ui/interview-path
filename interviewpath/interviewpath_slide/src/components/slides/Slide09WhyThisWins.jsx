import { motion } from 'framer-motion';
import { Check, X } from 'lucide-react';

import SlideFrame from '../SlideFrame.jsx';

const genericItems = [
  'Random, generic questions',
  'One-time feedback',
  'Only the candidate practises',
  'Session ends, data is lost',
  'No talent reuse',
];

const interviewPathItems = [
  'Company-specific questions (RAG)',
  'Long-term candidate memory',
  'Complete HR + Candidate journey',
  'Candidate Passport grows over time',
  'Talent Pool for future roles',
];

function ComparisonColumn({ title, items, type }) {
  const Icon = type === 'positive' ? Check : X;
  const x = type === 'positive' ? 30 : -30;

  return (
    <motion.div
      animate={{ opacity: 1, x: 0 }}
      className={`vs-col ${type === 'positive' ? 'interviewpath' : 'generic'}`}
      initial={false}
      transition={{ duration: 0.5, ease: 'easeOut', delay: type === 'positive' ? 0.14 : 0 }}
    >
      <div className="vs-title">{title}</div>
      {items.map((item) => (
        <div className="vs-item" key={item}>
          <Icon aria-hidden="true" />
          <div>{item}</div>
        </div>
      ))}
    </motion.div>
  );
}

function Slide09WhyThisWins() {
  return (
    <SlideFrame
      tag="Competitive Advantage"
      tagTone="green"
      title="Why This Wins"
      subtitle="Not just interview practice - a talent memory layer for the whole hiring journey."
    >
      <div className="vs-container">
        <ComparisonColumn items={genericItems} title="Generic AI Coach" type="negative" />
        <motion.div
          animate={{ opacity: 1, scale: 1 }}
          className="vs-badge-center"
          initial={false}
          transition={{ duration: 0.38, delay: 0.18 }}
        >
          VS
        </motion.div>
        <ComparisonColumn items={interviewPathItems} title="InterviewPath" type="positive" />
      </div>
    </SlideFrame>
  );
}

export default Slide09WhyThisWins;
