import FilesView from '../components/FilesView.svelte';
import DanbooruSurface from './danbooru/DanbooruSurface.svelte';
import RedditSurface from './reddit/RedditSurface.svelte';
import KaraokeSurface from './karaoke/KaraokeSurface.svelte';
import YouTubeSurface from './youtube/YouTubeSurface.svelte';
import LanguageSurface from './language/LanguageSurface.svelte';
import ManayomiSurface from './manayomi/ManayomiSurface.svelte';

const SURFACES = {
  files: FilesView,
  danbooru: DanbooruSurface,
  reddit: RedditSurface,
  karaoke: KaraokeSurface,
  youtube: YouTubeSurface,
  language: LanguageSurface,
  manayomi: ManayomiSurface,
} as const;

export function surfaceComponent(slug: string) {
  return SURFACES[slug as keyof typeof SURFACES] ?? FilesView;
}
