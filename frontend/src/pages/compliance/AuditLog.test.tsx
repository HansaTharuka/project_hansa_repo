import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as auditApi from '../../api/audit';
import type { AuditPageResponse } from '../../api/audit';
import { AuditLog } from './AuditLog';

const SAMPLE_PAGE: AuditPageResponse = {
  total: 3,
  limit: 50,
  offset: 0,
  entries: [
    {
      id: 411,
      entity_type: 'RiskBandAssignment',
      entity_id: '12',
      actor_id: 3,
      actor_role: 'customer',
      action: 'ASSIGN_RISK_BAND',
      timestamp: '2026-09-01T10:15:39Z',
      details_json: { customer_id: 3, risk_band: 'MODERATE', rule_version: 1 },
    },
    {
      id: 412,
      entity_type: 'RiskBandRule',
      entity_id: '2',
      actor_id: 13,
      actor_role: 'admin',
      action: 'PUBLISH_RISK_BAND_RULE',
      timestamp: '2026-09-02T11:48:55Z',
      details_json: { version: 2, question_count: 7 },
    },
    {
      id: 413,
      entity_type: 'RiskBandAssignment',
      entity_id: '13',
      actor_id: 7,
      actor_role: 'customer',
      action: 'ASSIGN_RISK_BAND',
      timestamp: '2026-09-03T16:22:47Z',
      details_json: { customer_id: 7, risk_band: 'AGGRESSIVE', rule_version: 1 },
    },
  ],
};

const FILTERED_PAGE: AuditPageResponse = {
  total: 2,
  limit: 50,
  offset: 0,
  entries: SAMPLE_PAGE.entries.filter((entry) => entry.entity_type === 'RiskBandAssignment'),
};

describe('AuditLog', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows a table with a row per entry and columns for actor, entity_type, action, timestamp', async () => {
    vi.spyOn(auditApi, 'getAuditEntries').mockResolvedValue(SAMPLE_PAGE);
    render(<AuditLog />);

    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(4)); // header + 3

    expect(screen.getByRole('columnheader', { name: 'actor_id' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'actor_role' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /entity_type/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /action/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /timestamp/i })).toBeInTheDocument();
  });

  it('selecting an entity_type filter and applying it re-queries the API with entity_type set', async () => {
    const spy = vi
      .spyOn(auditApi, 'getAuditEntries')
      .mockResolvedValueOnce(SAMPLE_PAGE)
      .mockResolvedValueOnce(FILTERED_PAGE);
    const user = userEvent.setup();
    render(<AuditLog />);
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(4));

    await user.selectOptions(screen.getByLabelText(/entity_type/i), 'RiskBandAssignment');
    await user.click(screen.getByRole('button', { name: /apply/i }));

    await waitFor(() => expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({ entity_type: 'RiskBandAssignment', offset: 0 }),
    ));
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows).toHaveLength(2);
    rows.forEach((row) => {
      expect(within(row).getByText('RiskBandAssignment')).toBeInTheDocument();
    });
  });

  it('filling from/to date inputs and applying issues a request with both bounds', async () => {
    const spy = vi.spyOn(auditApi, 'getAuditEntries').mockResolvedValue(SAMPLE_PAGE);
    const user = userEvent.setup();
    render(<AuditLog />);
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(4));

    await user.type(screen.getByLabelText(/^from/i), '2026-09-01');
    await user.type(screen.getByLabelText(/^to/i), '2026-09-03');
    await user.click(screen.getByRole('button', { name: /apply/i }));

    await waitFor(() =>
      expect(spy).toHaveBeenLastCalledWith(
        expect.objectContaining({ from: '2026-09-01', to: '2026-09-03' }),
      ),
    );
    // a fixture entry dated exactly on the "to" boundary day is still rendered
    expect(screen.getByText('413')).toBeInTheDocument();
  });

  it('renders no edit/delete/update/resolve control anywhere — only Apply, Clear and pagination', async () => {
    vi.spyOn(auditApi, 'getAuditEntries').mockResolvedValue(SAMPLE_PAGE);
    render(<AuditLog />);
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(4));

    const buttons = screen.getAllByRole('button').map((button) => button.textContent?.trim());
    buttons.forEach((label) => {
      expect(label).toMatch(/^(Apply|Clear|Previous|Next)$/i);
    });
  });

  it('every filter input is labeled and Enter inside a filter input submits the filter form', async () => {
    const spy = vi.spyOn(auditApi, 'getAuditEntries').mockResolvedValue(SAMPLE_PAGE);
    const user = userEvent.setup();
    render(<AuditLog />);
    await waitFor(() => expect(screen.getAllByRole('row')).toHaveLength(4));

    const actorInput = screen.getByLabelText(/actor_id/i);
    expect(actorInput).toHaveAttribute('id', 'actor_id');
    expect(screen.getByLabelText(/entity_type/i)).toHaveAttribute('id', 'entity_type');
    expect(screen.getByLabelText(/^from/i)).toHaveAttribute('id', 'from');
    expect(screen.getByLabelText(/^to/i)).toHaveAttribute('id', 'to');

    const toInput = screen.getByLabelText(/^to/i);
    await user.click(toInput);
    await user.keyboard('{Enter}');

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
  });
});
