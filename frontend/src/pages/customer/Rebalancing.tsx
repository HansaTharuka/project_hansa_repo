/**
 * Customer rebalancing recommendations — list, accept, dismiss (E8-S4
 * AC1-AC5; BRD §12; api-contracts.md §10.1-10.3).
 *
 * Every money/percent/quantity value is rendered verbatim from the API's
 * fixed-point string representation — never round-tripped through a JS
 * `number` (NFR-01), same convention as Holdings.tsx.
 *
 * Accept/Dismiss double-submit guard: in-flight state is tracked per
 * recommendation_id in a `useRef` map, checked and updated synchronously at
 * the top of `handleResolve` before any `await`. A `useState` mirror of that
 * map drives the `disabled` attribute on the buttons. The ref (not the
 * state) is the source of truth for the guard so two clicks fired in the
 * same tick — before React has re-rendered the disabled button — cannot
 * both pass the check and issue two network requests; the state copy exists
 * only to trigger a re-render for the visual/DOM disabled attribute.
 */
import { useEffect, useRef, useState } from 'react';

import { ApiError } from '../../api/client';
import type { ProposedAction, RebalancingRecommendation } from '../../api/rebalancing';
import {
  acceptRebalancingRecommendation,
  dismissRebalancingRecommendation,
  getRebalancingRecommendations,
} from '../../api/rebalancing';
import { EmptyState } from '../../components/EmptyState';
import { ErrorMessage } from '../../components/ErrorMessage';

type ResolveAction = 'accept' | 'dismiss';

function resolveActionLabel(action: ResolveAction, inFlight: boolean): string {
  if (!inFlight) {
    return action === 'accept' ? 'Accept' : 'Dismiss';
  }
  return action === 'accept' ? 'Accepting…' : 'Dismissing…';
}

export function Rebalancing() {
  const [recommendations, setRecommendations] = useState<RebalancingRecommendation[] | null>(
    null
  );
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [resolvingMap, setResolvingMap] = useState<ReadonlyMap<string, ResolveAction>>(new Map());
  const resolvingRef = useRef<Map<string, ResolveAction>>(new Map());

  useEffect(() => {
    let cancelled = false;
    getRebalancingRecommendations()
      .then((result) => {
        if (!cancelled) {
          setRecommendations(result);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError('Rebalancing recommendations could not be loaded. Please try again.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleResolve(recommendationId: string, action: ResolveAction): void {
    if (resolvingRef.current.has(recommendationId)) {
      return; // already in flight for this row — guard against double-submit
    }
    resolvingRef.current.set(recommendationId, action);
    setResolvingMap(new Map(resolvingRef.current));
    setActionError(null);

    const call = action === 'accept' ? acceptRebalancingRecommendation : dismissRebalancingRecommendation;
    call(recommendationId)
      .then(() => {
        setRecommendations((prev) =>
          prev === null ? prev : prev.filter((rec) => rec.recommendation_id !== recommendationId)
        );
      })
      .catch((error: unknown) => {
        const message =
          error instanceof ApiError
            ? error.message
            : `Could not ${action} this recommendation. Please try again.`;
        setActionError(message);
      })
      .finally(() => {
        resolvingRef.current.delete(recommendationId);
        setResolvingMap(new Map(resolvingRef.current));
      });
  }

  if (loadError !== null) {
    return (
      <main>
        <h2>Rebalancing recommendations</h2>
        <ErrorMessage message={loadError} />
      </main>
    );
  }

  if (recommendations === null) {
    return (
      <main>
        <h2>Rebalancing recommendations</h2>
        <p className="sub">Loading…</p>
      </main>
    );
  }

  return (
    <main className="rebalancing-page">
      <h2>Rebalancing recommendations</h2>
      <p className="sub">
        Generated when a holding drifts beyond your rebalancing threshold. Accepting or dismissing
        is a record of intent only.
      </p>

      {actionError !== null && <ErrorMessage message={actionError} />}

      {recommendations.length === 0 ? (
        <EmptyState
          message="No pending rebalancing recommendations."
          hint="A new recommendation appears here the next time a holding drifts beyond your threshold."
        />
      ) : (
        <div className="recommendations">
          {recommendations.map((recommendation) => {
            const pendingAction = resolvingMap.get(recommendation.recommendation_id) ?? null;
            return (
              <RecommendationCard
                key={recommendation.recommendation_id}
                recommendation={recommendation}
                pendingAction={pendingAction}
                onAccept={() => handleResolve(recommendation.recommendation_id, 'accept')}
                onDismiss={() => handleResolve(recommendation.recommendation_id, 'dismiss')}
              />
            );
          })}
        </div>
      )}
    </main>
  );
}

interface RecommendationCardProps {
  recommendation: RebalancingRecommendation;
  pendingAction: ResolveAction | null;
  onAccept: () => void;
  onDismiss: () => void;
}

function RecommendationCard({
  recommendation,
  pendingAction,
  onAccept,
  onDismiss,
}: RecommendationCardProps) {
  const isResolving = pendingAction !== null;

  return (
    <article className="rec" data-testid="recommendation">
      <header>
        <h4>{recommendation.recommendation_id}</h4>
        <span className="meta">generated_at {recommendation.generated_at}</span>
      </header>

      <table>
        <thead>
          <tr>
            <th scope="col">asset_class_code</th>
            <th scope="col">action</th>
            <th scope="col" className="num">
              amount
            </th>
            <th scope="col" className="num">
              units
            </th>
            <th scope="col" className="num">
              drift_percent
            </th>
          </tr>
        </thead>
        <tbody>
          {recommendation.proposed_actions.map((proposedAction) => (
            <ProposedActionRow key={proposedAction.asset_class_id} action={proposedAction} />
          ))}
        </tbody>
      </table>

      <div className="actions">
        <button
          type="button"
          data-testid="recommendation-accept"
          disabled={isResolving}
          onClick={onAccept}
        >
          {resolveActionLabel('accept', pendingAction === 'accept')}
        </button>
        <button
          type="button"
          className="secondary"
          data-testid="recommendation-dismiss"
          disabled={isResolving}
          onClick={onDismiss}
        >
          {resolveActionLabel('dismiss', pendingAction === 'dismiss')}
        </button>
      </div>
    </article>
  );
}

function ProposedActionRow({ action }: { action: ProposedAction }) {
  return (
    <tr>
      <td>{action.asset_class_code}</td>
      <td>
        <span className={`action ${action.action}`}>{action.action}</span>
      </td>
      <td className="num">{action.amount}</td>
      <td className="num">{action.units}</td>
      <td className="num">{action.drift_percent}</td>
    </tr>
  );
}
