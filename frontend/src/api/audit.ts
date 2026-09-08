/**
 * GET /api/audit — compliance-role-only, filterable, paginated audit trail
 * (E3-S4; api-contracts.md §13.1).
 */
import type { AuditAction, AuditDetailValue, AuditEntityType, Role } from '../types/entities';
import { apiRequest } from './client';

export interface AuditEntryResponse {
  id: number;
  entity_type: AuditEntityType;
  entity_id: string;
  actor_id: number;
  actor_role: Role;
  action: AuditAction;
  timestamp: string;
  details_json: Record<string, AuditDetailValue>;
}

export interface AuditPageResponse {
  total: number;
  limit: number;
  offset: number;
  entries: AuditEntryResponse[];
}

export interface AuditQuery {
  actor_id?: number;
  entity_type?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}

/** GET /api/audit?... — omits any filter that is `undefined` or an empty
 * string, so an untouched filter never narrows the server-side query. */
export function getAuditEntries(query: AuditQuery = {}): Promise<AuditPageResponse> {
  const params = new URLSearchParams();
  if (query.actor_id !== undefined) {
    params.set('actor_id', String(query.actor_id));
  }
  if (query.entity_type !== undefined && query.entity_type !== '') {
    params.set('entity_type', query.entity_type);
  }
  if (query.from !== undefined && query.from !== '') {
    params.set('from', query.from);
  }
  if (query.to !== undefined && query.to !== '') {
    params.set('to', query.to);
  }
  if (query.limit !== undefined) {
    params.set('limit', String(query.limit));
  }
  if (query.offset !== undefined) {
    params.set('offset', String(query.offset));
  }
  const queryString = params.toString();
  const path = queryString.length > 0 ? `/api/audit?${queryString}` : '/api/audit';
  return apiRequest<AuditPageResponse>(path);
}
