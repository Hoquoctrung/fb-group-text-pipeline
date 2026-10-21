"""Minimal passive Playwright collector; no request replay or bypasses."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fbpipe.collect.base import Collector
from fbpipe.collect.checkpoint import Checkpoint
from fbpipe.collect.graphql_parser import parse_response
from fbpipe.schema import RawPost

if TYPE_CHECKING:
    from playwright.sync_api import Response

logger = logging.getLogger(__name__)


class CollectionBlocked(RuntimeError):
    """Raised when the site presents a login wall, checkpoint, or restriction."""


class PlaywrightCollector(Collector):
    """Observe GraphQL-like responses generated naturally by the page.

    TODO(real-sample): The parser is not validated against a real anonymized
    probe sample. This collector may return zero records until it is.
    """

    name = "playwright_graphql"

    def __init__(
        self,
        *,
        url: str,
        group_id: str,
        state_path: str | Path = ".auth/state.json",
        checkpoint_path: str | Path = "data/bronze/checkpoint.json",
        headless: bool = False,
        max_posts: int = 300,
        max_minutes: int = 40,
        delay_range: tuple[float, float] = (3.0, 8.0),
        empty_scroll_limit: int = 6,
        seed: int = 42,
        resume: bool = False,
        data_path: str | Path = "data/bronze/raw_posts.jsonl",
    ) -> None:
        self.url = url
        self.group_id = group_id
        self.state_path = Path(state_path)
        self.checkpoint_path = Path(checkpoint_path)
        self.headless = headless
        self.max_posts = max_posts
        self.max_minutes = max_minutes
        self.delay_range = delay_range
        self.empty_scroll_limit = empty_scroll_limit
        self.rng = random.Random(seed)
        self.data_path = Path(data_path)
        self.resume = resume

    def iter_posts(self) -> Iterator[RawPost]:
        """Yield newly observed posts, checkpointing after consumer resumes."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is required. Install with `pip install -e '.[crawl]'`."
            ) from exc
        if not self.state_path.exists():
            raise RuntimeError("Missing auth state; run `fbpipe auth` first.")
        if not (
            self.delay_range[0] >= 0 and self.delay_range[1] >= self.delay_range[0]
        ):
            raise ValueError("delay_range must be ordered and non-negative")

        if self.resume:
            checkpoint = Checkpoint.load(self.checkpoint_path)
        else:
            checkpoint = Checkpoint(seen_ids=set())
        if checkpoint.run_id is None:
            checkpoint.run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        start = time.monotonic()
        yielded = 0
        empty_scrolls = 0
        responses: list[str] = []
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=self.headless)
            context = browser.new_context(storage_state=str(self.state_path))
            page = context.new_page()

            def handle_response(response: Response) -> None:
                response_url = getattr(response, "url", "")
                if "/api/graphql" not in response_url:
                    return
                try:
                    body = response.body()
                    responses.append(body.decode("utf-8", errors="replace"))
                except Exception:
                    logger.debug("Could not read response body", exc_info=True)

            page.on("response", handle_response)
            try:
                page.goto(self.url, wait_until="domcontentloaded")
                while yielded < self.max_posts:
                    current_url = page.url.lower()
                    page_text = page.locator("body").inner_text(timeout=3000).lower()
                    blocked_phrases = (
                        "captcha",
                        "temporarily blocked",
                        "temporarily restricted",
                        "tài khoản bị hạn chế",
                        "tạm thời bị hạn chế",
                    )
                    if (
                        "checkpoint" in current_url
                        or "/login" in current_url
                        or any(phrase in page_text for phrase in blocked_phrases)
                    ):
                        checkpoint.save(self.checkpoint_path)
                        raise CollectionBlocked(
                            "Login wall/checkpoint/restriction detected; "
                            "stopped without bypass."
                        )
                    if time.monotonic() - start >= self.max_minutes * 60:
                        break

                    before = yielded
                    pending = list(responses)
                    responses.clear()
                    for payload in pending:
                        try:
                            parsed_posts = parse_response(
                                payload, group_id=self.group_id
                            )
                        except (ValueError, TypeError) as exc:
                            logger.debug("Skipping unrecognized response: %s", exc)
                            continue
                        for post in parsed_posts:
                            if checkpoint.has_seen(post.post_id):
                                continue
                            checkpoint.mark_seen(post.post_id)
                            checkpoint.last_created_at = (
                                post.created_at.isoformat() if post.created_at else None
                            )
                            yielded += 1
                            yield post
                            # CLI writes yielded post before requesting the next one.
                            checkpoint.scroll_count += 1
                            checkpoint.save(self.checkpoint_path)
                            if yielded >= self.max_posts:
                                break
                        if yielded >= self.max_posts:
                            break

                    if yielded == before:
                        empty_scrolls += 1
                    else:
                        empty_scrolls = 0
                    if empty_scrolls >= self.empty_scroll_limit:
                        break
                    page.mouse.wheel(0, 2500)
                    time.sleep(self.rng.uniform(*self.delay_range))
            finally:
                context.close()
                browser.close()


def auth(*, url: str, state_path: str | Path = ".auth/state.json") -> None:
    """Open a visible browser for a human to authenticate manually."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required. Install with `pip install -e '.[crawl]'`."
        ) from exc
    target = Path(state_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        input(
            "Đăng nhập/2FA thủ công trong trình duyệt. Nhấn Enter sau khi hoàn tất..."
        )
        context.storage_state(path=str(target))
        browser.close()
