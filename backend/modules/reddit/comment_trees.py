"""Read-only Reddit comment-tree integrity and deterministic JSON export."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Generator, Iterator
from uuid import uuid4


COMMENT_TREE_FORMAT = "keivotos-reddit-comment-tree-v1"
COMMENT_TREE_SUMMARY_FORMAT = "keivotos-reddit-comment-tree-summary-v1"
DEFAULT_MAX_COMMENTS = 250_000
DEFAULT_MAX_OUTPUT_BYTES = 1024**3
REQUIRED_TABLES = {
    "comments",
    "comment_observations",
    "posts",
    "post_observations",
}
THING_PREFIX_RE = re.compile(r"^t\d+_", re.IGNORECASE)


class CommentTreeError(RuntimeError):
    """Base error for an offline comment-tree operation."""


class CommentTreeLimitError(CommentTreeError):
    """Raised before an operation would exceed an explicit safety limit."""


class CommentTreeExportError(CommentTreeError):
    """Raised when a create-only export cannot be installed or verified."""


@dataclass(frozen=True)
class CommentTreeOptions:
    """Bounded options for one post's read-only tree projection."""

    max_comments: int = DEFAULT_MAX_COMMENTS

    def __post_init__(self) -> None:
        if self.max_comments <= 0:
            raise ValueError("max_comments must be positive")


@dataclass(frozen=True)
class CommentTreeExport:
    """Small result returned after a create-only export."""

    post_id: str
    output_path: str
    output_bytes: int
    observed_comments: int
    root_comments: int
    detached_roots: int
    integrity_issues: int


def normalize_post_id(value: str) -> str:
    """Normalize a bare or ``t3_`` Reddit post identity."""
    result = str(value).strip()
    if result.casefold().startswith("t3_"):
        result = result[3:]
    if not result or "/" in result or "\\" in result or any(
        character.isspace() for character in result
    ):
        raise ValueError("post_id must be a bare Reddit ID or t3_<id>")
    return result.casefold()


@contextmanager
def _open_archive_readonly(
    database_path: Path,
) -> Generator[sqlite3.Connection, None, None]:
    path = Path(database_path).expanduser().resolve(strict=False)
    if not path.is_file():
        raise CommentTreeError(f"Reddit archive database does not exist: {path}")
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
            raise CommentTreeError(
                "Database is not a compatible Reddit archive; missing tables: "
                + ", ".join(missing)
            )
        yield connection
    except sqlite3.Error as exc:
        raise CommentTreeError(f"Cannot read Reddit archive {path}: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


def _node_sort_key(node: dict[str, Any]) -> tuple[bool, float, str]:
    created = node["created_utc"]
    return (created is None, float(created or 0), str(node["id"]))


def _parent_reference(raw_value: Any, post_id: str) -> tuple[str, str | None]:
    if raw_value is None or not str(raw_value).strip():
        return ("missing", None)
    raw = str(raw_value).strip()
    folded = raw.casefold()
    if folded.startswith("t3_"):
        reference = folded[3:]
        return ("post", reference) if reference == post_id else (
            "cross-post",
            reference,
        )
    if folded.startswith("t1_"):
        reference = folded[3:]
        return ("comment", reference) if reference else ("invalid", None)
    if THING_PREFIX_RE.match(folded):
        return ("invalid", folded)
    if folded == post_id:
        return ("post", folded)
    return ("comment", folded)


def _canonical_cycle(cycle: list[str]) -> tuple[str, ...]:
    pivot = min(range(len(cycle)), key=lambda index: cycle[index])
    return tuple(cycle[pivot:] + cycle[:pivot])


def _find_cycles(parent_links: dict[str, str]) -> list[tuple[str, ...]]:
    processed: set[str] = set()
    cycles: set[tuple[str, ...]] = set()
    for start in sorted(parent_links):
        if start in processed:
            continue
        path: list[str] = []
        positions: dict[str, int] = {}
        current: str | None = start
        while (
            current is not None
            and current in parent_links
            and current not in processed
        ):
            if current in positions:
                cycles.add(_canonical_cycle(path[positions[current] :]))
                break
            positions[current] = len(path)
            path.append(current)
            current = parent_links.get(current)
        processed.update(path)
    return sorted(cycles)


def _post_payload(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        key: row[key]
        for key in (
            "id",
            "fullname",
            "subreddit",
            "author",
            "author_id",
            "title",
            "selftext",
            "selftext_html",
            "created_utc",
            "edited_utc",
            "permalink",
            "url",
            "domain",
            "flair_text",
            "score",
            "upvote_ratio",
            "num_comments",
            "is_self",
            "nsfw",
            "spoiler",
            "stickied",
            "locked",
            "archived",
            "distinguished",
            "removed_by_category",
            "thumbnail_url",
            "first_observed_at",
            "latest_observed_at",
        )
    }


def _comment_payload(row: sqlite3.Row) -> dict[str, Any]:
    body = row["body"]
    body_state = (
        "deleted"
        if body == "[deleted]"
        else "removed"
        if body == "[removed]"
        else "present"
        if body is not None
        else "missing"
    )
    return {
        "id": row["id"],
        "fullname": row["fullname"],
        "post_id": row["post_id"],
        "parent_id": row["parent_id"],
        "subreddit": row["subreddit"],
        "author": row["author"],
        "body": body,
        "body_html": row["body_html"],
        "body_state": body_state,
        "created_utc": row["created_utc"],
        "edited_utc": row["edited_utc"],
        "score": row["score"],
        "depth": row["depth"],
        "is_submitter": row["is_submitter"],
        "distinguished": row["distinguished"],
        "stickied": row["stickied"],
        "score_hidden": row["score_hidden"],
        "controversiality": row["controversiality"],
        "permalink": row["permalink"],
        "first_observed_at": row["first_observed_at"],
        "latest_observed_at": row["latest_observed_at"],
    }


def _latest_declared_count(
    connection: sqlite3.Connection,
    post_id: str,
    post: sqlite3.Row | None,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT num_comments, observed_at
        FROM post_observations
        WHERE post_id=? AND num_comments IS NOT NULL
        ORDER BY observed_at DESC, id DESC
        LIMIT 1
        """,
        (post_id,),
    ).fetchone()
    if row is not None:
        return {
            "num_comments": int(row["num_comments"]),
            "observed_at": row["observed_at"],
            "source": "post_observations",
        }
    if post is not None and post["num_comments"] is not None:
        return {
            "num_comments": int(post["num_comments"]),
            "observed_at": post["latest_observed_at"],
            "source": "posts",
        }
    return None


def _integrity_issue_count(coverage: dict[str, Any]) -> int:
    counts = coverage["integrity"]["counts"]
    return sum(
        int(counts[key])
        for key in (
            "ambiguous_parent_references",
            "cross_post_parent_references",
            "cycles",
            "depth_mismatches",
            "duplicate_comment_identities",
            "duplicate_fullnames",
            "invalid_parent_references",
            "missing_parent_references",
            "missing_parent_values",
            "negative_depths",
            "self_parent_references",
            "unknown_post",
        )
    )


def build_comment_tree(
    database_path: Path,
    post_id: str,
    options: CommentTreeOptions | None = None,
) -> dict[str, Any]:
    """Build one deterministic, non-mutating comment-tree projection."""
    selected = options or CommentTreeOptions()
    normalized_post_id = normalize_post_id(post_id)
    with _open_archive_readonly(database_path) as connection:
        comment_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM comments WHERE post_id=?",
                (normalized_post_id,),
            ).fetchone()[0]
        )
        if comment_count > selected.max_comments:
            raise CommentTreeLimitError(
                f"Post {normalized_post_id} has {comment_count} comments; "
                f"--max-comments is {selected.max_comments}"
            )
        post_row = connection.execute(
            "SELECT * FROM posts WHERE id=?",
            (normalized_post_id,),
        ).fetchone()
        declared = _latest_declared_count(
            connection,
            normalized_post_id,
            post_row,
        )
        rows = connection.execute(
            """
            SELECT *
            FROM comments
            WHERE post_id=?
            ORDER BY created_utc IS NULL, created_utc, id COLLATE BINARY
            """,
            (normalized_post_id,),
        ).fetchall()
        placeholder_table_exists = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='comment_placeholders'
            """
        ).fetchone() is not None
        captured_placeholder_rows = (
            connection.execute(
                """
                SELECT placeholder_id, parent_id, child_ids_json,
                       declared_count, observed_at
                FROM comment_placeholders
                WHERE post_id=?
                ORDER BY observed_at, id
                """,
                (normalized_post_id,),
            ).fetchall()
            if placeholder_table_exists
            else []
        )

    nodes = {str(row["id"]): _comment_payload(row) for row in rows}
    normalized_identity_groups: dict[str, list[str]] = {}
    fullname_groups: dict[str, list[str]] = {}
    for node_id, node in nodes.items():
        normalized_identity_groups.setdefault(node_id.casefold(), []).append(node_id)
        fullname = node["fullname"]
        if fullname is not None and str(fullname).strip():
            fullname_groups.setdefault(str(fullname).casefold(), []).append(node_id)
    duplicate_identities = [
        {"normalized_id": identity, "comment_ids": sorted(comment_ids)}
        for identity, comment_ids in sorted(normalized_identity_groups.items())
        if len(comment_ids) > 1
    ]
    duplicate_fullnames = [
        {"fullname": fullname, "comment_ids": sorted(comment_ids)}
        for fullname, comment_ids in sorted(fullname_groups.items())
        if len(comment_ids) > 1
    ]
    identity_lookup = {
        identity: sorted(comment_ids)
        for identity, comment_ids in normalized_identity_groups.items()
    }

    relations: dict[str, dict[str, Any]] = {}
    parent_links: dict[str, str] = {}
    missing_parent_references: dict[str, list[str]] = {}
    issue_ids: dict[str, list[str]] = {
        "ambiguous_parent_references": [],
        "cross_post_parent_references": [],
        "invalid_parent_references": [],
        "missing_parent_values": [],
        "negative_depths": [],
        "self_parent_references": [],
    }
    for node_id, node in nodes.items():
        kind, reference = _parent_reference(node["parent_id"], normalized_post_id)
        relation: dict[str, Any] = {
            "kind": kind,
            "reference": reference,
            "parent_comment_id": None,
        }
        if kind == "comment" and reference is not None:
            candidates = identity_lookup.get(reference, [])
            if not candidates:
                relation["kind"] = "missing-comment"
                missing_parent_references.setdefault(reference, []).append(node_id)
            elif len(candidates) > 1:
                relation["kind"] = "ambiguous-comment"
                relation["candidates"] = candidates
                issue_ids["ambiguous_parent_references"].append(node_id)
            else:
                relation["parent_comment_id"] = candidates[0]
                parent_links[node_id] = candidates[0]
                if candidates[0] == node_id:
                    issue_ids["self_parent_references"].append(node_id)
        elif kind == "cross-post":
            issue_ids["cross_post_parent_references"].append(node_id)
        elif kind == "invalid":
            issue_ids["invalid_parent_references"].append(node_id)
        elif kind == "missing":
            issue_ids["missing_parent_values"].append(node_id)
        stored_depth = node["depth"]
        if stored_depth is not None and int(stored_depth) < 0:
            issue_ids["negative_depths"].append(node_id)
        relations[node_id] = relation

    cycles = _find_cycles(parent_links)
    cycle_members = {node_id for cycle in cycles for node_id in cycle}
    cycle_breaks = {min(cycle) for cycle in cycles}
    effective_parents = {
        node_id: parent_id
        for node_id, parent_id in parent_links.items()
        if node_id not in cycle_breaks
    }
    children: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    root_ids: list[str] = []
    detached_ids: list[str] = []
    detached_reasons: dict[str, str] = {}
    for node_id, relation in relations.items():
        parent_id = effective_parents.get(node_id)
        if parent_id is not None:
            children[parent_id].append(node_id)
        elif relation["kind"] == "post":
            root_ids.append(node_id)
        else:
            detached_ids.append(node_id)
            detached_reasons[node_id] = (
                "cycle-break" if node_id in cycle_breaks else relation["kind"]
            )
    for child_ids in children.values():
        child_ids.sort(key=lambda item: _node_sort_key(nodes[item]))
    root_ids.sort(key=lambda item: _node_sort_key(nodes[item]))
    detached_ids.sort(key=lambda item: _node_sort_key(nodes[item]))

    derived_depths: dict[str, int] = {}
    pending: list[tuple[str, int]] = [
        *((node_id, 0) for node_id in reversed(detached_ids)),
        *((node_id, 0) for node_id in reversed(root_ids)),
    ]
    while pending:
        node_id, depth = pending.pop()
        if node_id in derived_depths:
            continue
        derived_depths[node_id] = depth
        for child_id in reversed(children[node_id]):
            pending.append((child_id, depth + 1))
    for node_id in sorted(nodes):
        if node_id not in derived_depths:
            detached_ids.append(node_id)
            detached_reasons[node_id] = "unreachable"
            pending.append((node_id, 0))
            while pending:
                child_id, depth = pending.pop()
                if child_id in derived_depths:
                    continue
                derived_depths[child_id] = depth
                for descendant in reversed(children[child_id]):
                    pending.append((descendant, depth + 1))

    depth_mismatches = [
        {
            "comment_id": node_id,
            "stored_depth": int(node["depth"]),
            "derived_depth": derived_depths[node_id],
        }
        for node_id, node in sorted(nodes.items())
        if node["depth"] is not None
        and int(node["depth"]) != derived_depths[node_id]
    ]
    missing_parent_placeholders = [
        {
            "kind": "missing-parent",
            "id": f"t1_{reference}",
            "referenced_by": sorted(comment_ids),
        }
        for reference, comment_ids in sorted(missing_parent_references.items())
    ]
    captured_more_placeholders = []
    unresolved_comment_ids: set[str] = set()
    for row in captured_placeholder_rows:
        try:
            child_ids = json.loads(str(row["child_ids_json"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            child_ids = []
        if not isinstance(child_ids, list):
            child_ids = []
        normalized_child_ids = sorted(
            {
                str(value).strip().casefold()
                for value in child_ids
                if str(value).strip()
            }
        )
        unresolved_comment_ids.update(normalized_child_ids)
        captured_more_placeholders.append(
            {
                "kind": "captured-more",
                "id": row["placeholder_id"],
                "parent_id": row["parent_id"],
                "child_ids": normalized_child_ids,
                "declared_count": row["declared_count"],
                "observed_at": row["observed_at"],
            }
        )
    placeholders = [
        *missing_parent_placeholders,
        *captured_more_placeholders,
    ]
    deleted_count = sum(node["body_state"] == "deleted" for node in nodes.values())
    removed_count = sum(node["body_state"] == "removed" for node in nodes.values())
    missing_body_count = sum(
        node["body_state"] == "missing" for node in nodes.values()
    )
    declared_count = declared["num_comments"] if declared is not None else None
    coverage: dict[str, Any] = {
        "post_exists": post_row is not None,
        "observed_comments": comment_count,
        "root_comments": len(root_ids),
        "detached_roots": len(detached_ids),
        "maximum_derived_depth": max(derived_depths.values(), default=None),
        "maximum_stored_depth": max(
            (
                int(node["depth"])
                for node in nodes.values()
                if node["depth"] is not None
            ),
            default=None,
        ),
        "declared_num_comments": declared_count,
        "observed_minus_declared": (
            comment_count - declared_count if declared_count is not None else None
        ),
        "declared_unobserved_count": (
            max(declared_count - comment_count, 0)
            if declared_count is not None
            else None
        ),
        "count_matches_declared": (
            comment_count == declared_count if declared_count is not None else None
        ),
        "body_states": {
            "deleted": deleted_count,
            "removed": removed_count,
            "missing": missing_body_count,
            "present": (
                comment_count - deleted_count - removed_count - missing_body_count
            ),
        },
        "placeholder_coverage": {
            "missing_parent_placeholders": len(missing_parent_placeholders),
            "collapsed_more_nodes": (
                len(captured_more_placeholders)
                if placeholder_table_exists
                else None
            ),
            "unresolved_comment_ids": (
                len(unresolved_comment_ids)
                if placeholder_table_exists
                else None
            ),
            "collapsed_more_note": (
                "Captured more nodes preserve unresolved Reddit comment IDs."
                if placeholder_table_exists
                else (
                    "This older archive has no normalized more-node table; "
                    "a zero cannot be claimed."
                )
            ),
        },
        "integrity": {
            "counts": {
                "ambiguous_parent_references": len(
                    issue_ids["ambiguous_parent_references"]
                ),
                "cross_post_parent_references": len(
                    issue_ids["cross_post_parent_references"]
                ),
                "cycles": len(cycles),
                "cycle_comments": len(cycle_members),
                "depth_mismatches": len(depth_mismatches),
                "duplicate_comment_identities": len(duplicate_identities),
                "duplicate_fullnames": len(duplicate_fullnames),
                "invalid_parent_references": len(
                    issue_ids["invalid_parent_references"]
                ),
                "missing_parent_references": sum(
                    len(comment_ids)
                    for comment_ids in missing_parent_references.values()
                ),
                "missing_parent_values": len(issue_ids["missing_parent_values"]),
                "negative_depths": len(issue_ids["negative_depths"]),
                "self_parent_references": len(
                    issue_ids["self_parent_references"]
                ),
                "unknown_post": int(post_row is None and comment_count > 0),
            },
            "comment_ids": {
                key: sorted(values)
                for key, values in sorted(issue_ids.items())
            },
            "cycles": [list(cycle) for cycle in cycles],
            "depth_mismatches": depth_mismatches,
            "duplicate_comment_identities": duplicate_identities,
            "duplicate_fullnames": duplicate_fullnames,
            "missing_parent_references": [
                {
                    "parent_id": f"t1_{reference}",
                    "comment_ids": sorted(comment_ids),
                }
                for reference, comment_ids in sorted(
                    missing_parent_references.items()
                )
            ],
        },
    }
    coverage["integrity"]["total_issues"] = _integrity_issue_count(coverage)

    export_nodes: dict[str, dict[str, Any]] = {}
    for node_id, node in nodes.items():
        relation = relations[node_id]
        stored_depth = node["depth"]
        export_nodes[node_id] = {
            **node,
            "integrity": {
                "parent_relation": relation["kind"],
                "parent_reference": relation["reference"],
                "parent_comment_id": relation["parent_comment_id"],
                "detached_reason": detached_reasons.get(node_id),
                "cycle_member": node_id in cycle_members,
                "cycle_break": node_id in cycle_breaks,
                "stored_depth": stored_depth,
                "derived_depth": derived_depths[node_id],
                "depth_matches": (
                    int(stored_depth) == derived_depths[node_id]
                    if stored_depth is not None
                    else None
                ),
            },
            "children": [],
        }
    for parent_id, child_ids in children.items():
        export_nodes[parent_id]["children"].extend(
            export_nodes[child_id] for child_id in child_ids
        )

    return {
        "format": COMMENT_TREE_FORMAT,
        "post_id": normalized_post_id,
        "post": _post_payload(post_row),
        "latest_declared_comment_observation": declared,
        "coverage": coverage,
        "placeholders": placeholders,
        "root_comments": [export_nodes[node_id] for node_id in root_ids],
        "detached_comments": [export_nodes[node_id] for node_id in detached_ids],
    }


def summarize_comment_tree(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a bounded summary suitable for CLI output."""
    coverage = payload["coverage"]
    return {
        "format": COMMENT_TREE_SUMMARY_FORMAT,
        "post_id": payload["post_id"],
        "post_exists": coverage["post_exists"],
        "observed_comments": coverage["observed_comments"],
        "root_comments": coverage["root_comments"],
        "detached_roots": coverage["detached_roots"],
        "maximum_derived_depth": coverage["maximum_derived_depth"],
        "declared_num_comments": coverage["declared_num_comments"],
        "declared_unobserved_count": coverage["declared_unobserved_count"],
        "count_matches_declared": coverage["count_matches_declared"],
        "integrity_issues": coverage["integrity"]["total_issues"],
        "integrity_counts": coverage["integrity"]["counts"],
        "placeholder_coverage": coverage["placeholder_coverage"],
    }


def _json_scalar(value: Any) -> str:
    if isinstance(value, float) and not math.isfinite(value):
        raise CommentTreeExportError("Comment tree contains a non-finite number")
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def _iter_json(value: Any) -> Iterator[str]:
    """Encode supported JSON values iteratively so deep threads do not recurse."""
    stack: list[tuple[str, Any]] = [("value", value)]
    while stack:
        operation, current = stack.pop()
        if operation == "token":
            yield str(current)
            continue
        if isinstance(current, dict):
            items = list(current.items())
            stack.append(("token", "}"))
            for index in range(len(items) - 1, -1, -1):
                key, item = items[index]
                if not isinstance(key, str):
                    raise CommentTreeExportError("JSON object keys must be strings")
                stack.append(("value", item))
                stack.append(("token", ":"))
                stack.append(("token", _json_scalar(key)))
                if index:
                    stack.append(("token", ","))
            stack.append(("token", "{"))
        elif isinstance(current, (list, tuple)):
            stack.append(("token", "]"))
            for index in range(len(current) - 1, -1, -1):
                stack.append(("value", current[index]))
                if index:
                    stack.append(("token", ","))
            stack.append(("token", "["))
        elif current is None or isinstance(current, (str, int, float, bool)):
            yield _json_scalar(current)
        else:
            raise CommentTreeExportError(
                f"Unsupported JSON value: {type(current).__name__}"
            )


def _same_file(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as left_handle, right.open("rb") as right_handle:
        while True:
            left_chunk = left_handle.read(1024 * 1024)
            right_chunk = right_handle.read(1024 * 1024)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True


def _write_json_create_or_verify(
    path: Path,
    payload: dict[str, Any],
    *,
    max_output_bytes: int,
) -> int:
    if max_output_bytes <= 0:
        raise ValueError("max_output_bytes must be positive")
    destination = Path(path).expanduser().resolve(strict=False)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.{uuid4().hex}.tmp"
    total = 0
    try:
        with temporary.open("xb") as handle:
            for text in _iter_json(payload):
                encoded = text.encode("utf-8")
                total += len(encoded)
                if total + 1 > max_output_bytes:
                    raise CommentTreeLimitError(
                        f"JSON export exceeds --max-output-bytes "
                        f"({max_output_bytes})"
                    )
                handle.write(encoded)
            handle.write(b"\n")
            total += 1
            handle.flush()
            os.fsync(handle.fileno())
        if destination.exists():
            if not destination.is_file() or not _same_file(destination, temporary):
                raise CommentTreeExportError(
                    f"Existing JSON export does not match: {destination}"
                )
            return total
        os.replace(temporary, destination)
        return total
    finally:
        if temporary.exists():
            temporary.unlink()


def export_comment_tree(
    database_path: Path,
    post_id: str,
    output_path: Path,
    *,
    options: CommentTreeOptions | None = None,
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
) -> CommentTreeExport:
    """Build and install one deterministic tree export without overwriting."""
    database = Path(database_path).expanduser().resolve(strict=False)
    output = Path(output_path).expanduser().resolve(strict=False)
    if database == output:
        raise CommentTreeExportError("Output path cannot be the archive database")
    payload = build_comment_tree(database, post_id, options)
    output_bytes = _write_json_create_or_verify(
        output,
        payload,
        max_output_bytes=max_output_bytes,
    )
    summary = summarize_comment_tree(payload)
    return CommentTreeExport(
        post_id=summary["post_id"],
        output_path=str(output),
        output_bytes=output_bytes,
        observed_comments=summary["observed_comments"],
        root_comments=summary["root_comments"],
        detached_roots=summary["detached_roots"],
        integrity_issues=summary["integrity_issues"],
    )
