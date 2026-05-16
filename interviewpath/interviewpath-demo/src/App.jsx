import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import Sidebar from './components/Sidebar.jsx';
import WorkflowPage from './routes/WorkflowPage.jsx';
import N8nWorkflowPage from './routes/N8nWorkflowPage.jsx';
import KnowledgeGraphPage from './routes/KnowledgeGraphPage.jsx';
import InterviewPage from './routes/InterviewPage.jsx';

function App() {
  const location = useLocation();
  const isInterview = location.pathname.startsWith('/interview');

  if (isInterview) {
    return (
      <Routes>
        <Route path="/interview" element={<InterviewPage />} />
        <Route path="*" element={<Navigate to="/interview" replace />} />
      </Routes>
    );
  }

  return (
    <div className="min-h-[100dvh] bg-slate-100 text-slate-950">
      <Sidebar />
      <main className="ml-64 min-h-[100dvh] overflow-hidden">
        <Routes>
          <Route path="/" element={<Navigate to="/workflow" replace />} />
          <Route path="/workflow" element={<WorkflowPage />} />
          <Route path="/n8n" element={<N8nWorkflowPage />} />
          <Route path="/knowledge-graph" element={<KnowledgeGraphPage />} />
          <Route path="*" element={<Navigate to="/workflow" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
