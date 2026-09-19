# Third-party notices

Keivotos source code is licensed under Apache-2.0. It depends on open-source Python and JavaScript packages whose copyrights and licenses remain with their respective authors. The Windows build collects installed runtime license files into `licenses/`; `package-lock.json` and `uv.lock` record the resolved package set used by the build.

## Separately invoked tools

The portable folder keeps the following command-line tools separate from `Keivotos.exe` and invokes them as child processes:

- **gallery-dl 1.32.6** - GPL-2.0-only. Source: <https://github.com/mikf/gallery-dl>. The portable build includes its license.
- **FFmpeg 7.1 Gyan.dev essentials build** - configured with GPLv3 components. Source and build-provider information is included in `licenses/FFmpeg-7.1/FFMPEG_SOURCE.md`; `ffmpeg.exe -L` prints the applicable license and build configuration.
Do not remove license or source-availability material when redistributing a portable archive. Dependency licenses can change between versions; inspect the generated distribution rather than treating this file as legal advice.

## Reddit archive dependencies

- **zstandard 0.25.0** - BSD-3-Clause. Source:
  <https://github.com/indygreg/python-zstandard>. Keivotos uses its streaming
  reader for user-supplied Arctic Shift `.zst` files.
- **yt-dlp 2026.7.4** - Unlicense. Source:
  <https://github.com/yt-dlp/yt-dlp>. The standalone Reddit media command
  invokes the installed Python distribution as a child process and does not
  use yt-dlp's self-update feature.
- **mfget 0.1.3** - MIT. Source:
  <https://github.com/worstgirlinamerica/mediafire-dl>. Keivotos uses its
  MediaFire metadata resolver for user-confirmed single-file links, then
  streams the resolved bytes through Keivotos's own DNS, redirect, size,
  timeout, and free-space guards.

## Languages Analyzer dependencies

- **kiwipiepy 0.23.2** and **kiwipiepy-model 0.23.0** - LGPL-3.0.
  Source: <https://github.com/bab2min/kiwipiepy>. Keivotos uses Kiwi locally
  for Korean sentence splitting, morphology, lemmas, and part-of-speech tags.
  The Analyzer does not upload pasted text.
- **koroman 1.0.16** - MIT. Source:
  <https://github.com/fluorescent-t/korean-romanizer>. Keivotos uses it to
  show Revised Romanization beside local analyses.
- **NumPy 2.4.6** - BSD-3-Clause. Source:
  <https://github.com/numpy/numpy>. It is a runtime dependency of kiwipiepy.
- **tqdm 4.70.0** - MPL-2.0 and MIT. Source:
  <https://github.com/tqdm/tqdm>. It is a runtime dependency of kiwipiepy.
