/**
 * Risk-band result screen (E4-S4 AC2; api-contracts.md §6.2). Reads the
 * `POST /api/risk-profile/submit` response passed in via `navigate(...,
 * { state })` from `Questionnaire.tsx` — there is no separate global store
 * for this short-lived, single-navigation-hop value.
 */
import { Link, useLocation } from 'react-router-dom';

import type { RiskBandAssignmentResponse } from '../../api/riskProfile';
import { formatRiskBand } from '../../api/riskProfile';

function isRiskBandAssignmentResponse(value: unknown): value is RiskBandAssignmentResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    'risk_band' in value &&
    'assignment_id' in value &&
    'rule_version' in value &&
    'assigned_at' in value
  );
}

export function RiskResult() {
  const location = useLocation();
  const result = isRiskBandAssignmentResponse(location.state) ? location.state : null;

  if (result === null) {
    return (
      <main>
        <h2>Your risk band</h2>
        <p className="sub">
          No questionnaire result to display yet.{' '}
          <Link to="/customer/questionnaire">Take the risk-profile questionnaire</Link>.
        </p>
      </main>
    );
  }

  return (
    <main className="risk-result-page">
      <h2>Your risk band</h2>
      <p className="sub">Deterministic result of the rule-based scoring engine.</p>
      <section className="panel">
        <p className="band">{formatRiskBand(result.risk_band)}</p>
        <p className="band-raw">
          <code>risk_band: {result.risk_band}</code>
        </p>
        <dl className="summary">
          <div>
            <dt>assignment_id</dt>
            <dd>{result.assignment_id}</dd>
          </div>
          <div>
            <dt>rule_version</dt>
            <dd>{result.rule_version}</dd>
          </div>
          <div>
            <dt>assigned_at</dt>
            <dd>{result.assigned_at}</dd>
          </div>
        </dl>
        <p style={{ marginTop: 18 }}>
          <Link to="/customer/questionnaire">Retake questionnaire</Link>
        </p>
      </section>
    </main>
  );
}
