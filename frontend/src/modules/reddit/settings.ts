import { writable } from 'svelte/store';

import { persistentStorageKey } from '../../lib/product';


export interface RedditCaptureDefaults {
  images: boolean;
  videos: boolean;
  linkedFiles: boolean;
  retryFailed: boolean;
}

function normalizeFavoriteCommunities(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(
    value
      .filter((item): item is string => typeof item === 'string')
      .map((item) => item.trim())
      .filter(Boolean),
  )].slice(0, 500);
}

function initialFavoriteCommunities(): string[] {
  if (typeof localStorage === 'undefined') return [];
  try {
    return normalizeFavoriteCommunities(
      JSON.parse(localStorage.getItem(persistentStorageKey('reddit-favorite-communities')) ?? '[]'),
    );
  } catch {
    return [];
  }
}

export const redditFavoriteCommunities = writable<string[]>(
  initialFavoriteCommunities(),
);

if (typeof localStorage !== 'undefined') {
  redditFavoriteCommunities.subscribe(value => {
    localStorage.setItem(
      persistentStorageKey('reddit-favorite-communities'),
      JSON.stringify(normalizeFavoriteCommunities(value)),
    );
  });
}

export const DEFAULT_REDDIT_CAPTURE_DEFAULTS: RedditCaptureDefaults = {
  images: false,
  videos: false,
  linkedFiles: false,
  retryFailed: true,
};

const STORAGE_KEY = persistentStorageKey('reddit-capture-defaults');

function normalizeDefaults(value: unknown): RedditCaptureDefaults {
  if (!value || typeof value !== 'object') {
    return { ...DEFAULT_REDDIT_CAPTURE_DEFAULTS };
  }
  const candidate = value as Partial<RedditCaptureDefaults>;
  return {
    images: candidate.images === true,
    videos: candidate.videos === true,
    linkedFiles: candidate.linkedFiles === true,
    retryFailed: candidate.retryFailed !== false,
  };
}

function initialDefaults(): RedditCaptureDefaults {
  if (typeof localStorage === 'undefined') {
    return { ...DEFAULT_REDDIT_CAPTURE_DEFAULTS };
  }
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === null) {
    return { ...DEFAULT_REDDIT_CAPTURE_DEFAULTS };
  }
  try {
    return normalizeDefaults(JSON.parse(stored));
  } catch {
    return { ...DEFAULT_REDDIT_CAPTURE_DEFAULTS };
  }
}

export const redditCaptureDefaults = writable<RedditCaptureDefaults>(
  initialDefaults(),
);

if (typeof localStorage !== 'undefined') {
  redditCaptureDefaults.subscribe(value => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizeDefaults(value)));
  });
}

export function resetRedditCaptureDefaults(): void {
  redditCaptureDefaults.set({ ...DEFAULT_REDDIT_CAPTURE_DEFAULTS });
}
