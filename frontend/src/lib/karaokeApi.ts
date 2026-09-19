const BASE = '/api/karaoke';

import type { SubtitleCue } from './media';

export interface KaraokeLyricTrack {
  lyric_id: string;
  label: string;
  language: string;
  format: 'ass' | 'ssa' | 'srt' | 'vtt' | 'lrc' | string;
  source_kind: string;
  relative_path: string;
  sha256: string;
  cues: SubtitleCue[];
}

/* API payload fields remain karaoke-specific. Player-facing subtitle types
   live in lib/media.ts and wrappers adapt this payload at the module edge. */

export interface PlaybackState {
  item_key: string;
  file_sha256: string | null;
  position_seconds: number;
  duration_seconds: number | null;
  completed: number;
  lyric_id: string | null;
  lyric_offset_seconds: number;
  repeat_mode: 'off' | 'all' | 'one';
  shuffle: number;
  last_played_at: string | null;
  play_count: number;
}

export interface KaraokeItem {
  item_id: string;
  provider: string;
  provider_id: string;
  title: string;
  subtitle: string;
  year: number | null;
  duration: number | null;
  primary_video: string;
  thumbnail: string | null;
  metadata_path: string;
  receipt_path: string;
  primary_sha256: string;
  external_source_id: string | null;
  external_relative_path: string | null;
  files_source_id: string;
  files_relative_path: string;
  metadata: Record<string, unknown>;
  tags: Record<string, string[]>;
  lyrics: KaraokeLyricTrack[];
  added_at: string;
  favorite: boolean;
  playback?: PlaybackState;
  media_health: {
    status: 'valid' | 'incomplete' | 'missing' | 'unchecked';
    actual_bytes: number | null;
    expected_bytes: number | null;
    can_update: boolean;
    obsolete_primary_video: string | null;
  };
}

export interface KaraokePlaylist {
  playlist_id: number;
  name: string;
  description: string;
  items: Array<{
    item_key: string;
    file_sha256: string | null;
    position: number;
  }>;
}

export interface KaraMoeItem {
  provider: 'kara-moe';
  provider_id: string;
  item_id: string;
  title: string;
  subtitle: string;
  year: number | null;
  duration: number | null;
  created_at: string | null;
  tags: Record<string, string[]>;
  cues?: SubtitleCue[];
  source?: Record<string, unknown>;
}

export interface AcquisitionPlan {
  token: string;
  selection_sha256: string;
  selection: {
    provider_id: string;
    destination: string;
    max_bytes: number;
  };
  item: KaraMoeItem;
  estimated_bytes: number | null;
  expires_at: string;
  authorization_required: boolean;
  replacement: boolean;
  replacement_of: string | null;
  files: string[];
}

export interface AcquisitionJob {
  job_id: string;
  plan_token: string;
  provider_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted';
  phase: string;
  progress: number;
  downloaded_bytes: number;
  total_bytes: number | null;
  error: string | null;
  item_id: string | null;
}

async function apiError(res: Response): Promise<Error> {
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string') return new Error(body.detail);
  } catch {
    // Fall through to the HTTP status.
  }
  return new Error(`API ${res.status}: ${res.statusText}`);
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(BASE + path, init);
  if (!res.ok) throw await apiError(res);
  return res.json();
}

function json(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}

function assetPath(itemId: string, relativePath: string): string {
  const path = relativePath
    .replace(/\\/g, '/')
    .split('/')
    .map(encodeURIComponent)
    .join('/');
  return `${BASE}/media/${encodeURIComponent(itemId)}/${path}`;
}

export const karaokeApi = {
  status: () => request<Record<string, unknown>>('/status'),
  library: (query = '', favoritesOnly = false) =>
    request<{ items: KaraokeItem[] }>(
      `/library?query=${encodeURIComponent(query)}&favorites_only=${favoritesOnly}`,
    ),
  item: (itemId: string) =>
    request<{ item: KaraokeItem }>(`/library/${encodeURIComponent(itemId)}`),
  searchKaraMoe: (query: string, limit = 20) =>
    request<{ items: KaraMoeItem[] }>(
      `/kara-moe/search?query=${encodeURIComponent(query)}&limit=${limit}`,
    ),
  karaMoeDetail: (providerId: string) =>
    request<{ item: KaraMoeItem }>(`/kara-moe/${encodeURIComponent(providerId)}`),
  planKaraMoe: (providerId: string, maxBytes = 2 * 1024 * 1024 * 1024) =>
    request<{ plan: AcquisitionPlan }>(
      '/kara-moe/plan',
      json('POST', { provider_id: providerId, max_bytes: maxBytes }),
    ),
  downloadKaraMoe: (
    planToken: string,
    selectionSha256: string,
    authorized: boolean,
  ) =>
    request<{ job: AcquisitionJob }>(
      '/kara-moe/download',
      json('POST', {
        plan_token: planToken,
        selection_sha256: selectionSha256,
        authorized,
      }),
    ),
  job: (jobId: string) =>
    request<{ job: AcquisitionJob }>(`/jobs/${encodeURIComponent(jobId)}`),
  jobs: () => request<{ jobs: AcquisitionJob[] }>('/jobs'),
  cancelJob: (jobId: string) =>
    request<{ job: AcquisitionJob }>(
      `/jobs/${encodeURIComponent(jobId)}/cancel`,
      { method: 'POST' },
    ),
  resumeJob: (jobId: string) =>
    request<{ job: AcquisitionJob }>(
      `/jobs/${encodeURIComponent(jobId)}/resume`,
      { method: 'POST' },
    ),
  favorite: (itemId: string, favorite: boolean) =>
    request<{ favorite: boolean }>(
      `/library/${encodeURIComponent(itemId)}/favorite`,
      json('POST', { favorite }),
    ),
  playlists: () => request<{ playlists: KaraokePlaylist[] }>('/playlists'),
  createPlaylist: (name: string, description = '') =>
    request<{ playlist: KaraokePlaylist }>(
      '/playlists',
      json('POST', { name, description }),
    ),
  addToPlaylist: (playlistId: number, itemId: string) =>
    request<{ playlist: KaraokePlaylist }>(
      `/playlists/${playlistId}/items`,
      json('POST', { item_id: itemId }),
    ),
  updatePlaylist: (playlistId: number, name: string, description = '') =>
    request<{ playlist: KaraokePlaylist }>(
      `/playlists/${playlistId}`,
      json('PUT', { name, description }),
    ),
  deletePlaylist: (playlistId: number) =>
    request<{ playlist_id: number; deleted: boolean }>(
      `/playlists/${playlistId}`,
      { method: 'DELETE' },
    ),
  removeFromPlaylist: (playlistId: number, itemId: string) =>
    request<{ playlist: KaraokePlaylist }>(
      `/playlists/${playlistId}/items/${encodeURIComponent(itemId)}`,
      { method: 'DELETE' },
    ),
  reorderPlaylist: (playlistId: number, itemIds: string[]) =>
    request<{ playlist: KaraokePlaylist }>(
      `/playlists/${playlistId}/items`,
      json('PUT', { item_ids: itemIds }),
    ),
  playback: (itemId: string) =>
    request<{ playback: PlaybackState }>(
      `/library/${encodeURIComponent(itemId)}/playback`,
    ),
  savePlayback: (
    itemId: string,
    value: Partial<PlaybackState> & { position_seconds: number },
  ) =>
    request<{ playback: PlaybackState }>(
      `/library/${encodeURIComponent(itemId)}/playback`,
      json('PUT', value),
    ),
  recordPlay: (itemId: string) =>
    request<{ playback: PlaybackState }>(
      `/library/${encodeURIComponent(itemId)}/play`,
      { method: 'POST' },
    ),
  attachLyrics: (
    itemId: string,
    filename: string,
    contentBase64: string,
    label = '',
    language = '',
  ) =>
    request<{ item: KaraokeItem }>(
      `/library/${encodeURIComponent(itemId)}/lyrics`,
      json('POST', {
        filename,
        content_base64: contentBase64,
        label,
        language,
      }),
    ),
  importFiles: (
    sourceId: string,
    relativePath: string,
    title = '',
    subtitle = '',
  ) =>
    request<{ item: KaraokeItem; already_imported: boolean }>(
      '/library/import-files',
      json('POST', {
        source_id: sourceId,
        relative_path: relativePath,
        title,
        subtitle,
      }),
    ),
  importYouTube: (itemId: string) =>
    request<{
      item: KaraokeItem;
      already_imported: boolean;
      subtitles_attached: number;
      subtitles_skipped: number;
    }>(
      `/library/import-youtube/${encodeURIComponent(itemId)}`,
      { method: 'POST' },
    ),
  mediaUrl: assetPath,
  captionUrl: (itemId: string, lyricId: string) =>
    `${BASE}/library/${encodeURIComponent(itemId)}/lyrics/${encodeURIComponent(lyricId)}/captions.vtt`,
};
