from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
LANGUAGE_ROOT = ROOT / "frontend" / "src" / "modules" / "language"


class LanguageFrontendContractTests(unittest.TestCase):
    def test_language_surface_and_original_icon_are_registry_driven(self) -> None:
        surfaces = (
            ROOT / "frontend" / "src" / "modules" / "surfaces.ts"
        ).read_text(encoding="utf-8")
        registry = (
            ROOT / "frontend" / "src" / "modules" / "registry.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("language: LanguageSurface", surfaces)
        self.assertIn("slug: 'language'", registry)
        self.assertIn("iconSrc: '/language-logo.svg'", registry)
        self.assertTrue((ROOT / "frontend" / "public" / "language-logo.svg").is_file())

    def test_surface_exposes_the_full_browse_and_selection_workflow(self) -> None:
        surface = (LANGUAGE_ROOT / "LanguageSurface.svelte").read_text(
            encoding="utf-8"
        )

        for label in (
            "Words",
            "Today",
            "Sentences",
            "Grammar",
            "Decks",
            "Browser",
            "Hangul Atlas",
            "Analyzer",
            "Favorites",
            "Select",
            "Practice",
            "Connect",
            "Add word",
        ):
            self.assertIn(label, surface)
        self.assertIn("<GridSizeMenu", surface)
        self.assertIn("$languagePageSize === 'all'", surface)
        self.assertIn("appendWords()", surface)
        self.assertIn("languageApi.bulk(", surface)
        self.assertIn("<LanguageDetail", surface)
        self.assertIn("<LanguageComposer", surface)
        self.assertIn("<LanguagePractice", surface)
        self.assertIn("<LanguageBrowser", surface)
        self.assertIn("<LanguageHangulAtlas", surface)
        self.assertIn("<LanguageAnalyzer", surface)
        self.assertIn("languageApi.practiceStats()", surface)
        self.assertIn("content: view === 'sentences'", surface)
        self.assertNotIn("limit: specialView ? 5000", surface)
        self.assertNotIn("window.prompt", surface)
        self.assertIn("<LanguageNameDialog", surface)
        self.assertIn("Save filter", surface)
        self.assertIn("Clear all", surface)
        self.assertIn("Mastery legend", surface)

    def test_new_library_views_and_word_menu_keep_the_complete_workflow(self) -> None:
        surface = (LANGUAGE_ROOT / "LanguageSurface.svelte").read_text(
            encoding="utf-8"
        )
        browser = (LANGUAGE_ROOT / "LanguageBrowser.svelte").read_text(
            encoding="utf-8"
        )
        atlas = (LANGUAGE_ROOT / "LanguageHangulAtlas.svelte").read_text(
            encoding="utf-8"
        )
        menu = (LANGUAGE_ROOT / "LanguageWordMenu.svelte").read_text(
            encoding="utf-8"
        )
        analyzer = (LANGUAGE_ROOT / "LanguageAnalyzer.svelte").read_text(
            encoding="utf-8"
        )

        for label in (
            "Number",
            "Source",
            "Korean",
            "English",
            "Mongolian",
            "Note type",
            "Deck",
            "Mastery",
            "Media",
            "Flags",
        ):
            self.assertIn(label, browser)
        self.assertIn("selectedWord", browser)
        self.assertIn("LanguageWordMenu", browser)
        self.assertIn("INITIALS", atlas)
        self.assertIn("reduced", atlas)
        self.assertIn("Edit word", menu)
        self.assertIn("Add to list", menu)
        self.assertIn("aria-haspopup=\"menu\"", menu)
        self.assertIn("languageApi.analyze(", analyzer)
        self.assertIn("languageApi.saveAnalysis(", analyzer)
        self.assertIn("languageApi.dictionaryLookup(", analyzer)
        self.assertIn("Runs locally", analyzer)
        self.assertIn("No Anki writes", analyzer)
        self.assertIn("#121119", analyzer)
        self.assertIn("Keivotos owns the presentation", analyzer)
        self.assertIn("<ActionMenu", surface)
        self.assertIn("on:contextmenu", surface)

    def test_detail_composer_and_practice_keep_protected_interactions(self) -> None:
        detail = (LANGUAGE_ROOT / "LanguageDetail.svelte").read_text(
            encoding="utf-8"
        )
        composer = (LANGUAGE_ROOT / "LanguageComposer.svelte").read_text(
            encoding="utf-8"
        )
        practice = (LANGUAGE_ROOT / "LanguagePractice.svelte").read_text(
            encoding="utf-8"
        )

        self.assertIn("event.key === 'ArrowLeft'", detail)
        self.assertIn("event.key === 'ArrowRight'", detail)
        self.assertIn("event.code === 'Space'", detail)
        self.assertIn("example.includes(word.sentence_form)", detail)
        self.assertIn("languageAutoplay", detail)
        self.assertIn("local overrides and never sent to Anki", composer)
        self.assertIn("on:drop=", composer)
        self.assertIn("languageApi.attachMedia(", composer)
        self.assertIn("languageApi.retireWord(", composer)
        self.assertIn("'ko_meaning'", practice)
        self.assertIn("'meaning_ko'", practice)
        self.assertIn("'cloze'", practice)
        self.assertIn("'audio_meaning'", practice)
        self.assertIn("languageApi.practiceAnswer(", practice)
        self.assertIn("Practice just these again", practice)

    def test_language_media_is_always_served_from_the_local_api(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in LANGUAGE_ROOT.glob("*.svelte")
        )
        api = (
            ROOT / "frontend" / "src" / "lib" / "languageApi.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("/media/${encodeURIComponent(wordId)}/${role}", api)
        self.assertIn("languageApi.mediaUrl(", source)
        self.assertNotIn("ankiweb.net", source.lower())
        self.assertNotIn("https://", source)
        self.assertNotIn("<iframe", source)

    def test_anki_network_actions_are_explicit_user_flows(self) -> None:
        settings = (LANGUAGE_ROOT / "LanguageSettings.svelte").read_text(
            encoding="utf-8"
        )
        sync = (LANGUAGE_ROOT / "LanguageSyncDialog.svelte").read_text(
            encoding="utf-8"
        )
        surface = (LANGUAGE_ROOT / "LanguageSurface.svelte").read_text(
            encoding="utf-8"
        )

        self.assertIn("languageApi.status()", settings)
        self.assertIn("on:click={runProbe}", settings)
        self.assertIn("on:click={probe}", sync)
        self.assertIn("unmappedNoteTypes", sync)
        self.assertIn("Confirm proposed field mapping", sync)
        self.assertIn('aria-label="Close Anki mirror"', sync)
        self.assertNotIn("languageApi.probe()", surface)
        self.assertNotIn("languageApi.previewImport(", surface)
        self.assertIn("never changes Anki", sync)

    def test_languages_settings_are_searchable_in_the_suite_modal(self) -> None:
        modal = (
            ROOT / "frontend" / "src" / "components" / "AppSettingsModal.svelte"
        ).read_text(encoding="utf-8")

        self.assertIn("id: 'language'", modal)
        self.assertIn("language-anki", modal)
        self.assertIn("language-profiles", modal)
        self.assertIn("language-storage", modal)
        self.assertIn("language-display", modal)
        self.assertIn("language-dictionary", modal)
        self.assertIn("<LanguageSettings />", modal)
        settings = (LANGUAGE_ROOT / "LanguageSettings.svelte").read_text(
            encoding="utf-8"
        )
        self.assertIn("Study and meaning profile", settings)
        self.assertIn("languageStudyProfile", settings)


if __name__ == "__main__":
    unittest.main()
