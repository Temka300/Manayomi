export interface SubtitleCue {
  index?: number;
  start: number;
  end: number;
  text: string;
  raw?: string;
  translation?: string;
  romaji?: string;
}

export interface SubtitleTrack {
  track_id: string;
  label: string;
  language: string;
  format: 'ass' | 'ssa' | 'srt' | 'vtt' | 'lrc' | string;
  url: string;
  sha256?: string;
  source_kind?: string;
  automatic?: boolean;
  cues?: SubtitleCue[];
}

export interface MediaSourceOption {
  id: string;
  label: string;
  src: string;
  description?: string;
}

export interface MediaAudioOption {
  id: string;
  label: string;
  language?: string;
}

export interface MediaQueueItem {
  id: string;
  title: string;
  subtitle?: string;
}

export interface MediaProgress {
  position: number;
  duration: number;
  completed: boolean;
  subtitleTrackId: string | null;
  subtitleOffset: number;
  repeatMode: 'off' | 'all' | 'one';
  shuffle: boolean;
}

export interface MinimizeDetail {
  src: string;
  position: number;
  duration: number;
}

