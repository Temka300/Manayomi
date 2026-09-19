<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import LocalMediaPlayer from '../../components/media/LocalMediaPlayer.svelte';
  import type { MediaProgress, MediaSourceOption, SubtitleTrack } from '../../lib/media';
  import { miniPlayerState, playerCenterControls, playerControlReveal, playerDarkenOverlay } from '../../lib/stores';
  import { youtubeApi, type YouTubeLibraryItem } from '../../lib/youtubeApi';
  import type { MinimizeDetail } from '../../lib/media';

  export let item: YouTubeLibraryItem;
  export let queue: YouTubeLibraryItem[] = [];
  export let sourceVariants: YouTubeLibraryItem[] = [];
  const dispatch = createEventDispatcher<{ close: void; progress: MediaProgress }>();

  function handleMinimize(event: CustomEvent<MinimizeDetail>) {
    miniPlayerState.set({
      src: event.detail.src,
      title: item.title,
      subtitle: item.channel,
      poster: item.thumbnail_path ? youtubeApi.mediaUrl(item.item_id, item.thumbnail_path) : null,
      accent: '#ff4e45',
      position: event.detail.position,
      duration: event.detail.duration,
      module: 'youtube',
      itemId: item.item_id,
    });
    dispatch('close');
  }

  async function saveProgress(event: CustomEvent<MediaProgress>): Promise<void> {
    dispatch('progress', event.detail);
    try {
      const response = await youtubeApi.savePlayback(item.item_id, {
        position_seconds: event.detail.position,
        duration_seconds: event.detail.duration || null,
        completed: event.detail.completed,
      });
      item.playback = response.playback;
    } catch {
      // Playback stays uninterrupted. The next periodic save retries.
    }
  }

  function subtitleLanguage(path: string): string {
    const filename = path.replaceAll('\\', '/').split('/').at(-1) ?? path;
    const parts = filename.split('.');
    return parts.length > 2 ? parts.at(-2) ?? 'und' : 'und';
  }

  $: tracks = item.subtitles.map((track): SubtitleTrack => ({
    track_id: `${item.item_id}:${track.path}`,
    label: `${track.automatic ? 'Automatic captions' : 'Subtitles'} · ${subtitleLanguage(track.path)}`,
    language: subtitleLanguage(track.path),
    format: track.format,
    source_kind: track.automatic
      ? 'youtube-automatic-caption'
      : 'youtube-manual-subtitle',
    automatic: track.automatic,
    url: youtubeApi.mediaUrl(item.item_id, track.path),
  }));
  $: sameVideoVariants = sourceVariants.filter((entry) => entry.video_id === item.video_id);
  $: sourceOptions = sameVideoVariants.map((entry): MediaSourceOption => ({
    id: entry.item_id,
    label: entry.quality_label,
    src: youtubeApi.mediaUrl(entry.item_id, entry.video_path),
    description: entry.video_path,
  }));
  $: currentIndex = queue.findIndex((entry) => entry.item_id === item.item_id);
</script>

<LocalMediaPlayer
  src={youtubeApi.mediaUrl(item.item_id, item.video_path)}
  title={item.title}
  subtitle={item.channel}
  poster={item.thumbnail_path ? youtubeApi.mediaUrl(item.item_id, item.thumbnail_path) : null}
  {tracks}
  {sourceOptions}
  initialPosition={item.playback?.position_seconds ?? 0}
  qualityLabel={item.quality_label}
  hasPrevious={currentIndex > 0}
  hasNext={currentIndex >= 0 && currentIndex < queue.length - 1}
  queueItems={queue.map((entry) => ({
    id: entry.item_id,
    title: entry.title,
    subtitle: `${entry.channel} · ${entry.quality_label}`,
  }))}
  currentItemId={item.item_id}
  showCenterControls={$playerCenterControls}
  showDarkenOverlay={$playerDarkenOverlay}
  controlRevealMode={$playerControlReveal}
  accent="#ff4e45"
  appName="Keivotos YouTube"
  backLabel="Back to YouTube library"
  panelLabel="Subtitles & transcript"
  allowSubtitleAttach={false}
  on:close
  on:minimize={handleMinimize}
  on:previous
  on:next
  on:shuffle
  on:select
  on:progress={saveProgress}
  on:attach
  on:started
/>
