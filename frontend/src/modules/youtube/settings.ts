import { writable } from 'svelte/store';

import { persistentStorageKey } from '../../lib/product';


export interface YouTubeDownloadDefaults {
  resolution: '480' | '720' | '1080' | '1440' | '2160' | 'highest';
  compatibility: boolean;
  audioFormat: 'none' | 'best' | 'm4a' | 'opus' | 'mp3';
  audioQuality: '128K' | '192K' | '320K';
  automaticCaptions: boolean;
  browserSession: 'none' | 'chrome' | 'edge' | 'firefox';
}

export const DEFAULT_YOUTUBE_DOWNLOAD_DEFAULTS: YouTubeDownloadDefaults = {
  resolution: '1080',
  compatibility: true,
  audioFormat: 'none',
  audioQuality: '192K',
  automaticCaptions: false,
  browserSession: 'none',
};

const STORAGE_KEY = persistentStorageKey('youtube-download-defaults');
const RESOLUTIONS = new Set(['480', '720', '1080', '1440', '2160', 'highest']);
const AUDIO_FORMATS = new Set(['none', 'best', 'm4a', 'opus', 'mp3']);
const AUDIO_QUALITIES = new Set(['128K', '192K', '320K']);
const BROWSER_SESSIONS = new Set(['none', 'chrome', 'edge', 'firefox']);

function normalize(value: unknown): YouTubeDownloadDefaults {
  if (!value || typeof value !== 'object') {
    return { ...DEFAULT_YOUTUBE_DOWNLOAD_DEFAULTS };
  }
  const candidate = value as Partial<YouTubeDownloadDefaults>;
  return {
    resolution: RESOLUTIONS.has(candidate.resolution ?? '')
      ? candidate.resolution!
      : DEFAULT_YOUTUBE_DOWNLOAD_DEFAULTS.resolution,
    compatibility: candidate.compatibility !== false,
    audioFormat: AUDIO_FORMATS.has(candidate.audioFormat ?? '')
      ? candidate.audioFormat!
      : DEFAULT_YOUTUBE_DOWNLOAD_DEFAULTS.audioFormat,
    audioQuality: AUDIO_QUALITIES.has(candidate.audioQuality ?? '')
      ? candidate.audioQuality!
      : DEFAULT_YOUTUBE_DOWNLOAD_DEFAULTS.audioQuality,
    automaticCaptions: candidate.automaticCaptions === true,
    browserSession: BROWSER_SESSIONS.has(candidate.browserSession ?? '')
      ? candidate.browserSession!
      : DEFAULT_YOUTUBE_DOWNLOAD_DEFAULTS.browserSession,
  };
}

function initialValue(): YouTubeDownloadDefaults {
  if (typeof localStorage === 'undefined') {
    return { ...DEFAULT_YOUTUBE_DOWNLOAD_DEFAULTS };
  }
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === null) return { ...DEFAULT_YOUTUBE_DOWNLOAD_DEFAULTS };
  try {
    return normalize(JSON.parse(stored));
  } catch {
    return { ...DEFAULT_YOUTUBE_DOWNLOAD_DEFAULTS };
  }
}

export const youtubeDownloadDefaults = writable<YouTubeDownloadDefaults>(
  initialValue(),
);

if (typeof localStorage !== 'undefined') {
  youtubeDownloadDefaults.subscribe((value) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(normalize(value)));
  });
}

export function resetYouTubeDownloadDefaults(): void {
  youtubeDownloadDefaults.set({ ...DEFAULT_YOUTUBE_DOWNLOAD_DEFAULTS });
}
