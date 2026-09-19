from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class KaraokeYouTubeFrontendContractTests(unittest.TestCase):
    def test_both_optional_surfaces_are_registry_driven(self) -> None:
        surfaces = (
            ROOT / "frontend" / "src" / "modules" / "surfaces.ts"
        ).read_text(encoding="utf-8")
        registry = (
            ROOT / "frontend" / "src" / "modules" / "registry.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("karaoke: KaraokeSurface", surfaces)
        self.assertIn("youtube: YouTubeSurface", surfaces)
        self.assertIn("slug: 'karaoke'", registry)
        self.assertIn("slug: 'youtube'", registry)

    def test_player_is_neutral_click_driven_and_keyboard_accessible(self) -> None:
        player = (
            ROOT
            / "frontend"
            / "src"
            / "components"
            / "media"
            / "LocalMediaPlayer.svelte"
        ).read_text(encoding="utf-8")

        self.assertIn("function stageClick(event: MouseEvent)", player)
        self.assertIn("controlsVisible = false", player)
        self.assertNotIn("$playerControlReveal", player)
        self.assertNotIn("hiddenPointerRevealAt", player)
        self.assertIn("function scheduleHide()", player)
        self.assertIn("setTimeout(() =>", player)
        self.assertIn("3000", player)
        self.assertIn("arrowleft: () => seekBy(-5)", player)
        self.assertIn("arrowright: () => seekBy(5)", player)
        self.assertIn("c: togglePanel", player)
        self.assertIn("Subtitles & lyrics", player)
        self.assertIn("panelComponent", player)
        self.assertIn("initialRepeatMode", player)
        self.assertIn("syncNativeTracks", player)
        self.assertIn("track[data-track-id]", player)
        self.assertIn("requestPictureInPicture", player)
        self.assertIn("requestFullscreen", player)
        self.assertIn("Playback queue", player)
        self.assertIn("seekBy(-10)", player)
        self.assertIn("seekBy(10)", player)
        self.assertIn('class="repeat-one"', player)
        self.assertIn("prefers-reduced-motion", player)

        lyrics = (
            ROOT
            / "frontend"
            / "src"
            / "components"
            / "media"
            / "LyricsPanel.svelte"
        ).read_text(encoding="utf-8")
        self.assertIn("followEnabled", lyrics)
        self.assertIn("activeCue?.romaji", lyrics)
        self.assertIn("activeCue?.translation", lyrics)
        self.assertIn("selectedTrack?.cues ?? []", lyrics)
        self.assertNotIn("(cue.index)", lyrics)

        media_types = (
            ROOT / "frontend" / "src" / "lib" / "media.ts"
        ).read_text(encoding="utf-8")
        karaoke_wrapper = (
            ROOT / "frontend" / "src" / "modules" / "karaoke" / "KaraokePlayer.svelte"
        ).read_text(encoding="utf-8")
        youtube_wrapper = (
            ROOT / "frontend" / "src" / "modules" / "youtube" / "YouTubePlayer.svelte"
        ).read_text(encoding="utf-8")
        self.assertIn("cues?: SubtitleCue[]", media_types)
        self.assertIn('accent="#67e8f9"', karaoke_wrapper)
        self.assertIn("initialPosition={0}", karaoke_wrapper)
        self.assertIn("karaokeApi.captionUrl", karaoke_wrapper)
        self.assertIn('accent="#ff4e45"', youtube_wrapper)
        self.assertNotIn("Keivotos Karaoke", player)
        self.assertNotIn("Back to karaoke detail", player)

    def test_karaoke_searches_kara_moe_then_hands_query_to_youtube(self) -> None:
        karaoke = (
            ROOT
            / "frontend"
            / "src"
            / "modules"
            / "karaoke"
            / "KaraokeSurface.svelte"
        ).read_text(encoding="utf-8")
        youtube = (
            ROOT
            / "frontend"
            / "src"
            / "modules"
            / "youtube"
            / "YouTubeSurface.svelte"
        ).read_text(encoding="utf-8")

        self.assertIn("karaokeApi.searchKaraMoe(query)", karaoke)
        self.assertIn("Search YouTube instead", karaoke)
        self.assertIn("Replace broken copy", karaoke)
        self.assertIn("queueIds", karaoke)
        self.assertIn("moduleHandoff.set({ target: 'youtube', query", karaoke)
        self.assertIn("handoff.query", youtube)
        self.assertIn("handoff.intent === 'karaoke'", youtube)
        self.assertIn("youtubeApi.resumeJob", youtube)
        self.assertIn("Add to queue", karaoke)
        self.assertIn("Update local copy", youtube)
        self.assertIn("queueIds", youtube)

    def test_youtube_never_streams_remote_video_in_the_player(self) -> None:
        youtube = (
            ROOT
            / "frontend"
            / "src"
            / "modules"
            / "youtube"
            / "YouTubeSurface.svelte"
        ).read_text(encoding="utf-8")
        api = (
            ROOT / "frontend" / "src" / "lib" / "youtubeApi.ts"
        ).read_text(encoding="utf-8")
        wrapper = (
            ROOT / "frontend" / "src" / "modules" / "youtube" / "YouTubePlayer.svelte"
        ).read_text(encoding="utf-8")

        self.assertIn("youtubeApi.inspectUrl", youtube)
        self.assertIn("youtubeApi.mediaUrl(item.item_id, item.video_path)", wrapper)
        self.assertNotIn("src={result.webpage_url}", youtube)
        self.assertNotIn("src={selectedInspection.webpage_url}", youtube)
        self.assertIn("/media/${encodeURIComponent(itemId)}", api)
        self.assertIn("/search-thumbnails/${encodeURIComponent(cacheId)}", api)

    def test_youtube_download_sheet_exposes_real_plan_and_saved_defaults(self) -> None:
        sheet = (
            ROOT
            / "frontend"
            / "src"
            / "modules"
            / "youtube"
            / "YouTubeDownloadSheet.svelte"
        ).read_text(encoding="utf-8")
        settings = (
            ROOT / "frontend" / "src" / "modules" / "youtube" / "settings.ts"
        ).read_text(encoding="utf-8")
        modal = (
            ROOT / "frontend" / "src" / "components" / "AppSettingsModal.svelte"
        ).read_text(encoding="utf-8")

        self.assertIn("item.available_resolutions", sheet)
        self.assertIn("plan.selected_formats", sheet)
        self.assertIn("plan.selection_sha256", sheet)
        self.assertIn("authorized", sheet)
        self.assertIn("youtube-download-defaults", settings)
        self.assertIn("id: 'karaoke'", modal)
        self.assertIn("id: 'youtube'", modal)
        self.assertIn("<KaraokeSettings />", modal)
        self.assertIn("<YouTubeSettings />", modal)

    def test_add_to_karaoke_uses_server_side_handoff(self) -> None:
        youtube = (
            ROOT
            / "frontend"
            / "src"
            / "modules"
            / "youtube"
            / "YouTubeSurface.svelte"
        ).read_text(encoding="utf-8")

        self.assertIn("karaokeApi.importYouTube(item.item_id)", youtube)
        self.assertNotIn("new FileReader()", youtube)
        self.assertNotIn("contentBase64", youtube)

    def test_youtube_uses_a_native_wrapper_without_fake_karaoke_tracks(self) -> None:
        youtube = (
            ROOT / "frontend" / "src" / "modules" / "youtube" / "YouTubeSurface.svelte"
        ).read_text(encoding="utf-8")
        wrapper = (
            ROOT / "frontend" / "src" / "modules" / "youtube" / "YouTubePlayer.svelte"
        ).read_text(encoding="utf-8")
        self.assertIn("<YouTubePlayer", youtube)
        self.assertNotIn("type LyricTrack", youtube)
        self.assertNotIn("cues: []", youtube)
        self.assertIn("SubtitleTrack", wrapper)
        self.assertIn("hasPrevious={currentIndex > 0}", wrapper)

    def test_player_resumes_idle_hide_after_closing_overlays(self) -> None:
        player = (
            ROOT / "frontend" / "src" / "components" / "media" / "LocalMediaPlayer.svelte"
        ).read_text(encoding="utf-8")
        self.assertIn("function overlayStateChanged()", player)
        self.assertIn("on:click={togglePanel}", player)
        self.assertIn("on:click={toggleQueue}", player)
        self.assertIn("on:click={toggleSettings}", player)
        self.assertIn("overlayStateChanged();", player)


if __name__ == "__main__":
    unittest.main()
