import { motion } from 'framer-motion';

import Tag from './Tag.jsx';

export const fadeUp = {
  hidden: { opacity: 1, y: 0 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.46, ease: 'easeOut' },
  },
};

export const fadeIn = {
  hidden: { opacity: 1 },
  show: {
    opacity: 1,
    transition: { duration: 0.5, ease: 'easeOut' },
  },
};

export const stagger = {
  hidden: {},
  show: {
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.06,
    },
  },
};

function SlideFrame({
  tag,
  tagTone = 'blue',
  title,
  subtitle,
  center = false,
  headerAlign = 'left',
  className = '',
  bodyClassName = '',
  children,
}) {
  const hasHeader = Boolean(tag || title || subtitle);

  return (
    <div className={`slide ${center ? 'slide-center' : ''} ${className}`.trim()}>
      {hasHeader ? (
        <motion.header
          className={`slide-header slide-header-${headerAlign}`}
          initial="hidden"
          animate="show"
          variants={stagger}
        >
          {tag ? (
            <motion.div variants={fadeUp}>
              <Tag tone={tagTone}>{tag}</Tag>
            </motion.div>
          ) : null}
          {title ? (
            <motion.h2 className="slide-title" variants={fadeUp}>
              {title}
            </motion.h2>
          ) : null}
          {subtitle ? (
            <motion.p className="slide-subtitle" variants={fadeUp}>
              {subtitle}
            </motion.p>
          ) : null}
        </motion.header>
      ) : null}
      <div className={`slide-body ${bodyClassName}`.trim()}>{children}</div>
    </div>
  );
}

export default SlideFrame;
