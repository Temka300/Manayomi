const BASE = '/api/language';

export type LanguageStage = 'new' | 'learning' | 'young' | 'mature';
export type LanguageMediaRole = 'word_audio' | 'sentence_audio' | 'image';

export interface LanguageSense {
  lang: string;
  position?: number;
  text: string;
}

export interface LanguageTranslation {
  lang: string;
  text: string;
}

export interface LanguageExample {
  position?: number;
  sentence: string;
  translations: LanguageTranslation[];
  audio_rel?: string | null;
}

export interface LanguageNoteText {
  kind: string;
  position?: number;
  body: string;
}

export interface LanguageMedia {
  media_id: string;
  role: LanguageMediaRole;
  position: number;
  relative_path: string;
  sha256: string;
  bytes: number;
  origin_filename: string;
  active: boolean | number;
  imported_at: string;
}

export interface LanguageProgress {
  card_id: string;
  interval: number;
  due: number | null;
  reps: number;
  lapses: number;
  queue: number | null;
  type: number | null;
  stage: LanguageStage;
  due_now: boolean | number;
  last_reviewed_at: string | null;
  synced_at: string;
}

export interface LanguageWord {
  word_id: string;
  lang: string;
  headword: string;
  sentence_form: string;
  reading: string;
  source: 'anki' | 'manual';
  source_key: string;
  note_type: string;
  deck: string;
  sort_index: number | null;
  fields: Record<string, string>;
  media_dir_rel: string | null;
  anki_mod: number | null;
  missing: boolean;
  suspended: boolean;
  possible_duplicate: boolean;
  added_at: string;
  updated_at: string;
  senses: LanguageSense[];
  examples: LanguageExample[];
  notes_text: LanguageNoteText[];
  tags: string[];
  media: LanguageMedia[];
  media_by_role: Record<LanguageMediaRole, LanguageMedia | null>;
  progress: LanguageProgress[];
  stage: LanguageStage;
  weakest_interval: number;
  due_now: boolean;
  last_reviewed_at: string | null;
  personal_note: string;
  favorite: boolean;
  overridden_fields: string[];
  edited: boolean;
  practice: {
    answers: number;
    correct: number;
    accuracy: number | null;
  };
}

export interface WordsQuery {
  query?: string;
  deck?: string;
  tag?: string;
  stage?: string;
  source?: string;
  favorites?: boolean;
  missing?: boolean;
  suspended?: boolean;
  list_id?: string;
  content?: 'all' | 'sentences' | 'grammar';
  sort?: string;
  descending?: boolean;
  offset?: number;
  limit?: number;
}

export interface WordsResponse {
  format: string;
  items: LanguageWord[];
  total: number;
  offset: number;
  limit: number;
}

export interface LanguageList {
  list_id: string;
  name: string;
  description: string;
  word_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface LanguagePracticeStats {
  format: string;
  totals: {
    sessions: number;
    completed_sessions: number;
    answers: number;
    correct: number;
    accuracy: number | null;
    practiced_words: number;
  };
  activity: Array<{
    date: string;
    answers: number;
    correct: number;
    accuracy: number | null;
  }>;
  streak: {
    current_days: number;
    active_days: number;
  };
  words: Array<{
    word_id: string;
    answers: number;
    correct: number;
    accuracy: number | null;
    last_answered_at: string | null;
  }>;
}

export interface LanguageStatus {
  format: string;
  enabled: boolean;
  counts: Record<string, number>;
  storage: Record<string, string>;
  anki: {
    port: number;
    sync_mode: 'incremental' | 'full';
    api_key_source: string;
    cached_probe: Record<string, unknown> | null;
  };
  last_sync: Record<string, unknown> | null;
  jobs: LanguageImportJob[];
}

export interface LanguageSettings {
  format: string;
  port: number;
  sync_mode: 'incremental' | 'full';
  cached_probe: Record<string, unknown> | null;
  updated_at: string | null;
  has_api_key: boolean;
  api_key_source: string;
  has_krdict_api_key: boolean;
  krdict_api_key_source: string;
}

export interface LanguageAnalyzerMatch {
  word_id: string;
  headword: string;
  sentence_form: string;
  english: string;
  mongolian: string;
  source: 'anki' | 'manual';
  stage: LanguageStage;
  has_word_audio: boolean;
  has_sentence_audio: boolean;
  provenance: string;
}

export interface LanguageGrammarRule {
  rule_id: string;
  pattern: string;
  title: string;
  summary: string;
  category: string;
  level: string;
  provenance: string;
  token_indexes: number[];
}

export interface LanguageAnalyzerToken {
  token_index: number;
  sentence_index: number;
  group: number;
  surface: string;
  original_surface: string;
  form: string;
  lemma: string;
  group_lemma?: string;
  tag: string;
  pos: string;
  color_group: string;
  start: number;
  end: number;
  romanization: string;
  grammar: Omit<LanguageGrammarRule, 'token_indexes'> | null;
}

export interface LanguageAnalysis {
  format: string;
  text: string;
  romanization: string;
  sentences: Array<{
    sentence_index: number;
    text: string;
    start: number;
    end: number;
    romanization: string;
    token_indexes: number[];
  }>;
  tokens: LanguageAnalyzerToken[];
  grammar: LanguageGrammarRule[];
  engine: {
    name: string;
    version: string | null;
    provenance: string;
  };
  cached: boolean;
  library: {
    token_matches: Record<string, LanguageAnalyzerMatch[]>;
    exact_example: {
      word_id: string;
      headword: string;
      translations: LanguageTranslation[];
      has_sentence_audio: boolean;
      provenance: string;
    } | null;
  };
  translation: {
    en: string;
    mn: string;
    provenance: string;
    editable: boolean;
  };
}

export interface LanguageSavedAnalysis {
  analysis_id: string;
  source_text: string;
  translation_en: string;
  translation_mn: string;
  analysis: LanguageAnalysis;
  created_at: string;
  updated_at: string;
}

export interface LanguageAnalyzerStatus {
  format: string;
  available: boolean;
  engine: string;
  engine_version: string | null;
  romanizer: string;
  romanizer_version: string | null;
  offline: boolean;
  max_text_length: number;
  saved_analyses: number;
  dictionary: {
    provider: string;
    configured: boolean;
    key_source: string;
    automatic: boolean;
  };
}

export interface LanguageImportPreview {
  token: string;
  selection_sha256: string;
  deck_pattern: string;
  note_count: number;
  note_types: string[];
  proposed_profiles: Array<Record<string, unknown>>;
  duplicates: Array<{
    manual_word_id: string;
    headword: string;
    anki_note_ids: string[];
  }>;
  expires_at: string;
}

export interface LanguageImportJob {
  job_id: string;
  status: string;
  phase: string;
  progress: number;
  processed: number;
  total: number;
  counts: Record<string, number>;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ManualWordInput {
  lang?: string;
  headword: string;
  sentence_form?: string;
  reading?: string;
  deck?: string;
  sort_index?: number | null;
  senses?: LanguageSense[];
  examples?: LanguageExample[];
  notes_text?: LanguageNoteText[];
  tags?: string[];
  personal_note?: string;
}

async function apiError(response: Response): Promise<Error> {
  let detail = '';
  try {
    const payload = await response.json();
    detail = typeof payload?.detail === 'string' ? payload.detail : '';
  } catch {
    // Use the status line for a non-JSON response.
  }
  return new Error(detail || `API ${response.status}: ${response.statusText}`);
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${BASE}${path}`, options);
  if (!response.ok) throw await apiError(response);
  return response.json();
}

function jsonRequest(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}

function queryString(query: WordsQuery): string {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value));
    }
  });
  const encoded = params.toString();
  return encoded ? `?${encoded}` : '';
}

export async function fileToBase64(file: File): Promise<string> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error('Could not read file'));
    reader.readAsDataURL(file);
  });
  return dataUrl.slice(dataUrl.indexOf(',') + 1);
}

export const languageApi = {
  status: () => request<LanguageStatus>('/status'),
  words: (query: WordsQuery = {}) =>
    request<WordsResponse>(`/words${queryString(query)}`),
  word: (wordId: string) =>
    request<{ word: LanguageWord }>(`/words/${encodeURIComponent(wordId)}`),
  createWord: (payload: ManualWordInput) =>
    request<{ word: LanguageWord }>('/words', jsonRequest('POST', payload)),
  updateWord: (wordId: string, payload: Partial<ManualWordInput>) =>
    request<{ word: LanguageWord }>(
      `/words/${encodeURIComponent(wordId)}`,
      jsonRequest('PATCH', payload),
    ),
  retireWord: (wordId: string) =>
    request<{ retired: string }>(
      `/words/${encodeURIComponent(wordId)}`,
      { method: 'DELETE' },
    ),
  revertOverrides: (wordId: string, field?: string) =>
    request<{ word: LanguageWord }>(
      `/words/${encodeURIComponent(wordId)}/override${field ? `?field=${encodeURIComponent(field)}` : ''}`,
      { method: 'DELETE' },
    ),
  attachMedia: (
    wordId: string,
    role: LanguageMediaRole,
    filename: string,
    contentBase64: string,
  ) =>
    request<Record<string, unknown>>(
      `/words/${encodeURIComponent(wordId)}/media`,
      jsonRequest('POST', {
        role,
        filename,
        content_base64: contentBase64,
      }),
    ),
  mediaUrl: (wordId: string, role: LanguageMediaRole) =>
    `${BASE}/media/${encodeURIComponent(wordId)}/${role}`,
  decks: () =>
    request<{ items: Array<{ deck: string; words: number; missing: number }> }>('/decks'),
  today: () => request<{ items: LanguageWord[]; cached: boolean }>('/today'),
  favorites: () => request<{ word_ids: string[] }>('/favorites'),
  favorite: (wordId: string, favorite: boolean) =>
    request<{ word_id: string; favorite: boolean }>(
      `/favorites/${encodeURIComponent(wordId)}`,
      jsonRequest('PUT', { favorite }),
    ),
  lists: () => request<{ items: LanguageList[] }>('/lists'),
  createList: (name: string, description = '') =>
    request<{ item: LanguageList }>(
      '/lists',
      jsonRequest('POST', { name, description }),
    ),
  updateList: (listId: string, name: string, description = '') =>
    request<{ item: LanguageList }>(
      `/lists/${encodeURIComponent(listId)}`,
      jsonRequest('PATCH', { name, description }),
    ),
  retireList: (listId: string) =>
    request<{ retired: string }>(
      `/lists/${encodeURIComponent(listId)}`,
      { method: 'DELETE' },
    ),
  setListMembership: (listId: string, wordIds: string[], member: boolean) =>
    request<Record<string, unknown>>(
      `/lists/${encodeURIComponent(listId)}/items`,
      jsonRequest('PUT', { word_ids: wordIds, member }),
    ),
  bulk: (
    wordIds: string[],
    action: 'favorite' | 'unfavorite' | 'add_to_list' | 'remove_from_list',
    listId?: string,
  ) =>
    request<Record<string, unknown>>(
      '/bulk',
      jsonRequest('POST', {
        word_ids: wordIds,
        action,
        list_id: listId ?? null,
      }),
    ),
  practiceSession: (
    mode: 'ko_meaning' | 'meaning_ko' | 'audio_meaning' | 'cloze',
    wordIds: string[],
    length: number,
  ) =>
    request<{
      session: {
        session_id: string;
        mode: string;
        word_ids: string[];
        status: string;
      };
    }>('/practice/session', jsonRequest('POST', {
      mode,
      word_ids: wordIds,
      length,
    })),
  practiceAnswer: (
    sessionId: string,
    wordId: string,
    correct: boolean,
    finish: boolean,
  ) =>
    request<Record<string, unknown>>(
      '/practice/answer',
      jsonRequest('POST', {
        session_id: sessionId,
        word_id: wordId,
        correct,
        finish,
      }),
    ),
  practiceStats: () => request<LanguagePracticeStats>('/practice/stats'),
  settings: () => request<LanguageSettings>('/settings'),
  saveSettings: (
    port: number,
    syncMode: 'incremental' | 'full',
    apiKey?: string,
    clearApiKey = false,
    krdictApiKey?: string,
    clearKrdictApiKey = false,
  ) =>
    request<LanguageSettings>(
      '/settings',
      jsonRequest('PUT', {
        port,
        sync_mode: syncMode,
        api_key: apiKey || null,
        clear_api_key: clearApiKey,
        krdict_api_key: krdictApiKey || null,
        clear_krdict_api_key: clearKrdictApiKey,
      }),
    ),
  analyzerStatus: () =>
    request<LanguageAnalyzerStatus>('/analyzer/status'),
  analyze: (text: string) =>
    request<LanguageAnalysis>(
      '/analyzer/analyze',
      jsonRequest('POST', { text }),
    ),
  analyzerHistory: () =>
    request<{ items: LanguageSavedAnalysis[] }>('/analyzer/history'),
  saveAnalysis: (
    analysis: LanguageAnalysis,
    translationEn: string,
    translationMn: string,
    analysisId?: string,
  ) =>
    request<{ item: LanguageSavedAnalysis }>(
      '/analyzer/history',
      jsonRequest('POST', {
        analysis_id: analysisId ?? null,
        text: analysis.text,
        translation_en: translationEn,
        translation_mn: translationMn,
        analysis,
      }),
    ),
  retireAnalysis: (analysisId: string) =>
    request<{ retired: string }>(
      `/analyzer/history/${encodeURIComponent(analysisId)}`,
      { method: 'DELETE' },
    ),
  dictionaryLookup: (query: string) =>
    request<{
      query: string;
      provider: string;
      provenance: string;
      cached: boolean;
      entries: Array<{
        word: string;
        part_of_speech: string;
        language: string;
        translated_word: string;
        definition: string;
        sense_order: string | number | null;
        target_code: string | number | null;
      }>;
    }>(
      '/analyzer/dictionary',
      jsonRequest('POST', { query }),
    ),
  profiles: () =>
    request<{
      items: Array<{
        note_type: string;
        mapping: Record<string, unknown>;
        updated_at: string;
      }>;
    }>('/profiles'),
  saveProfile: (noteType: string, mapping: Record<string, unknown>) =>
    request<Record<string, unknown>>(
      `/profiles/${encodeURIComponent(noteType)}`,
      jsonRequest('PUT', { mapping }),
    ),
  probe: () => request<Record<string, unknown>>('/anki/probe'),
  preview: (deckPattern: string) =>
    request<{ preview: LanguageImportPreview }>(
      '/anki/preview',
      jsonRequest('POST', { deck_pattern: deckPattern }),
    ),
  startImport: (
    preview: LanguageImportPreview,
    mergeManualIds: string[],
  ) =>
    request<{ job: LanguageImportJob }>(
      '/anki/import',
      jsonRequest('POST', {
        preview_token: preview.token,
        selection_sha256: preview.selection_sha256,
        authorized: true,
        merge_manual_ids: mergeManualIds,
      }),
    ),
  importJob: (jobId: string) =>
    request<{ job: LanguageImportJob }>(
      `/anki/jobs/${encodeURIComponent(jobId)}`,
    ),
  cancelImport: (jobId: string) =>
    request<{ job: LanguageImportJob }>(
      `/anki/jobs/${encodeURIComponent(jobId)}`,
      { method: 'DELETE' },
    ),
  exportUrl: `${BASE}/export`,
};
