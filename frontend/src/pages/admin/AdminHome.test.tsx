import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { AdminHome } from './AdminHome';

describe('AdminHome', () => {
  it('links to the allocation template editor, rule editor, asset-class master, and threshold editor', () => {
    render(
      <MemoryRouter>
        <AdminHome />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: /allocation template/i })).toHaveAttribute(
      'href',
      '/admin/templates',
    );
    expect(screen.getByRole('link', { name: /risk-band rule/i })).toHaveAttribute('href', '/admin/rules');
    expect(screen.getByRole('link', { name: /asset-class/i })).toHaveAttribute(
      'href',
      '/admin/asset-classes',
    );
    expect(screen.getByRole('link', { name: /rebalancing threshold/i })).toHaveAttribute(
      'href',
      '/admin/threshold',
    );
  });
});
