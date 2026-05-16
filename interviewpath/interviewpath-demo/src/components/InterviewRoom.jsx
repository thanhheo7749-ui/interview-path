import { ArrowRight, Bot, CheckCircle2, ClipboardCheck, Send, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { interviewQuestions, simulatedFeedback } from '../data/mockInterview.js';
import CameraPreview from './CameraPreview.jsx';

function ScorePill({ label, value, tone }) {
  const tones = {
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-emerald-50 text-emerald-700',
    purple: 'bg-violet-50 text-violet-700',
    slate: 'bg-slate-100 text-slate-700',
  };

  return (
    <div className={`rounded-2xl px-4 py-3 ${tones[tone]}`}>
      <p className="text-xs font-bold uppercase tracking-[0.14em] opacity-80">{label}</p>
      <p className="mt-1 text-2xl font-extrabold">{value}%</p>
    </div>
  );
}

function InterviewRoom() {
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [feedback, setFeedback] = useState(null);
  const [completed, setCompleted] = useState(false);
  const [reportSent, setReportSent] = useState(false);
  const progress = completed ? 100 : Math.round(((questionIndex + (feedback ? 0.65 : 0.2)) / interviewQuestions.length) * 100);

  function submitAnswer() {
    if (!answer.trim()) return;
    setFeedback(simulatedFeedback);
  }

  function nextQuestion() {
    if (questionIndex === interviewQuestions.length - 1) {
      setCompleted(true);
      return;
    }
    setQuestionIndex((current) => current + 1);
    setAnswer('');
    setFeedback(null);
  }

  return (
    <div className="min-h-[100dvh] bg-slate-100 p-6">
      <header className="mb-5 flex items-center justify-between rounded-3xl border border-slate-200 bg-white px-6 py-4 shadow-card">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-[0.2em] text-blue-600">Candidate Interview Room</p>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-950">AI practice based on company memory</h1>
        </div>
        <div className="min-w-[280px]">
          <div className="mb-2 flex items-center justify-between text-xs font-extrabold uppercase tracking-[0.16em] text-slate-500">
            <span>Interview progress</span>
            <span>{progress}%</span>
          </div>
          <div className="h-2 rounded-full bg-slate-100">
            <div className="h-2 rounded-full bg-emerald-500 transition-all" style={{ width: `${progress}%` }} />
          </div>
        </div>
      </header>

      <div className="grid min-h-[calc(100dvh-132px)] grid-cols-[0.95fr_1.2fr_0.85fr] gap-5">
        <CameraPreview />

        <main className="flex flex-col rounded-3xl border border-slate-200 bg-white p-5 shadow-card">
          <div className="flex items-start gap-3 rounded-2xl bg-slate-950 p-4 text-white">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-500">
              <Bot size={20} />
            </div>
            <div>
              <p className="text-sm font-extrabold">AI Interviewer</p>
              <p className="mt-1 text-sm leading-6 text-slate-200">
                {completed ? 'Your practice interview is complete.' : interviewQuestions[questionIndex]}
              </p>
            </div>
          </div>

          {completed ? (
            <section className="mt-5 flex flex-1 flex-col justify-center">
              <div className="rounded-3xl bg-slate-50 p-6">
                <p className="text-sm font-extrabold uppercase tracking-[0.18em] text-violet-600">Interview Summary</p>
                <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-950">Ready for the next hiring step</h2>
                <div className="mt-6 grid grid-cols-2 gap-3">
                  <ScorePill label="English clarity" value={78} tone="purple" />
                  <ScorePill label="Technical relevance" value={84} tone="blue" />
                  <ScorePill label="Culture fit" value={81} tone="green" />
                  <ScorePill label="Overall readiness" value={82} tone="slate" />
                </div>
                <div className="mt-6 rounded-2xl bg-emerald-50 p-4">
                  <p className="text-sm font-extrabold text-emerald-800">Recommended next step</p>
                  <p className="mt-1 text-lg font-extrabold text-emerald-950">Proceed to technical round.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setReportSent(true)}
                  className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-950 px-5 py-4 text-sm font-extrabold text-white transition hover:bg-slate-800"
                >
                  <ClipboardCheck size={18} />
                  {reportSent ? 'Feedback Report Sent to HR' : 'Send Feedback Report to HR'}
                </button>
                {reportSent ? (
                  <div className="mt-4 rounded-2xl border border-blue-100 bg-blue-50 p-4">
                    <p className="text-sm font-extrabold text-blue-900">HR workspace updated</p>
                    <p className="mt-1 text-sm font-semibold leading-6 text-blue-800">
                      The Candidate Passport now contains readiness scores, answer feedback, and the recommended next step.
                    </p>
                  </div>
                ) : null}
              </div>
            </section>
          ) : (
            <>
              <div className="mt-5">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-sm font-extrabold text-slate-950">
                    Question {questionIndex + 1} of {interviewQuestions.length}
                  </p>
                  <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">Simulated AI</span>
                </div>
                <div className="mb-3 grid grid-cols-3 gap-2">
                  {interviewQuestions.map((question, index) => (
                    <div
                      key={question}
                      className={[
                        'rounded-xl px-3 py-2 text-xs font-extrabold',
                        index < questionIndex || (index === questionIndex && feedback)
                          ? 'bg-emerald-50 text-emerald-700'
                          : index === questionIndex
                            ? 'bg-blue-50 text-blue-700'
                            : 'bg-slate-100 text-slate-500',
                      ].join(' ')}
                    >
                      Q{index + 1} {index < questionIndex || (index === questionIndex && feedback) ? 'scored' : index === questionIndex ? 'live' : 'queued'}
                    </div>
                  ))}
                </div>
                <textarea
                  value={answer}
                  onChange={(event) => setAnswer(event.target.value)}
                  rows={7}
                  placeholder="Type your answer here..."
                  className="w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 p-4 text-base font-medium leading-7 outline-none transition focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-100"
                />
                <button
                  type="button"
                  onClick={submitAnswer}
                  className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-extrabold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={!answer.trim()}
                >
                  <Send size={17} />
                  Submit Answer
                </button>
              </div>

              <div className="thin-scrollbar mt-5 flex-1 overflow-y-auto">
                {feedback ? (
                  <div className="space-y-3">
                    <FeedbackBlock title="Grammar feedback" text={feedback.grammar} />
                    <FeedbackBlock title="STAR method feedback" text={feedback.star} />
                    <FeedbackBlock title="Culture-fit feedback" text={feedback.culture} />
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
                      <p className="flex items-center gap-2 text-sm font-extrabold text-emerald-800">
                        <Sparkles size={17} />
                        Polished answer
                      </p>
                      <p className="mt-2 text-sm font-semibold leading-6 text-emerald-950">{feedback.polished}</p>
                    </div>
                    <button
                      type="button"
                      onClick={nextQuestion}
                      className="flex items-center justify-center gap-2 rounded-xl bg-slate-950 px-5 py-3 text-sm font-extrabold text-white transition hover:bg-slate-800"
                    >
                      Next Question
                      <ArrowRight size={17} />
                    </button>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
                    <p className="text-sm font-bold text-slate-500">Feedback will appear after you submit an answer.</p>
                  </div>
                )}
              </div>
            </>
          )}
        </main>

        <aside className="rounded-3xl border border-slate-200 bg-white p-5 shadow-card">
          <p className="text-sm font-extrabold text-slate-950">Candidate Passport / JD Context</p>
          <div className="mt-4 rounded-2xl bg-violet-50 p-4">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-violet-600">Target role</p>
            <p className="mt-1 text-lg font-extrabold text-violet-950">Backend Engineer</p>
          </div>
          <div className="mt-4 space-y-3">
            {['Spring Boot API design', 'Deadline communication', 'Korean team collaboration', 'English status reporting'].map((item) => (
              <div key={item} className="flex gap-3 rounded-2xl bg-slate-50 p-3">
                <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-600" />
                <p className="text-sm font-semibold leading-6 text-slate-700">{item}</p>
              </div>
            ))}
          </div>
          <div className="mt-5 rounded-2xl bg-slate-950 p-4 text-white">
            <p className="text-sm font-extrabold">Company hiring brain</p>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Questions are simulated from company culture, job description, CV signals, and interview rubrics.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}

function FeedbackBlock({ title, text }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-extrabold text-slate-950">{title}</p>
      <p className="mt-1 text-sm font-medium leading-6 text-slate-600">{text}</p>
    </div>
  );
}

export default InterviewRoom;
