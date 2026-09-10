import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import * as advisorApi from '../../api/advisor';
import type { ManualRecommendationResponse } from '../../api/advisor';
import { ManualRecommendationModal } from './ManualRecommendationModal';

const MANUAL_REC_RESULT: ManualRecommendationResponse = {
  audit_entry_id: 512,
  customer_id: 3,
  advisor_id: 11,
  note: 'Recommended increasing cash weighting ahead of the client Q4 liquidity need.',
  created_at: '2026-09-04T14:10:00Z',
};

describe('ManualRecommendationModal', () => {
  it('renders as a dialog and calls neither callback before submit', () => {
    const onClose = vi.fn();
    const onLogged = vi.fn();
    render(<ManualRecommendationModal customerId={3} onClose={onClose} onLogged={onLogged} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    expect(onLogged).not.toHaveBeenCalled();
  });

  it('shows an inline validation error and does not call the API when note is left blank', async () => {
    const user = userEvent.setup();
    const postSpy = vi.spyOn(advisorApi, 'postManualRecommendation');
    const onClose = vi.fn();
    const onLogged = vi.fn();
    render(<ManualRecommendationModal customerId={3} onClose={onClose} onLogged={onLogged} />);

    await user.click(screen.getByTestId('manual-rec-submit'));

    expect(await screen.findByRole('alert')).toHaveTextContent(/note is required/i);
    expect(postSpy).not.toHaveBeenCalled();
    expect(onLogged).not.toHaveBeenCalled();
  });

  it('posts the note and calls onLogged on a successful submit', async () => {
    const user = userEvent.setup();
    vi.spyOn(advisorApi, 'postManualRecommendation').mockResolvedValue(MANUAL_REC_RESULT);
    const onClose = vi.fn();
    const onLogged = vi.fn();
    render(<ManualRecommendationModal customerId={3} onClose={onClose} onLogged={onLogged} />);

    await user.type(screen.getByTestId('manual-rec-note'), MANUAL_REC_RESULT.note);
    await user.click(screen.getByTestId('manual-rec-submit'));

    expect(advisorApi.postManualRecommendation).toHaveBeenCalledWith(3, MANUAL_REC_RESULT.note);
    await waitFor(() => expect(onLogged).toHaveBeenCalledTimes(1));
  });

  it('closes via the close control without calling onLogged', async () => {
    const user = userEvent.setup();
    const postSpy = vi.spyOn(advisorApi, 'postManualRecommendation');
    const onClose = vi.fn();
    const onLogged = vi.fn();
    render(<ManualRecommendationModal customerId={3} onClose={onClose} onLogged={onLogged} />);

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onLogged).not.toHaveBeenCalled();
    expect(postSpy).not.toHaveBeenCalled();
  });
});
