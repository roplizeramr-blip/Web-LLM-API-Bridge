from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from playwright.async_api import Error

from app.browser_engine import (
    CHROME_124_USER_AGENT,
    HUMAN_LIKE_HEADERS,
    WEBDRIVER_INIT_SCRIPT,
    BrowserEngine,
    CLOSED_BROWSER_ERROR,
    ProviderHandle,
)
from app.models import ProviderConfig, ProviderStatus


class FakePage:
    def __init__(self, *, closed: bool = False, goto_error: Error | None = None) -> None:
        self.closed = closed
        self.goto_error = goto_error
        self.goto_calls = 0
        self.bring_to_front_calls = 0
        self.viewport_sizes: list[dict[str, int]] = []
        self.evaluate_calls: list[str] = []
        self.init_scripts: list[str] = []
        self.url = "about:blank"

    def is_closed(self) -> bool:
        return self.closed

    async def goto(self, url: str, *, wait_until: str) -> None:
        self.goto_calls += 1
        if self.goto_error is not None:
            exc = self.goto_error
            self.goto_error = None
            raise exc
        self.url = url

    async def bring_to_front(self) -> None:
        self.bring_to_front_calls += 1

    async def set_viewport_size(self, size: dict[str, int]) -> None:
        self.viewport_sizes.append(size)

    async def evaluate(self, script: str) -> None:
        self.evaluate_calls.append(script)

    async def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)


class FakeContext:
    def __init__(self, page: FakePage) -> None:
        self.page = page
        self.closed = False
        self.close_calls = 0

    @property
    def pages(self) -> list[FakePage]:
        return [] if self.closed else [self.page]

    async def new_page(self) -> FakePage:
        self.page = FakePage()
        return self.page

    async def close(self) -> None:
        self.close_calls += 1
        self.closed = True
        self.page.closed = True


class FakeChromium:
    def __init__(self, contexts: list[FakeContext]) -> None:
        self.contexts = contexts
        self.launch_calls = 0
        self.launch_kwargs: list[dict[str, object]] = []

    async def launch_persistent_context(self, **kwargs: object) -> FakeContext:
        self.launch_calls += 1
        self.launch_kwargs.append(kwargs)
        return self.contexts.pop(0)


class FakePlaywright:
    def __init__(self, contexts: list[FakeContext]) -> None:
        self.chromium = FakeChromium(contexts)


class FakeStore:
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    def load(self, provider_name: str) -> ProviderConfig:
        if provider_name != self.config.name:
            raise KeyError(provider_name)
        return self.config


def provider_config() -> ProviderConfig:
    return ProviderConfig(
        name="test",
        display_name="Test",
        url="https://example.com/",
        input_selector="textarea",
        response_selector=".response",
    )


class BrowserEngineTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_or_create_replaces_closed_cached_page(self) -> None:
        config = provider_config()
        old_page = FakePage(closed=True)
        old_context = FakeContext(old_page)
        new_page = FakePage()
        new_context = FakeContext(new_page)
        engine = BrowserEngine(FakeStore(config))
        engine._playwright = FakePlaywright([new_context])
        old_handle = ProviderHandle(
            config=config,
            context=old_context,
            page=old_page,
            lock=asyncio.Lock(),
        )
        engine._handles[config.name] = old_handle

        handle = await engine._get_or_create(config.name)

        self.assertIsNot(handle, old_handle)
        self.assertIs(handle.context, new_context)
        self.assertEqual(old_context.close_calls, 1)
        self.assertIs(engine._handles[config.name], handle)

    async def test_create_handle_maximizes_chromium_window(self) -> None:
        config = provider_config()
        context = FakeContext(FakePage())
        engine = BrowserEngine(FakeStore(config))
        fake_playwright = FakePlaywright([context])
        engine._playwright = fake_playwright

        with patch.object(engine, "_maximize_window", new=AsyncMock()) as maximize_window:
            await engine._create_handle(config.name)

        launch_kwargs = fake_playwright.chromium.launch_kwargs[0]
        self.assertNotIn("viewport", launch_kwargs)
        self.assertNotIn("no_sandbox", launch_kwargs)
        self.assertEqual(launch_kwargs["user_agent"], CHROME_124_USER_AGENT)
        self.assertEqual(launch_kwargs["extra_http_headers"], HUMAN_LIKE_HEADERS)
        self.assertEqual(launch_kwargs["args"][0], "--window-size=1920,1080")
        self.assertIn("--no-sandbox", launch_kwargs["args"])
        self.assertIn("--start-maximized", launch_kwargs["args"])
        self.assertIn("--window-position=0,0", launch_kwargs["args"])
        self.assertIn("--window-size=1920,1080", launch_kwargs["args"])
        self.assertIn(f"--user-agent={CHROME_124_USER_AGENT}", launch_kwargs["args"])
        maximize_window.assert_awaited_once_with()
        self.assertEqual(context.page.init_scripts, [WEBDRIVER_INIT_SCRIPT])
        self.assertEqual(context.page.viewport_sizes, [{"width": 1920, "height": 1080}])
        self.assertEqual(
            context.page.evaluate_calls,
            ["window.moveTo(0,0); window.resizeTo(1920, 1080)"],
        )

    async def test_login_recreates_context_when_goto_reports_closed_browser(self) -> None:
        config = provider_config()
        old_page = FakePage(goto_error=Error(CLOSED_BROWSER_ERROR))
        old_context = FakeContext(old_page)
        new_page = FakePage()
        new_context = FakeContext(new_page)
        engine = BrowserEngine(FakeStore(config))
        engine._playwright = FakePlaywright([new_context])
        old_handle = ProviderHandle(
            config=config,
            context=old_context,
            page=old_page,
            lock=asyncio.Lock(),
        )
        engine._handles[config.name] = old_handle

        runtime = await engine.login(config.name)
        handle = engine._handles[config.name]

        self.assertIs(handle.context, new_context)
        self.assertEqual(runtime.status, ProviderStatus.connected)
        self.assertEqual(old_context.close_calls, 1)
        self.assertEqual(old_page.goto_calls, 1)
        self.assertEqual(new_page.goto_calls, 1)
        self.assertEqual(new_page.bring_to_front_calls, 1)


if __name__ == "__main__":
    unittest.main()
