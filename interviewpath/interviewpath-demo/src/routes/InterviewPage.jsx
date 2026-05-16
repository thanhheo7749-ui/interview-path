import { Lock, Mail, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import InterviewRoom from '../components/InterviewRoom.jsx';
import { demoLogin } from '../data/mockInterview.js';

function InterviewPage() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [email, setEmail] = useState(demoLogin.email);
  const [password, setPassword] = useState(demoLogin.password);
  const [error, setError] = useState('');

  function handleSubmit(event) {
    event.preventDefault();
    if (email === demoLogin.email && password === demoLogin.password) {
      setLoggedIn(true);
      setError('');
      return;
    }
    setError('Use candidate@demo.com and demo123 for this demo.');
  }

  if (loggedIn) return <InterviewRoom />;

  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-slate-950 p-6">
      <div className="grid w-full max-w-5xl grid-cols-[1.05fr_0.95fr] overflow-hidden rounded-[2rem] bg-white shadow-panel">
        <section className="bg-blue-600 p-10 text-white">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15">
            <ShieldCheck size={25} />
          </div>
          <h1 className="mt-10 text-4xl font-extrabold tracking-tight">InterviewPath Candidate Practice</h1>
          <p className="mt-4 max-w-md text-base font-medium leading-7 text-blue-50">
            Practise AI interviews grounded in company knowledge, your CV, and the job description before meeting HR.
          </p>
          <div className="mt-10 rounded-3xl bg-white/12 p-5">
            <p className="text-sm font-extrabold">Demo login</p>
            <p className="mt-2 text-sm font-semibold text-blue-50">Email: candidate@demo.com</p>
            <p className="mt-1 text-sm font-semibold text-blue-50">Password: demo123</p>
          </div>
        </section>

        <form onSubmit={handleSubmit} className="flex flex-col justify-center p-10">
          <p className="text-xs font-extrabold uppercase tracking-[0.2em] text-blue-600">Secure demo access</p>
          <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-950">Enter interview room</h2>
          <p className="mt-2 text-sm font-medium leading-6 text-slate-600">No real account is created. This route uses local state only.</p>

          <label className="mt-8 text-sm font-bold text-slate-700" htmlFor="email">
            Email
          </label>
          <div className="mt-2 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-100">
            <Mail size={18} className="text-slate-400" />
            <input
              id="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full bg-transparent text-base font-semibold outline-none"
              type="email"
            />
          </div>

          <label className="mt-5 text-sm font-bold text-slate-700" htmlFor="password">
            Password
          </label>
          <div className="mt-2 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 focus-within:border-blue-400 focus-within:ring-4 focus-within:ring-blue-100">
            <Lock size={18} className="text-slate-400" />
            <input
              id="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full bg-transparent text-base font-semibold outline-none"
              type="password"
            />
          </div>

          {error ? <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700">{error}</p> : null}

          <button type="submit" className="mt-7 rounded-2xl bg-slate-950 px-5 py-4 text-base font-extrabold text-white transition hover:bg-slate-800">
            Start AI Practice Interview
          </button>
        </form>
      </div>
    </div>
  );
}

export default InterviewPage;
