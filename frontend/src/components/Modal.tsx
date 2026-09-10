/**
 * A generic modal/panel (E9-S4 AC5) — `role="dialog"` layered over the
 * calling page via a fixed-position overlay. The caller owns all open/close
 * state; this component never registers a route, so content shown inside it
 * (e.g. the manual-recommendation form) never becomes a standalone screen.
 */
import type { ReactNode } from 'react';

interface ModalProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

export function Modal({ title, onClose, children }: ModalProps) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-header">
          <h3>{title}</h3>
          <button type="button" aria-label="Close" onClick={onClose}>
            &times;
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}
