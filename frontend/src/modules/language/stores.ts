import { writable } from 'svelte/store';
import type { ImageSize } from '../../lib/stores';
import { persistentStorageKey } from '../../lib/product';

export type LanguagePageSize = 30 | 60 | 120 | 'all';
export type LanguageMeaningLanguage = 'en' | 'mn';

export interface LanguageStudyProfile {
  targetLanguage: 'ko';
  primaryMeaning: LanguageMeaningLanguage;
  showSecondaryMeaning: boolean;
}

export interface LanguageFilterPreset {
  id: string;
  name: string;
  stage: string;
  source: string;
  missing: boolean;
  suspended: boolean;
  sort: string;
  descending: boolean;
}

function persisted<T>(
  key: string,
  fallback: T,
  valid: (value: unknown) => value is T,
) {
  let initial = fallback;
  if (typeof localStorage !== 'undefined') {
    try {
      const value = JSON.parse(localStorage.getItem(key) ?? 'null');
      if (valid(value)) initial = value;
    } catch {
      initial = fallback;
    }
  }
  const store = writable<T>(initial);
  if (typeof localStorage !== 'undefined') {
    store.subscribe((value) => {
      localStorage.setItem(key, JSON.stringify(value));
    });
  }
  return store;
}

const imageSizes = ['small', 'medium', 'large', 'huge', 'gigantic', 'absurd'];

export const languageGridSize = persisted<ImageSize>(
  persistentStorageKey('language-grid-size'),
  'medium',
  (value): value is ImageSize => imageSizes.includes(String(value)),
);

export const languagePageSize = persisted<LanguagePageSize>(
  persistentStorageKey('language-page-size'),
  60,
  (value): value is LanguagePageSize =>
    value === 'all' || value === 30 || value === 60 || value === 120,
);

export const languageAutoplay = persisted<boolean>(
  persistentStorageKey('language-autoplay'),
  true,
  (value): value is boolean => typeof value === 'boolean',
);

export const languageStudyProfile = persisted<LanguageStudyProfile>(
  persistentStorageKey('language-study-profile'),
  {
    targetLanguage: 'ko',
    primaryMeaning: 'en',
    showSecondaryMeaning: true,
  },
  (value): value is LanguageStudyProfile => Boolean(
    value
    && typeof value === 'object'
    && (value as LanguageStudyProfile).targetLanguage === 'ko'
    && ['en', 'mn'].includes((value as LanguageStudyProfile).primaryMeaning)
    && typeof (value as LanguageStudyProfile).showSecondaryMeaning === 'boolean'
  ),
);

export const languageFilterPresets = persisted<LanguageFilterPreset[]>(
  persistentStorageKey('language-filter-presets'),
  [],
  (value): value is LanguageFilterPreset[] => Array.isArray(value) && value.every((item) => Boolean(
    item
    && typeof item === 'object'
    && typeof (item as LanguageFilterPreset).id === 'string'
    && typeof (item as LanguageFilterPreset).name === 'string'
    && typeof (item as LanguageFilterPreset).stage === 'string'
    && typeof (item as LanguageFilterPreset).source === 'string'
    && typeof (item as LanguageFilterPreset).missing === 'boolean'
    && typeof (item as LanguageFilterPreset).suspended === 'boolean'
    && typeof (item as LanguageFilterPreset).sort === 'string'
    && typeof (item as LanguageFilterPreset).descending === 'boolean'
  )),
);
