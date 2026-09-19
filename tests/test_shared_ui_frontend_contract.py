from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SharedUiFrontendContractTests(unittest.TestCase):
    def test_global_toast_supports_progress_retry_and_dismiss(self) -> None:
        source = (ROOT / "frontend" / "src" / "lib" / "ui.ts").read_text(
            encoding="utf-8"
        )
        viewport = (
            ROOT
            / "frontend"
            / "src"
            / "components"
            / "ui"
            / "ToastViewport.svelte"
        ).read_text(encoding="utf-8")
        app = (ROOT / "frontend" / "src" / "App.svelte").read_text(encoding="utf-8")

        self.assertIn("progress?: number", source)
        self.assertIn("action?: ToastAction", source)
        self.assertIn("runWithToast", source)
        self.assertIn("dismissToast", source)
        self.assertIn('aria-live="polite"', viewport)
        self.assertIn("<ToastViewport />", app)

    def test_action_menu_and_dialog_foundations_are_keyboard_accessible(self) -> None:
        menu = (
            ROOT
            / "frontend"
            / "src"
            / "components"
            / "ui"
            / "ActionMenu.svelte"
        ).read_text(encoding="utf-8")
        trap = (ROOT / "frontend" / "src" / "lib" / "focusTrap.ts").read_text(
            encoding="utf-8"
        )

        self.assertIn('role="menu"', menu)
        self.assertIn('role="menuitem"', menu)
        self.assertIn("use:focusTrap", menu)
        self.assertIn("event.key !== 'Tab'", trap)
        self.assertIn("event.key === 'Escape'", trap)
        self.assertIn("previouslyFocused.focus()", trap)

    def test_action_menu_reaches_each_library_surface(self) -> None:
        surfaces = (
            ROOT / "frontend" / "src" / "components" / "FilesView.svelte",
            ROOT / "frontend" / "src" / "components" / "ImageGrid.svelte",
            ROOT / "frontend" / "src" / "modules" / "reddit" / "RedditSurface.svelte",
            ROOT / "frontend" / "src" / "modules" / "karaoke" / "KaraokeSurface.svelte",
            ROOT / "frontend" / "src" / "modules" / "youtube" / "YouTubeSurface.svelte",
            ROOT / "frontend" / "src" / "modules" / "language" / "LanguageSurface.svelte",
        )
        for path in surfaces:
            with self.subTest(surface=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn("ActionMenu", source)
                interaction_source = source
                if path.name == "ImageGrid.svelte":
                    interaction_source += (
                        ROOT / "frontend" / "src" / "components" / "ImageCard.svelte"
                    ).read_text(encoding="utf-8")
                self.assertIn("contextmenu", interaction_source)


if __name__ == "__main__":
    unittest.main()
