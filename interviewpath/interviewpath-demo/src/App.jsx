import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import RequireAuth from './auth/RequireAuth.jsx';
import { CompanyProvider } from './company/CompanyContext.jsx';
import SampleBanner from './components/SampleBanner.jsx';
import Sidebar from './components/Sidebar.jsx';
import CompanySettingsPage from './routes/CompanySettingsPage.jsx';
import LoginPage from './routes/LoginPage.jsx';

function PortalLayout() {
  return (
    <div className="min-h-[100dvh] bg-slate-100 text-slate-950">
      <Sidebar />
      <main className="ml-64 min-h-[100dvh]">
        <SampleBanner />
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
        <Route path="*" element={<Navigate to="/settings" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
