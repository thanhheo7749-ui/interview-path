import { AnimatePresence, motion } from 'framer-motion';
import { Briefcase, Sparkles, TriangleAlert, WandSparkles } from 'lucide-react';
import { useState } from 'react';

import DemoButton from '../DemoButton.jsx';
import SlideFrame, { fadeUp, stagger } from '../SlideFrame.jsx';
import { polishAnswer } from '../../services/geminiService.js';

function Slide08LiveDemo() {
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    const rawAnswer = answer.trim();
    if (!rawAnswer || loading) return;

    setResult(null);
    setLoading(true);
    const polished = await polishAnswer(rawAnswer);
    setResult(polished);
    setLoading(false);
  }

  return (
    <SlideFrame
      tag="Live Demo"
      tagTone="purple"
      title="See AI In Action"
      subtitle='Try the "Polish & Shadow" feature live. Enter an unstructured answer below.'
    >
      <div className="grid-2 live-demo-grid">
        <motion.div animate="show" className="demo-copy" initial="hidden" variants={stagger}>
          <motion.div variants={fadeUp}>
            <h3>AI Practice Link</h3>
            <p>Candidates receive an automated link to practice before the real interview.</p>
          </motion.div>
          <motion.div variants={fadeUp}>
            <h3>Company-Specific</h3>
            <p>AI generates scenarios based on their CV and company culture.</p>
          </motion.div>
          <motion.div variants={fadeUp}>
            <h3>Constructive Feedback</h3>
            <p>AI improves English grammar, clarity, answer structure, and professional tone.</p>
          </motion.div>
        </motion.div>

        <motion.div
          animate="show"
          className="diagram-container interactive-element demo-panel-wrap"
          data-interactive="true"
          initial="hidden"
          variants={fadeUp}
        >
          <form className="ai-demo-container" onSubmit={handleSubmit}>
            <div className="ai-question-box">
              <Briefcase aria-hidden="true" />
              <div>
                <strong>Role: Backend Engineer</strong>
                <span>Interviewer asks:</span>
                <p>"Tell me about a time you handled deadline pressure."</p>
              </div>
            </div>

            <label className="sr-only" htmlFor="demo-answer">
              Candidate answer
            </label>
            <textarea
              aria-label="Candidate answer"
              className="ai-input"
              id="demo-answer"
              onChange={(event) => setAnswer(event.target.value)}
              placeholder="Type a raw, imperfect answer here... (e.g., 'I try my best and ask friend when I stuck')"
              rows="4"
              value={answer}
            />

            <DemoButton disabled={loading || !answer.trim()} loading={loading} type="submit">
              {loading ? 'AI is polishing...' : 'Polish My Answer'}
            </DemoButton>

            <AnimatePresence>
              {result ? (
                <motion.div
                  animate={{ opacity: 1, y: 0 }}
                  className="ai-result"
                  exit={{ opacity: 0, y: 10 }}
                  initial={{ opacity: 0, y: 14 }}
                  transition={{ duration: 0.32, ease: 'easeOut' }}
                >
                  <div className="ai-feedback">
                    <div className="ai-feedback-title">
                      <TriangleAlert aria-hidden="true" /> Coach Feedback
                    </div>
                    <div>{result.feedback}</div>
                  </div>
                  <div className="ai-polished">
                    <div className="ai-polished-title">
                      <WandSparkles aria-hidden="true" /> Polished Answer (Ready for Shadowing)
                    </div>
                    <div>{result.polishedAnswer}</div>
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>

            {!result && !loading ? (
              <div className="demo-empty-state">
                <Sparkles aria-hidden="true" />
                Write a rough answer, then let the coach structure it.
              </div>
            ) : null}
          </form>
        </motion.div>
      </div>
    </SlideFrame>
  );
}

export default Slide08LiveDemo;
