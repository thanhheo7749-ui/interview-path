import { motion } from 'framer-motion';
import { Brain, Workflow } from 'lucide-react';

import SlideFrame, { fadeUp, stagger } from '../SlideFrame.jsx';

function Slide04Solution() {
  return (
    <SlideFrame
      tag="The Solution"
      title="InterviewPath Platform"
      subtitle="A unified AI Recruitment Journey Platform driven by two core engines."
    >
      <motion.div animate="show" className="grid-2 solution-grid" initial="hidden" variants={stagger}>
        <motion.article className="term-card term-card-blue" variants={fadeUp}>
          <div className="term-title">
            <Workflow aria-hidden="true" /> Workflow Automator (n8n)
          </div>
          <p className="term-desc">
            Controls the entire lifecycle automatically: from receiving CVs, sending practice
            links, scheduling calendar invites, to moving profiles from applicant to employee
            record.
          </p>
        </motion.article>
        <motion.article className="term-card term-card-purple" variants={fadeUp}>
          <div className="term-title">
            <Brain aria-hidden="true" /> Company Hiring Brain (RAG)
          </div>
          <p className="term-desc">
            Stores company culture, rubrics, and technical requirements. Generates personalized
            interview coaching, evaluates culture fit, and provides detailed candidate readiness
            reports.
          </p>
        </motion.article>
      </motion.div>
    </SlideFrame>
  );
}

export default Slide04Solution;
