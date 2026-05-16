import { motion } from 'framer-motion';
import {
  Brain,
  Briefcase,
  CalendarCheck,
  ChartLine,
  ChevronRight,
  ClipboardList,
  Columns3,
  Database,
  FileQuestion,
  FolderOpen,
  IdCard,
  Monitor,
  Network,
  PanelTop,
  RefreshCcw,
  Server,
  Star,
  User,
  Users,
  Video,
  Workflow,
  Zap,
} from 'lucide-react';

import ArchitectureCard from '../ArchitectureCard.jsx';
import SlideFrame, { fadeUp, stagger } from '../SlideFrame.jsx';

const userLayer = [
  { title: 'Candidate', icon: User },
  { title: 'HR Recruiter', icon: Users },
  { title: 'Hiring Manager', icon: Briefcase },
];

const appLayer = [
  { title: 'Candidate Portal', description: 'CV submission & practice', icon: Monitor },
  { title: 'AI Interview Room', description: 'Camera, mic, answers', icon: Video },
  { title: 'HR Workspace', description: 'Pipeline, scores, actions', icon: Columns3 },
  { title: 'RAG Graph Viewer', description: 'Company & candidate memory', icon: Network },
];

const coreLayer = [
  { title: 'n8n Workflow', description: 'Screening, scheduling, reminders.', icon: Workflow, variant: 'blue' },
  { title: 'RAG Retrieval', description: 'JD, culture, rubrics, memory.', icon: Database, variant: 'purple' },
  {
    title: 'Graph Intelligence',
    description: 'Connects candidate-job-culture fit.',
    icon: Network,
    variant: 'amber',
  },
  {
    title: 'LLM Interview Coach',
    description: 'Generates questions & feedback.',
    icon: Brain,
    variant: 'green',
  },
];

const dataLayer = [
  { title: 'Company Graph', icon: Network, variant: 'green' },
  { title: 'Candidate DB', icon: Server, variant: 'purple' },
  { title: 'Recruitment DB', icon: FolderOpen, variant: 'blue' },
];

const outputLayer = [
  { title: 'Match Score', icon: Zap },
  { title: 'Personalized Questions', icon: FileQuestion },
  { title: 'Readiness Report', icon: ChartLine },
  { title: 'HR Recommendation', icon: ClipboardList },
  { title: 'Talent Pool / Employee Record', icon: Users, highlight: true },
];

function ArrowConnector({ label }) {
  return (
    <motion.div className="sa-arrow" variants={fadeUp}>
      <span>{label}</span>
      <ChevronRight aria-hidden="true" />
    </motion.div>
  );
}

function Slide06Architecture() {
  return (
    <SlideFrame
      bodyClassName="architecture-body"
      className="architecture-slide"
      headerAlign="center"
      title="InterviewPath System Architecture"
      subtitle="How workflow automation, AI reasoning, and talent memory work together."
    >
      <motion.div animate="show" className="sa-wrapper" initial="hidden" variants={stagger}>
        <div className="sa-main-grid">
          <motion.div className="sa-col sa-col-users" variants={fadeUp}>
            <div className="sa-title">Users</div>
            {userLayer.map((item) => (
              <ArchitectureCard key={item.title} simple variant="user" {...item} />
            ))}
          </motion.div>

          <ArrowConnector label="submit" />

          <motion.div className="sa-col sa-col-app" variants={fadeUp}>
            <div className="sa-title">Application Layer</div>
            {appLayer.map((item) => (
              <ArchitectureCard key={item.title} variant="app" {...item} />
            ))}
          </motion.div>

          <ArrowConnector label="process" />

          <motion.div className="sa-core-wrapper" variants={fadeUp}>
            <div className="sa-core-container">
              <div className="sa-core-title">AI & Automation Core</div>
              <div className="sa-core-grid">
                {coreLayer.map((item) => (
                  <ArchitectureCard key={item.title} {...item} />
                ))}
                <div className="sa-mod-passport">
                  <div className="sa-mod-passport-badge">
                    <Star aria-hidden="true" /> Core Memory Layer
                  </div>
                  <h4>
                    <IdCard aria-hidden="true" /> Candidate Passport Service
                  </h4>
                  <p>Stores readiness, feedback history, fit signals, and growth progress.</p>
                </div>
              </div>
            </div>

            <div className="sa-data-connector">
              <RefreshCcw aria-hidden="true" />
              <span>store & retrieve</span>
            </div>

            <div className="sa-data-layer">
              <div className="sa-data-title">Data Layer</div>
              <div className="sa-data-grid">
                {dataLayer.map(({ title, icon: Icon, variant }) => (
                  <div className={`sa-db-card sa-db-${variant}`} key={title}>
                    <Icon aria-hidden="true" />
                    <span>{title}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>

          <ArrowConnector label="recommend" />

          <motion.div className="sa-col sa-col-outputs" variants={fadeUp}>
            <div className="sa-title sa-title-output">Outputs</div>
            {outputLayer.map((item) => (
              <ArchitectureCard
                key={item.title}
                simple
                variant="output"
                highlight={item.highlight}
                {...item}
              />
            ))}
          </motion.div>
        </div>

        <motion.div className="sa-loop" variants={fadeUp}>
          <RefreshCcw aria-hidden="true" />
          Memory Loop: Every answer, score, and HR feedback updates the Candidate Passport.
        </motion.div>
      </motion.div>
    </SlideFrame>
  );
}

export default Slide06Architecture;
