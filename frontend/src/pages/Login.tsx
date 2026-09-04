/**
 * The shared login screen for all four personas (E2-S3 — BRD §12).
 */
import type { FormEvent } from 'react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { roleRedirect } from '../auth/roleRedirect';
import { ErrorMessage } from '../components/ErrorMessage';
import { LabeledField } from '../components/LabeledField';

export function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const role = await login(email, password);
      navigate(roleRedirect(role), { replace: true });
    } catch (caught) {
      setError(describeLoginError(caught));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main>
      <h2>Sign in</h2>
      <p className="sub">
        Shared entry point for all four personas. Your role determines the landing screen.
      </p>
      <section className="panel">
        {error !== null && <ErrorMessage message={error} />}
        <form onSubmit={(event) => void handleSubmit(event)} noValidate>
          <LabeledField
            id="email"
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            autoComplete="username"
          />
          <LabeledField
            id="password"
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
          />
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  );
}

function describeLoginError(caught: unknown): string {
  if (caught instanceof ApiError) {
    return `${caught.code}: ${caught.message}`;
  }
  return 'Unable to sign in. Please try again.';
}
