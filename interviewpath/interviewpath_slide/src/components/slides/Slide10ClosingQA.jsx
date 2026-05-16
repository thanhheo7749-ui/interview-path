import { AnimatePresence, motion } from 'framer-motion';
import { useState } from 'react';

import DemoButton from '../DemoButton.jsx';
import SlideFrame, { fadeUp, stagger } from '../SlideFrame.jsx';
import { answerJudgeQuestion } from '../../services/geminiService.js';

function Slide10ClosingQA() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    const rawQuestion = question.trim();
    if (!rawQuestion || loading) return;

    setAnswer('');
    setLoading(true);
    const qaAnswer = await answerJudgeQuestion(rawQuestion);
    setAnswer(qaAnswer);
    setLoading(false);
  }

  return (
    <SlideFrame center className="closing-slide">
      <motion.div animate="show" className="closing-lockup" initial="hidden" variants={stagger}>
        <motion.h1 className="title-main" variants={fadeUp}>
          InterviewPath
        </motion.h1>
        <motion.p className="closing-primary" variants={fadeUp}>
          The AI Talent Memory Platform.
        </motion.p>
        <motion.p className="closing-secondary" variants={fadeUp}>
          Turn every application into a living Candidate Digital Twin.
        </motion.p>
      </motion.div>

      <motion.form
        animate="show"
        className="qa-container interactive-element"
        data-interactive="true"
        initial="hidden"
        onSubmit={handleSubmit}
        variants={fadeUp}
      >
        <label className="qa-label" htmlFor="judge-question">
          Judge Q&A Session
        </label>
        <div className="qa-input-wrapper">
          <input
            aria-label="Judge question"
            className="qa-input"
            id="judge-question"
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask the AI Co-founder a question about our business..."
            type="text"
            value={question}
          />
          <DemoButton className="qa-btn" disabled={loading || !question.trim()} loading={loading} type="submit">
            {loading ? 'Thinking...' : 'Ask AI'}
          </DemoButton>
        </div>

        <AnimatePresence>
          {answer ? (
            <motion.div
              animate={{ opacity: 1, y: 0 }}
              className="qa-result-box"
              exit={{ opacity: 0, y: 10 }}
              initial={{ opacity: 0, y: 12 }}
              transition={{ duration: 0.32, ease: 'easeOut' }}
            >
              {answer}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </motion.form>
    </SlideFrame>
  );
}

export default Slide10ClosingQA;
