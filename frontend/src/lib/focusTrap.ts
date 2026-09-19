import type { Action } from 'svelte/action';

const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export interface FocusTrapOptions {
  close?: () => void;
  initialFocus?: string;
}

export const focusTrap: Action<HTMLElement, FocusTrapOptions | undefined> = (node, options = {}) => {
  const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;

  function focusable(): HTMLElement[] {
    return Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE))
      .filter((element) => !element.hidden && element.getAttribute('aria-hidden') !== 'true');
  }

  function focusInitial(): void {
    const requested = options?.initialFocus
      ? node.querySelector<HTMLElement>(options.initialFocus)
      : null;
    (requested ?? focusable()[0] ?? node).focus();
  }

  function keydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && options?.close) {
      event.preventDefault();
      event.stopPropagation();
      options.close();
      return;
    }
    if (event.key !== 'Tab') return;
    const items = focusable();
    if (!items.length) {
      event.preventDefault();
      node.focus();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  node.addEventListener('keydown', keydown);
  queueMicrotask(focusInitial);

  return {
    update(next) {
      options = next ?? {};
    },
    destroy() {
      node.removeEventListener('keydown', keydown);
      if (previouslyFocused?.isConnected) previouslyFocused.focus();
    },
  };
};
