"""Manayomi manga module — nHentai hoarder integrated into the Keivotos suite.

Ported from the Waifu-Manga-Hoarder SvelteKit app and the original
Waifu-Hoard-Hoarder prototype. Follows the Keivotos two-database contract:

- ``manga.sqlite`` is the disposable index (rebuildable from sidecars/rescans);
- ``user.sqlite`` (module-local) is irreplaceable user data — roots, favorites,
  pins, categories, settings — and is never dropped or rebuilt.
"""
