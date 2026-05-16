import { motion } from 'framer-motion';
import { Bookmark, CalendarCheck, Check, Code, Database, FileSearch, Menu, PenTool, Video } from 'lucide-react';

import SlideFrame, { fadeUp, stagger } from '../SlideFrame.jsx';

const features = [
  {
    title: '1. AI CV Screening',
    icon: FileSearch,
    text: 'Automatically extracts CV info, compares it with the JD, and generates a ranked candidate shortlist.',
  },
  {
    title: '2. Auto Scheduling',
    icon: CalendarCheck,
    text: 'Syncs with Google Calendar. n8n sends automated interview invitations and reminders without back-and-forth emails.',
  },
  {
    title: '3. AI Talent Memory',
    icon: Database,
    text: 'Creates a Candidate Passport. Stores evaluation scores and reuses strong candidates for future roles instead of losing them.',
  },
];

const columns = [
  {
    title: 'Shortlisted',
    count: 1,
    cards: [
      {
        name: 'Le Thi B',
        sub: 'UI/UX Designer',
        icon: PenTool,
        badge: 'Match: 75%',
        badgeClass: 'match',
      },
    ],
  },
  {
    title: 'Scheduled',
    count: 1,
    cards: [
      {
        name: 'Tran Van C',
        sub: 'Culture Round',
        icon: Video,
        badge: 'Tomorrow, 10 AM',
        badgeClass: 'sched',
      },
    ],
  },
  {
    title: 'Technical',
    count: 1,
    cards: [
      {
        name: 'Nguyen Van A',
        sub: 'Backend Dev',
        icon: Code,
        badge: 'In Progress',
        badgeClass: 'progress',
      },
    ],
  },
  {
    title: 'Hired / Pool',
    count: 2,
    cards: [
      {
        name: 'Pham Dao D',
        sub: 'Passed All',
        icon: Check,
        badge: 'Profile Saved',
        badgeClass: 'hired',
      },
      {
        name: 'Le Minh E',
        sub: 'Fit for Q3 Role',
        icon: Bookmark,
        badge: 'Passport to Pool',
        badgeClass: 'pool',
      },
    ],
  },
];

function Slide07HRExperience() {
  return (
    <SlideFrame tag="HR Experience" tagTone="green" title="Empowering the Recruiter">
      <div className="grid-2 hr-grid">
        <motion.div animate="show" className="hr-feature-list" initial="hidden" variants={stagger}>
          {features.map(({ title, icon: Icon, text }) => (
            <motion.div className="hr-feature" key={title} variants={fadeUp}>
              <h3>
                <Icon aria-hidden="true" /> {title}
              </h3>
              <p>{text}</p>
            </motion.div>
          ))}
        </motion.div>

        <motion.div animate="show" className="diagram-container hr-panel" initial="hidden" variants={fadeUp}>
          <div className="hr-dash">
            <div className="hr-dash-header">
              <div className="hr-dots" aria-hidden="true">
                <div className="hr-dot" />
                <div className="hr-dot" />
                <div className="hr-dot" />
              </div>
              <div className="hr-dash-title">InterviewPath HR Workspace</div>
              <Menu className="hr-menu" aria-hidden="true" />
            </div>
            <div className="hr-board">
              {columns.map((column) => (
                <div className="hr-col" key={column.title}>
                  <div className="hr-col-title">
                    {column.title} <span>{column.count}</span>
                  </div>
                  {column.cards.map(({ name, sub, icon: Icon, badge, badgeClass }) => (
                    <div className="hr-card" key={name}>
                      <div className="hr-card-title">{name}</div>
                      <div className="hr-card-sub">
                        <Icon aria-hidden="true" /> {sub}
                      </div>
                      <div className={`hr-badge ${badgeClass}`}>{badge}</div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      </div>
    </SlideFrame>
  );
}

export default Slide07HRExperience;
