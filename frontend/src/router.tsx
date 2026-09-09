/**
 * Route table (E2-S3). Every landing route beyond `/login` is a stub until
 * its owning epic's UI story replaces it (component-map.md note 5) — a fully
 * featured screen is out of scope for this group's contract.
 */
import { Navigate, Route, Routes } from 'react-router-dom';

import { ProtectedRoute } from './auth/ProtectedRoute';
import { useAuth } from './auth/AuthContext';
import { roleRedirect } from './auth/roleRedirect';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { AuditLog } from './pages/compliance/AuditLog';
import { AdminHome } from './pages/admin/AdminHome';
import { AssetClasses } from './pages/admin/AssetClasses';
import { RuleEditor } from './pages/admin/RuleEditor';
import { TemplateEditor } from './pages/admin/TemplateEditor';
import { ThresholdEditor } from './pages/admin/ThresholdEditor';
import { Dashboard } from './pages/customer/Dashboard';
import { Goals } from './pages/customer/Goals';
import { Holdings } from './pages/customer/Holdings';
import { Questionnaire } from './pages/customer/Questionnaire';
import { Rebalancing } from './pages/customer/Rebalancing';
import { RiskResult } from './pages/customer/RiskResult';

function RootRedirect() {
  const { user, isLoading } = useAuth();
  if (isLoading) {
    return <p>Loading…</p>;
  }
  return <Navigate to={user === null ? '/login' : roleRedirect(user.role)} replace />;
}

function AdvisorCustomerListStub() {
  return <p>Advisor customer list — built by a later story.</p>;
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<RootRedirect />} />
      <Route
        path="/customer/dashboard"
        element={
          <ProtectedRoute allowedRoles={['customer']}>
            <Layout>
              <Dashboard />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/customer/questionnaire"
        element={
          <ProtectedRoute allowedRoles={['customer']}>
            <Layout>
              <Questionnaire />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/customer/risk-result"
        element={
          <ProtectedRoute allowedRoles={['customer']}>
            <Layout>
              <RiskResult />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/customer/goals"
        element={
          <ProtectedRoute allowedRoles={['customer']}>
            <Layout>
              <Goals />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/customer/holdings"
        element={
          <ProtectedRoute allowedRoles={['customer']}>
            <Layout>
              <Holdings />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/customer/rebalancing"
        element={
          <ProtectedRoute allowedRoles={['customer']}>
            <Layout>
              <Rebalancing />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/advisor/customers"
        element={
          <ProtectedRoute allowedRoles={['advisor']}>
            <Layout>
              <AdvisorCustomerListStub />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute allowedRoles={['admin']}>
            <Layout>
              <AdminHome />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/templates"
        element={
          <ProtectedRoute allowedRoles={['admin']}>
            <Layout>
              <TemplateEditor />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/rules"
        element={
          <ProtectedRoute allowedRoles={['admin']}>
            <Layout>
              <RuleEditor />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/asset-classes"
        element={
          <ProtectedRoute allowedRoles={['admin']}>
            <Layout>
              <AssetClasses />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/threshold"
        element={
          <ProtectedRoute allowedRoles={['admin']}>
            <Layout>
              <ThresholdEditor />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/compliance/audit-log"
        element={
          <ProtectedRoute allowedRoles={['compliance']}>
            <Layout>
              <AuditLog />
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
