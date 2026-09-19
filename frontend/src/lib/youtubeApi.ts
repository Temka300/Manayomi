const BASE = '/api/youtube';

export interface YouTubeSearchItem {
  video_id: string;
  title: string;
  channel: string;
  duration: number | null;
  view_count: number | null;
  upload_date: string | null;
  webpage_url: string;
  thumbnail_cache_id: string | null;
  categories: string[];
  live_status: string;
}

export interface YouTubeFormat {
  format_id: string;
  ext: string;
  width: number | null;
  height: number | null;
  fps: number | null;
  vcodec: string;
  acodec: string;
  filesize: number | null;
  tbr: number | null;
  abr: number | null;
  format_note: string;
  resolution: string;
}

export interface YouTubeInspection extends YouTubeSearchItem {
  description: string;
  formats: YouTubeFormat[];
  available_resolutions: number[];
  subtitles: Record<string, string[]>;
  automatic_captions: Record<string, string[]>;
}

export interface YouTubePlan {
  token: string;
  selection_sha256: string;
  selection: {
    video_id: string;
    resolution: string;
    quality_label: string;
    compatibility: boolean;
    format_selector: string;
    format_ids: string[];
    audio_format: string;
    audio_quality: string;
    subtitle_languages: string[];
    automatic_captions: boolean;
    karaoke_intent: boolean;
    browser_session: string;
    max_bytes: number;
  };
  metadata: YouTubeInspection;
  selected_formats: YouTubeFormat[];
  estimated_bytes: number | null;
  display_quality: string;
  destination: string;
  replacement: boolean;
  expires_at: string;
  authorization_required: boolean;
  files: {
    video: boolean;
    companion_audio: boolean;
    thumbnail: boolean;
    subtitle_languages: string[];
    metadata_receipt: boolean;
  };
}

export interface YouTubeJob {
  job_id: string;
  plan_token: string;
  video_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted';
  phase: string;
  progress: number;
  downloaded_bytes: number;
  total_bytes: number | null;
  speed: number | null;
  eta: number | null;
  error: string | null;
  item_id: string | null;
}

export interface YouTubeSubtitle {
  path: string;
  format: string;
  automatic: boolean;
}

export interface YouTubeLibraryItem {
  item_id: string;
  video_id: string;
  title: string;
  channel: string;
  duration: number | null;
  upload_date: string | null;
  view_count: number | null;
  quality_label: string;
  video_path: string;
  video_sha256: string;
  thumbnail_path: string | null;
  audio_paths: string[];
  subtitles: YouTubeSubtitle[];
  metadata_path: string;
  receipt_path: string;
  metadata: Record<string, unknown>;
  karaoke_intent: boolean;
  added_at: string;
  files_source_id: string;
  files_relative_path: string;
  playback: YouTubePlaybackState;
}

export interface YouTubePlaybackState {
  item_id: string;
  position_seconds: number;
  duration_seconds: number | null;
  completed: number;
  last_played_at: string | null;
  updated_at: string | null;
}

async function apiError(res: Response): Promise<Error> {
  try {
    const value = await res.json();
    if (typeof value?.detail === 'string') return new Error(value.detail);
  } catch {
    // Fall back to HTTP status.
  }
  return new Error(`API ${res.status}: ${res.statusText}`);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
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

function encodedPath(value: string): string {
  return value
    .replace(/\\/g, '/')
    .split('/')
    .map(encodeURIComponent)
    .join('/');
}

export const youtubeApi = {
  status: () => request<Record<string, unknown>>('/status'),
  search: (query: string, limit = 20) =>
    request<{ items: YouTubeSearchItem[] }>(
      `/search?query=${encodeURIComponent(query)}&limit=${limit}`,
    ),
  inspect: (videoId: string) =>
    request<{ item: YouTubeInspection }>(`/videos/${encodeURIComponent(videoId)}`),
  inspectUrl: (url: string) =>
    request<{ item: YouTubeInspection }>(
      `/inspect?url=${encodeURIComponent(url)}`,
    ),
  plan: (value: {
    video_id: string;
    resolution: string;
    compatibility: boolean;
    audio_format: string;
    audio_quality: string;
    subtitle_languages: string[];
    automatic_captions: boolean;
    karaoke_intent: boolean;
    browser_session?: 'none' | 'chrome' | 'edge' | 'firefox';
    max_bytes?: number;
  }) => request<{ plan: YouTubePlan }>('/plan', json('POST', value)),
  download: (
    planToken: string,
    selectionSha256: string,
    authorized: boolean,
  ) =>
    request<{ job: YouTubeJob }>(
      '/download',
      json('POST', {
        plan_token: planToken,
        selection_sha256: selectionSha256,
        authorized,
      }),
    ),
  job: (jobId: string) =>
    request<{ job: YouTubeJob }>(`/jobs/${encodeURIComponent(jobId)}`),
  jobs: () => request<{ jobs: YouTubeJob[] }>('/jobs'),
  cancelJob: (jobId: string) =>
    request<{ job: YouTubeJob }>(
      `/jobs/${encodeURIComponent(jobId)}/cancel`,
      { method: 'POST' },
    ),
  resumeJob: (jobId: string) =>
    request<{ job: YouTubeJob }>(
      `/jobs/${encodeURIComponent(jobId)}/resume`,
      { method: 'POST' },
    ),
  library: (query = '') =>
    request<{ items: YouTubeLibraryItem[] }>(
      `/library?query=${encodeURIComponent(query)}`,
    ),
  item: (itemId: string) =>
    request<{ item: YouTubeLibraryItem }>(
      `/library/${encodeURIComponent(itemId)}`,
    ),
  savePlayback: (
    itemId: string,
    value: {
      position_seconds: number;
      duration_seconds: number | null;
      completed: boolean;
    },
  ) =>
    request<{ playback: YouTubePlaybackState }>(
      `/library/${encodeURIComponent(itemId)}/playback`,
      json('PUT', value),
    ),
  thumbnailUrl: (cacheId: string) =>
    `${BASE}/search-thumbnails/${encodeURIComponent(cacheId)}`,
  mediaUrl: (itemId: string, path: string) =>
    `${BASE}/media/${encodeURIComponent(itemId)}/${encodedPath(path)}`,
};
