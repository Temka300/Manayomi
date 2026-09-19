<script lang="ts">
  import { createEventDispatcher, onMount, tick } from 'svelte';
  import {
    api,
    type DanbooruCredentialStatus,
    type FolderInfo,
    type FolderRemovalMode,
    type FolderRemovalPreview,
    type ToolInfo,
    type ToolStatus,
  } from '../lib/api';
  import BackupRestoreSettings from './BackupRestoreSettings.svelte';
  import LibraryImportSettings from './LibraryImportSettings.svelte';
  import ThumbnailCacheSettings from './ThumbnailCacheSettings.svelte';
  import RedditSettings from '../modules/reddit/RedditSettings.svelte';
  import KaraokeSettings from '../modules/karaoke/KaraokeSettings.svelte';
  import YouTubeSettings from '../modules/youtube/YouTubeSettings.svelte';
  import LanguageSettings from '../modules/language/LanguageSettings.svelte';
  import { SUITE_NAME } from '../lib/product';
  import { MODULE_NAME } from '../modules/danbooru/identity';
  import { prepareSettingsPresentation, restoreSettingsPresentation } from '../lib/settingsPresentation';
  import { focusTrap } from '../lib/focusTrap';
  import {
    activeRating,
    appTheme,
    artistNotificationIntervalMinutes,
    artistNotificationsEnabled,
    duplicateScope,
    duplicatesOnly,
    fitMode,
    heartSpamEnabled,
    homeLayout,
    imagePageSize,
    imagePageSizeOptions,
    imageRefreshToken,
    imageSize,
    imageSizeOptions,
    interfaceScale,
    mediaPlayback,
    motionPreference,
    miniPlayerStyle,
    playerCenterControls,
    playerDarkenOverlay,
    sidebarOpen,
    sortBy,
    sortOrder,
    startupView,
    tagBannerHeight,
  } from '../lib/stores';
  import type { ArtistNotificationIntervalMinutes, DuplicateScope, FitMode, HomeLayout, ImagePageSize, ImageSize, InterfaceScale, MediaPlayback, MotionPreference, StartupView, ThemeId } from '../lib/stores';
  import { themes } from '../lib/themes';

  const dispatch = createEventDispatcher<{ close: void }>();

  let selectedSection = 'browsing';
  let settingsSearch = '';

  const sections = [
    {
      id: 'browsing',
      label: 'Browsing',
      icon: 'window',
      group: 'Suite',
    },
    {
      id: 'appearance',
      label: 'Display',
      icon: 'palette',
      group: 'Suite',
    },
    {
      id: 'player',
      label: 'Player',
      icon: 'player',
      group: 'Suite',
    },
    {
      id: 'library',
      label: 'Files & Library',
      icon: 'folder',
      group: 'Files',
    },
    {
      id: 'metadata',
      label: 'Danbooru & Metadata',
      icon: 'database',
      group: 'Files',
    },
    {
      id: 'safety',
      label: 'Safety & Recovery',
      icon: 'shield',
      group: 'Files',
    },
    {
      id: 'reddit',
      label: 'Reddit',
      icon: 'reddit',
      group: 'Modules',
    },
    {
      id: 'karaoke',
      label: 'Karaoke',
      icon: 'karaoke',
      group: 'Modules',
    },
    {
      id: 'youtube',
      label: 'YouTube',
      icon: 'youtube',
      group: 'Modules',
    },
    {
      id: 'language',
      label: 'Languages',
      icon: 'language',
      group: 'Modules',
    },
  ];

  type SettingSearchItem = {
    id: string;
    section: string;
    label: string;
    description: string;
    keywords: string[];
  };

  const settingSearchItems: SettingSearchItem[] = [
    { id: 'startup-view', section: 'browsing', label: 'Startup destination', description: `Choose where ${MODULE_NAME} opens.`, keywords: ['home', 'browse', 'last page', 'launch'] },
    { id: 'home-layout', section: 'browsing', label: 'Home layout', description: 'Use the new discovery dashboard or restore the preserved classic Home.', keywords: ['home', 'classic', 'legacy', 'old design', 'discovery', 'dashboard'] },
    { id: 'rating-filter', section: 'browsing', label: 'Default rating', description: 'Choose the rating used for normal browsing.', keywords: ['general', 'sensitive', 'questionable', 'explicit', 'unrated'] },
    { id: 'browse-sort', section: 'browsing', label: 'Browse sort', description: 'Choose the persisted image order.', keywords: ['date', 'downloaded', 'score', 'views', 'name', 'size'] },
    { id: 'page-size', section: 'browsing', label: 'Images per page', description: 'Choose the normal grid page size.', keywords: ['pagination', '10', '20', '30', '50', 'all'] },
    { id: 'sidebar', section: 'browsing', label: 'Sidebar recovery', description: 'Mirror the draggable Browse and Tags edge grip state.', keywords: ['folders', 'visible', 'navigation', 'grip', 'handle', 'draggable'] },
    { id: 'heart-spam', section: 'browsing', label: 'Heart Spam', description: 'Show the playful heart action in ImageDetail.', keywords: ['image detail', 'button'] },
    { id: 'artist-notifications', section: 'browsing', label: 'Artist notifications', description: 'Check followed artists while the app is open.', keywords: ['danbooru', 'followed', 'polling', 'bell', 'timer', 'interval', 'manual check'] },
    { id: 'duplicate-review', section: 'browsing', label: 'Duplicate review', description: 'Choose which duplicate groups to review.', keywords: ['same folder', 'different folders', 'review'] },
    { id: 'theme', section: 'appearance', label: 'Theme', description: 'Choose the suite colour scheme.', keywords: ['dark', 'light', 'oled', 'catppuccin', 'midnight dusk', 'gallery', 'stage', 'color', 'colour'] },
    { id: 'gallery-card-size', section: 'appearance', label: 'Gallery card size', description: 'Set the image-grid scale.', keywords: ['small', 'medium', 'large', 'huge', 'gigantic', 'absurd'] },
    { id: 'image-fit', section: 'appearance', label: 'Image fit', description: 'Crop cards or preserve the full image.', keywords: ['crop', 'contain', 'fill'] },
    { id: 'media-playback', section: 'appearance', label: 'Animated media', description: 'Control GIF and video playback.', keywords: ['autoplay', 'hover', 'never', 'always', 'gif', 'video'] },
    { id: 'motion', section: 'appearance', label: 'Interface motion', description: 'Follow the system or reduce interface animation.', keywords: ['animation', 'reduced motion', 'accessibility'] },
    { id: 'interface-scale', section: 'appearance', label: 'Interface scale', description: 'Use the default or a roomier readable scale.', keywords: ['density', 'comfortable', 'readability', 'text'] },
    { id: 'tag-banner', section: 'appearance', label: 'Tag banner height', description: 'Set tag and artist banner height.', keywords: ['low', 'tall', 'huge', 'artist'] },
    { id: 'player-center-controls', section: 'player', label: 'Center controls', description: 'Toggle the large play/pause and 10-second skip buttons.', keywords: ['skip', 'play', 'pause', '10 seconds', 'forward', 'backward'] },
    { id: 'player-darken-overlay', section: 'player', label: 'Darken overlay', description: 'Dim the video behind the center controls.', keywords: ['dim', 'dark', 'overlay', 'tint', 'background'] },
    { id: 'player-mini-style', section: 'player', label: 'Mini player style', description: 'Choose the persistent player layout when navigating away from a video.', keywords: ['mini', 'pip', 'card', 'bar', 'floating', 'minimize'] },
    { id: 'library-health', section: 'library', label: 'Library health', description: 'See indexed folders, images, and scan state.', keywords: ['status', 'count', 'index'] },
    { id: 'storage-location', section: 'library', label: 'Generated metadata location', description: 'See where databases, sidecars, and derived files live.', keywords: ['documents', 'portable', 'data', 'sidecars', 'sqlite'] },
    { id: 'import-pipeline', section: 'metadata', label: 'Import pipeline', description: 'Run the four resumable library import phases.', keywords: ['discover', 'enrich', 'metadata', 'finalize'] },
    { id: 'folders', section: 'library', label: 'Library folders', description: 'Add, rescan, or remove media roots from the index.', keywords: ['path', 'browse', 'remove', 'register', 'un-index', 'sidecars'] },
    { id: 'rescan', section: 'library', label: 'Re-scan library', description: 'Incrementally reconcile the local index.', keywords: ['sync', 'sqlite', 'changed', 'removed'] },
    { id: 'danbooru-access', section: 'metadata', label: 'Danbooru access', description: 'Manage encrypted credentials.', keywords: ['username', 'api key', 'credentials', 'connection'] },
    { id: 'automation', section: 'metadata', label: 'Local library watcher', description: 'Detect new or changed files without contacting Danbooru.', keywords: ['automatic', 'watcher', 'sidecar', 'interval', 'local'] },
    { id: 'backup', section: 'safety', label: 'Manual metadata backup', description: `Choose protected metadata components for the fixed ${SUITE_NAME} backup location.`, keywords: ['snapshot', 'database', 'sidecar', 'destination', 'size'] },
    { id: 'restore', section: 'safety', label: 'Restore metadata', description: `Validate and restore a ${SUITE_NAME} backup bundle with rollback.`, keywords: ['recovery', 'rollback', 'backup'] },
    { id: 'local-recovery', section: 'safety', label: 'Automatic local recovery', description: 'Keep rotating user database checkpoints.', keywords: ['checkpoint', 'user sqlite', 'favorites', 'collections', 'automatic'] },
    { id: 'thumbnail-cache', section: 'safety', label: 'Thumbnail cache', description: 'Manage the three derived thumbnail tiers and size limit.', keywords: ['300', '600', '1200', 'cleanup', 'cache'] },
    { id: 'clean-sidecars', section: 'safety', label: 'Clean orphan sidecars', description: 'Remove metadata whose reachable media file is gone.', keywords: ['cleanup', 'orphan', 'metadata'] },
    { id: 'rebuild', section: 'safety', label: 'Rebuild database', description: 'Recover the regenerable SQLite index from sidecars.', keywords: ['recovery', 'sqlite', 'repair'] },
    { id: 'reddit-download-defaults', section: 'reddit', label: 'Save-link defaults', description: 'Choose which media options prefill the Reddit Save Link drawer.', keywords: ['images', 'gifs', 'videos', 'linked files', 'retry', 'download'] },
    { id: 'reddit-archive-health', section: 'reddit', label: 'Local Reddit archive', description: 'Inspect saved post, comment, community, media, queue, and job totals.', keywords: ['sqlite', 'status', 'posts', 'comments', 'community', 'media', 'queue'] },
    { id: 'reddit-storage-policy', section: 'reddit', label: 'Reddit storage and Files', description: 'See the archive, media-object, and Files publication locations.', keywords: ['path', 'database', 'files module', 'content addressed', 'local'] },
    { id: 'reddit-download-safety', section: 'reddit', label: 'Reddit download safety', description: 'Review fixed run, file-size, free-space, and confirmation limits.', keywords: ['limit', 'bytes', 'confirmation', 'fingerprint', 'dns', 'redirect'] },
    { id: 'reddit-capture-provider', section: 'reddit', label: 'Reddit capture source', description: 'See what post and subreddit links preserve through Arctic Shift.', keywords: ['arctic shift', 'provider', 'rules', 'wiki', 'moderators', 'scope'] },
    { id: 'karaoke-providers', section: 'karaoke', label: 'Karaoke discovery', description: 'Review Kara.moe discovery and the YouTube fallback handoff.', keywords: ['kara moe', 'lyrics', 'youtube', 'fallback', 'search'] },
    { id: 'karaoke-player', section: 'karaoke', label: 'Karaoke player', description: 'Review the local video, control overlay, and timed lyrics behavior.', keywords: ['ass', 'srt', 'vtt', 'lrc', 'mouse', 'controls', 'jassub'] },
    { id: 'karaoke-storage', section: 'karaoke', label: 'Karaoke storage', description: 'See the local library, database, and Files publication paths.', keywords: ['files', 'local', 'database', 'media'] },
    { id: 'youtube-defaults', section: 'youtube', label: 'YouTube download defaults', description: 'Choose default quality, compatibility, audio, and automatic captions.', keywords: ['720p', '1080p', 'highest', 'mp4', 'mp3', 'opus', 'captions'] },
    { id: 'youtube-safety', section: 'youtube', label: 'YouTube acquisition boundary', description: 'Review confirmation, host, playlist, cookies, and concurrency limits.', keywords: ['yt-dlp', 'public', 'single video', 'safety', 'limits'] },
    { id: 'youtube-storage', section: 'youtube', label: 'YouTube storage', description: 'See local downloads, cache, database, and Files publication paths.', keywords: ['files', 'video', 'thumbnail', 'database', 'local'] },
    { id: 'language-anki', section: 'language', label: 'AnkiConnect', description: 'Configure and explicitly test the local read-only Anki connection.', keywords: ['anki', 'port', 'api key', 'probe', 'read only'] },
    { id: 'language-dictionary', section: 'language', label: 'KRDICT enrichment', description: 'Save the optional dictionary key used only by explicit Analyzer lookups.', keywords: ['krdict', 'dictionary', 'english', 'mongolian', 'analyzer', 'api key'] },
    { id: 'language-profiles', section: 'language', label: 'Import profiles', description: 'Map note types and fields before importing vocabulary.', keywords: ['deck', 'model', 'fields', 'preview', 'mapping'] },
    { id: 'language-storage', section: 'language', label: 'Language storage', description: 'Inspect the local catalog, media, receipts, and export paths.', keywords: ['files', 'sqlite', 'media', 'receipts', 'json', 'export'] },
    { id: 'language-display', section: 'language', label: 'Language display', description: 'Choose word density, paging, and audio autoplay behavior.', keywords: ['grid', 'page size', 'audio', 'autoplay', 'display'] },
  ];

  let folders: FolderInfo[] = [];
  let folderPathInput = '';
  let folderBusy = false;
  let folderError = '';
  let folderMessage = '';
  let folderRemovalFolder: FolderInfo | null = null;
  let folderRemovalPreview: FolderRemovalPreview | null = null;
  let folderRemovalBusy = false;
  let folderRemovalError = '';
  let syncStatus: { status: string; output?: string; progress?: number; total?: number } | null = null;
  let tools: ToolInfo[] = [];
  let activeToolId = '';
  let activeToolStatus: ToolStatus | null = null;
  let toolPoller: ReturnType<typeof setTimeout> | null = null;
  let toolError = '';
  let credentials: DanbooruCredentialStatus | null = null;
  let credentialUsername = '';
  let credentialApiKey = '';
  let credentialBusy = false;
  let credentialMessage = '';
  let credentialError = '';
  let foldersLoaded = false;
  let toolsLoaded = false;
  let credentialsLoaded = false;
  let foldersRequest: Promise<void> | null = null;
  let toolsRequest: Promise<void> | null = null;
  let credentialsRequest: Promise<void> | null = null;
  let searchHighlightTimer: ReturnType<typeof setTimeout> | null = null;

  // Registered folders plus top-level indexed folders (subfolder labels like
  // "Danbooru\x" stay out of the management list; the sidebar still shows them).
  $: libraryFolders = folders.filter(
    folder => folder.registered || (!folder.name.includes('\\') && !folder.name.includes('/'))
  );
  $: syncRunning = syncStatus?.status === 'running';
  $: toolRunning = activeToolStatus?.status === 'running' || activeToolStatus?.status === 'cancelling';
  $: syncTool = tools.find(tool => tool.id === 'sync');
  $: safetyTools = tools.filter(tool => ['clean-sidecars', 'sqlite'].includes(tool.id));
  $: totalIndexedImages = libraryFolders.reduce((total, folder) => total + folder.count, 0);

  async function loadFolders(force = false): Promise<void> {
    if (foldersRequest) return foldersRequest;
    if (foldersLoaded && !force) return;
    foldersRequest = api.getFolders()
      .then(value => {
        folders = value;
        foldersLoaded = true;
      })
      .finally(() => {
        foldersRequest = null;
      });
    return foldersRequest;
  }

  function stopToolPolling() {
    if (toolPoller) {
      clearTimeout(toolPoller);
      toolPoller = null;
    }
  }

  function scheduleToolPolling(delay = 1500) {
    if (!activeToolId || toolPoller) return;
    toolPoller = setTimeout(() => {
      toolPoller = null;
      void pollActiveTool();
    }, delay);
  }

  async function pollActiveTool() {
    if (!activeToolId) return;
    try {
      activeToolStatus = await api.getToolStatus(activeToolId);
    } catch (error) {
      toolError = error instanceof Error ? error.message : String(error);
      scheduleToolPolling(2200);
      return;
    }
    if (activeToolId === 'sync') syncStatus = activeToolStatus;
    if (!['running', 'cancelling'].includes(activeToolStatus.status)) {
      stopToolPolling();
      tools = await api.getTools();
      toolsLoaded = true;
      await loadFolders(true);
      imageRefreshToken.update(n => n + 1);
    } else {
      scheduleToolPolling();
    }
  }

  function startToolPolling(toolId: string) {
    activeToolId = toolId;
    activeToolStatus = { status: 'running', output: '', progress: 0, total: 0 };
    if (toolId === 'sync') syncStatus = activeToolStatus;
    stopToolPolling();
    scheduleToolPolling(0);
  }

  async function loadTools(): Promise<void> {
    if (toolsRequest) return toolsRequest;
    if (toolsLoaded) return;
    toolsRequest = api.getTools()
      .then(value => {
        tools = value;
        toolsLoaded = true;
        const sync = value.find(tool => tool.id === 'sync');
        syncStatus = sync ?? null;
        const active = value.find(tool => tool.status === 'running' || tool.status === 'cancelling');
        if (active) startToolPolling(active.id);
      })
      .finally(() => {
        toolsRequest = null;
      });
    return toolsRequest;
  }

  async function loadCredentials(): Promise<void> {
    if (credentialsRequest) return credentialsRequest;
    if (credentialsLoaded) return;
    credentialsRequest = api.getDanbooruCredentials()
      .then(value => {
        credentials = value;
        credentialUsername = value.username ?? '';
      })
      .catch(() => {
        credentials = null;
        credentialUsername = '';
      })
      .finally(() => {
        credentialsLoaded = true;
        credentialsRequest = null;
      });
    return credentialsRequest;
  }

  async function ensureSectionData(section: string): Promise<void> {
    if (section === 'library') {
      await Promise.all([loadFolders(), loadTools()]);
    } else if (section === 'metadata') {
      await Promise.all([loadFolders(), loadTools(), loadCredentials()]);
    } else if (section === 'safety') {
      await loadTools();
    }
  }

  $: void ensureSectionData(selectedSection);

  onMount(() => {
    prepareSettingsPresentation();
    return () => {
      stopToolPolling();
      if (searchHighlightTimer) clearTimeout(searchHighlightTimer);
      restoreSettingsPresentation($mediaPlayback === 'always');
    };
  });

  async function saveDanbooruCredentials() {
    if (credentialBusy) return;
    credentialBusy = true;
    credentialError = '';
    credentialMessage = '';
    try {
      credentials = await api.saveDanbooruCredentials(credentialUsername.trim(), credentialApiKey.trim() || undefined);
      credentialUsername = credentials.username ?? '';
      credentialApiKey = '';
      credentialMessage = 'Credentials saved securely for this Windows user.';
    } catch (error) {
      credentialError = error instanceof Error ? error.message : String(error);
    } finally {
      credentialBusy = false;
    }
  }

  async function checkCredentials() {
    if (credentialBusy) return;
    credentialBusy = true;
    credentialError = '';
    credentialMessage = '';
    try {
      const result = await api.checkDanbooruCredentials();
      credentialMessage = `Connected as ${result.username}${result.user_id ? ` (user ${result.user_id})` : ''}.`;
    } catch (error) {
      credentialError = error instanceof Error ? error.message : String(error);
    } finally {
      credentialBusy = false;
    }
  }

  async function clearDanbooruCredentials() {
    if (!confirm('Remove the saved Danbooru username and API key from this computer?')) return;
    credentialBusy = true;
    credentialError = '';
    try {
      credentials = await api.clearDanbooruCredentials();
      credentialUsername = credentials.username ?? '';
      credentialApiKey = '';
      credentialMessage = credentials.source === 'environment'
        ? 'Saved credentials removed. Environment credentials are still active.'
        : 'Saved credentials removed.';
    } catch (error) {
      credentialError = error instanceof Error ? error.message : String(error);
    } finally {
      credentialBusy = false;
    }
  }

  async function beginTool(toolId: string, runner: () => Promise<{ status: string; active_tool_id?: string }>) {
    if (toolRunning) return;
    toolError = '';
    try {
      const result = await runner();
      const runningId = result.active_tool_id ?? toolId;
      if (result.status === 'started' || result.status === 'already_running' || result.status === 'busy') {
        startToolPolling(runningId);
      }
    } catch (error) {
      toolError = error instanceof Error ? error.message : String(error);
    }
  }

  function maintenanceDisplayName(tool: ToolInfo) {
    if (tool.id === 'clean-sidecars') return 'Clean orphan sidecars';
    if (tool.id === 'sqlite') return 'Rebuild database (recovery)';
    return tool.name;
  }

  async function runMaintenanceTool(tool: ToolInfo) {
    if (tool.id === 'clean-sidecars' && !confirm('Clean sidecars whose media files are missing? This removes orphan metadata files.')) return;
    if (tool.id === 'sqlite' && !confirm('Rebuild the regenerable image database from sidecars? User data is kept separately.')) return;
    await beginTool(tool.id, () => api.runTool(tool.id));
  }

  async function cancelActiveTool() {
    if (!activeToolId || !toolRunning) return;
    try {
      activeToolStatus = { ...(activeToolStatus ?? { output: '' }), status: 'cancelling', cancellable: false };
      await api.cancelTool(activeToolId);
    } catch (error) {
      toolError = error instanceof Error ? error.message : String(error);
    }
  }

  async function browseForFolder() {
    if (folderBusy) return;
    folderError = '';
    folderMessage = '';
    folderBusy = true;
    try {
      const result = await api.browseFolder();
      if (result.path) folderPathInput = result.path;
    } catch (error) {
      folderError = error instanceof Error ? error.message : String(error);
    } finally {
      folderBusy = false;
    }
  }

  async function addFolder() {
    const path = folderPathInput.trim();
    if (!path || folderBusy) return;
    folderError = '';
    folderMessage = '';
    folderBusy = true;
    try {
      const result = await api.registerFolder(path);
      folderPathInput = '';
      folders = [
        {
          name: result.name,
          selector: result.selector,
          count: 0,
          path: result.path,
          root_id: result.root_id,
          registered: true,
        },
        ...folders,
      ];
      if (result.sync === 'started' || result.sync === 'already_running') {
        startToolPolling('sync');
      } else if (result.active_tool_id) {
        startToolPolling(result.active_tool_id);
        folderError = `Folder registered. Waiting for the active ${result.active_tool_id} job; run Sync afterward to index it.`;
      }
    } catch (error) {
      folderError = error instanceof Error ? error.message : String(error);
    } finally {
      folderBusy = false;
    }
  }

  async function rescanLibraryFolder(folder: FolderInfo) {
    folderError = '';
    folderMessage = '';
    try {
      const result = await api.rescanFolder(folder.root_id ?? folder.selector);
      if (result.status === 'started' || result.status === 'already_running') {
        startToolPolling('sync');
      } else if (result.active_tool_id) {
        startToolPolling(result.active_tool_id);
        folderError = `Cannot rescan while ${result.active_tool_id} is running.`;
      }
    } catch (error) {
      folderError = error instanceof Error ? error.message : String(error);
    }
  }

  async function relocateLibraryFolder(folder: FolderInfo) {
    if (!folder.root_id || folderBusy || syncRunning || toolRunning) return;
    folderError = '';
    folderMessage = '';
    folderBusy = true;
    try {
      const selection = await api.browseFolder();
      if (!selection.path) return;
      const result = await api.relocateFolder(folder.root_id, selection.path);
      folders = folders.map(item => item.root_id === result.root_id
        ? { ...item, name: result.name, selector: result.selector, path: result.path }
        : item
      );
      imageRefreshToken.update(n => n + 1);
      folderMessage = `Relocated ${result.files_updated.toLocaleString()} indexed file references. Originals and sidecars were not moved.`;
      if (result.sync === 'started' || result.sync === 'already_running') {
        startToolPolling('sync');
      }
    } catch (error) {
      folderError = error instanceof Error ? error.message : String(error);
    } finally {
      folderBusy = false;
    }
  }

  async function openFolderRemoval(folder: FolderInfo) {
    if (folderRemovalBusy) return;
    folderRemovalFolder = folder;
    folderRemovalPreview = null;
    folderRemovalError = '';
    folderRemovalBusy = true;
    try {
      folderRemovalPreview = await api.getFolderRemovalPreview(folder.root_id ?? folder.selector);
    } catch (error) {
      folderRemovalError = error instanceof Error ? error.message : String(error);
    } finally {
      folderRemovalBusy = false;
    }
  }

  function closeFolderRemoval() {
    if (folderRemovalBusy) return;
    folderRemovalFolder = null;
    folderRemovalPreview = null;
    folderRemovalError = '';
  }

  async function confirmFolderRemoval(mode: FolderRemovalMode) {
    if (!folderRemovalFolder || !folderRemovalPreview || folderRemovalBusy) return;
    const folder = folderRemovalFolder;
    folderRemovalBusy = true;
    folderRemovalError = '';
    folderError = '';
    folderMessage = '';
    try {
      const result = await api.removeFolder(folder.root_id ?? folder.selector, mode);
      folders = folders.filter(item => item.selector !== folder.selector);
      imageRefreshToken.update(n => n + 1);
      folderMessage = mode === 'delete_sidecars'
        ? `Removed ${result.files_removed.toLocaleString()} indexed images and ${result.sidecar_files_removed.toLocaleString()} current sidecar files. External images and sidecar history were preserved.`
        : `Removed ${result.files_removed.toLocaleString()} indexed images from SQLite. Sidecars and external images were preserved.`;
      folderRemovalFolder = null;
      folderRemovalPreview = null;
    } catch (error) {
      folderRemovalError = error instanceof Error ? error.message : String(error);
    } finally {
      folderRemovalBusy = false;
    }
  }

  function formatByteCount(value: number) {
    if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(2)} GB`;
    if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(2)} MB`;
    if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
    return `${value.toLocaleString()} B`;
  }

  const ratingOptions: { value: string | null; label: string; description: string }[] = [
    { value: null, label: 'All', description: 'Show every rating' },
    { value: 'g', label: 'General', description: 'Default safe browse' },
    { value: 's', label: 'Sensitive', description: 'Include sensitive posts' },
    { value: 'q', label: 'Questionable', description: 'Questionable only' },
    { value: 'e', label: 'Explicit', description: 'Explicit only' },
    { value: 'u', label: 'Unrated', description: 'Missing sidecar rating' },
  ];

  const artistNotificationIntervalOptions: ArtistNotificationIntervalMinutes[] = [5, 15, 30, 60];

  const fitModeOptions: { value: FitMode; label: string; description: string }[] = [
    { value: 'fit', label: 'Crop Fill', description: 'Dense grid with filled cards' },
    { value: 'contain', label: 'Contain', description: 'Show the full image shape' },
  ];

  const startupOptions: { value: StartupView; label: string }[] = [
    { value: 'home', label: 'Home' },
    { value: 'gallery', label: 'Browse' },
    { value: 'last', label: 'Last visited' },
  ];

  const homeLayoutOptions: { value: HomeLayout; label: string }[] = [
    { value: 'discovery', label: 'Discovery' },
    { value: 'classic', label: 'Classic' },
  ];

  const sortOptions = [
    { value: 'date', label: 'Date' },
    { value: 'downloaded', label: 'Downloaded' },
    { value: 'score', label: 'Score' },
    { value: 'views', label: 'Viewed' },
    { value: 'tags', label: 'Most tagged' },
    { value: 'random', label: 'Random' },
    { value: 'name', label: 'Name' },
    { value: 'size', label: 'File size' },
  ];

  const playbackOptions: { value: MediaPlayback; label: string; description: string }[] = [
    { value: 'never', label: 'Never', description: 'Keep GIFs and videos still until explicitly played.' },
    { value: 'hover', label: 'On hover', description: 'Animate while the pointer is over the media.' },
    { value: 'always', label: 'Always', description: 'Automatically animate visible media.' },
  ];

  const motionOptions: { value: MotionPreference; label: string }[] = [
    { value: 'system', label: 'System' },
    { value: 'full', label: 'Full' },
    { value: 'reduced', label: 'Reduced' },
  ];

  const interfaceScaleOptions: { value: InterfaceScale; label: string }[] = [
    { value: 'default', label: 'Default' },
    { value: 'comfortable', label: 'Comfortable' },
  ];

  const duplicateOptions: { value: DuplicateScope | 'off'; label: string; description: string }[] = [
    { value: 'off', label: 'Off', description: 'Normal browsing' },
    { value: 'all', label: 'All', description: 'Every duplicate group' },
    { value: 'same_folder', label: 'Same Folder', description: 'Duplicates inside one folder' },
    { value: 'different_folder', label: 'Different Folders', description: 'Duplicates split across folders' },
  ];

  const bannerPresets = [
    { label: 'Low', value: 360 },
    { label: 'Tall', value: 520 },
    { label: 'Huge', value: 660 },
  ];

  $: query = settingsSearch.trim().toLowerCase();
  $: searchResults = query
    ? settingSearchItems
        .filter(item => {
          const section = sections.find(candidate => candidate.id === item.section);
          return [item.label, item.description, section?.label ?? '', ...item.keywords]
            .some(value => value.toLowerCase().includes(query));
        })
        .sort((left, right) => settingSearchScore(left, query) - settingSearchScore(right, query)
          || left.label.localeCompare(right.label))
    : [];
  $: currentDuplicateMode = $duplicatesOnly ? $duplicateScope : 'off';
  $: selectedImageSize = imageSizeOptions.find(option => option.value === $imageSize) ?? imageSizeOptions[1];

  function close() {
    dispatch('close');
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      if (folderRemovalFolder) closeFolderRemoval();
      else close();
    }
  }

  function setDuplicateMode(value: DuplicateScope | 'off') {
    if (value === 'off') {
      duplicatesOnly.set(false);
      return;
    }
    duplicateScope.set(value);
    duplicatesOnly.set(true);
  }

  function settingSearchScore(item: SettingSearchItem, needle: string) {
    const label = item.label.toLowerCase();
    const description = item.description.toLowerCase();
    const section = sections.find(candidate => candidate.id === item.section)?.label.toLowerCase() ?? '';
    const keywords = item.keywords.map(keyword => keyword.toLowerCase());
    if (label === needle) return 0;
    if (label.startsWith(needle)) return 1;
    if (label.includes(needle)) return 2;
    if (keywords.some(keyword => keyword === needle)) return 3;
    if (keywords.some(keyword => keyword.startsWith(needle))) return 4;
    if (section.includes(needle)) return 5;
    if (description.includes(needle)) return 6;
    return 7;
  }

  async function openSearchResult(item: SettingSearchItem) {
    selectedSection = item.section;
    settingsSearch = '';
    await tick();
    const target = document.getElementById(`setting-${item.id}`);
    if (!target) return;
    document.querySelector('.setting-flash')?.classList.remove('setting-flash');
    if (searchHighlightTimer) clearTimeout(searchHighlightTimer);
    target.scrollIntoView({
      block: 'center',
      behavior: $motionPreference === 'reduced' ? 'auto' : 'smooth',
    });
    await tick();
    target.classList.remove('setting-flash');
    void target.getBoundingClientRect();
    target.classList.add('setting-flash');
    searchHighlightTimer = window.setTimeout(() => {
      target.classList.remove('setting-flash');
      searchHighlightTimer = null;
    }, 1400);
  }

  function resetCurrentSection() {
    if (selectedSection === 'browsing') {
      startupView.set('home');
      homeLayout.set('discovery');
      activeRating.set('g');
      sortBy.set('date');
      sortOrder.set('desc');
      imagePageSize.set(10);
      sidebarOpen.set(true);
      heartSpamEnabled.set(false);
      artistNotificationsEnabled.set(true);
      artistNotificationIntervalMinutes.set(15);
      duplicatesOnly.set(false);
      duplicateScope.set('all');
      return;
    }
    if (selectedSection === 'appearance') {
      appTheme.set('keivotos-dark');
      imageSize.set('medium');
      fitMode.set('fit');
      mediaPlayback.set('always');
      motionPreference.set('system');
      interfaceScale.set('default');
      tagBannerHeight.set(520);
      return;
    }
    if (selectedSection === 'player') {
      playerCenterControls.set(true);
      playerDarkenOverlay.set(true);
      miniPlayerStyle.set('card');
      return;
    }
  }

  function compactSegmentClass(active: boolean) {
    return `px-3 py-1.5 text-xs font-medium transition-colors ${
      active
        ? 'bg-purple-600/25 text-purple-100'
        : 'bg-[var(--bg-base)] text-[var(--text-muted)] hover:bg-[var(--hover-bg)] hover:text-[var(--text-primary)]'
    }`;
  }

  function iconPath(icon: string) {
    if (icon === 'folder') {
      return 'M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z';
    }
    if (icon === 'palette') {
      return 'M12 3a9 9 0 00-3 17.49c.6.2 1-.28.83-.87-.22-.76.27-1.54 1.06-1.54h1.33c4.18 0 7.56-3.05 7.56-6.82C19.78 6.7 16.3 3 12 3zm-4 8h.01M11 7h.01M15 8h.01M16 12h.01';
    }
    if (icon === 'database') {
      return 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zm0 0v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6m-16 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6';
    }
    if (icon === 'shield') {
      return 'M12 3l7 3v5c0 4.6-2.8 8.2-7 10-4.2-1.8-7-5.4-7-10V6l7-3zm-3 9l2 2 4-4';
    }
    if (icon === 'reddit') {
      return 'M20 12a8 8 0 11-16 0 8 8 0 0116 0zm-12.5.5h.01m9 0h.01M8 16c1 .8 2.3 1.2 4 1.2s3-.4 4-1.2M12 4l1.2-2 3.3.8';
    }
    if (icon === 'karaoke') {
      return 'M9 18V5l10-2v13M9 8l10-2M6 21a3 3 0 100-6 3 3 0 000 6zm10-2a3 3 0 100-6 3 3 0 000 6z';
    }
    if (icon === 'youtube') {
      return 'M21 8.2a3 3 0 00-2.1-2.1C17 5.5 12 5.5 12 5.5s-5 0-6.9.6A3 3 0 003 8.2 31 31 0 003 12a31 31 0 00.1 3.8 3 3 0 002.1 2.1c1.9.6 6.9.6 6.9.6s5 0 6.9-.6a3 3 0 002.1-2.1A31 31 0 0021 12a31 31 0 00-.1-3.8zM10 15V9l5 3-5 3z';
    }
    if (icon === 'language') {
      return 'M4 5h9v12H7l-3 3V5zm9 4h7v10h-4l-3 2V9zM7 9h3m-3 3h3m6 1h2m-2 3h2';
    }
    if (icon === 'player') {
      return 'M5 4h14a2 2 0 012 2v12a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2zm5 4l6 4-6 4V8z';
    }
    return 'M4 5h16v14H4V5zm0 4h16M8 5v4';
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
<div
  class="settings-layer fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
  on:click={close}
>
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div
    class="settings-shell grid h-[min(800px,calc(100vh-2rem))] w-[min(1120px,calc(100vw-2rem))] grid-cols-[252px_minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)] items-start overflow-hidden rounded-2xl border border-[#303042] bg-[#09090e] shadow-2xl shadow-black/70"
    role="dialog"
    aria-modal="true"
    aria-label="Settings"
    tabindex="-1"
    use:focusTrap={{ close }}
    on:click|stopPropagation
  >
    <header class="col-span-2 flex h-16 items-center justify-between border-b border-[#272735] bg-[#111117]/95 px-5">
      <div class="flex min-w-0 items-center gap-3">
        <div class="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-purple-400/20 bg-purple-500/10 text-purple-200 shadow-inner shadow-purple-500/10">
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M10.3 4.3c.4-1.8 2.9-1.8 3.4 0a1.7 1.7 0 002.6 1.1c1.5-.9 3.3.8 2.4 2.4a1.7 1.7 0 001.1 2.6c1.8.4 1.8 2.9 0 3.4a1.7 1.7 0 00-1.1 2.6c.9 1.5-.8 3.3-2.4 2.4a1.7 1.7 0 00-2.6 1.1c-.4 1.8-2.9 1.8-3.4 0a1.7 1.7 0 00-2.6-1.1c-1.5.9-3.3-.8-2.4-2.4a1.7 1.7 0 00-1.1-2.6c-1.8-.4-1.8-2.9 0-3.4a1.7 1.7 0 001.1-2.6c-.9-1.5.8-3.3 2.4-2.4a1.7 1.7 0 002.6-1.1z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </div>
        <h2 class="text-xl font-bold text-gray-100">Settings</h2>
      </div>
      <button
        class="grid h-9 w-9 place-items-center rounded-xl border border-[var(--border-default)] bg-[#17171f] text-[var(--text-secondary)] transition-colors hover:border-purple-400/40 hover:text-white"
        type="button"
        on:click={close}
        title="Close settings"
        aria-label="Close settings"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
    </header>

    <aside class="flex h-full min-h-0 flex-col overflow-hidden border-r border-[#252532] bg-[#0d0d12] p-3.5">
      <label class="relative block shrink-0">
        <span class="sr-only">Search settings</span>
        <svg class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.3-4.3m1.3-5.2a6.5 6.5 0 11-13 0 6.5 6.5 0 0113 0z" />
        </svg>
        <input
          class="w-full rounded-xl border border-[#2b2b3a] bg-[#15151d] py-2.5 pl-9 pr-8 text-sm text-[var(--text-primary)] outline-none transition-colors placeholder:text-gray-600 focus:border-purple-500/60"
          type="search"
          placeholder="Find a setting"
          bind:value={settingsSearch}
        />
        {#if settingsSearch}
          <button class="absolute right-2 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-md text-gray-600 hover:bg-white/5 hover:text-[var(--text-primary)]" type="button" title="Clear search" aria-label="Clear search" on:click={() => settingsSearch = ''}>×</button>
        {/if}
      </label>

      <nav class="settings-section-list mt-4 min-h-0 flex-1 overflow-y-auto pr-1" aria-label="Settings sections">
        {#each sections as section, index}
          {#if index === 0 || sections[index - 1].group !== section.group}
            <div class="settings-group-label px-3 pb-1 pt-3 text-[9px] font-bold uppercase tracking-[0.2em] text-gray-700 first:pt-0">{section.group}</div>
          {/if}
          <button
            class="group relative mb-1.5 flex w-full items-center gap-3 overflow-hidden rounded-xl px-3 py-2.5 text-left transition-all duration-200 {selectedSection === section.id && !query ? 'translate-x-0.5 bg-[#1a1a23] text-gray-100 shadow-inner shadow-white/[0.025]' : 'text-[var(--text-muted)] hover:translate-x-0.5 hover:bg-[#14141b] hover:text-[var(--text-primary)]'}"
            type="button"
            aria-current={selectedSection === section.id && !query ? 'page' : undefined}
            on:click={() => { selectedSection = section.id; settingsSearch = ''; }}
          >
            {#if selectedSection === section.id && !query}
              <span class="settings-section-marker absolute inset-y-2 left-0 w-0.5 rounded-full {section.id === 'youtube' ? 'bg-red-400' : section.id === 'karaoke' || section.id === 'language' ? 'bg-cyan-300' : section.id === 'reddit' ? 'bg-orange-300' : section.id === 'safety' ? 'bg-amber-300' : section.id === 'library' ? 'bg-cyan-300' : section.id === 'appearance' ? 'bg-pink-300' : 'bg-purple-300'}"></span>
            {/if}
            <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border transition-all duration-200 {selectedSection === section.id && !query ? 'border-white/10 bg-white/[0.055]' : 'border-transparent bg-white/[0.02] group-hover:bg-white/[0.045]'}">
              <svg class="h-[18px] w-[18px] {section.id === 'youtube' ? 'text-red-400' : section.id === 'karaoke' || section.id === 'language' ? 'text-cyan-300' : section.id === 'reddit' ? 'text-orange-300' : section.id === 'safety' ? 'text-amber-300' : section.id === 'library' ? 'text-cyan-300' : section.id === 'appearance' ? 'text-pink-300' : 'text-purple-300'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d={iconPath(section.icon)} />
              </svg>
            </span>
            <span class="min-w-0 truncate text-[13px] font-semibold">{section.label}</span>
          </button>
        {/each}
      </nav>
    </aside>

    <main class="settings-scroll h-full min-h-0 overflow-y-auto bg-[#09090e] p-5">
      {#if query}
        <section class="mx-auto max-w-3xl">
          <div class="mb-4 flex items-end justify-between gap-4">
            <div>
              <div class="text-xs font-semibold uppercase tracking-[0.18em] text-purple-300">Search</div>
              <h3 class="mt-1 text-2xl font-bold text-gray-100">{searchResults.length} result{searchResults.length === 1 ? '' : 's'} for “{settingsSearch.trim()}”</h3>
            </div>
          </div>
          {#if searchResults.length}
            <div class="space-y-2">
              {#each searchResults as result}
                <button
                  class="group flex w-full items-center gap-4 rounded-xl border border-[var(--border-default)] bg-[#121219] px-4 py-3 text-left transition-all hover:-translate-y-0.5 hover:border-purple-400/35 hover:bg-[var(--hover-bg)]"
                  type="button"
                  on:click={() => openSearchResult(result)}
                >
                  <span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-purple-500/10 text-purple-200">
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d={iconPath(sections.find(section => section.id === result.section)?.icon ?? 'window')} />
                    </svg>
                  </span>
                  <span class="min-w-0 flex-1">
                    <span class="block text-xs font-semibold uppercase tracking-wide text-gray-600">{sections.find(section => section.id === result.section)?.label}</span>
                    <span class="mt-0.5 block text-sm font-semibold text-[var(--text-primary)]">{result.label}</span>
                    <span class="mt-1 block text-xs leading-relaxed text-[var(--text-muted)]">{result.description}</span>
                  </span>
                  <svg class="h-4 w-4 shrink-0 text-gray-600 transition-transform group-hover:translate-x-0.5 group-hover:text-purple-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              {/each}
            </div>
          {:else}
            <div class="rounded-2xl border border-dashed border-[var(--border-default)] bg-[#111117] px-6 py-14 text-center">
              <div class="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-white/[0.035] text-gray-600">
                <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M21 21l-4.3-4.3m1.3-5.2a6.5 6.5 0 11-13 0 6.5 6.5 0 0113 0z" /></svg>
              </div>
              <h3 class="mt-4 text-base font-semibold text-[var(--text-primary)]">No matching setting</h3>
              <p class="mt-1 text-sm text-gray-600">Try a control name, task, or value such as “backup,” “hover,” or “folder.”</p>
            </div>
          {/if}
        </section>
      {:else}
        {#if activeToolStatus && ['library', 'metadata', 'safety'].includes(selectedSection)}
          <section class="mb-4 rounded-xl border border-purple-400/20 bg-purple-500/[0.055] p-3.5">
            <div class="flex items-center justify-between gap-4">
              <div>
                <div class="text-xs font-semibold uppercase tracking-wider {activeToolStatus.status === 'error' ? 'text-red-300' : activeToolStatus.status === 'done' ? 'text-green-300' : 'text-purple-200'}">
                  {activeToolStatus.status === 'running' ? (activeToolStatus.stage ?? ('Running ' + activeToolId)) : activeToolStatus.status}
                </div>
                {#if activeToolStatus.stage_total && activeToolStatus.stage_total > 1}
                  <div class="mt-0.5 text-[10px] text-gray-600">Stage {activeToolStatus.stage_index ?? 1} of {activeToolStatus.stage_total}</div>
                {/if}
              </div>
              {#if toolRunning && activeToolStatus.cancellable !== false}
                <button class="rounded-lg border border-red-400/20 px-2.5 py-1.5 text-xs text-red-300 hover:bg-red-500/10" type="button" on:click={cancelActiveTool}>Cancel</button>
              {/if}
            </div>
            {#if activeToolStatus.total && activeToolStatus.total > 0}
              <div class="mt-3">
                <div class="mb-1 flex justify-between text-[10px] text-[var(--text-muted)]"><span>{activeToolStatus.progress ?? 0} / {activeToolStatus.total}</span><span>{Math.round(((activeToolStatus.progress ?? 0) / activeToolStatus.total) * 100)}%</span></div>
                <div class="h-1.5 overflow-hidden rounded-full bg-[var(--bg-overlay)]"><div class="h-full rounded-full bg-purple-400 transition-all" style="width: {((activeToolStatus.progress ?? 0) / activeToolStatus.total) * 100}%"></div></div>
              </div>
            {/if}
            {#if activeToolStatus.output}<pre class="mt-3 max-h-28 overflow-auto whitespace-pre-wrap rounded-lg bg-black/25 p-2.5 text-[10px] leading-relaxed text-[var(--text-muted)]">{activeToolStatus.output}</pre>{/if}
          </section>
        {/if}

        {#if selectedSection === 'browsing'}
          <div class="mx-auto max-w-3xl space-y-4">
            <section class="rounded-2xl border border-purple-400/20 bg-[radial-gradient(circle_at_85%_0%,rgba(168,85,247,.16),transparent_38%),linear-gradient(135deg,#171420,#101017_70%)] px-4 py-3.5" aria-label="Current browsing defaults">
              <div class="flex flex-wrap items-end justify-between gap-3">
                <div class="min-w-0">
                  <h3 class="mb-2 text-sm font-semibold text-purple-100">Browsing</h3>
                  <div class="flex flex-wrap gap-2 text-[11px]">
                    <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">Start: {startupOptions.find(option => option.value === $startupView)?.label}</span>
                    <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">{$imagePageSize === 'all' ? 'All images' : ($imagePageSize + ' per page')}</span>
                    <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">{$artistNotificationsEnabled ? `Artist check: ${$artistNotificationIntervalMinutes} min` : 'Artist check: Off'}</span>
                  </div>
                </div>
                <button class="shrink-0 rounded-lg border border-white/10 bg-black/15 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-white/5 hover:text-[var(--text-primary)]" type="button" on:click={resetCurrentSection}>Reset section</button>
              </div>
            </section>

            <section class="overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)]">
              <div class="divide-y divide-[var(--border-subtle)]">
                <div id="setting-startup-view" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Startup destination</div>
                  <div class="flex shrink-0 divide-x divide-[var(--border-default)] overflow-hidden rounded-lg border border-[var(--border-default)]">
                    {#each startupOptions as option}
                      <button class={compactSegmentClass($startupView === option.value)} type="button" on:click={() => startupView.set(option.value)}>{option.label}</button>
                    {/each}
                  </div>
                </div>
                <div id="setting-home-layout" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Home layout</div>
                  <div class="flex shrink-0 divide-x divide-[var(--border-default)] overflow-hidden rounded-lg border border-[var(--border-default)]">
                    {#each homeLayoutOptions as option}
                      <button class={compactSegmentClass($homeLayout === option.value)} type="button" on:click={() => homeLayout.set(option.value)}>{option.label}</button>
                    {/each}
                  </div>
                </div>
                <div id="setting-rating-filter" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Default rating</div>
                  <select class="w-44 rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-purple-400/60" value={$activeRating ?? ''} on:change={(event) => activeRating.set((event.currentTarget as HTMLSelectElement).value || null)}>
                    {#if $activeRating?.includes(',')}<option value={$activeRating}>Multiple ratings</option>{/if}
                    {#each ratingOptions as option}<option value={option.value ?? ''}>{option.label}</option>{/each}
                  </select>
                </div>
                <div id="setting-browse-sort" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Browse sort</div>
                  <div class="flex shrink-0 items-center gap-2">
                    <select class="w-36 rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-purple-400/60" value={$sortBy} on:change={(event) => sortBy.set((event.currentTarget as HTMLSelectElement).value)}>
                      {#each sortOptions as option}<option value={option.value}>{option.label}</option>{/each}
                    </select>
                    <button
                      class="grid h-8 w-8 place-items-center rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] text-[var(--text-primary)] transition-colors hover:border-purple-400/50 hover:bg-purple-500/10 hover:text-purple-100"
                      type="button"
                      title="Sort order: {$sortOrder === 'desc' ? 'Descending' : 'Ascending'}"
                      aria-label="Toggle sort order; currently {$sortOrder === 'desc' ? 'descending' : 'ascending'}"
                      on:click={() => sortOrder.update(order => order === 'desc' ? 'asc' : 'desc')}
                    >
                      <svg class="h-3.5 w-3.5 transition-transform {$sortOrder === 'asc' ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                  </div>
                </div>
                <div id="setting-page-size" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Images per page</div>
                  <select class="w-32 rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-purple-400/60" value={$imagePageSize} on:change={(event) => imagePageSize.set(((event.currentTarget as HTMLSelectElement).value === 'all' ? 'all' : Number((event.currentTarget as HTMLSelectElement).value)) as ImagePageSize)}>
                    {#each imagePageSizeOptions as option}<option value={option.value}>{option.value === 'all' ? 'All images' : option.label}</option>{/each}
                  </select>
                </div>
              </div>
            </section>

            <section class="overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)]">
              <div class="divide-y divide-[var(--border-subtle)]">
                <div id="setting-sidebar" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Sidebar default</div>
                  <button class="relative h-6 w-11 shrink-0 rounded-full transition-colors {$sidebarOpen ? 'bg-purple-500' : 'bg-[#2a2a3a]'}" type="button" role="switch" aria-label="Toggle library sidebar" aria-checked={$sidebarOpen} on:click={() => sidebarOpen.update(value => !value)}><span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {$sidebarOpen ? 'translate-x-5' : ''}"></span></button>
                </div>
                <div id="setting-heart-spam" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Heart Spam button</div>
                  <button class="relative h-6 w-11 shrink-0 rounded-full transition-colors {$heartSpamEnabled ? 'bg-pink-500' : 'bg-[#2a2a3a]'}" type="button" role="switch" aria-label="Toggle Heart Spam" aria-checked={$heartSpamEnabled} on:click={() => heartSpamEnabled.update(value => !value)}><span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {$heartSpamEnabled ? 'translate-x-5' : ''}"></span></button>
                </div>
                <div id="setting-artist-notifications" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Artist checks</div>
                  <div class="flex shrink-0 items-center gap-2">
                    <select
                      class="w-24 rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-2.5 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-cyan-400/60 disabled:opacity-50"
                      value={$artistNotificationIntervalMinutes}
                      disabled={!$artistNotificationsEnabled}
                      aria-label="Artist notification check interval"
                      on:change={(event) => artistNotificationIntervalMinutes.set(Number((event.currentTarget as HTMLSelectElement).value) as ArtistNotificationIntervalMinutes)}
                    >
                      {#each artistNotificationIntervalOptions as minutes}<option value={minutes}>{minutes} min</option>{/each}
                    </select>
                    <button class="relative h-6 w-11 shrink-0 rounded-full transition-colors {$artistNotificationsEnabled ? 'bg-cyan-500' : 'bg-[#2a2a3a]'}" type="button" role="switch" aria-label="Toggle artist notifications" aria-checked={$artistNotificationsEnabled} on:click={() => artistNotificationsEnabled.update(value => !value)}><span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform {$artistNotificationsEnabled ? 'translate-x-5' : ''}"></span></button>
                  </div>
                </div>
              </div>
            </section>

            <section id="setting-duplicate-review" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
              <div class="flex flex-wrap items-center justify-between gap-4">
                <div class="text-sm font-semibold text-[var(--text-primary)]">Duplicate review filter</div>
                <div class="flex divide-x divide-[var(--border-default)] overflow-hidden rounded-lg border border-[var(--border-default)]">
                  {#each duplicateOptions as option}<button class={compactSegmentClass(currentDuplicateMode === option.value)} type="button" title={option.description} on:click={() => setDuplicateMode(option.value)}>{option.label}</button>{/each}
                </div>
              </div>
            </section>
          </div>
        {:else if selectedSection === 'appearance'}
          <div class="mx-auto max-w-3xl space-y-4">
            <section class="rounded-2xl border border-pink-400/20 bg-[radial-gradient(circle_at_20%_0%,rgba(236,72,153,.14),transparent_38%),linear-gradient(135deg,#1b131c,#101017_72%)] px-4 py-3.5" aria-label="Current display settings">
              <div class="flex flex-wrap items-end justify-between gap-3">
                <div class="min-w-0">
                  <h3 class="mb-2 text-sm font-semibold text-pink-100">Display</h3>
                  <div class="flex flex-wrap gap-2 text-[11px]">
                    <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">Theme: {themes.find(t => t.id === $appTheme)?.label ?? 'Dark'}</span>
                    <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">Cards: {selectedImageSize.label} ({selectedImageSize.cardWidth}px)</span>
                    <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">Fit: {$fitMode === 'fit' ? 'Crop fill' : 'Contain'}</span>
                    <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">Animation: {$mediaPlayback === 'always' ? 'Always' : $mediaPlayback === 'hover' ? 'On hover' : 'Never'}</span>
                    <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">Motion: {$motionPreference === 'system' ? 'System' : $motionPreference === 'full' ? 'Full' : 'Reduced'}</span>
                    <span class="rounded-full border border-white/5 bg-black/20 px-2.5 py-1 text-[var(--text-primary)]">Scale: {$interfaceScale === 'comfortable' ? 'Comfortable' : 'Default'}</span>
                  </div>
                </div>
                <button class="shrink-0 rounded-lg border border-white/10 bg-black/15 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-white/5 hover:text-[var(--text-primary)]" type="button" on:click={resetCurrentSection}>Reset section</button>
              </div>
            </section>

            <section id="setting-theme" class="overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] px-4 py-3.5">
              <div class="mb-3 text-sm font-medium text-[var(--text-primary)]">Theme</div>
              <div class="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
                {#each themes as theme}
                  <button
                    type="button"
                    class="group relative flex flex-col items-center gap-1.5 rounded-xl border px-3 py-2.5 text-xs transition-all {$appTheme === theme.id ? 'border-pink-400/60 bg-pink-500/10 text-pink-100' : 'border-[var(--border-default)] bg-[var(--bg-base)] text-[var(--text-secondary)] hover:border-white/20 hover:text-[var(--text-primary)]'}"
                    on:click={() => appTheme.set(theme.id)}
                  >
                    <div class="flex gap-1">
                      <span class="h-3 w-3 rounded-full" style="background:{theme.tokens['--bg-base']}; border:1px solid {theme.tokens['--border-default']}"></span>
                      <span class="h-3 w-3 rounded-full" style="background:{theme.tokens['--accent']}"></span>
                      <span class="h-3 w-3 rounded-full" style="background:{theme.tokens['--text-primary']}"></span>
                    </div>
                    <span class="font-medium">{theme.label}</span>
                    {#if theme.group === 'community'}<span class="text-[9px] text-[var(--text-muted)]">Community</span>{/if}
                  </button>
                {/each}
              </div>
            </section>

            <section class="overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)]">
              <div class="divide-y divide-[var(--border-subtle)]">
                <div id="setting-gallery-card-size" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="flex items-center gap-2 text-sm font-medium text-[var(--text-primary)]">Gallery card size <span class="rounded-full bg-pink-500/10 px-2 py-0.5 text-[10px] text-pink-200">{selectedImageSize.cardWidth}px</span></div>
                  <select class="w-40 rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-xs text-[var(--text-primary)] outline-none focus:border-pink-400/60" value={$imageSize} on:change={(event) => imageSize.set((event.currentTarget as HTMLSelectElement).value as ImageSize)}>
                    {#each imageSizeOptions as option}<option value={option.value}>{option.label}</option>{/each}
                  </select>
                </div>
                <div id="setting-image-fit" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Image fit</div>
                  <div class="flex divide-x divide-[var(--border-default)] overflow-hidden rounded-lg border border-[var(--border-default)]">{#each fitModeOptions as option}<button class={compactSegmentClass($fitMode === option.value)} type="button" title={option.description} on:click={() => fitMode.set(option.value)}>{option.label}</button>{/each}</div>
                </div>
              </div>
            </section>

            <section class="overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)]">
              <div class="divide-y divide-[var(--border-subtle)]">
                <div id="setting-media-playback" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Animated media</div>
                  <div class="flex shrink-0 divide-x divide-[var(--border-default)] overflow-hidden rounded-lg border border-[var(--border-default)]">{#each playbackOptions as option}<button class={compactSegmentClass($mediaPlayback === option.value)} type="button" on:click={() => mediaPlayback.set(option.value)}>{option.label}</button>{/each}</div>
                </div>
                <div id="setting-motion" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Interface motion</div>
                  <div class="flex divide-x divide-[var(--border-default)] overflow-hidden rounded-lg border border-[var(--border-default)]">{#each motionOptions as option}<button class={compactSegmentClass($motionPreference === option.value)} type="button" on:click={() => motionPreference.set(option.value)}>{option.label}</button>{/each}</div>
                </div>
                <div id="setting-interface-scale" class="flex items-center justify-between gap-5 px-4 py-3">
                  <div class="text-sm font-medium text-[var(--text-primary)]">Interface scale</div>
                  <div class="flex divide-x divide-[var(--border-default)] overflow-hidden rounded-lg border border-[var(--border-default)]">{#each interfaceScaleOptions as option}<button class={compactSegmentClass($interfaceScale === option.value)} type="button" on:click={() => interfaceScale.set(option.value)}>{option.label}</button>{/each}</div>
                </div>
              </div>
            </section>

            <section id="setting-tag-banner" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
              <div class="flex items-start justify-between gap-6">
                <div class="text-sm font-semibold text-[var(--text-primary)]">Tag banner height</div>
                <div class="w-[360px] max-w-[58%]">
                  <div class="flex items-center gap-3"><input class="min-w-0 flex-1 accent-pink-500" type="range" min="280" max="720" step="20" value={$tagBannerHeight} on:input={(event) => tagBannerHeight.set(Number((event.currentTarget as HTMLInputElement).value))} /><span class="w-14 text-right text-xs font-semibold text-pink-200">{$tagBannerHeight}px</span></div>
                  <div class="mt-2 flex justify-end divide-x divide-[var(--border-default)] overflow-hidden rounded-lg border border-[var(--border-default)]">{#each bannerPresets as preset}<button class={compactSegmentClass($tagBannerHeight === preset.value) + ' flex-1'} type="button" on:click={() => tagBannerHeight.set(preset.value)}>{preset.label}</button>{/each}</div>
                </div>
              </div>
            </section>
          </div>
        {:else if selectedSection === 'player'}
          <div class="mx-auto max-w-3xl space-y-4">
            <section class="rounded-2xl border border-violet-400/20 bg-[radial-gradient(circle_at_85%_0%,rgba(139,92,246,.16),transparent_42%),linear-gradient(135deg,#171421,#101017_70%)] px-4 py-3.5">
              <div class="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <div class="text-[10px] font-semibold uppercase tracking-[0.2em] text-violet-300">Shared media engine</div>
                  <h3 class="mt-1 text-lg font-bold text-white">Player</h3>
                  <p class="mt-1 text-xs text-[var(--text-muted)]">One transport for Karaoke and YouTube, with module-specific subtitles and queues.</p>
                </div>
                <button class="rounded-lg border border-white/10 bg-black/15 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-white/5 hover:text-[var(--text-primary)]" type="button" on:click={resetCurrentSection}>Reset section</button>
              </div>
            </section>

            <section id="setting-player-center-controls" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
              <div class="flex items-center justify-between gap-6">
                <div>
                  <div class="text-sm font-semibold text-[var(--text-primary)]">Center controls</div>
                  <p class="mt-1 text-xs text-[var(--text-muted)]">Show the large play/pause and 10-second skip buttons over the video.</p>
                </div>
                <button class="relative h-6 w-11 shrink-0 rounded-full transition-colors {$playerCenterControls ? 'bg-violet-500' : 'bg-[var(--bg-base)]'}" type="button" role="switch" aria-checked={$playerCenterControls} aria-label="Toggle center controls" on:click={() => playerCenterControls.set(!$playerCenterControls)}>
                  <span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform {$playerCenterControls ? 'translate-x-5' : ''}"></span>
                </button>
              </div>
            </section>

            <section id="setting-player-darken-overlay" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
              <div class="flex items-center justify-between gap-6">
                <div>
                  <div class="text-sm font-semibold text-[var(--text-primary)]">Darken overlay</div>
                  <p class="mt-1 text-xs text-[var(--text-muted)]">Dim the video behind the center controls for better visibility.</p>
                </div>
                <button class="relative h-6 w-11 shrink-0 rounded-full transition-colors {$playerDarkenOverlay ? 'bg-violet-500' : 'bg-[var(--bg-base)]'}" type="button" role="switch" aria-checked={$playerDarkenOverlay} aria-label="Toggle darken overlay" on:click={() => playerDarkenOverlay.set(!$playerDarkenOverlay)}>
                  <span class="absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform {$playerDarkenOverlay ? 'translate-x-5' : ''}"></span>
                </button>
              </div>
            </section>

            <section id="setting-player-reveal-mode" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
              <div class="text-sm font-semibold text-[var(--text-primary)]">Control reveal</div>
              <p class="mt-1 text-xs text-[var(--text-muted)]">Pointer movement reveals the controls; click or tap the video toggles them, and playback hides them again after three seconds of inactivity.</p>
            </section>

            <section id="setting-player-mini-style" class="rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] p-4">
              <div class="flex items-start justify-between gap-6">
                <div>
                  <div class="text-sm font-semibold text-[var(--text-primary)]">Mini player style</div>
                  <p class="mt-1 text-xs text-[var(--text-muted)]">Layout when navigating away from a playing video.</p>
                </div>
                <div class="w-[220px] max-w-[50%]">
                  <div class="flex divide-x divide-[var(--border-default)] overflow-hidden rounded-lg border border-[var(--border-default)]">
                    <button class={compactSegmentClass($miniPlayerStyle === 'card')} type="button" on:click={() => miniPlayerStyle.set('card')}>Card</button>
                    <button class={compactSegmentClass($miniPlayerStyle === 'bar')} type="button" on:click={() => miniPlayerStyle.set('bar')}>Bar</button>
                  </div>
                  <p class="mt-2 text-[11px] text-[var(--text-muted)]">{$miniPlayerStyle === 'card' ? 'Floating card with live video in the corner.' : 'Slim bar at the bottom with thumbnail and title.'}</p>
                </div>
              </div>
            </section>
          </div>
        {:else if selectedSection === 'library'}
          <div class="mx-auto max-w-3xl space-y-4">
            <LibraryImportSettings {toolRunning} surface="storage" />

            <section id="setting-library-health" class="overflow-hidden rounded-2xl border border-cyan-400/20 bg-[radial-gradient(circle_at_82%_0%,rgba(34,211,238,.14),transparent_38%),linear-gradient(135deg,#101a20,#101017_72%)] p-4">
              <div class="flex flex-wrap items-center justify-between gap-4">
                <div class="flex flex-wrap items-center gap-3">
                  <div class="flex items-center gap-2 text-sm font-semibold text-cyan-100"><span class="h-2 w-2 rounded-full {syncRunning ? 'animate-pulse bg-cyan-300' : 'bg-green-400'}"></span>Library: {!foldersLoaded || !toolsLoaded ? 'Loading' : syncRunning ? 'Indexing' : 'Ready'}</div>
                  <div class="flex flex-wrap gap-2">
                    <span class="rounded-full border border-cyan-300/10 bg-cyan-500/[0.07] px-2.5 py-1 text-[11px] text-cyan-100">{foldersLoaded ? `${libraryFolders.length} root${libraryFolders.length === 1 ? '' : 's'}` : 'Loading roots…'}</span>
                    <span class="rounded-full border border-white/5 bg-black/15 px-2.5 py-1 text-[11px] text-[var(--text-primary)]">{foldersLoaded ? `${totalIndexedImages.toLocaleString()} indexed images` : 'Loading image count…'}</span>
                  </div>
                </div>
                {#if syncTool}
                  <button id="setting-rescan" class="shrink-0 rounded-xl bg-cyan-500/15 px-4 py-2 text-xs font-semibold text-cyan-100 ring-1 ring-inset ring-cyan-300/15 hover:bg-cyan-500/25 disabled:opacity-50" type="button" disabled={toolRunning} on:click={() => runMaintenanceTool(syncTool)}>{syncTool.status === 'running' ? 'Re-scanning…' : 'Re-scan library'}</button>
                {/if}
              </div>
              {#if syncStatus && syncStatus.status !== 'idle'}
                <div class="mt-4 rounded-xl border border-white/5 bg-black/15 px-3 py-2.5">
                  <div class="flex items-center justify-between text-xs"><span class="{syncRunning ? 'text-cyan-200' : syncStatus.status === 'error' ? 'text-red-300' : 'text-green-300'}">{syncRunning ? ('Syncing' + (syncStatus.total ? (' - ' + (syncStatus.progress ?? 0) + ' / ' + syncStatus.total) : '…')) : syncStatus.status === 'error' ? 'Sync failed' : 'Sync complete'}</span>{#if syncRunning}<span class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent"></span>{/if}</div>
                  {#if syncRunning && syncStatus.total}<div class="mt-2 h-1.5 overflow-hidden rounded-full bg-[#15151d]"><div class="h-full rounded-full bg-cyan-400 transition-all" style="width: {((syncStatus.progress ?? 0) / syncStatus.total) * 100}%"></div></div>{/if}
                </div>
              {/if}
            </section>

            <section id="setting-folders" class="overflow-visible rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)]">
              <div class="border-b border-[#242432] p-4">
                <div class="flex items-center justify-between gap-4"><h4 class="text-sm font-semibold text-[var(--text-primary)]">Library roots</h4><span class="rounded-full bg-cyan-500/10 px-2.5 py-1 text-[11px] text-cyan-300">{libraryFolders.length}</span></div>
                <div class="mt-3 flex gap-2">
                  <input class="min-w-0 flex-1 rounded-xl border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none placeholder:text-gray-650 focus:border-cyan-400/50" type="text" placeholder="D:\Pictures\MyFolder" bind:value={folderPathInput} on:keydown={(event) => event.key === 'Enter' && addFolder()} />
                  <button class="rounded-xl border border-[var(--border-default)] px-3 py-2 text-xs text-[var(--text-primary)] hover:bg-white/5 disabled:opacity-50" type="button" disabled={folderBusy} on:click={browseForFolder}>Browse…</button>
                  <button class="rounded-xl bg-cyan-500/15 px-4 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-500/25 disabled:opacity-40" type="button" disabled={folderBusy || !folderPathInput.trim()} on:click={addFolder}>Add folder</button>
                </div>
                {#if folderError}<p class="mt-2 text-xs text-red-400">{folderError}</p>{/if}
                {#if folderMessage}<p class="mt-2 text-xs text-green-400">{folderMessage}</p>{/if}
              </div>
              <div class="space-y-2 p-3">
                {#if !foldersLoaded}<div class="rounded-xl border border-dashed border-[var(--border-default)] px-4 py-8 text-center text-sm text-[var(--text-muted)]">Loading library roots…</div>{:else if libraryFolders.length === 0}<div class="rounded-xl border border-dashed border-[var(--border-default)] px-4 py-8 text-center text-sm text-[var(--text-muted)]">No library roots yet. Add an existing media folder above.</div>{/if}
                {#each libraryFolders as folder (folder.selector)}
                  <div class="relative flex items-center gap-3 rounded-xl border border-white/5 bg-[var(--bg-base)] px-3 py-2.5 transition-colors hover:border-cyan-300/15">
                    <span class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-cyan-500/10 text-cyan-300"><svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d={iconPath('folder')} /></svg></span>
                    <div class="min-w-0 flex-1"><div class="flex items-baseline gap-2"><span class="truncate text-sm font-semibold text-[var(--text-primary)]">{folder.name}</span><span class="shrink-0 rounded-full bg-white/[0.04] px-2 py-0.5 text-[10px] text-[var(--text-muted)]">{folder.count.toLocaleString()} images</span></div><div class="mt-0.5 truncate text-xs text-gray-600" title={folder.path ?? ''}>{folder.path ?? 'Built-in scan folder'}</div></div>
                    <details class="group relative">
                      <summary class="grid h-8 w-8 cursor-pointer list-none place-items-center rounded-lg text-[var(--text-muted)] hover:bg-white/5 hover:text-[var(--text-primary)]" title="Folder actions" aria-label="Folder actions">•••</summary>
                      <div class="absolute right-0 top-9 z-20 w-36 overflow-hidden rounded-lg border border-[var(--border-default)] bg-[#191920] p-1 shadow-xl shadow-black/50">
                        <button class="w-full rounded-md px-3 py-2 text-left text-xs text-[var(--text-primary)] hover:bg-white/5" type="button" disabled={syncRunning || toolRunning} on:click={() => rescanLibraryFolder(folder)}>Re-scan</button>
                        {#if folder.registered}<button class="w-full rounded-md px-3 py-2 text-left text-xs text-cyan-200 hover:bg-cyan-500/10" type="button" disabled={folderBusy || syncRunning || toolRunning} on:click={() => relocateLibraryFolder(folder)}>Relocate…</button>{/if}
                        {#if folder.registered}<button class="w-full rounded-md px-3 py-2 text-left text-xs text-red-300 hover:bg-red-500/10" type="button" disabled={folderRemovalBusy} on:click={() => openFolderRemoval(folder)}>Remove…</button>{/if}
                      </div>
                    </details>
                  </div>
                {/each}
              </div>
            </section>
          </div>
        {:else if selectedSection === 'metadata'}
          <div class="mx-auto max-w-3xl space-y-4">
            <section class="rounded-2xl border border-purple-400/20 bg-[radial-gradient(circle_at_50%_-20%,rgba(139,92,246,.18),transparent_48%),linear-gradient(135deg,#171322,#101017_72%)] p-4" aria-label="Metadata flow">
              <div class="mb-3 text-sm font-semibold text-purple-100">Metadata flow</div>
              <div class="grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-3">
                <div class="rounded-xl border border-white/5 bg-black/20 p-3 text-center"><div class="text-xs font-semibold text-[var(--text-primary)]">Media</div><div class="mt-1 text-[10px] text-gray-600">{foldersLoaded ? `${totalIndexedImages.toLocaleString()} indexed` : 'Loading…'}</div></div>
                <span class="text-gray-700">→</span>
                <div class="rounded-xl border border-purple-300/10 bg-purple-500/[0.07] p-3 text-center"><div class="text-xs font-semibold text-purple-100">Sidecars</div><div class="mt-1 text-[10px] text-purple-300">Durable metadata</div></div>
                <span class="text-gray-700">→</span>
                <div class="rounded-xl border border-cyan-300/10 bg-cyan-500/[0.06] p-3 text-center"><div class="text-xs font-semibold text-cyan-100">SQLite</div><div class="mt-1 text-[10px] {toolRunning ? 'text-purple-300' : 'text-green-400'}">{toolRunning ? 'Working' : 'Ready'}</div></div>
              </div>
            </section>

            <details id="setting-danbooru-access" class="group overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)]">
              <summary class="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3.5">
                <div class="flex items-center gap-3"><span class="grid h-9 w-9 place-items-center rounded-xl bg-amber-500/10 text-amber-300"><svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4" /></svg></span><div class="text-sm font-semibold text-[var(--text-primary)]">Danbooru credentials</div></div>
                <div class="flex items-center gap-3"><span class="rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase {credentials?.configured ? 'border-green-400/20 bg-green-500/10 text-green-300' : 'border-amber-400/20 bg-amber-500/10 text-amber-300'}">{!credentialsLoaded ? 'Loading…' : credentials?.configured ? (credentials.source === 'environment' ? 'Environment' : 'Configured') : 'Not configured'}</span><svg class="h-4 w-4 text-gray-600 transition-transform group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 9l6 6 6-6" /></svg></div>
              </summary>
              <div class="border-t border-[#242432] bg-black/10 p-4">
                {#if credentials?.source === 'environment'}<p class="mb-3 rounded-lg border border-cyan-400/15 bg-cyan-500/[0.06] px-3 py-2 text-xs text-cyan-200">Environment credentials are active and override saved values.</p>{/if}
                <div class="grid gap-3 sm:grid-cols-2">
                  <label><span class="mb-1 block text-[11px] font-medium text-[var(--text-muted)]">Username</span><input class="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-purple-400/60" type="text" autocomplete="username" bind:value={credentialUsername} /></label>
                  <label><span class="mb-1 block text-[11px] font-medium text-[var(--text-muted)]">API key {credentials?.has_api_key ? '(leave blank to keep)' : ''}</span><input class="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-purple-400/60" type="password" autocomplete="off" bind:value={credentialApiKey} /></label>
                </div>
                <div class="mt-3 flex flex-wrap gap-2"><button class="rounded-lg bg-purple-500/20 px-3 py-2 text-xs font-semibold text-purple-100 hover:bg-purple-500/30 disabled:opacity-50" type="button" disabled={credentialBusy || !credentialUsername.trim()} on:click={saveDanbooruCredentials}>Save securely</button><button class="rounded-lg border border-[var(--border-default)] px-3 py-2 text-xs text-[var(--text-primary)] hover:bg-white/5 disabled:opacity-50" type="button" disabled={credentialBusy || !credentials?.configured} on:click={checkCredentials}>Test connection</button>{#if credentials?.source === 'saved'}<button class="rounded-lg px-3 py-2 text-xs text-red-300 hover:bg-red-500/10 disabled:opacity-50" type="button" disabled={credentialBusy} on:click={clearDanbooruCredentials}>Remove saved</button>{/if}</div>
                {#if credentialMessage}<p class="mt-2 text-xs text-green-400">{credentialMessage}</p>{/if}{#if credentialError}<p class="mt-2 text-xs text-red-400">{credentialError}</p>{/if}
              </div>
            </details>

            <LibraryImportSettings {toolRunning} surface="metadata" />
            {#if toolError}<p class="rounded-xl border border-red-400/15 bg-red-500/[0.06] px-4 py-3 text-xs text-red-300">{toolError}</p>{/if}
          </div>
        {:else if selectedSection === 'reddit'}
          <RedditSettings />
        {:else if selectedSection === 'karaoke'}
          <KaraokeSettings />
        {:else if selectedSection === 'youtube'}
          <YouTubeSettings />
        {:else if selectedSection === 'language'}
          <LanguageSettings />
        {:else}
          <div class="mx-auto max-w-3xl space-y-4">
            <BackupRestoreSettings {toolRunning} />
            <ThumbnailCacheSettings />

            <section class="overflow-hidden rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)]">
              <div class="border-b border-[#242432] px-4 py-3"><h4 class="text-sm font-semibold text-[var(--text-primary)]">Recovery maintenance</h4></div>
              <div class="divide-y divide-[var(--border-subtle)]">
                {#each safetyTools as tool (tool.id)}
                  <div id={tool.id === 'sqlite' ? 'setting-rebuild' : 'setting-clean-sidecars'} class="flex items-start justify-between gap-4 px-4 py-3.5">
                    <div class="flex items-start gap-3"><span class="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg {tool.id === 'sqlite' ? 'bg-red-500/10 text-red-300' : 'bg-amber-500/10 text-amber-300'}"><svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">{#if tool.id === 'sqlite'}<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d={iconPath('database')} />{:else}<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5" />{/if}</svg></span><div><h4 class="text-sm font-semibold text-[var(--text-primary)]">{maintenanceDisplayName(tool)}</h4><p class="mt-0.5 text-xs leading-relaxed text-[var(--text-muted)]">{tool.description}</p>{#if tool.id === 'sqlite'}<p class="mt-1 text-[11px] text-red-200/60">Recovery only. The user database is kept separately.</p>{/if}</div></div>
                    <button class="shrink-0 rounded-lg border px-3 py-2 text-xs font-semibold disabled:opacity-50 {tool.id === 'sqlite' ? 'border-red-400/20 text-red-300 hover:bg-red-500/10' : 'border-amber-400/20 text-amber-300 hover:bg-amber-500/10'}" type="button" disabled={toolRunning} on:click={() => runMaintenanceTool(tool)}>{tool.status === 'running' ? 'Running…' : 'Run'}</button>
                  </div>
                {/each}
              </div>
            </section>

            <section class="rounded-xl border border-green-400/15 bg-green-500/[0.045] px-4 py-3.5" aria-label="Cleanup safety">
              <div class="flex flex-wrap items-center gap-2 text-[11px]"><span class="font-semibold text-green-200">Cleanup safety</span><span class="rounded-full bg-black/15 px-2.5 py-1 text-green-100/65">Originals untouched</span><span class="rounded-full bg-black/15 px-2.5 py-1 text-green-100/65">Sidecar deletes counted first</span><span class="rounded-full bg-black/15 px-2.5 py-1 text-green-100/65">Unavailable roots skipped</span></div>
            </section>
            {#if toolError}<p class="rounded-xl border border-red-400/15 bg-red-500/[0.06] px-4 py-3 text-xs text-red-300">{toolError}</p>{/if}
          </div>
        {/if}
      {/if}

    </main>
  </div>

  {#if folderRemovalFolder}
    <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
    <div class="fixed inset-0 z-[140] grid place-items-center bg-black/80 p-4 backdrop-blur-sm" on:click={closeFolderRemoval}>
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <div
        class="w-full max-w-xl overflow-hidden rounded-2xl border border-red-300/20 bg-[#111117] shadow-2xl shadow-black/80"
        role="dialog"
        aria-modal="true"
        aria-labelledby="folder-removal-title"
        tabindex="-1"
        use:focusTrap={{ close: closeFolderRemoval }}
        on:click|stopPropagation
      >
        <header class="flex items-start justify-between gap-4 border-b border-[#292936] bg-[radial-gradient(circle_at_85%_-30%,rgba(239,68,68,.16),transparent_52%)] px-5 py-4">
          <div>
            <div class="text-[10px] font-semibold uppercase tracking-[0.2em] text-red-300">Library root removal</div>
            <h3 id="folder-removal-title" class="mt-1 text-xl font-bold text-gray-100">What should be removed?</h3>
            <p class="mt-1 break-all text-xs text-[var(--text-muted)]">{folderRemovalFolder.path ?? folderRemovalFolder.name}</p>
          </div>
          <button class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-[var(--border-default)] text-[var(--text-muted)] hover:bg-white/5 hover:text-[var(--text-primary)] disabled:opacity-40" type="button" disabled={folderRemovalBusy} aria-label="Cancel folder removal" on:click={closeFolderRemoval}>×</button>
        </header>

        <div class="space-y-4 p-5">
          <div class="flex items-center gap-3 rounded-xl border border-green-400/15 bg-green-500/[0.055] px-3.5 py-3">
            <span class="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-green-500/10 text-green-300">✓</span>
            <div><div class="text-xs font-semibold text-green-100">External images affected: 0</div><p class="mt-0.5 text-[11px] text-green-100/55">Neither choice moves, edits, or deletes your original media folder.</p></div>
          </div>

          {#if folderRemovalBusy && !folderRemovalPreview}
            <div class="flex items-center justify-center gap-3 rounded-xl border border-[var(--border-default)] bg-black/15 px-4 py-10 text-sm text-[var(--text-secondary)]"><span class="h-4 w-4 animate-spin rounded-full border-2 border-cyan-300 border-t-transparent"></span>Calculating exact impact…</div>
          {:else if folderRemovalPreview}
            <div class="grid grid-cols-2 gap-3">
              <div class="rounded-xl border border-[var(--border-default)] bg-black/15 p-3"><div class="text-[10px] uppercase tracking-wider text-gray-600">SQLite records</div><div class="mt-1 text-lg font-bold text-[var(--text-primary)]">{folderRemovalPreview.indexed_files.toLocaleString()}</div><div class="text-[11px] text-gray-600">indexed images</div></div>
              <div class="rounded-xl border border-[var(--border-default)] bg-black/15 p-3"><div class="text-[10px] uppercase tracking-wider text-gray-600">Current sidecars</div><div class="mt-1 text-lg font-bold text-[var(--text-primary)]">{folderRemovalPreview.sidecar_files.toLocaleString()}</div><div class="text-[11px] text-gray-600">{formatByteCount(folderRemovalPreview.sidecar_bytes)}</div></div>
            </div>

            <div class="space-y-2.5">
              <button class="group flex w-full items-start gap-3 rounded-xl border border-cyan-400/15 bg-cyan-500/[0.045] px-4 py-3.5 text-left transition-colors hover:border-cyan-300/35 hover:bg-cyan-500/[0.09] disabled:opacity-45" type="button" disabled={folderRemovalBusy} on:click={() => confirmFolderRemoval('unindex_only')}>
                <span class="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-cyan-500/10 text-cyan-300"><svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d={iconPath('database')} /></svg></span>
                <span class="min-w-0 flex-1"><span class="block text-sm font-semibold text-cyan-100">Un-index only</span><span class="mt-1 block text-xs leading-relaxed text-[var(--text-muted)]">Remove the folder registration and {folderRemovalPreview.indexed_files.toLocaleString()} image records from SQLite. Keep all sidecars.</span></span>
                <span class="mt-1 text-cyan-300 transition-transform group-hover:translate-x-0.5">→</span>
              </button>

              <button class="group flex w-full items-start gap-3 rounded-xl border border-red-400/20 bg-red-500/[0.045] px-4 py-3.5 text-left transition-colors hover:border-red-300/40 hover:bg-red-500/[0.09] disabled:opacity-45" type="button" disabled={folderRemovalBusy} on:click={() => confirmFolderRemoval('delete_sidecars')}>
                <span class="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-red-500/10 text-red-300"><svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13M10 11v5m4-5v5" /></svg></span>
                <span class="min-w-0 flex-1"><span class="block text-sm font-semibold text-red-100">Delete sidecars &amp; un-index</span><span class="mt-1 block text-xs leading-relaxed text-[var(--text-muted)]">Permanently delete {folderRemovalPreview.sidecar_files.toLocaleString()} current central sidecars ({formatByteCount(folderRemovalPreview.sidecar_bytes)}), then remove the SQLite records.</span></span>
                <span class="mt-1 text-red-300 transition-transform group-hover:translate-x-0.5">→</span>
              </button>
            </div>

            <p class="text-center text-[11px] text-gray-600">Archived sidecar history is preserved by both choices.</p>
          {/if}

          {#if folderRemovalError}<p class="rounded-lg border border-red-400/15 bg-red-500/[0.06] px-3 py-2 text-xs text-red-300">{folderRemovalError}</p>{/if}
          <div class="flex justify-end"><button class="rounded-lg border border-[var(--border-default)] px-3 py-2 text-xs text-[var(--text-primary)] hover:bg-white/5 disabled:opacity-40" type="button" disabled={folderRemovalBusy} on:click={closeFolderRemoval}>Cancel</button></div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .settings-scroll {
    scrollbar-gutter: stable;
    contain: layout paint;
    overscroll-behavior: contain;
  }

  .settings-layer {
    contain: paint;
    isolation: isolate;
  }

  .settings-shell {
    contain: layout paint style;
  }

  .settings-section-list {
    scrollbar-gutter: stable;
    overscroll-behavior: contain;
  }

  .settings-section-marker {
    animation: settings-section-marker-in 180ms ease-out;
  }

  :global(.setting-flash) {
    position: relative;
    z-index: 1;
    animation: setting-highlight 1.35s ease-out;
  }

  @keyframes settings-section-marker-in {
    from {
      opacity: 0;
      transform: translateX(-4px) scaleY(0.45);
    }
    to {
      opacity: 1;
      transform: translateX(0) scaleY(1);
    }
  }

  @keyframes setting-highlight {
    0%, 20% {
      box-shadow: 0 0 0 2px rgba(216, 180, 254, 0.78), 0 0 28px rgba(168, 85, 247, 0.22);
      background-color: rgba(168, 85, 247, 0.11);
    }
    100% {
      box-shadow: 0 0 0 0 transparent;
      background-color: transparent;
    }
  }

  @media (max-width: 780px) {
    .settings-shell {
      grid-template-columns: 205px minmax(0, 1fr);
    }
  }

  @media (max-width: 640px) {
    .settings-layer {
      padding: 0;
    }

    .settings-shell {
      height: 100dvh;
      width: 100vw;
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: auto auto minmax(0, 1fr);
      border: 0;
      border-radius: 0;
    }

    .settings-shell > :global(header) {
      grid-column: 1;
    }

    .settings-shell > :global(aside) {
      height: auto;
      border-right: 0;
      border-bottom: 1px solid #252532;
      padding: 0.75rem;
    }

    .settings-section-list {
      display: flex;
      margin-top: 0.65rem;
      gap: 0.4rem;
      overflow-x: auto;
      padding-bottom: 0.1rem;
    }

    .settings-section-list :global(button) {
      flex: 0 0 auto;
      width: auto;
      margin: 0;
    }

    .settings-group-label {
      display: none;
    }

    .settings-section-marker {
      inset: auto 0.75rem 0.2rem;
      width: auto;
      height: 0.125rem;
    }
  }
</style>
