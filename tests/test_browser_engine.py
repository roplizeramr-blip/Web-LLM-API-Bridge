from __future__ import annotations

import asyncio
import unittest

from playwright.async_api import Error

from app.browser_engine import BrowserEngine, CLOSED_BROWSER_ERROR, ProviderHandle
from app.models import ProviderConfig, ProviderStatus


class FakePage:
    def __init__(self, *, closed: bool = False, goto_error: Error | None = None) -> None:
        self.closed = closed
        self.goto_error = goto_error
        self.goto_calls = 0
        self.bring_to_front_calls = 0
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

    async def launch_persistent_context(self, **_: object) -> FakeContext:
        self.launch_calls += 1
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
