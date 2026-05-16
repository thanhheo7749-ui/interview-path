import { motion } from 'framer-motion';
import {
  Brain,
  CalendarCheck,
  Database,
  FileSearch,
  Handshake,
  IdCard,
  Layers,
  MessageCircle,
  Sparkles,
  Users,
  WandSparkles,
  Zap,
} from 'lucide-react';

import SlideFrame, { fadeUp, stagger } from '../SlideFrame.jsx';

const journeySteps = [
  { label: 'CV Submission', icon: FileSearch, state: 'active' },
  { label: 'AI CV Screening', icon: Sparkles, state: 'active' },
  { label: 'Passport Created', icon: IdCard, state: 'highlight' },
  { label: 'AI Interview Practice', icon: MessageCircle, state: 'highlight' },
  { label: 'Auto Scheduling', icon: CalendarCheck, state: 'active' },
  { label: 'Multi-round Evaluation', icon: Layers, state: 'highlight' },
  { label: 'Hiring Decision', icon: Handshake, state: 'active' },
  { label: 'Employee / Talent Pool', icon: Users, state: 'success' },
];

const flowLabels = [
  { label: 'Reads CV', icon: FileSearch, className: 'flow-label-muted', top: 72, left: '14.28%' },
  {
    label: 'Creates Passport',
    icon: IdCard,
    className: 'flow-label-purple',
    top: 132,
    left: '28.57%',
  },
  {
    label: 'Coaches',
    icon: WandSparkles,
    className: 'flow-label-purple',
    top: 72,
    left: '42.85%',
  },
  {
    label: 'Schedules',
    icon: CalendarCheck,
    className: 'flow-label-muted',
    top: 132,
    left: '57.14%',
  },
  {
    label: 'Evaluates Fit',
    icon: Zap,
    className: 'flow-label-purple',
    top: 72,
    left: '71.42%',
  },
  {
    label: 'Saves Memory',
    icon: Database,
    className: 'flow-label-green',
    top: 132,
    left: '100%',
  },
];

function JourneyStep({ index, label, icon: Icon, state }) {
  const parts = label.split(' ');
  const firstLine = index === 7 ? 'Employee /' : parts.slice(0, -1).join(' ');
  const secondLine = index === 7 ? 'Talent Pool' : parts.at(-1);

  return (
    <motion.div className={`j-node ${state}`} variants={fadeUp}>
      <div className="icon-box">
        <Icon aria-hidden="true" />
        <div className="step-num">{index + 1}</div>
      </div>
      <div className="step-text">
        {firstLine}
        <br />
        {secondLine}
      </div>
    </motion.div>
  );
}

function Slide05CoreFlow() {
  return (
    <SlideFrame
      tag="The Core Flow"
      tagTone="dark"
      title="From CV to Employee"
      subtitle="How the AI Orchestrator manages the seamless recruitment journey."
    >
      <motion.div animate="show" className="journey-diagram" initial="hidden" variants={stagger}>
        <motion.div className="orchestrator" variants={fadeUp}>
          <div className="orchestrator-core ai-brain-pulse">
            <Brain aria-hidden="true" /> AI Orchestrator
          </div>
          <div className="orchestrator-caption">
            Continuously coordinates, evaluates, and stores memory
          </div>
        </motion.div>

        <svg
          aria-hidden="true"
          className="journey-svg"
          preserveAspectRatio="none"
          viewBox="0 0 1000 520"
        >
          <defs>
            <linearGradient id="lineGrad" x1="0%" x2="0%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#cbd5e1" stopOpacity="0.2" />
            </linearGradient>
            <linearGradient id="lineGradHighlight" x1="0%" x2="0%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#cbd5e1" stopOpacity="0.2" />
            </linearGradient>
          </defs>
          <path className="n8n-flow-slow" d="M 500 0 C 500 70, 143 70, 143 120 L 143 520" />
          <path
            className="n8n-flow-fast"
            d="M 500 0 C 500 120, 286 120, 286 190 L 286 520"
          />
          <path
            className="n8n-flow-fast"
            d="M 500 0 C 500 70, 429 70, 429 120 L 429 520"
          />
          <path className="n8n-flow-slow" d="M 500 0 C 500 120, 571 120, 571 190 L 571 520" />
          <path
            className="n8n-flow-fast"
            d="M 500 0 C 500 70, 714 70, 714 120 L 714 520"
          />
          <path className="n8n-flow-green" d="M 500 0 C 500 120, 1000 120, 1000 190 L 1000 520" />
        </svg>

        <div className="flow-label-layer" aria-hidden="true">
          {flowLabels.map(({ label, icon: Icon, className, top, left }) => (
            <div className={`term-card-label ${className}`} key={label} style={{ left, top }}>
              <Icon aria-hidden="true" />
              {label}
            </div>
          ))}
        </div>

        <motion.div className="journey-container" variants={stagger}>
          {journeySteps.map((step, index) => (
            <JourneyStep index={index} key={step.label} {...step} />
          ))}
        </motion.div>
      </motion.div>
    </SlideFrame>
  );
}

export default Slide05CoreFlow;
