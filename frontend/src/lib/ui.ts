import { writable } from 'svelte/store';

export type ToastTone = 'info' | 'success' | 'warning' | 'error';

export interface ToastAction {
  label: string;
  run: () => void | Promise<void>;
}

export interface ToastMessage {
  id: string;
  title: string;
  message?: string;
  tone: ToastTone;
  progress?: number;
  persistent?: boolean;
  action?: ToastAction;
  createdAt: number;
}

export interface ToastInput extends Omit<ToastMessage, 'id' | 'createdAt' | 'tone'> {
  id?: string;
  tone?: ToastTone;
  timeout?: number;
}

const toastStore = writable<ToastMessage[]>([]);
const toastTimers = new Map<string, ReturnType<typeof setTimeout>>();
let toastSequence = 0;

export const toasts = {
  subscribe: toastStore.subscribe,
};

function clearToastTimer(id: string): void {
  const timer = toastTimers.get(id);
  if (timer) clearTimeout(timer);
  toastTimers.delete(id);
}

export function dismissToast(id: string): void {
  clearToastTimer(id);
  toastStore.update((messages) => messages.filter((message) => message.id !== id));
}

export function showToast(input: ToastInput): string {
  const id = input.id ?? `toast-${Date.now()}-${++toastSequence}`;
  clearToastTimer(id);
  const message: ToastMessage = {
    id,
    title: input.title,
    message: input.message,
    tone: input.tone ?? 'info',
    progress: input.progress,
    persistent: input.persistent,
    action: input.action,
    createdAt: Date.now(),
  };
  toastStore.update((messages) => [...messages.filter((item) => item.id !== id), message].slice(-6));
  const timeout = input.timeout ?? (message.tone === 'error' || message.progress !== undefined ? 0 : 5000);
  if (timeout > 0 && !message.persistent) {
    toastTimers.set(id, setTimeout(() => dismissToast(id), timeout));
  }
  return id;
}

export function updateToast(id: string, patch: Partial<Omit<ToastMessage, 'id' | 'createdAt'>>): void {
  toastStore.update((messages) => messages.map((message) => (
    message.id === id ? { ...message, ...patch } : message
  )));
  if (patch.progress !== undefined && patch.progress < 1) clearToastTimer(id);
}

export async function runWithToast<T>(
  operation: () => Promise<T>,
  options: {
    pending: string;
    success: string | ((value: T) => string);
    failure?: string;
    retry?: () => void | Promise<void>;
  },
): Promise<T> {
  const id = showToast({ title: options.pending, tone: 'info', persistent: true, progress: 0 });
  try {
    const value = await operation();
    updateToast(id, {
      title: typeof options.success === 'function' ? options.success(value) : options.success,
      tone: 'success',
      progress: 1,
      persistent: false,
    });
    setTimeout(() => dismissToast(id), 3500);
    return value;
  } catch (cause) {
    updateToast(id, {
      title: options.failure ?? 'The action could not be completed',
      message: cause instanceof Error ? cause.message : String(cause),
      tone: 'error',
      progress: undefined,
      persistent: true,
      action: options.retry ? { label: 'Retry', run: options.retry } : undefined,
    });
    throw cause;
  }
}

export interface ActionMenuItem {
  id: string;
  label: string;
  description?: string;
  icon?: string;
  disabled?: boolean;
  danger?: boolean;
  separatorBefore?: boolean;
  run: () => void | Promise<void>;
}

