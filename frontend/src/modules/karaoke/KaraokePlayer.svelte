<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import LocalMediaPlayer from '../../components/media/LocalMediaPlayer.svelte';
  import type { MinimizeDetail } from '../../lib/media';
  import { karaokeApi, type KaraokeItem } from '../../lib/karaokeApi';
  import type { SubtitleTrack } from '../../lib/media';
  import { miniPlayerState, playerCenterControls, playerControlReveal, playerDarkenOverlay } from '../../lib/stores';

  export let item: KaraokeItem;
  export let queue: KaraokeItem[] = [];
  export let performanceMode = false;
  export let showTranslations = true;

  const dispatch = createEventDispatcher<{ close: void }>();

  function handleMinimize(event: CustomEvent<MinimizeDetail>) {
    miniPlayerState.set({
      src: event.detail.src,
      title: item.title,
      subtitle: item.subtitle,
      poster: item.thumbnail ? karaokeApi.mediaUrl(item.item_id, item.thumbnail) : null,
      accent: '#67e8f9',
      position: event.detail.position,
      duration: event.detail.duration,
      module: 'karaoke',
      itemId: item.item_id,
    });
    dispatch('close');
  }

  $: tracks = item.lyrics.map((track): SubtitleTrack => ({
    track_id: track.lyric_id,
    label: track.label,
    language: track.language,
    format: track.format,
    source_kind: track.source_kind,
    url: track.format.toLowerCase() === 'vtt'
      ? karaokeApi.captionUrl(item.item_id, track.lyric_id)
      : karaokeApi.mediaUrl(item.item_id, track.relative_path),
    sha256: track.sha256,
    cues: track.cues,
  }));
  $: playback = item.playback;
  $: currentIndex = queue.findIndex((entry) => entry.item_id === item.item_id);
</script>

<LocalMediaPlayer
  src={karaokeApi.mediaUrl(item.item_id, item.primary_video)}
  title={item.title}
  subtitle={item.subtitle}
  poster={item.thumbnail ? karaokeApi.mediaUrl(item.item_id, item.thumbnail) : null}
  {tracks}
  initialPosition={0}
  initialTrackId={playback?.lyric_id ?? null}
  initialOffset={playback?.lyric_offset_seconds ?? 0}
  initialRepeatMode={playback?.repeat_mode ?? 'off'}
  initialShuffle={Boolean(playback?.shuffle)}
  qualityLabel={item.provider === 'kara-moe' ? 'Kara.moe' : 'Local'}
  hasPrevious={currentIndex > 0}
  hasNext={currentIndex >= 0 && currentIndex < queue.length - 1}
  queueItems={queue.map((entry) => ({
    id: entry.item_id,
    title: entry.title,
    subtitle: entry.subtitle,
  }))}
  currentItemId={item.item_id}
  showCenterControls={$playerCenterControls}
  showDarkenOverlay={$playerDarkenOverlay}
  controlRevealMode={$playerControlReveal}
  accent="#67e8f9"
  appName="Keivotos Karaoke"
  backLabel="Back to Karaoke detail"
  panelLabel="Subtitles & lyrics"
  allowSubtitleAttach={true}
  {performanceMode}
  {showTranslations}
  on:close
  on:minimize={handleMinimize}
  on:previous
  on:next
  on:shuffle
  on:select
  on:progress
  on:attach
  on:started
/>
