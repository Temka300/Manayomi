from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RedditFrontendContractTests(unittest.TestCase):
    def test_reddit_surface_is_registered_and_cursor_driven(self) -> None:
        surfaces = (
            ROOT / "frontend" / "src" / "modules" / "surfaces.ts"
        ).read_text(encoding="utf-8")
        registry = (
            ROOT / "frontend" / "src" / "modules" / "registry.ts"
        ).read_text(encoding="utf-8")
        surface = (
            ROOT
            / "frontend"
            / "src"
            / "modules"
            / "reddit"
            / "RedditSurface.svelte"
        ).read_text(encoding="utf-8")

        self.assertIn("reddit: RedditSurface", surfaces)
        self.assertIn("slug: 'reddit'", registry)
        self.assertIn("new IntersectionObserver", surface)
        self.assertIn("cursor: nextCursor", surface)
        self.assertIn("page.next_cursor", surface)
        self.assertIn("page.has_more", surface)
        self.assertIn("Search saved posts and comments", surface)

    def test_reddit_ui_renders_only_sha_addressed_local_media(self) -> None:
        reddit_root = (
            ROOT / "frontend" / "src" / "modules" / "reddit"
        )
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in reddit_root.glob("*.svelte")
        )
        api = (
            ROOT / "frontend" / "src" / "lib" / "redditApi.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("/media/${encodeURIComponent(sha256)}", api)
        self.assertIn("redditMediaUrl(", source)
        self.assertNotIn("https://i.redd.it", source)
        self.assertNotIn("https://preview.redd.it", source)
        self.assertNotIn("post.url", source)
        self.assertIn("does not hotlink Reddit images", source)

    def test_post_thread_and_community_snapshots_have_visible_entry_points(self) -> None:
        surface = (
            ROOT
            / "frontend"
            / "src"
            / "modules"
            / "reddit"
            / "RedditSurface.svelte"
        ).read_text(encoding="utf-8")
        thread = (
            ROOT
            / "frontend"
            / "src"
            / "modules"
            / "reddit"
            / "RedditThreadView.svelte"
        ).read_text(encoding="utf-8")
        community = (
            ROOT
            / "frontend"
            / "src"
            / "modules"
            / "reddit"
            / "RedditCommunityView.svelte"
        ).read_text(encoding="utf-8")

        self.assertIn("<RedditThreadView", surface)
        self.assertIn("<RedditCommunityView", surface)
        self.assertIn("Archived comments", thread)
        self.assertIn("preserved gap marker", thread)
        self.assertIn("About community", community)
        self.assertIn("Rules", community)
        self.assertIn("Wiki", community)
        self.assertIn("Moderators", community)

    def test_reddit_navigation_profiles_threads_and_observation_charts_are_actionable(self) -> None:
        reddit_root = ROOT / "frontend" / "src" / "modules" / "reddit"
        surface = (reddit_root / "RedditSurface.svelte").read_text(
            encoding="utf-8"
        )
        thread = (reddit_root / "RedditThreadView.svelte").read_text(
            encoding="utf-8"
        )
        comment = (reddit_root / "RedditCommentBranch.svelte").read_text(
            encoding="utf-8"
        )
        post = (reddit_root / "RedditPostCard.svelte").read_text(encoding="utf-8")
        profile = (reddit_root / "RedditProfileView.svelte").read_text(
            encoding="utf-8"
        )
        post = (reddit_root / "RedditPostCard.svelte").read_text(
            encoding="utf-8"
        )

        for label in ("Home", "Popular", "Communities", "Profiles"):
            self.assertIn(label, surface)
        self.assertIn("<RedditProfileView", surface)
        self.assertIn("<ActionMenu", surface)
        self.assertIn("refreshPost(", surface)
        self.assertIn("refreshCommunity(", surface)
        self.assertIn("Score history", thread)
        self.assertIn("Comment-count history", thread)
        self.assertIn("Upvote-ratio history", thread)
        self.assertIn("<RedditCommentBranch", thread)
        self.assertIn("<svelte:self", comment)
        self.assertIn("collapsed", comment)
        self.assertIn("Refresh profile", profile)
        self.assertIn("More actions for saved post", post)

    def test_save_link_drawer_uses_capture_api_and_right_to_left_motion(self) -> None:
        reddit_root = (
            ROOT / "frontend" / "src" / "modules" / "reddit"
        )
        surface = (reddit_root / "RedditSurface.svelte").read_text(
            encoding="utf-8"
        )
        drawer = (reddit_root / "RedditCaptureDrawer.svelte").read_text(
            encoding="utf-8"
        )
        api = (
            ROOT / "frontend" / "src" / "lib" / "redditApi.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("Save a Reddit link", surface)
        self.assertIn("<RedditCaptureDrawer", surface)
        self.assertLess(surface.index(">Refresh</button>"), surface.index("Save a Reddit link"))
        self.assertIn("transition:fly={{ x: 460, duration: 240 }}", drawer)
        self.assertIn("transition:fade={{ duration: 160 }}", drawer)
        self.assertIn("redditApi.capture(value", drawer)
        self.assertIn("Saving link…", drawer)
        self.assertIn("Images and GIFs", drawer)
        self.assertIn("Videos", drawer)
        self.assertIn("Linked files", drawer)
        self.assertIn("redditApi.mediaPlan(", drawer)
        self.assertIn("redditApi.startMediaJob(", drawer)
        self.assertIn("redditApi.mediaJob(", drawer)
        self.assertIn("Download plan ready", drawer)
        self.assertIn("progress stays in the Reddit header", drawer)
        self.assertIn("RedditDownloadActivity", surface)
        self.assertIn("Reddit download activity", surface)
        self.assertIn("indexed.comments", drawer)
        self.assertIn("post<RedditCaptureResult>('/capture', { url }, signal)", api)
        self.assertIn("Profile link:", drawer)

    def test_deep_threads_and_pointer_menus_remain_readable(self) -> None:
        reddit_root = ROOT / "frontend" / "src" / "modules" / "reddit"
        comment = (reddit_root / "RedditCommentBranch.svelte").read_text(
            encoding="utf-8"
        )
        post = (reddit_root / "RedditPostCard.svelte").read_text(
            encoding="utf-8"
        )
        action_menu = (
            ROOT / "frontend" / "src" / "components" / "ui" / "ActionMenu.svelte"
        ).read_text(encoding="utf-8")

        self.assertNotIn("Math.min(depth, 12) * 14", comment)
        self.assertIn("depth < 7 ? 14 : 4", comment)
        self.assertIn("break-words", comment)
        self.assertIn("placeMenu(x, y, items.length)", action_menu)
        self.assertIn("anchorX: bounds.left", post)
        self.assertIn("event.detail.anchorX", (
            reddit_root / "RedditSurface.svelte"
        ).read_text(encoding="utf-8"))

    def test_outbound_links_are_visible_without_remote_previews(self) -> None:
        reddit_root = ROOT / "frontend" / "src" / "modules" / "reddit"
        cards = (reddit_root / "RedditLinkCards.svelte").read_text(
            encoding="utf-8"
        )
        thread = (reddit_root / "RedditThreadView.svelte").read_text(
            encoding="utf-8"
        )
        post = (reddit_root / "RedditPostCard.svelte").read_text(
            encoding="utf-8"
        )

        self.assertIn("Linked files and pages", cards)
        self.assertIn("href={link.url}", cards)
        self.assertIn('rel="noopener noreferrer"', cards)
        self.assertNotIn("<iframe", cards)
        self.assertIn("<RedditLinkCards", thread)
        self.assertIn("<RedditLinkCards", post)

    def test_reddit_settings_control_capture_defaults_and_show_archive_health(self) -> None:
        reddit_root = ROOT / "frontend" / "src" / "modules" / "reddit"
        modal = (
            ROOT / "frontend" / "src" / "components" / "AppSettingsModal.svelte"
        ).read_text(encoding="utf-8")
        settings = (reddit_root / "RedditSettings.svelte").read_text(
            encoding="utf-8"
        )
        defaults = (reddit_root / "settings.ts").read_text(encoding="utf-8")
        drawer = (reddit_root / "RedditCaptureDrawer.svelte").read_text(
            encoding="utf-8"
        )

        self.assertIn("id: 'reddit'", modal)
        self.assertIn("<RedditSettings />", modal)
        self.assertIn("setting-reddit-download-defaults", settings)
        self.assertIn("setting-reddit-archive-health", settings)
        self.assertIn("setting-reddit-storage-policy", settings)
        self.assertIn("setting-reddit-download-safety", settings)
        self.assertIn("redditApi.status()", settings)
        self.assertIn("duplicate_alias_candidates", settings)
        self.assertIn("reddit-capture-defaults", defaults)
        self.assertIn("get(redditCaptureDefaults)", drawer)
        self.assertIn("retry_failed: retryFailed", drawer)


if __name__ == "__main__":
    unittest.main()
