import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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
import TrustPage from './routes/TrustPage.jsx';
import JobEditorPage from './routes/JobEditorPage.jsx';
import JobsPage from './routes/JobsPage.jsx';
import BoardPage from './routes/BoardPage.jsx';
import ChannelsPage from './routes/ChannelsPage.jsx';
import RealityCheckPage from './routes/RealityCheckPage.jsx';
import HiringRequestsPage from './routes/HiringRequestsPage.jsx';
import IntakePage from './routes/IntakePage.jsx';
import InterviewBriefPage from './routes/InterviewBriefPage.jsx';
import MyInterviewsPage from './routes/MyInterviewsPage.jsx';
import JdStudioPage from './routes/JdStudioPage.jsx';
import DemoAiNotice from './components/DemoAiNotice.jsx';
import { useCompany } from './company/CompanyContext.jsx';

// Knowledge base management is for HR. Other members go to the Copilot.
function HrOnly() {
  const { membership } = useCompany();
  return membership?.role === 'hr' ? <Outlet /> : <Navigate to="/copilot" replace />;
}

// Hiring requests are for HR, who open them, and for managers, who answer their own.
function HrOrManager() {
  const { membership } = useCompany();
  return membership?.role === 'hr' || membership?.role === 'manager' ? <Outlet /> : <Navigate to="/copilot" replace />;
}

function ManagerOnly() {
  const { membership } = useCompany();
  return membership?.role === 'manager' ? <Outlet /> : <Navigate to="/hiring-requests" replace />;
}

// A manager sees Korean unless they have chosen a language themselves; the switch stores that choice.
function useDefaultLanguage(role) {
  const { i18n } = useTranslation();
  useEffect(() => {
    if (!role || localStorage.getItem('portal_lang')) return;
    const wanted = role === 'manager' ? 'ko' : 'en';
    if (i18n.language !== wanted) i18n.changeLanguage(wanted);
  }, [role, i18n]);
}

function PortalLayout() {
  const { membership } = useCompany();
  useDefaultLanguage(membership?.role);
  return (
    <div className="min-h-[100dvh] bg-slate-100 text-slate-950">
      <Sidebar />
      <main className="ml-64 min-h-[100dvh]">
        <SampleBanner />
        <DemoAiNotice />
        {/* Keyed by company so no page keeps the previous company's data after a switch. */}
        <Outlet key={membership?.company_id ?? 'none'} />
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
          <Route path="/trust" element={<TrustPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          <Route path="/jobs/new" element={<JobEditorPage />} />
          <Route path="/jobs/:jobId" element={<JobEditorPage />} />
          <Route path="/jobs/:jobId/board" element={<BoardPage />} />
          <Route path="/jobs/:jobId/channels" element={<ChannelsPage />} />
          <Route path="/jobs/:jobId/reality-check" element={<RealityCheckPage />} />
        </Route>
        <Route element={<HrOrManager />}>
          <Route path="/hiring-requests" element={<HiringRequestsPage />} />
          <Route path="/jd-studio/:draftId" element={<JdStudioPage />} />
        </Route>
        <Route element={<ManagerOnly />}>
          <Route path="/intake/:requestId" element={<IntakePage />} />
          <Route path="/my-interviews" element={<MyInterviewsPage />} />
          <Route path="/my-interviews/:appId" element={<InterviewBriefPage />} />
        </Route>
        <Route path="/copilot" element={<CopilotPage />} />
        <Route path="*" element={<Navigate to="/settings" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
