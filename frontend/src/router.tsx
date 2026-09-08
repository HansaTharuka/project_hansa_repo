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
import { Holdings } from './pages/customer/Holdings';

function RootRedirect() {
  const { user, isLoading } = useAuth();
  if (isLoading) {
    return <p>Loading…</p>;
  }
  return <Navigate to={user === null ? '/login' : roleRedirect(user.role)} replace />;
}

function CustomerDashboardStub() {
  return <p>Customer dashboard — built by a later story.</p>;
}

function AdvisorCustomerListStub() {
  return <p>Advisor customer list — built by a later story.</p>;
}

function AdminHomeStub() {
  return <p>Admin console — built by a later story.</p>;
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
              <CustomerDashboardStub />
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
              <AdminHomeStub />
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
