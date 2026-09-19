export type ThemeId =
  | 'keivotos-dark'
  | 'keivotos-light'
  | 'oled-black'
  | 'gallery'
  | 'stage'
  | 'catppuccin'
  | 'midnight-dusk';

export interface ThemeTokens {
  /* Background layers (deepest → most elevated) */
  '--bg-base': string;
  '--bg-surface': string;
  '--bg-elevated': string;
  '--bg-overlay': string;
  '--bg-inset': string;

  /* Text */
  '--text-primary': string;
  '--text-secondary': string;
  '--text-muted': string;

  /* Borders */
  '--border-default': string;
  '--border-subtle': string;

  /* Suite accent (purple by default, modules override --module-accent) */
  '--accent': string;
  '--accent-hover': string;
  '--accent-text': string;
  '--accent-muted': string;

  /* Scrollbar */
  '--scrollbar-track': string;
  '--scrollbar-thumb': string;
  '--scrollbar-thumb-hover': string;

  /* Misc */
  '--color-scheme': 'dark' | 'light';
  '--backdrop-tint': string;
  '--input-bg': string;
  '--input-border': string;
  '--hover-bg': string;
  '--active-bg': string;
  '--danger': string;
  '--success': string;
  '--warning': string;
}

export interface ThemeDefinition {
  id: ThemeId;
  label: string;
  group: 'core' | 'community';
  tokens: ThemeTokens;
}

const keivotosDark: ThemeTokens = {
  '--bg-base': '#0b0b10',
  '--bg-surface': '#0f0f14',
  '--bg-elevated': '#16161e',
  '--bg-overlay': '#1a1a24',
  '--bg-inset': '#0a0a0e',
  '--text-primary': '#e0e0e8',
  '--text-secondary': '#a0a0b0',
  '--text-muted': '#6a6a7a',
  '--border-default': '#2a2a3a',
  '--border-subtle': '#1e1e2a',
  '--accent': '#a855f7',
  '--accent-hover': '#9333ea',
  '--accent-text': '#ffffff',
  '--accent-muted': 'rgba(168, 85, 247, 0.15)',
  '--scrollbar-track': '#1a1a24',
  '--scrollbar-thumb': '#3a3a4a',
  '--scrollbar-thumb-hover': '#4a4a5a',
  '--color-scheme': 'dark',
  '--backdrop-tint': 'rgba(0, 0, 0, 0.6)',
  '--input-bg': '#16161e',
  '--input-border': '#2a2a3a',
  '--hover-bg': 'rgba(255, 255, 255, 0.05)',
  '--active-bg': 'rgba(255, 255, 255, 0.08)',
  '--danger': '#ef4444',
  '--success': '#22c55e',
  '--warning': '#eab308',
};

const keivotosLight: ThemeTokens = {
  '--bg-base': '#f8f8fc',
  '--bg-surface': '#ffffff',
  '--bg-elevated': '#f0f0f6',
  '--bg-overlay': '#e8e8f0',
  '--bg-inset': '#f4f4fa',
  '--text-primary': '#1a1a2e',
  '--text-secondary': '#4a4a60',
  '--text-muted': '#8a8a9e',
  '--border-default': '#d0d0de',
  '--border-subtle': '#e0e0ea',
  '--accent': '#7c3aed',
  '--accent-hover': '#6d28d9',
  '--accent-text': '#ffffff',
  '--accent-muted': 'rgba(124, 58, 237, 0.1)',
  '--scrollbar-track': '#ececf4',
  '--scrollbar-thumb': '#c0c0cc',
  '--scrollbar-thumb-hover': '#a0a0b0',
  '--color-scheme': 'light',
  '--backdrop-tint': 'rgba(0, 0, 0, 0.3)',
  '--input-bg': '#ffffff',
  '--input-border': '#d0d0de',
  '--hover-bg': 'rgba(0, 0, 0, 0.04)',
  '--active-bg': 'rgba(0, 0, 0, 0.07)',
  '--danger': '#dc2626',
  '--success': '#16a34a',
  '--warning': '#ca8a04',
};

const oledBlack: ThemeTokens = {
  '--bg-base': '#000000',
  '--bg-surface': '#050505',
  '--bg-elevated': '#0c0c0c',
  '--bg-overlay': '#141414',
  '--bg-inset': '#000000',
  '--text-primary': '#e8e8e8',
  '--text-secondary': '#a0a0a0',
  '--text-muted': '#606060',
  '--border-default': '#1e1e1e',
  '--border-subtle': '#141414',
  '--accent': '#a855f7',
  '--accent-hover': '#9333ea',
  '--accent-text': '#ffffff',
  '--accent-muted': 'rgba(168, 85, 247, 0.12)',
  '--scrollbar-track': '#0a0a0a',
  '--scrollbar-thumb': '#2a2a2a',
  '--scrollbar-thumb-hover': '#3a3a3a',
  '--color-scheme': 'dark',
  '--backdrop-tint': 'rgba(0, 0, 0, 0.8)',
  '--input-bg': '#0c0c0c',
  '--input-border': '#1e1e1e',
  '--hover-bg': 'rgba(255, 255, 255, 0.04)',
  '--active-bg': 'rgba(255, 255, 255, 0.06)',
  '--danger': '#ef4444',
  '--success': '#22c55e',
  '--warning': '#eab308',
};

const gallery: ThemeTokens = {
  '--bg-base': '#0a0e14',
  '--bg-surface': '#0f1318',
  '--bg-elevated': '#161b22',
  '--bg-overlay': '#1c2128',
  '--bg-inset': '#080c10',
  '--text-primary': '#d0d8e4',
  '--text-secondary': '#8b98a8',
  '--text-muted': '#5a6676',
  '--border-default': '#262e38',
  '--border-subtle': '#1c2430',
  '--accent': '#0075f8',
  '--accent-hover': '#0060d0',
  '--accent-text': '#ffffff',
  '--accent-muted': 'rgba(0, 117, 248, 0.15)',
  '--scrollbar-track': '#0f1318',
  '--scrollbar-thumb': '#2a3440',
  '--scrollbar-thumb-hover': '#3a4450',
  '--color-scheme': 'dark',
  '--backdrop-tint': 'rgba(0, 0, 0, 0.65)',
  '--input-bg': '#161b22',
  '--input-border': '#262e38',
  '--hover-bg': 'rgba(255, 255, 255, 0.05)',
  '--active-bg': 'rgba(255, 255, 255, 0.08)',
  '--danger': '#f85149',
  '--success': '#3fb950',
  '--warning': '#d29922',
};

const stage: ThemeTokens = {
  '--bg-base': '#0a1014',
  '--bg-surface': '#0c1113',
  '--bg-elevated': '#11181a',
  '--bg-overlay': '#182022',
  '--bg-inset': '#080e12',
  '--text-primary': '#dce8ec',
  '--text-secondary': '#8aa0a8',
  '--text-muted': '#5a7078',
  '--border-default': '#1e2c30',
  '--border-subtle': '#162428',
  '--accent': '#67e8f9',
  '--accent-hover': '#22d3ee',
  '--accent-text': '#0a1014',
  '--accent-muted': 'rgba(103, 232, 249, 0.12)',
  '--scrollbar-track': '#0c1113',
  '--scrollbar-thumb': '#243438',
  '--scrollbar-thumb-hover': '#344448',
  '--color-scheme': 'dark',
  '--backdrop-tint': 'rgba(0, 0, 0, 0.65)',
  '--input-bg': '#11181a',
  '--input-border': '#1e2c30',
  '--hover-bg': 'rgba(103, 232, 249, 0.05)',
  '--active-bg': 'rgba(103, 232, 249, 0.08)',
  '--danger': '#f87171',
  '--success': '#34d399',
  '--warning': '#fbbf24',
};

const catppuccin: ThemeTokens = {
  '--bg-base': '#1e1e2e',
  '--bg-surface': '#181825',
  '--bg-elevated': '#313244',
  '--bg-overlay': '#45475a',
  '--bg-inset': '#11111b',
  '--text-primary': '#cdd6f4',
  '--text-secondary': '#bac2de',
  '--text-muted': '#6c7086',
  '--border-default': '#45475a',
  '--border-subtle': '#313244',
  '--accent': '#cba6f7',
  '--accent-hover': '#b4befe',
  '--accent-text': '#1e1e2e',
  '--accent-muted': 'rgba(203, 166, 247, 0.12)',
  '--scrollbar-track': '#181825',
  '--scrollbar-thumb': '#45475a',
  '--scrollbar-thumb-hover': '#585b70',
  '--color-scheme': 'dark',
  '--backdrop-tint': 'rgba(17, 17, 27, 0.7)',
  '--input-bg': '#313244',
  '--input-border': '#45475a',
  '--hover-bg': 'rgba(205, 214, 244, 0.05)',
  '--active-bg': 'rgba(205, 214, 244, 0.08)',
  '--danger': '#f38ba8',
  '--success': '#a6e3a1',
  '--warning': '#f9e2af',
};

const midnightDusk: ThemeTokens = {
  '--bg-base': '#16151d',
  '--bg-surface': '#1c1b25',
  '--bg-elevated': '#221320',
  '--bg-overlay': '#281624',
  '--bg-inset': '#12111a',
  '--text-primary': '#e5e1e5',
  '--text-secondary': '#d6c1c4',
  '--text-muted': '#9f8c8f',
  '--border-default': '#2f1f2c',
  '--border-subtle': '#251522',
  '--accent': '#f02475',
  '--accent-hover': '#bd1c5c',
  '--accent-text': '#ffffff',
  '--accent-muted': 'rgba(240, 36, 117, 0.12)',
  '--scrollbar-track': '#1c1b25',
  '--scrollbar-thumb': '#2d1c2a',
  '--scrollbar-thumb-hover': '#3d2c3a',
  '--color-scheme': 'dark',
  '--backdrop-tint': 'rgba(22, 21, 29, 0.75)',
  '--input-bg': '#221320',
  '--input-border': '#2f1f2c',
  '--hover-bg': 'rgba(240, 36, 117, 0.06)',
  '--active-bg': 'rgba(240, 36, 117, 0.1)',
  '--danger': '#f87171',
  '--success': '#55971c',
  '--warning': '#fbbf24',
};

export const themes: ThemeDefinition[] = [
  { id: 'keivotos-dark', label: 'Keivotos Dark', group: 'core', tokens: keivotosDark },
  { id: 'keivotos-light', label: 'Keivotos Light', group: 'core', tokens: keivotosLight },
  { id: 'oled-black', label: 'OLED Black', group: 'core', tokens: oledBlack },
  { id: 'gallery', label: 'Gallery', group: 'core', tokens: gallery },
  { id: 'stage', label: 'Stage', group: 'core', tokens: stage },
  { id: 'catppuccin', label: 'Catppuccin Mocha', group: 'community', tokens: catppuccin },
  { id: 'midnight-dusk', label: 'Midnight Dusk', group: 'community', tokens: midnightDusk },
];

export const themeById = Object.fromEntries(themes.map(t => [t.id, t])) as Record<ThemeId, ThemeDefinition>;

export function applyTheme(id: ThemeId): void {
  const theme = themeById[id];
  if (!theme) return;
  const root = document.documentElement;
  const tokens = theme.tokens;
  for (const [prop, value] of Object.entries(tokens)) {
    if (prop === '--color-scheme') {
      root.style.colorScheme = value;
    } else {
      root.style.setProperty(prop, value);
    }
  }
  root.dataset.theme = id;
  root.dataset.themeMode = tokens['--color-scheme'];
}
