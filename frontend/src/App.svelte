<script lang="ts">
  import { onMount } from 'svelte';
  import './app.css';
  import { SUITE_NAME } from './lib/product';
  import { suiteApi } from './lib/suiteApi';
  import { activeModule, appTheme, enabledModules, interfaceScale, motionPreference, suiteModules } from './lib/stores';
  import { applyTheme } from './lib/themes';
  import { surfaceComponent } from './modules/surfaces';
  import { moduleUi } from './modules/registry';
  import MiniPlayer from './components/media/MiniPlayer.svelte';
  import ToastViewport from './components/ui/ToastViewport.svelte';

  $: if (typeof document !== 'undefined') {
    document.documentElement.dataset.motion = $motionPreference;
    document.documentElement.dataset.interfaceScale = $interfaceScale;
    applyTheme($appTheme);
  }

  $: baseDescriptor = $suiteModules.find((module) => module.is_base);
  $: requestedDescriptor = $suiteModules.find((module) => module.slug === $activeModule);
  $: activeDescriptor = requestedDescriptor?.enabled ? requestedDescriptor : baseDescriptor;
  $: ActiveSurface = surfaceComponent(activeDescriptor?.slug ?? 'files');
  $: if (activeDescriptor && activeDescriptor.slug !== $activeModule) {
    activeModule.set(activeDescriptor.slug);
  }
  $: if (typeof document !== 'undefined') {
    document.title = activeDescriptor && !activeDescriptor.is_base
      ? `${SUITE_NAME} - ${activeDescriptor.name}`
      : SUITE_NAME;
  }
  $: if (typeof document !== 'undefined' && activeDescriptor) {
    const accent = moduleUi(activeDescriptor.slug).accent;
    document.documentElement.style.setProperty('--module-accent', accent);
    document.documentElement.style.setProperty('--module-accent-muted', accent + '26');
    document.documentElement.style.setProperty('--module-accent-hover', accent + '18');
  }

  onMount(async () => {
    try {
      const modules = await suiteApi.listModules();
      suiteModules.set(modules);
      enabledModules.set(modules.filter((m) => m.enabled).map((m) => m.id));
    } catch (e) {
      console.error('Failed to load modules:', e);
    }
  });
</script>

<div class="flex h-full min-h-0 flex-col" style="background:var(--bg-surface);color:var(--text-primary)">
  <svelte:component this={ActiveSurface} />
  <MiniPlayer />
  <ToastViewport />
</div>
