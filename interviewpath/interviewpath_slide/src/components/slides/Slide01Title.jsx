import { motion } from 'framer-motion';

import SlideFrame, { fadeUp, stagger } from '../SlideFrame.jsx';
import Tag from '../Tag.jsx';

function Slide01Title() {
  return (
    <SlideFrame center className="title-slide">
      <motion.div animate="show" className="title-lockup" initial="hidden" variants={stagger}>
        <motion.div variants={fadeUp}>
          <Tag>AI Recruitment Platform</Tag>
        </motion.div>
        <motion.h1 className="title-main" variants={fadeUp}>
          InterviewPath
        </motion.h1>
        <motion.p className="subtitle" variants={fadeUp}>
          AI Talent Memory Platform
          <br />
          from CV Screening to Employee Onboarding.
        </motion.p>
        <motion.div className="title-team" variants={fadeUp}>
          <p className="title-team-label">TEAM MEMBERS</p>
          <div className="title-team-grid">
            <div>
              <p>Lưu Gia Bảo</p>
              <p>Tạ Hoàng Thành</p>
            </div>
            <div>
              <p>Nguyễn Phương Quang</p>
              <p>Tạ Vĩnh Quang</p>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </SlideFrame>
  );
}

export default Slide01Title;
