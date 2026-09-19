import {
  activeCollectionId,
  activeModule,
  selectedImageId,
  viewMode,
} from '../lib/stores';

export interface DrawerAction {
  id: string;
  label: string;
  iconSrc: string;
  run: () => void;
}

export interface ModuleUiDescriptor {
  slug: string;
  iconSrc: string | null;
  accent: string;
  drawerActions: DrawerAction[];
  activate?: () => void;
}

const UI_DESCRIPTORS: Record<string, ModuleUiDescriptor> = {
  files: {
    slug: 'files',
    iconSrc: null,
    accent: '#a855f7',
    drawerActions: [],
  },
  danbooru: {
    slug: 'danbooru',
    iconSrc: '/logo.svg',
    accent: '#a855f7',
    activate: () => {
      activeCollectionId.set(null);
      selectedImageId.set(null);
      viewMode.set('home');
    },
    drawerActions: [
      {
        id: 'profile',
        label: 'Profile',
        iconSrc: '/profile-avatar.svg',
        run: () => {
          activeModule.set('danbooru');
          activeCollectionId.set(null);
          selectedImageId.set(null);
          viewMode.set('profile');
        },
      },
    ],
  },
  reddit: {
    slug: 'reddit',
    iconSrc: '/reddit-logo.svg',
    accent: '#ff4500',
    drawerActions: [],
  },
  karaoke: {
    slug: 'karaoke',
    iconSrc: null,
    accent: '#67e8f9',
    drawerActions: [],
  },
  youtube: {
    slug: 'youtube',
    iconSrc: null,
    accent: '#ff4e45',
    drawerActions: [],
  },
  language: {
    slug: 'language',
    iconSrc: '/language-logo.svg',
    accent: '#fbbf24',
    drawerActions: [],
  },
  manayomi: {
    slug: 'manayomi',
    iconSrc: null,
    accent: '#c084fc',
    drawerActions: [],
  },
};

const FALLBACK_UI: ModuleUiDescriptor = {
  slug: 'unknown',
  iconSrc: null,
  accent: '#a855f7',
  drawerActions: [],
};

export function moduleUi(slug: string): ModuleUiDescriptor {
  return UI_DESCRIPTORS[slug] ?? { ...FALLBACK_UI, slug };
}

export function activateModule(slug: string): void {
  moduleUi(slug).activate?.();
  activeModule.set(slug);
}
