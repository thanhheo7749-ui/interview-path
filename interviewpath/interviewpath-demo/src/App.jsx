import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import RequireAuth from './auth/RequireAuth.jsx';
import { CompanyProvider } from './company/CompanyContext.jsx';
import SampleBanner from './components/SampleBanner.jsx';
import Sidebar from './components/Sidebar.jsx';
import ChangePasswordPage from './routes/ChangePasswordPage.jsx';
import CompanySettingsPage from './routes/CompanySettingsPage.jsx';
import CopilotPage from './routes/CopilotPage.jsx';
import GraphPage from './routes/GraphPage.jsx';
import LoginPage from './routes/LoginPage.jsx';
import ConflictsPage from './routes/ConflictsPage.jsx';
import DocumentsPage from './routes/DocumentsPage.jsx';
import GapsPage from './routes/GapsPage.jsx';
import ReviewPage from './routes/ReviewPage.jsx';
import JobEditorPage from './routes/JobEditorPage.jsx';
import JobsPage from './routes/JobsPage.jsx';
import DemoAiNotice from './components/DemoAiNotice.jsx';
import { useCompany } from './company/CompanyContext.jsx';

// Knowledge base management is for HR. Other members go to the Copilot.
function HrOnly() {
  const { membership } = useCompany();
  return membership?.role === 'hr' ? <Outlet /> : <Navigate to="/copilot" replace />;
}

function PortalLayout() {
  return (
    <div className="min-h-[100dvh] bg-slate-100 text-slate-950">
      <Sidebar />
      <main className="ml-64 min-h-[100dvh]">
        <SampleBanner />
        <DemoAiNotice />
        <Outlet />
      </main>
    </div>
  );
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <CompanyProvider>
              <PortalLayout />
            </CompanyProvider>
          </RequireAuth>
        }
      >
        <Route path="/settings" element={<CompanySettingsPage />} />
        <Route path="/account/password" element={<ChangePasswordPage />} />
        <Route element={<HrOnly />}>
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/conflicts" element={<ConflictsPage />} />
          <Route path="/gaps" element={<GapsPage />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/jobs/new" element={<JobEditorPage />} />
          <Route path="/jobs/:jobId" element={<JobEditorPage />} />
        </Route>
        <Route path="/copilot" element={<CopilotPage />} />
        <Route path="*" element={<Navigate to="/settings" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
