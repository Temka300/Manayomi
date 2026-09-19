from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from modules.reddit import reddit_api  # noqa: E402
from modules.reddit.reddit_api import (  # noqa: E402
    DiscoveryOutputExistsError,
    RedditApiClient,
    RedditApiCredentials,
    RedditApiError,
    write_discovery_manifest,
)
from modules.reddit.url_targets import parse_capture_target  # noqa: E402
import reddit_capture  # noqa: E402


def _child(index: int, *, kind: str = "t3") -> dict:
    reddit_id = f"id{index}"
    return {
        "kind": kind,
        "data": {
            "id": reddit_id,
            "name": f"{kind}_{reddit_id}",
            "link_id": "t3_parent",
            "permalink": f"/r/AIcrack/comments/{reddit_id}/example/",
        },
    }


class _Transport:
    def __init__(self, responses: list[object]):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout, max_response_bytes):
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _response(payload: object, **headers: str):
    return reddit_api._JsonResponse(status=200, headers=headers, payload=payload)


class RedditApiDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.credentials = RedditApiCredentials(
            client_id="client-id",
            client_secret="client-secret",
            user_agent="windows:keivotos-reddit:v0.1 (by /u/archive_owner)",
        )
        self.now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)

    def test_oauth_listing_uses_100_item_pages_and_after_cursor(self) -> None:
        first_children = [_child(index) for index in range(100)]
        second_children = [_child(99), _child(100)]
        transport = _Transport(
            [
                _response({"access_token": "secret-token", "token_type": "bearer"}),
                _response(
                    {"data": {"children": first_children, "after": "t3_id99"}},
                    **{
                        "x-ratelimit-remaining": "0",
                        "x-ratelimit-reset": "2",
                    },
                ),
                _response(
                    {"data": {"children": second_children, "after": None}},
                    **{"x-ratelimit-remaining": "99"},
                ),
            ]
        )
        sleeps: list[float] = []
        client = RedditApiClient(
            self.credentials,
            transport=transport,
            sleep=sleeps.append,
            now=lambda: self.now,
        )

        result = client.discover(
            parse_capture_target("r/AIcrack"),
            max_items=101,
        )

        self.assertEqual(result.item_count, 101)
        self.assertEqual(result.page_count, 2)
        self.assertTrue(result.listing_exhausted)
        self.assertEqual(result.stopped_reason, "listing_exhausted")
        self.assertEqual(sleeps, [2.0])
        token_request, first_page, second_page = transport.requests
        self.assertTrue(token_request.full_url.startswith(reddit_api.TOKEN_URL))
        self.assertTrue(token_request.get_header("Authorization").startswith("Basic "))
        self.assertEqual(first_page.get_header("Authorization"), "Bearer secret-token")
        first_query = parse_qs(urlsplit(first_page.full_url).query)
        second_query = parse_qs(urlsplit(second_page.full_url).query)
        self.assertEqual(first_query["limit"], ["100"])
        self.assertNotIn("after", first_query)
        self.assertEqual(second_query["limit"], ["1"])
        self.assertEqual(second_query["after"], ["t3_id99"])

    def test_retries_429_and_stops_repeated_cursor_without_looping(self) -> None:
        transport = _Transport(
            [
                _response({"access_token": "token", "token_type": "bearer"}),
                reddit_api._HttpStatusError(429, {"retry-after": "3"}),
                _response({"data": {"children": [_child(1)], "after": "t3_same"}}),
                _response({"data": {"children": [_child(1)], "after": "t3_same"}}),
            ]
        )
        sleeps: list[float] = []
        client = RedditApiClient(
            self.credentials,
            transport=transport,
            sleep=sleeps.append,
            now=lambda: self.now,
        )

        result = client.discover(
            parse_capture_target("https://reddit.com/r/AIcrack/new/"),
            max_items=10,
        )

        self.assertEqual(sleeps, [3.0])
        self.assertEqual(result.item_count, 1)
        self.assertEqual(result.page_count, 2)
        self.assertEqual(result.stopped_reason, "repeated_cursor")
        self.assertFalse(result.listing_exhausted)

    def test_limits_targets_credentials_and_create_only_output(self) -> None:
        client = RedditApiClient(
            self.credentials,
            transport=_Transport([]),
            now=lambda: self.now,
        )
        with self.assertRaises(ValueError):
            client.discover(parse_capture_target("r/AIcrack"), max_items=1001)
        with self.assertRaisesRegex(RedditApiError, "supports subreddit"):
            client.discover(
                parse_capture_target(
                    "https://reddit.com/r/AIcrack/comments/abc123/example/"
                )
            )
        with self.assertRaisesRegex(RedditApiError, "REDDIT_CLIENT_SECRET"):
            RedditApiCredentials.from_environment(
                {
                    "REDDIT_CLIENT_ID": "id",
                    "REDDIT_USER_AGENT": "windows:app:v1 (by /u/owner)",
                }
            )

        result_transport = _Transport(
            [
                _response({"access_token": "token", "token_type": "bearer"}),
                _response({"data": {"children": [_child(1)], "after": None}}),
            ]
        )
        result = RedditApiClient(
            self.credentials,
            transport=result_transport,
            now=lambda: self.now,
        ).discover(parse_capture_target("r/AIcrack"), max_items=1)
        with tempfile.TemporaryDirectory(
            prefix=".tmp-reddit-api-",
            dir=ROOT / "tests",
        ) as temporary:
            output = Path(temporary) / "discovery.json"
            write_discovery_manifest(output, result)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["format"], "keivotos-reddit-api-discovery-v1")
            self.assertEqual(payload["items"][0]["reddit_id"], "id1")
            with self.assertRaises(DiscoveryOutputExistsError):
                write_discovery_manifest(output, result)

    def test_cli_api_mode_writes_summary_without_exposing_items(self) -> None:
        target = parse_capture_target("r/AIcrack")
        fake_result = reddit_api.DiscoveryResult(
            target=target.as_dict(),
            listing_path="/r/AIcrack/new",
            retrieved_at=self.now.isoformat(),
            max_items=5,
            page_count=1,
            item_count=1,
            listing_exhausted=True,
            stopped_reason="listing_exhausted",
            last_after=None,
            items=(reddit_api.DiscoveryItem("t3_id1", "post", "id1", "https://www.reddit.com/comments/id1/"),),
        )
        with tempfile.TemporaryDirectory(
            prefix=".tmp-reddit-api-cli-",
            dir=ROOT / "tests",
        ) as temporary:
            output = Path(temporary) / "discovery.json"
            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch.object(
                    reddit_capture.RedditApiCredentials,
                    "from_environment",
                    return_value=self.credentials,
                ),
                patch.object(
                    reddit_capture.RedditApiClient,
                    "discover",
                    return_value=fake_result,
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                status = reddit_capture.main(
                    [
                        "--subreddit",
                        "AIcrack",
                        "--reddit-api",
                        "--posts",
                        "5",
                        "--reddit-api-output",
                        str(output),
                    ]
                )

            summary = json.loads(stdout.getvalue())
            self.assertEqual(status, 0)
            self.assertEqual(summary["item_count"], 1)
            self.assertNotIn("items", summary)
            self.assertEqual(stderr.getvalue(), "")
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
