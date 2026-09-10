/**
 * Goals CRUD (E7-S4; api-contracts.md §9.1-§9.3). `target_amount` and
 * `percent_complete` are fixed-point decimal strings — forwarded/rendered
 * verbatim by callers, never round-tripped through a JS `number` for
 * storage or display (NFR-01).
 */
import { apiRequest } from './client';

export interface GoalResponse {
  id: number;
  customer_id: number;
  /** Money, 2 decimals, verbatim from the API. */
  target_amount: string;
  /** YYYY-MM-DD. */
  target_date: string;
  priority: number;
  created_at: string;
  updated_at: string;
  /** Percent, 2 decimals, verbatim from the API; `null` until the first
   * `GoalProgressSnapshot` exists. */
  percent_complete: string | null;
}

export interface GoalCreateRequest {
  target_amount: string;
  target_date: string;
  priority: number;
}

export interface GoalUpdateRequest {
  target_amount?: string;
  target_date?: string;
  priority?: number;
}

export function getGoals(): Promise<GoalResponse[]> {
  return apiRequest<GoalResponse[]>('/api/goals');
}

export function createGoal(body: GoalCreateRequest): Promise<GoalResponse> {
  return apiRequest<GoalResponse>('/api/goals', { method: 'POST', body });
}

export function updateGoal(goalId: number, body: GoalUpdateRequest): Promise<GoalResponse> {
  return apiRequest<GoalResponse>(`/api/goals/${goalId}`, { method: 'PATCH', body });
}
