const BASE = '/api/reddit';

export interface RedditLocalMedia {
  sha256: string;
  role: string;
  source_url: string;
  display_name: string;
  byte_size: number | null;
  content_type: string | null;
}

export interface RedditMediaSummary {
  local: RedditLocalMedia[];
  queued_count: number;
  failed_count: number;
}

export interface RedditOutboundLink {
  url: string;
  host: string;
  label: string;
  download_kind: 'mediafire' | 'https-file' | null;
}

export interface RedditPost {
  id: string;
  fullname: string | null;
  subreddit: string | null;
  author: string | null;
  author_id: string | null;
  title: string | null;
  selftext: string | null;
  selftext_html: string | null;
  created_utc: number | null;
  edited_utc: number | null;
  permalink: string | null;
  url: string | null;
  domain: string | null;
  flair_text: string | null;
  score: number | null;
  upvote_ratio: number | null;
  num_comments: number | null;
  is_self: number | null;
  nsfw: number | null;
  spoiler: number | null;
  stickied: number | null;
  locked: number | null;
  archived: number | null;
  distinguished: string | null;
  removed_by_category: string | null;
  first_observed_at: string;
  latest_observed_at: string;
  archived_comment_count: number;
  links: RedditOutboundLink[];
  media: RedditMediaSummary;
}

export interface RedditFeed {
  format: string;
  items: RedditPost[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface RedditSearchItem {
  record_type: 'post' | 'comment';
  id: string;
  post_id: string;
  subreddit: string | null;
  author: string | null;
  title: string | null;
  body: string | null;
  score: number | null;
  created_utc: number | null;
}

export interface RedditSearch {
  format: string;
  query: string;
  items: RedditSearchItem[];
}

export interface RedditCommentNode {
  id: string;
  fullname: string | null;
  author: string | null;
  body: string | null;
  score: number | null;
  created_utc: number | null;
  body_state: string;
  links: RedditOutboundLink[];
  children: RedditCommentNode[];
}

export interface RedditPostDetail {
  format: string;
  post: RedditPost;
  media: RedditMediaSummary;
  observations: Record<string, unknown>[];
  comment_tree: {
    coverage: Record<string, unknown>;
    placeholders: Record<string, unknown>[];
    root_comments: RedditCommentNode[];
    detached_comments: RedditCommentNode[];
  };
}

export interface RedditCommunity {
  format: string;
  subreddit: string;
  about: Record<string, unknown> | null;
  rules: { snapshot: Record<string, unknown>; items: Record<string, unknown>[] } | null;
  wiki: Record<string, unknown>[];
  moderators: { snapshot: Record<string, unknown>; items: Record<string, unknown>[] } | null;
  media: RedditMediaSummary;
  history: Record<string, number>;
}

export interface RedditStatus {
  format: string;
  initialized: boolean;
  database_path: string;
  counts: {
    posts: number;
    comments: number;
    communities: number;
    media_objects: number;
    queued_assets: number;
    duplicate_alias_candidates: number;
  };
  jobs: Record<string, unknown>[];
  storage: {
    archive: string;
    media: string;
    files_library: string;
  };
  limits: {
    max_files: number;
    max_file_bytes: number;
    max_run_bytes: number;
    min_free_bytes: number;
    max_thread_comments: number;
  };
  runtime: {
    capture_busy: boolean;
    download_busy: boolean;
  };
}

export interface RedditCommunitySummary {
  subreddit: string;
  posts: number;
  comments: number;
  snapshots: number;
  latest_observed_at: string | null;
}

export interface RedditProfileSummary {
  author: string;
  posts: number;
  comments: number;
  latest_observed_at: string | null;
}

export interface RedditProfile {
  format: string;
  username: string;
  posts: RedditPost[];
  comments: Array<{
    id: string;
    post_id: string;
    subreddit: string | null;
    body: string | null;
    score: number | null;
    created_utc: number | null;
  }>;
  stats: { posts: number; comments: number; score: number };
}

export interface RedditCaptureBundleSummary {
  capture_id: string;
  target_kind: 'post' | 'subreddit' | 'user';
  target_url: string;
  retrieved_at: string;
  request_count: number;
  post_count: number;
  comment_count: number;
  placeholder_count: number;
  unresolved_comment_ids: number;
  wiki_page_count: number;
  wiki_pages_truncated: boolean;
  moderators_available: boolean;
}

export interface RedditCaptureResult {
  format: string;
  capture: RedditCaptureBundleSummary;
  imports: Record<string, unknown>[];
  indexed: {
    target_kind: 'post' | 'subreddit' | 'user';
    target_id: string;
    posts?: number;
    comments?: number;
    community_snapshots?: number;
  };
}

export interface RedditMediaSelection {
  target_kind: 'post' | 'subreddit';
  target_id: string;
  images: boolean;
  videos: boolean;
  linked_files: boolean;
  retry_failed?: boolean;
}

export interface RedditMediaPlan {
  selected_assets: number;
  eligible_assets: number;
  already_downloaded: number;
  failed_not_selected: number;
  rejected_external: number;
  rejected_policy: number;
  can_start: boolean;
  selected_by_engine: Record<string, number>;
  selected_by_host: Record<string, number>;
  selected_by_role: Record<string, number>;
  selection_preview: {
    asset_id: number;
    owner_type: string;
    owner_id: string;
    role: string;
    host: string;
    engine: string;
  }[];
  confirmation: {
    confirm_assets: number;
    selection_sha256: string;
  };
}

export interface RedditMediaPlanResult {
  format: string;
  plan: RedditMediaPlan;
}

export interface RedditMediaDownloadResult {
  format: string;
  plan: RedditMediaPlan;
  download: {
    planned: number;
    attempted: number;
    completed: number;
    failed: number;
    deduplicated: number;
    bytes_acquired: number;
    new_object_bytes: number;
    published_files: number;
    publication_failed: number;
    stop_reason: string;
  };
  files: {
    published: boolean;
    source_id: string | null;
    scan: Record<string, number> | null;
  };
}

export interface RedditMediaJob {
  job_id: string;
  target_kind: 'post' | 'subreddit';
  target_id: string;
  status: 'queued' | 'running' | 'completed' | 'completed_with_errors' | 'failed';
  phase: string;
  progress: number;
  planned: number;
  attempted: number;
  completed: number;
  failed: number;
  bytes_acquired: number;
  error: string | null;
  result: RedditMediaDownloadResult | null;
  created_at: string;
  updated_at: string;
}

async function responseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = '';
    try {
      const payload = await response.json();
      detail = typeof payload?.detail === 'string' ? payload.detail : '';
    } catch {
      // Use the status line below.
    }
    throw new Error(detail || `Reddit API ${response.status}: ${response.statusText}`);
  }
  return response.json();
}

async function get<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  for (const [key, value] of Object.entries(params ?? {})) {
    if (value !== undefined && value !== '') {
      url.searchParams.set(key, String(value));
    }
  }
  const response = await fetch(url, { signal });
  return responseJson<T>(response);
}

async function post<T>(
  path: string,
  payload: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(BASE + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
  return responseJson<T>(response);
}

export function redditMediaUrl(sha256: string): string {
  return `${BASE}/media/${encodeURIComponent(sha256)}`;
}

export const redditApi = {
  feed: (
    params: {
      limit?: number;
      cursor?: string;
      subreddit?: string;
      author?: string;
      flair?: string;
      sort?: 'new' | 'popular';
    },
    signal?: AbortSignal,
  ) => get<RedditFeed>('/feed', params, signal),
  search: (
    query: string,
    params?: { limit?: number; subreddit?: string; author?: string; record_type?: string },
    signal?: AbortSignal,
  ) => get<RedditSearch>('/search', { q: query, ...params }, signal),
  post: (postId: string, signal?: AbortSignal) =>
    get<RedditPostDetail>(
      `/posts/${encodeURIComponent(postId)}`,
      { max_comments: 25_000 },
      signal,
    ),
  community: (subreddit: string, signal?: AbortSignal) =>
    get<RedditCommunity>(`/community/${encodeURIComponent(subreddit)}`, undefined, signal),
  communities: (signal?: AbortSignal) =>
    get<{ items: RedditCommunitySummary[] }>('/communities', undefined, signal),
  profiles: (signal?: AbortSignal) =>
    get<{ items: RedditProfileSummary[] }>('/profiles', undefined, signal),
  profile: (username: string, signal?: AbortSignal) =>
    get<RedditProfile>(`/profiles/${encodeURIComponent(username)}`, undefined, signal),
  status: (signal?: AbortSignal) => get<RedditStatus>('/status', undefined, signal),
  capture: (url: string, signal?: AbortSignal) =>
    post<RedditCaptureResult>('/capture', { url }, signal),
  refreshPost: (postId: string, signal?: AbortSignal) =>
    post<RedditCaptureResult>(
      `/posts/${encodeURIComponent(postId)}/refresh`,
      {},
      signal,
    ),
  refreshCommunity: (subreddit: string, signal?: AbortSignal) =>
    post<RedditCaptureResult>(
      `/community/${encodeURIComponent(subreddit)}/refresh`,
      {},
      signal,
    ),
  mediaPlan: (selection: RedditMediaSelection, signal?: AbortSignal) =>
    post<RedditMediaPlanResult>('/media/plan', { ...selection }, signal),
  mediaDownload: (
    selection: RedditMediaSelection,
    confirmation: RedditMediaPlan['confirmation'],
    signal?: AbortSignal,
  ) => post<RedditMediaDownloadResult>(
    '/media/download',
    {
      ...selection,
      confirm_assets: confirmation.confirm_assets,
      confirm_selection: confirmation.selection_sha256,
    },
    signal,
  ),
  startMediaJob: (
    selection: RedditMediaSelection,
    confirmation: RedditMediaPlan['confirmation'],
    signal?: AbortSignal,
  ) => post<{ job: RedditMediaJob }>(
    '/media/jobs',
    {
      ...selection,
      confirm_assets: confirmation.confirm_assets,
      confirm_selection: confirmation.selection_sha256,
    },
    signal,
  ),
  mediaJobs: (signal?: AbortSignal) =>
    get<{ jobs: RedditMediaJob[] }>('/media/jobs', undefined, signal),
  mediaJob: (jobId: string, signal?: AbortSignal) =>
    get<{ job: RedditMediaJob }>(
      `/media/jobs/${encodeURIComponent(jobId)}`,
      undefined,
      signal,
    ),
};
