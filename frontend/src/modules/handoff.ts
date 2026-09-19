import { writable } from 'svelte/store';

export interface ModuleHandoff {
  target: 'youtube';
  query: string;
  intent: 'karaoke';
}

export const moduleHandoff = writable<ModuleHandoff | null>(null);
