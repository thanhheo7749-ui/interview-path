import { motion } from 'framer-motion';

import { fadeUp } from './SlideFrame.jsx';

function FeatureCard({ icon: Icon, title, children, tone = 'blue', className = '' }) {
  return (
    <motion.article className={`feature-card feature-card-${tone} ${className}`} variants={fadeUp}>
      {Icon ? <Icon className="feature-icon" aria-hidden="true" /> : null}
      <h3>{title}</h3>
      <p>{children}</p>
    </motion.article>
  );
}

export default FeatureCard;
