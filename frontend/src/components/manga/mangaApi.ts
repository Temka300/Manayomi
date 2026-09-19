// Typed client for the Manayomi module API (/api/manga/*).

export interface MangaCard {
  id: number;
  source: string;
  gallery_id: number;
  external_id: string | null;
  parent_external_id: string | null;
  media_id: string | null;
  title: string;
  pages: number | null;
  cover_name: string | null;
  cover_ext: string | null;
  favorites: number | null;
  matched: number;
  file_size: number | null;
  created_at: number;
  languages: string | null;
  tag_names: string | null;
  favorite: number;
  pinned: number;
  read_last_page: number | null;
  read_page_count: number | null;
  read_completed_at: number | null;
  series_id: number | null;
  series_title: string | null;
  series_chapter_count: number | null;
}

export interface MangaSeries {
  id: number;
  title: string;
  created_at: number;
  chapter_count: number;
  cover_gallery_id: number | null;
}

export interface MangaSeriesDetail {
  id: number;
  title: string;
  created_at: number;
  chapters: MangaCard[];
}

export type CoverProgressMode = 'off' | 'bar' | 'percent' | 'pages';

export interface MangaTag {
  name: string;
  category: string;
  count?: number;
}

export interface MangaDetail extends MangaCard {
  title_english: string | null;
  title_japanese: string | null;
  title_pretty: string | null;
  scanlator: string | null;
  upload_date: number | null;
  raw_json: string | null;
  file_path: string;
  root_id: number | null;
  tags: MangaTag[];
  category_ids: number[];
  files_source_id: string | null;
  files_relative_path: string | null;
}

export interface MangaDownloadItem {
  source: 'nhentai' | 'mangadex';
  gallery_id: number | null;
  external_id: string;
  local_manga_id?: number;
  title: string;
  status: 'queued' | 'downloading' | 'done' | 'error';
  page: number;
  pages: number;
  error?: string;
}

export interface MangaDownloadState {
  running: boolean;
  current: MangaDownloadItem | null;
  queue: MangaDownloadItem[];
  recent: MangaDownloadItem[];
}

export interface RecentDownloadsResult {
  manga: MangaCard[];
  total: number;
  limit: number;
  offset: number;
}

export interface HehTag {
  name: string;
  slug: string;
  count: number;
}

export interface MangaReadingProgress {
  source: string;
  gallery_id: number;
  title: string;
  cover_path: string | null;
  last_page: number;
  page_count: number;
  started_at: number;
  last_read_at: number;
  completed_at: number | null;
}

export interface MangaHistoryItem extends MangaReadingProgress {
  external_id: string | null;
  local_manga_id: number | null;
  cover_name: string | null;
  cover_ext: string | null;
  downloaded: boolean;
}

export interface MangaHistoryResult {
  items: MangaHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface LibraryResult {
  manga: MangaCard[];
  total: number;
  page: number;
  per_page: number;
  page_count: number;
  stats: { manga_count: number; tag_count: number; favorite_count: number };
}

export interface MangaRoot {
  id: number;
  path: string;
  label: string | null;
  added_at: number;
  last_scan_at: number | null;
  manga_count: number;
}

export interface RootRelocation {
  root_id: number;
  old_path: string;
  new_path: string;
  indexed_files: number;
  verified_files: number;
  missing_files: number;
  unchanged: boolean;
}

export interface MangaSettings {
  nhentai_enabled: boolean;
  cf_clearance: string;
  user_agent: string;
  request_delay_ms: number;
  blur_covers: boolean;
  show_ignored: boolean;
  cover_progress: CoverProgressMode;
  ignored_tags: string[];
}

export interface ScanProgress {
  running: boolean;
  root_id: number | null;
  total: number;
  processed: number;
  added: number;
  matched: number;
  skipped: number;
  errors: number;
  current_file: string;
  started_at: number;
  finished_at: number | null;
  message: string;
}

export interface MangaCategory {
  id: number;
  name: string;
  position: number;
  manga_count: number;
}

export interface MangaDexTag {
  id: string;
  name: string;
  group: string;
}

export interface MangaDexFilterOption {
  value: string;
  label: string;
}

export interface MangaDexFilterCatalog {
  languages: MangaDexFilterOption[];
  content_ratings: MangaDexFilterOption[];
  publication_demographics: MangaDexFilterOption[];
  statuses: MangaDexFilterOption[];
  sorts: MangaDexFilterOption[];
  tag_modes: MangaDexFilterOption[];
  tag_groups: Record<'content' | 'format' | 'genre' | 'theme', MangaDexTag[]>;
}

export interface MangaDexBrowseFilters {
  language: string;
  originalLanguages: string[];
  contentRatings: string[];
  publicationDemographics: string[];
  statuses: string[];
  sort: string;
  tagsMode: 'AND' | 'OR';
  includedTags: string[];
}

export interface MangaDexTitle {
  id: string;
  title: string;
  titles: Record<string, string>;
  alternate_titles: string[];
  description: string;
  authors: string[];
  artists: string[];
  cover_filename: string;
  tags: MangaDexTag[];
  status: string;
  year: number | null;
  original_language: string;
  available_languages: string[];
  content_rating: string;
  publication_demographic: string;
  last_volume: string | null;
  last_chapter: string | null;
  links: Record<string, string>;
  official_links: unknown[];
  created_at: string | null;
  updated_at: string | null;
  downloaded_chapters: number;
  ignored_matches?: string[];
}

export interface MangaDexChapter {
  id: string;
  manga_id: string;
  title: string;
  volume: string | null;
  chapter: string | null;
  pages: number;
  translated_language: string;
  external_url: string;
  publish_at: string | null;
  readable_at: string | null;
  created_at: string | null;
  updated_at: string | null;
  unavailable: boolean;
  scanlation_groups: string[];
  downloaded: boolean;
}

export interface MangaDexBrowseResult {
  items: MangaDexTitle[];
  total: number;
  page: number;
  per_page: number;
  num_pages: number;
}

export interface MangaDexChaptersResult {
  items: MangaDexChapter[];
  total: number;
  limit: number;
  offset: number;
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `${response.status}`;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* keep status */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

const post = (url: string, body?: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body)
});

export const mangaApi = {
  library(params: {
    q?: string;
    page?: number;
    perPage?: number;
    sort?: string;
    language?: string;
    favorites?: boolean;
    category?: number | null;
  }): Promise<LibraryResult> {
    const qs = new URLSearchParams();
    if (params.q) qs.set('q', params.q);
    qs.set('page', String(params.page ?? 1));
    qs.set('per_page', String(params.perPage ?? 60));
    qs.set('sort', params.sort ?? 'recent');
    qs.set('language', params.language ?? 'all');
    if (params.favorites) qs.set('favorites', 'true');
    if (params.category) qs.set('category', String(params.category));
    return json(`/api/manga/library?${qs}`);
  },
  detail: (id: number) => json<MangaDetail>(`/api/manga/detail/${id}`),
  coverUrl: (galleryId: number) => `/api/manga/cover/${galleryId}`,
  pageUrl(galleryId: number, n: number, version = '', maxWidth = 0): string {
    const qs = new URLSearchParams();
    if (version) qs.set('v', version);
    if (maxWidth > 0) qs.set('max_width', String(maxWidth));
    const suffix = qs.size ? `?${qs}` : '';
    return `/api/manga/page/${galleryId}/${n}${suffix}`;
  },
  pageList: (galleryId: number) =>
    json<{ gallery_id: number; pages: number; names: string[]; version: string }>(`/api/manga/pages/${galleryId}`),
  roots: () => json<{ roots: MangaRoot[] }>('/api/manga/roots'),
  addRoot: (path: string) => json<{ ok: boolean }>('/api/manga/roots', post('/api/manga/roots', { path })),
  removeRoot: (id: number) => json<{ ok: boolean }>(`/api/manga/roots/${id}`, { method: 'DELETE' }),
  previewRootRelocation: (id: number, path: string) =>
    json<RootRelocation>(`/api/manga/roots/${id}/relocate-preview`, post('', { path })),
  relocateRoot: (id: number, path: string) =>
    json<RootRelocation>(`/api/manga/roots/${id}/relocate`, post('', { path, confirm: true })),
  settings: () => json<MangaSettings>('/api/manga/settings'),
  updateSettings: (changes: Partial<MangaSettings>) =>
    json<MangaSettings>('/api/manga/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changes)
    }),
  startScan: (rootId: number, enrich: boolean) =>
    json<{ ok: boolean }>('/api/manga/scan', post('/api/manga/scan', { root_id: rootId, enrich })),
  scanProgress: () => json<ScanProgress>('/api/manga/scan'),
  topTags: (limit = 60) => json<{ tags: MangaTag[] }>(`/api/manga/tags/top?limit=${limit}`),
  suggestTags: (q: string) =>
    json<{ tags: MangaTag[] }>(`/api/manga/tags/suggest?q=${encodeURIComponent(q)}`),
  toggleFavorite: (galleryId: number) =>
    json<{ favorite: boolean }>(`/api/manga/favorite/${galleryId}`, { method: 'POST' }),
  togglePin: (galleryId: number) =>
    json<{ pinned: boolean }>(`/api/manga/pin/${galleryId}`, { method: 'POST' }),
  categories: () => json<{ categories: MangaCategory[] }>('/api/manga/categories'),
  createCategory: (name: string) =>
    json<{ ok: boolean; categories: MangaCategory[] }>(
      '/api/manga/categories',
      post('/api/manga/categories', { name })
    ),
  deleteCategory: (id: number) =>
    json<{ ok: boolean; categories: MangaCategory[] }>(`/api/manga/categories/${id}`, {
      method: 'DELETE'
    }),
  toggleCategory: (categoryId: number, galleryId: number) =>
    json<{ member: boolean }>(`/api/manga/categories/${categoryId}/toggle/${galleryId}`, {
      method: 'POST'
    }),
  series: () => json<{ series: MangaSeries[] }>('/api/manga/series'),
  seriesDetail: (id: number) => json<MangaSeriesDetail>(`/api/manga/series/${id}`),
  createSeries: (title: string, galleryIds: number[]) =>
    json<{ ok: boolean; series_id: number; series: MangaSeries[] }>(
      '/api/manga/series',
      post('/api/manga/series', { title, gallery_ids: galleryIds })
    ),
  renameSeries: (id: number, title: string) =>
    json<{ ok: boolean; series: MangaSeries[] }>(`/api/manga/series/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title })
    }),
  deleteSeries: (id: number) =>
    json<{ ok: boolean; series: MangaSeries[] }>(`/api/manga/series/${id}`, { method: 'DELETE' }),
  addToSeries: (seriesId: number, galleryId: number) =>
    json<{ ok: boolean; series: MangaSeries[] }>(
      `/api/manga/series/${seriesId}/items`,
      post('', { gallery_id: galleryId })
    ),
  removeFromSeries: (galleryId: number) =>
    json<{ ok: boolean; series: MangaSeries[] }>(`/api/manga/series/items/${galleryId}`, {
      method: 'DELETE'
    }),
  setSeriesFirst: (galleryId: number) =>
    json<{ ok: boolean }>(`/api/manga/series/items/${galleryId}/first`, { method: 'POST' }),
  reorderSeries: (id: number, galleryIds: number[]) =>
    json<{ ok: boolean }>(`/api/manga/series/${id}/order`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gallery_ids: galleryIds })
    }),
  downloads: () => json<MangaDownloadState>('/api/manga/downloads'),
  recentDownloads: (limit = 6, offset = 0) =>
    json<RecentDownloadsResult>(`/api/manga/downloads/recent?limit=${limit}&offset=${offset}`),
  hehTags: (sort: 'popular' | 'a-z') =>
    json<{ source: 'heh'; sort: 'popular' | 'a-z'; count_scope: 'downloaded-library'; tags: HehTag[] }>(`/api/manga/heh/tags?sort=${sort}`),
  history: (limit = 60, offset = 0) =>
    json<MangaHistoryResult>(`/api/manga/history?limit=${limit}&offset=${offset}`),
  readingProgress: (galleryId: number) =>
    json<{ progress: MangaReadingProgress | null }>(`/api/manga/history/progress/${galleryId}`),
  saveReadingProgress: (
    galleryId: number,
    progress: { title: string; cover_path: string | null; page: number; page_count: number }
  ) => json<MangaReadingProgress>(`/api/manga/history/${galleryId}`, post('', progress)),
  remoteImageUrl: (path: string, kind: 'thumb' | 'image' = 'thumb') =>
    `/api/manga/nh-image?path=${encodeURIComponent(path)}&kind=${kind}`,
  mangaDexBrowse(params: {
    query?: string;
    page?: number;
    perPage?: number;
    sort?: string;
    language?: string;
    originalLanguages?: string[];
    contentRatings?: string[];
    publicationDemographics?: string[];
    statuses?: string[];
    includedTags?: string[];
    tagsMode?: 'AND' | 'OR';
  }): Promise<MangaDexBrowseResult> {
    const qs = new URLSearchParams({
      query: params.query ?? '',
      page: String(params.page ?? 1),
      per_page: String(params.perPage ?? 20),
      sort: params.sort ?? 'latest',
      language: params.language ?? 'all',
      original_languages: (params.originalLanguages ?? []).join(','),
      content_ratings: (params.contentRatings ?? []).join(','),
      publication_demographics: (params.publicationDemographics ?? []).join(','),
      statuses: (params.statuses ?? []).join(','),
      included_tags: (params.includedTags ?? []).join(','),
      tags_mode: params.tagsMode ?? 'AND'
    });
    return json(`/api/manga/remote/mangadex/browse?${qs}`);
  },
  mangaDexFilters: () =>
    json<MangaDexFilterCatalog>('/api/manga/remote/mangadex/filters'),
  mangaDexTitle: (id: string) =>
    json<MangaDexTitle>(`/api/manga/remote/mangadex/title/${encodeURIComponent(id)}`),
  mangaDexChapters: (id: string, language = 'all', limit = 500, offset = 0) => {
    const qs = new URLSearchParams({ language, limit: String(limit), offset: String(offset) });
    return json<MangaDexChaptersResult>(
      `/api/manga/remote/mangadex/title/${encodeURIComponent(id)}/chapters?${qs}`
    );
  },
  mangaDexChapter: (id: string) =>
    json<{ chapter: MangaDexChapter; title: MangaDexTitle; local: MangaCard | null }>(
      `/api/manga/remote/mangadex/chapter/${encodeURIComponent(id)}`
    ),
  mangaDexPages: (id: string) =>
    json<{ chapter_id: string; pages: number; data_saver: number; external_url?: string }>(
      `/api/manga/remote/mangadex/chapter/${encodeURIComponent(id)}/pages`
    ),
  mangaDexPageUrl: (id: string, number: number, quality: 'data' | 'data-saver') =>
    `/api/manga/remote/mangadex/chapter/${encodeURIComponent(id)}/page/${number}?quality=${quality}`,
  mangaDexCoverUrl: (id: string, filename: string, size: 0 | 256 | 512 = 512) =>
    `/api/manga/remote/mangadex/cover/${encodeURIComponent(id)}/${encodeURIComponent(filename)}?size=${size}`,
  downloadMangaDexChapter: (id: string) =>
    json<{ queued: boolean; reason?: string }>(
      `/api/manga/remote/mangadex/download/${encodeURIComponent(id)}`,
      { method: 'POST' }
    ),
  mangaDexProgress: (id: string) =>
    json<{ gallery_id: number | null; progress: MangaReadingProgress | null }>(
      `/api/manga/remote/mangadex/chapter/${encodeURIComponent(id)}/progress`
    ),
  saveMangaDexProgress: (
    id: string,
    progress: { title: string; cover_path: string | null; page: number; page_count: number }
  ) => json<MangaReadingProgress>(
    `/api/manga/remote/mangadex/chapter/${encodeURIComponent(id)}/progress`,
    post('', progress)
  ),
  status: () =>
    json<{
      suite: string;
      module: string;
      version: string;
      module_home: string;
      default_library: string;
      manga_count: number;
      tag_count: number;
      nhentai_enabled: boolean;
    }>('/api/manga/status')
};

/** nHentai tag categories with the WMH colour coding. */
export const MANGA_TAG_COLORS: Record<string, string> = {
  parody: '#da77f2',
  character: '#69db7c',
  artist: '#ff8787',
  group: '#ffa94d',
  tag: '#4dabf7',
  category: '#3bc9db',
  language: '#ffd43b'
};

export const LANGUAGE_CODES: Record<string, string> = {
  japanese: 'JP',
  english: 'EN',
  chinese: 'CN',
  korean: 'KR'
};

export function languageBadges(raw: string | null): string[] {
  if (!raw) return [];
  const out: string[] = [];
  for (const name of raw.split(',')) {
    const code = LANGUAGE_CODES[name.trim().toLowerCase()];
    if (code && !out.includes(code)) out.push(code);
  }
  return out;
}

/** Unpack the U+001F-separated tag_names card column. */
export function splitTagNames(raw: string | null): string[] {
  return raw ? raw.split('\u001f').filter(Boolean) : [];
}
