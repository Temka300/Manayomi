"""Read-only projections for the local Reddit library.

All display surfaces and runtime endpoints consume this module. It opens the
rebuildable index in SQLite read-only/query-only mode and never falls back to
remote media URLs.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Generator, Iterable

from modules.reddit.archive import search_archive
from modules.reddit.comment_trees import (
    CommentTreeOptions,
    build_comment_tree,
    normalize_post_id,
)
from modules.reddit.community import normalize_subreddit
from modules.reddit.links import extract_outbound_links


LIBRARY_FORMAT = "keivotos-reddit-library-v1"
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
DEFAULT_MAX_THREAD_COMMENTS = 250_000
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_TABLES = {
    "assets",
    "capture_jobs",
    "comments",
    "media_objects",
    "posts",
}


class RedditLibraryError(RuntimeError):
    """Raised when the local Reddit library cannot be read safely."""


class InvalidCursorError(RedditLibraryError):
    """Raised when a pagination cursor is malformed."""


def _bounded_limit(limit: int) -> int:
    if not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")
    return limit


def _cursor_encode(created_utc: float, post_id: str) -> str:
    value = json.dumps(
        {"created_utc": created_utc, "id": post_id},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _cursor_decode(value: str) -> tuple[float, str]:
    try:
        padding = "=" * (-len(value) % 4)
        decoded = base64.urlsafe_b64decode(value + padding)
        payload = json.loads(decoded.decode("utf-8"))
        created_utc = payload["created_utc"]
        post_id = payload["id"]
        if (
            not isinstance(created_utc, (int, float))
            or isinstance(created_utc, bool)
            or not isinstance(post_id, str)
            or not post_id
            or set(payload) != {"created_utc", "id"}
        ):
            raise ValueError
        return float(created_utc), post_id
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidCursorError("Invalid Reddit feed cursor") from exc


def _json_value(value: str | None, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


@contextmanager
def _open_readonly(
    database_path: Path,
) -> Generator[sqlite3.Connection | None, None, None]:
    path = Path(database_path).expanduser().resolve(strict=False)
    if not path.is_file():
        yield None
        return
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"{path.as_uri()}?mode=ro",
            uri=True,
            timeout=60,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        tables = {
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            raise RedditLibraryError(
                "Database is not a compatible Reddit archive; missing tables: "
                + ", ".join(missing)
            )
        yield connection
    except sqlite3.Error as exc:
        raise RedditLibraryError(
            f"Cannot read Reddit archive {path}: {exc}"
        ) from exc
    finally:
        if connection is not None:
            connection.close()


def _post_payload(row: sqlite3.Row) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "fullname": row["fullname"],
        "subreddit": row["subreddit"],
        "author": row["author"],
        "author_id": row["author_id"],
        "title": row["title"],
        "selftext": row["selftext"],
        "selftext_html": row["selftext_html"],
        "created_utc": row["created_utc"],
        "edited_utc": row["edited_utc"],
        "permalink": row["permalink"],
        "url": row["url"],
        "domain": row["domain"],
        "flair_text": row["flair_text"],
        "score": row["score"],
        "upvote_ratio": row["upvote_ratio"],
        "num_comments": row["num_comments"],
        "is_self": row["is_self"],
        "nsfw": row["nsfw"],
        "spoiler": row["spoiler"],
        "stickied": row["stickied"],
        "locked": row["locked"],
        "archived": row["archived"],
        "distinguished": row["distinguished"],
        "removed_by_category": row["removed_by_category"],
        "first_observed_at": row["first_observed_at"],
        "latest_observed_at": row["latest_observed_at"],
    }
    payload["links"] = [
        link.as_dict()
        for link in extract_outbound_links(row["url"], row["selftext"])
    ]
    return payload


def _comment_counts(
    connection: sqlite3.Connection,
    post_ids: Iterable[str],
) -> dict[str, int]:
    values = sorted(set(post_ids))
    result = {post_id: 0 for post_id in values}
    if not values:
        return result
    placeholders = ",".join("?" for _ in values)
    for row in connection.execute(
        f"""
        SELECT post_id, COUNT(*) AS count
        FROM comments
        WHERE post_id IN ({placeholders})
        GROUP BY post_id
        """,
        values,
    ).fetchall():
        result[str(row["post_id"])] = int(row["count"])
    return result


def _add_comment_links(comment_tree: dict[str, Any]) -> None:
    pending = [
        *comment_tree.get("root_comments", []),
        *comment_tree.get("detached_comments", []),
    ]
    while pending:
        node = pending.pop()
        node["links"] = [
            link.as_dict()
            for link in extract_outbound_links(None, node.get("body"))
        ]
        pending.extend(node.get("children", []))


def _media_for_owners(
    connection: sqlite3.Connection,
    owner_type: str,
    owner_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    values = sorted(set(owner_ids))
    result = {
        owner_id: {"local": [], "queued_count": 0, "failed_count": 0}
        for owner_id in values
    }
    if not values:
        return result
    placeholders = ",".join("?" for _ in values)
    rows = connection.execute(
        f"""
        SELECT a.owner_id, a.role, a.url, a.status, e.object_sha256,
               mo.byte_size, mo.content_type
        FROM assets a
        LEFT JOIN asset_download_events e ON e.id=(
            SELECT event.id
            FROM asset_download_events event
            WHERE event.asset_id=a.id AND event.event_type='complete'
            ORDER BY event.id DESC
            LIMIT 1
        )
        LEFT JOIN media_objects mo ON mo.sha256=e.object_sha256
        WHERE a.owner_type=? AND a.owner_id IN ({placeholders})
        ORDER BY a.owner_id, a.id
        """,
        (owner_type, *values),
    ).fetchall()
    seen_local: set[tuple[str, str]] = set()
    for row in rows:
        owner = result[str(row["owner_id"])]
        sha256 = row["object_sha256"]
        if sha256 and (str(row["owner_id"]), str(sha256)) not in seen_local:
            seen_local.add((str(row["owner_id"]), str(sha256)))
            source_links = extract_outbound_links(row["url"], None)
            owner["local"].append(
                {
                    "sha256": sha256,
                    "role": row["role"],
                    "source_url": row["url"],
                    "display_name": (
                        source_links[0].label
                        if source_links
                        else row["role"]
                    ),
                    "byte_size": row["byte_size"],
                    "content_type": row["content_type"],
                }
            )
        elif row["status"] == "failed":
            owner["failed_count"] += 1
        elif row["status"] != "downloaded":
            owner["queued_count"] += 1
    return result


class RedditLibrary:
    """One read-only interface over a standalone Reddit archive."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path).expanduser().resolve(strict=False)

    def list_posts(
        self,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
        subreddit: str | None = None,
        author: str | None = None,
        flair: str | None = None,
        sort: str = "new",
    ) -> dict[str, Any]:
        limit = _bounded_limit(limit)
        if sort not in {"new", "popular"}:
            raise ValueError("sort must be new or popular")
        clauses: list[str] = []
        params: list[Any] = []
        if subreddit:
            clauses.append("subreddit=? COLLATE NOCASE")
            params.append(normalize_subreddit(subreddit))
        if author:
            clauses.append("author=? COLLATE NOCASE")
            params.append(author.strip())
        if flair:
            clauses.append("flair_text=? COLLATE NOCASE")
            params.append(flair.strip())
        if cursor:
            created_utc, post_id = _cursor_decode(cursor)
            clauses.append(
                "(COALESCE(created_utc, -1) < ? OR "
                "(COALESCE(created_utc, -1) = ? AND id < ? COLLATE BINARY))"
            )
            params.extend((created_utc, created_utc, post_id))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with _open_readonly(self.database_path) as connection:
            if connection is None:
                return {
                    "format": LIBRARY_FORMAT,
                    "items": [],
                    "next_cursor": None,
                    "has_more": False,
                }
            order = (
                "COALESCE(score, -1) DESC, COALESCE(created_utc, -1) DESC, id DESC"
                if sort == "popular"
                else "COALESCE(created_utc, -1) DESC, id DESC"
            )
            rows = connection.execute(
                f"""
                SELECT * FROM posts
                {where}
                ORDER BY {order}
                LIMIT ?
                """,
                (*params, limit + 1),
            ).fetchall()
            has_more = sort == "new" and len(rows) > limit
            selected = rows[:limit]
            media = _media_for_owners(
                connection,
                "post",
                (str(row["id"]) for row in selected),
            )
            archived_comment_counts = _comment_counts(
                connection,
                (str(row["id"]) for row in selected),
            )
        items = []
        for row in selected:
            payload = _post_payload(row)
            payload["media"] = media[str(row["id"])]
            payload["archived_comment_count"] = archived_comment_counts[
                str(row["id"])
            ]
            items.append(payload)
        next_cursor = None
        if has_more and selected:
            final = selected[-1]
            next_cursor = _cursor_encode(
                float(final["created_utc"] if final["created_utc"] is not None else -1),
                str(final["id"]),
            )
        return {
            "format": LIBRARY_FORMAT,
            "items": items,
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

    def list_communities(self) -> list[dict[str, Any]]:
        with _open_readonly(self.database_path) as connection:
            if connection is None:
                return []
            rows = connection.execute(
                """
                WITH names AS (
                  SELECT subreddit FROM posts WHERE subreddit IS NOT NULL
                  UNION
                  SELECT subreddit FROM subreddit_observations
                )
                SELECT n.subreddit,
                       (SELECT COUNT(*) FROM posts p
                        WHERE p.subreddit=n.subreddit COLLATE NOCASE) AS posts,
                       (SELECT COUNT(*) FROM comments c
                        WHERE c.subreddit=n.subreddit COLLATE NOCASE) AS comments,
                       (SELECT COUNT(*) FROM subreddit_observations so
                        WHERE so.subreddit=n.subreddit COLLATE NOCASE) AS snapshots,
                       (SELECT MAX(latest_observed_at) FROM posts p
                        WHERE p.subreddit=n.subreddit COLLATE NOCASE) AS latest_observed_at
                FROM names n
                ORDER BY n.subreddit COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_profiles(self) -> list[dict[str, Any]]:
        with _open_readonly(self.database_path) as connection:
            if connection is None:
                return []
            rows = connection.execute(
                """
                WITH authors AS (
                  SELECT author FROM posts
                  WHERE author IS NOT NULL AND author NOT IN ('[deleted]', '[removed]')
                  UNION
                  SELECT author FROM comments
                  WHERE author IS NOT NULL AND author NOT IN ('[deleted]', '[removed]')
                )
                SELECT a.author,
                       (SELECT COUNT(*) FROM posts p
                        WHERE p.author=a.author COLLATE NOCASE) AS posts,
                       (SELECT COUNT(*) FROM comments c
                        WHERE c.author=a.author COLLATE NOCASE) AS comments,
                       MAX(
                         COALESCE((SELECT MAX(latest_observed_at) FROM posts p
                                   WHERE p.author=a.author COLLATE NOCASE), ''),
                         COALESCE((SELECT MAX(latest_observed_at) FROM comments c
                                   WHERE c.author=a.author COLLATE NOCASE), '')
                       ) AS latest_observed_at
                FROM authors a
                ORDER BY (posts + comments) DESC, a.author COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_profile(self, username: str) -> dict[str, Any]:
        clean = username.strip()
        if not clean or len(clean) > 32:
            raise ValueError("Invalid Reddit username")
        with _open_readonly(self.database_path) as connection:
            if connection is None:
                return {
                    "format": LIBRARY_FORMAT,
                    "username": clean,
                    "posts": [],
                    "comments": [],
                    "stats": {"posts": 0, "comments": 0, "score": 0},
                }
            post_rows = connection.execute(
                """SELECT * FROM posts WHERE author=? COLLATE NOCASE
                   ORDER BY COALESCE(created_utc, -1) DESC LIMIT 100""",
                (clean,),
            ).fetchall()
            comment_rows = connection.execute(
                """SELECT id, post_id, parent_id, subreddit, author, body,
                          created_utc, edited_utc, score, permalink,
                          first_observed_at, latest_observed_at
                   FROM comments WHERE author=? COLLATE NOCASE
                   ORDER BY COALESCE(created_utc, -1) DESC LIMIT 200""",
                (clean,),
            ).fetchall()
            media = _media_for_owners(
                connection, "post", (str(row["id"]) for row in post_rows)
            )
        posts = []
        for row in post_rows:
            item = _post_payload(row)
            item["media"] = media[str(row["id"])]
            item["archived_comment_count"] = 0
            posts.append(item)
        comments = [dict(row) for row in comment_rows]
        return {
            "format": LIBRARY_FORMAT,
            "username": clean,
            "posts": posts,
            "comments": comments,
            "stats": {
                "posts": len(posts),
                "comments": len(comments),
                "score": sum(
                    int(item.get("score") or 0) for item in [*posts, *comments]
                ),
            },
        }

    def search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        subreddit: str | None = None,
        author: str | None = None,
        record_type: str = "all",
    ) -> dict[str, Any]:
        limit = _bounded_limit(limit)
        with _open_readonly(self.database_path) as connection:
            results = (
                search_archive(
                    connection,
                    query,
                    limit=limit,
                    subreddit=subreddit,
                    author=author,
                    record_type=record_type,
                )
                if connection is not None
                else []
            )
        return {
            "format": LIBRARY_FORMAT,
            "query": query,
            "items": results,
        }

    def get_post(
        self,
        post_id: str,
        *,
        max_comments: int = DEFAULT_MAX_THREAD_COMMENTS,
    ) -> dict[str, Any] | None:
        normalized = normalize_post_id(post_id)
        with _open_readonly(self.database_path) as connection:
            if connection is None:
                return None
            row = connection.execute(
                "SELECT * FROM posts WHERE id=?",
                (normalized,),
            ).fetchone()
            if row is None:
                return None
            observations = [
                {
                    **dict(observation),
                    "vote_fields": _json_value(
                        observation["vote_fields_json"],
                        {},
                    ),
                }
                for observation in connection.execute(
                    """
                    SELECT observed_at, score, upvote_ratio, num_comments,
                           edited_utc, author, removed_by_category, my_vote,
                           reddit_saved, vote_fields_json
                    FROM post_observations
                    WHERE post_id=?
                    ORDER BY observed_at, id
                    """,
                    (normalized,),
                ).fetchall()
            ]
            for observation in observations:
                observation.pop("vote_fields_json", None)
            media = _media_for_owners(connection, "post", [normalized])[normalized]
            archived_comment_count = _comment_counts(
                connection,
                [normalized],
            )[normalized]
        comment_tree = build_comment_tree(
            self.database_path,
            normalized,
            CommentTreeOptions(max_comments=max_comments),
        )
        _add_comment_links(comment_tree)
        return {
            "format": LIBRARY_FORMAT,
            "post": {
                **_post_payload(row),
                "archived_comment_count": archived_comment_count,
            },
            "media": media,
            "observations": observations,
            "comment_tree": comment_tree,
        }

    def get_community(self, subreddit: str) -> dict[str, Any]:
        normalized = normalize_subreddit(subreddit)
        empty = {
            "format": LIBRARY_FORMAT,
            "subreddit": normalized,
            "about": None,
            "rules": None,
            "wiki": [],
            "moderators": None,
            "media": {"local": [], "queued_count": 0, "failed_count": 0},
            "history": {"about": 0, "rules": 0, "wiki": 0, "moderators": 0},
        }
        with _open_readonly(self.database_path) as connection:
            if connection is None:
                return empty
            about = connection.execute(
                """
                SELECT * FROM subreddit_observations
                WHERE subreddit=?
                ORDER BY COALESCE(retrieved_utc, -1) DESC, id DESC LIMIT 1
                """,
                (normalized,),
            ).fetchone()
            rule_snapshot = connection.execute(
                """
                SELECT * FROM subreddit_rule_snapshots
                WHERE subreddit=?
                ORDER BY COALESCE(retrieved_utc, -1) DESC, id DESC LIMIT 1
                """,
                (normalized,),
            ).fetchone()
            rules = (
                [
                    dict(row)
                    for row in connection.execute(
                        """
                        SELECT position, priority, short_name, description,
                               kind, violation_reason, created_utc
                        FROM subreddit_rule_observations
                        WHERE snapshot_id=? ORDER BY position
                        """,
                        (rule_snapshot["id"],),
                    ).fetchall()
                ]
                if rule_snapshot is not None
                else None
            )
            wiki_rows = connection.execute(
                """
                SELECT * FROM subreddit_wiki_observations
                WHERE subreddit=?
                ORDER BY path COLLATE NOCASE,
                         COALESCE(retrieved_utc, -1) DESC, id DESC
                """,
                (normalized,),
            ).fetchall()
            wiki: list[dict[str, Any]] = []
            seen_paths: set[str] = set()
            for row in wiki_rows:
                key = str(row["path"]).casefold()
                if key not in seen_paths:
                    seen_paths.add(key)
                    wiki.append(dict(row))
            moderator_snapshot = connection.execute(
                """
                SELECT * FROM subreddit_moderator_snapshots
                WHERE subreddit=?
                ORDER BY COALESCE(retrieved_utc, -1) DESC, id DESC LIMIT 1
                """,
                (normalized,),
            ).fetchone()
            moderators = (
                [
                    {
                        **dict(row),
                        "permissions": _json_value(
                            row["permissions_json"],
                            [],
                        ),
                    }
                    for row in connection.execute(
                        """
                        SELECT position, username, account_id,
                               permissions_json, added_utc
                        FROM subreddit_moderator_observations
                        WHERE snapshot_id=? ORDER BY position
                        """,
                        (moderator_snapshot["id"],),
                    ).fetchall()
                ]
                if moderator_snapshot is not None
                else None
            )
            if moderators is not None:
                for moderator in moderators:
                    moderator.pop("permissions_json", None)
            history = {
                "about": connection.execute(
                    "SELECT COUNT(*) FROM subreddit_observations WHERE subreddit=?",
                    (normalized,),
                ).fetchone()[0],
                "rules": connection.execute(
                    "SELECT COUNT(*) FROM subreddit_rule_snapshots WHERE subreddit=?",
                    (normalized,),
                ).fetchone()[0],
                "wiki": connection.execute(
                    "SELECT COUNT(*) FROM subreddit_wiki_observations WHERE subreddit=?",
                    (normalized,),
                ).fetchone()[0],
                "moderators": connection.execute(
                    "SELECT COUNT(*) FROM subreddit_moderator_snapshots WHERE subreddit=?",
                    (normalized,),
                ).fetchone()[0],
            }
            media = _media_for_owners(
                connection,
                "subreddit",
                [normalized],
            )[normalized]
        about_payload = dict(about) if about is not None else None
        if about_payload is not None:
            about_payload["metadata"] = _json_value(
                about_payload.pop("metadata_json", None),
                {},
            )
        return {
            "format": LIBRARY_FORMAT,
            "subreddit": normalized,
            "about": about_payload,
            "rules": (
                {"snapshot": dict(rule_snapshot), "items": rules}
                if rule_snapshot is not None
                else None
            ),
            "wiki": wiki,
            "moderators": (
                {"snapshot": dict(moderator_snapshot), "items": moderators}
                if moderator_snapshot is not None
                else None
            ),
            "media": media,
            "history": history,
        }

    def status(self) -> dict[str, Any]:
        with _open_readonly(self.database_path) as connection:
            if connection is None:
                return {
                    "format": LIBRARY_FORMAT,
                    "initialized": False,
                    "database_path": str(self.database_path),
                    "counts": {
                        "posts": 0,
                        "comments": 0,
                        "communities": 0,
                        "media_objects": 0,
                        "queued_assets": 0,
                        "duplicate_alias_candidates": 0,
                    },
                    "jobs": [],
                }
            counts = {
                "posts": connection.execute(
                    "SELECT COUNT(*) FROM posts"
                ).fetchone()[0],
                "comments": connection.execute(
                    "SELECT COUNT(*) FROM comments"
                ).fetchone()[0],
                "communities": connection.execute(
                    "SELECT COUNT(DISTINCT subreddit) FROM subreddit_observations"
                ).fetchone()[0],
                "media_objects": connection.execute(
                    "SELECT COUNT(*) FROM media_objects"
                ).fetchone()[0],
                "queued_assets": connection.execute(
                    "SELECT COUNT(*) FROM assets WHERE status='queued'"
                ).fetchone()[0],
                "duplicate_alias_candidates": connection.execute(
                    """
                    SELECT COALESCE(SUM(asset_count - 1), 0)
                    FROM (
                      SELECT a.owner_type, a.owner_id, e.object_sha256,
                             COUNT(*) AS asset_count
                      FROM assets a
                      JOIN asset_download_events e ON e.id=(
                        SELECT latest.id FROM asset_download_events latest
                        WHERE latest.asset_id=a.id
                          AND latest.event_type='complete'
                        ORDER BY latest.id DESC LIMIT 1
                      )
                      WHERE e.object_sha256 IS NOT NULL
                      GROUP BY a.owner_type, a.owner_id, e.object_sha256
                      HAVING COUNT(*) > 1
                    )
                    """
                ).fetchone()[0],
            }
            jobs = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT 'capture' AS job_family, id, target_kind AS scope,
                           status, created_at, updated_at, errors
                    FROM capture_jobs
                    UNION ALL
                    SELECT 'community', id, source_type, status,
                           created_at, updated_at, errors
                    FROM community_import_jobs
                    ORDER BY updated_at DESC LIMIT 25
                    """
                ).fetchall()
            ]
        return {
            "format": LIBRARY_FORMAT,
            "initialized": True,
            "database_path": str(self.database_path),
            "counts": counts,
            "jobs": jobs,
        }

    def media_object(self, sha256: str) -> dict[str, Any] | None:
        normalized = sha256.strip().casefold()
        if not SHA256_RE.fullmatch(normalized):
            raise ValueError("sha256 must be 64 lowercase hexadecimal digits")
        with _open_readonly(self.database_path) as connection:
            if connection is None:
                return None
            row = connection.execute(
                """
                SELECT mo.sha256, mo.byte_size, mo.content_type,
                       mo.relative_path, a.local_path, a.url, a.role
                FROM media_objects mo
                LEFT JOIN asset_download_events e ON e.id=(
                    SELECT event.id FROM asset_download_events event
                    WHERE event.object_sha256=mo.sha256
                      AND event.event_type='complete'
                    ORDER BY event.id DESC LIMIT 1
                )
                LEFT JOIN assets a ON a.id=e.asset_id
                WHERE mo.sha256=?
                """,
                (normalized,),
            ).fetchone()
        return dict(row) if row is not None else None
