"""Reusable direct-link capture workflow for the Reddit CLI and HTTP API."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from modules.reddit.archive import CaptureOptions, import_local_source, open_archive
from modules.reddit.arctic_shift_api import (
    DEFAULT_MAX_COMMENTS,
    DEFAULT_MAX_WIKI_PAGES,
    ArcticShiftApiClient,
)
from modules.reddit.community import (
    CommunityImportOptions,
    import_community_source,
)
from modules.reddit.url_targets import CaptureTarget


def capture_direct_target(
    target: CaptureTarget,
    *,
    database_path: Path,
    output_root: Path,
    media_directory: Path,
    client: ArcticShiftApiClient,
    max_comments: int = DEFAULT_MAX_COMMENTS,
    max_wiki_pages: int = DEFAULT_MAX_WIKI_PAGES,
    comments: str = "all",
    save_external_assets: bool = False,
    external_domains: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Preserve one bounded structured response bundle, then normalize it."""
    if target.kind not in {"post", "subreddit", "user"}:
        raise ValueError(
            "Direct capture accepts only a Reddit post, subreddit, or user URL"
        )

    database_path = Path(database_path).expanduser().resolve(strict=False)
    output_root = Path(output_root).expanduser().resolve(strict=False)
    media_directory = Path(media_directory).expanduser().resolve(strict=False)
    bundle = client.capture(
        target,
        output_root,
        max_comments=max_comments,
        max_wiki_pages=max_wiki_pages,
    )

    imports: list[dict[str, Any]] = []
    if target.kind in {"post", "user"}:
        summary = import_local_source(
            database_path,
            Path(bundle.source_files["records"]),
            target,
            CaptureOptions(
                posts_limit=1 if target.kind == "post" else 100,
                comments=comments,
                save_images="both",
                save_videos="full",
                save_avatars=True,
                save_linked_files=True,
                save_external_assets=save_external_assets,
                external_domains=external_domains,
                media_directory=str(media_directory),
            ),
        )
        imports.append(asdict(summary))
    else:
        assert target.subreddit is not None
        for source_type in ("about", "rules", "wiki"):
            summary = import_community_source(
                database_path,
                Path(bundle.source_files[source_type]),
                target.subreddit,
                CommunityImportOptions(
                    source_type=source_type,
                    source_scope="scoped",
                ),
            )
            imports.append(asdict(summary))

    indexed: dict[str, Any]
    if target.kind == "post":
        assert target.post_id is not None
        with open_archive(database_path) as connection:
            post_exists = connection.execute(
                "SELECT 1 FROM posts WHERE id=?",
                (target.post_id,),
            ).fetchone()
            comment_count = connection.execute(
                "SELECT COUNT(*) FROM comments WHERE post_id=?",
                (target.post_id,),
            ).fetchone()[0]
        if post_exists is None:
            raise ValueError(
                "The response bundle was preserved, but its requested post "
                "was not present in the local index"
            )
        indexed = {
            "target_kind": "post",
            "target_id": target.post_id,
            "posts": 1,
            "comments": int(comment_count),
        }
    elif target.kind == "subreddit":
        assert target.subreddit is not None
        indexed = {
            "target_kind": "subreddit",
            "target_id": target.subreddit,
            "community_snapshots": sum(
                int(summary.get("records_imported", 0)) for summary in imports
            ),
        }
    else:
        assert target.username is not None
        with open_archive(database_path) as connection:
            post_count = connection.execute(
                "SELECT COUNT(*) FROM posts WHERE author=? COLLATE NOCASE",
                (target.username,),
            ).fetchone()[0]
            comment_count = connection.execute(
                "SELECT COUNT(*) FROM comments WHERE author=? COLLATE NOCASE",
                (target.username,),
            ).fetchone()[0]
        indexed = {
            "target_kind": "user",
            "target_id": target.username,
            "posts": int(post_count),
            "comments": int(comment_count),
        }

    return {
        "format": "keivotos-reddit-direct-capture-result-v1",
        "capture": bundle.as_dict(),
        "imports": imports,
        "indexed": indexed,
    }
