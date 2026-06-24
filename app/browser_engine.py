from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import BrowserContext, Error, Page, Playwright, async_playwright

from app.models import ProviderConfig, ProviderMode, ProviderRuntime, ProviderStatus
from app.provider_store import ProviderStore
from app.settings import BROWSER_DIR, SESSIONS_DIR, ensure_data_dirs, settings


CLOSED_BROWSER_ERROR = "Target page, context or browser has been closed"


@dataclass
class ProviderHandle:
    config: ProviderConfig
    context: BrowserContext
    page: Page
    lock: asyncio.Lock
    status: ProviderStatus = ProviderStatus.disconnected
    error: str | None = None


class BrowserEngine:
    def __init__(self, store: ProviderStore) -> None:
        self.store = store
        self._playwright: Playwright | None = None
        self._handles: dict[str, ProviderHandle] = {}
        self._engine_lock = asyncio.Lock()

    async def start(self) -> None:
        ensure_data_dirs()
        if self._playwright is None:
            self._playwright = await async_playwright().start()

    async def stop(self) -> None:
        for handle in list(self._handles.values()):
            if self._is_handle_alive(handle):
                await self._save_session(handle)
            await self._close_context(handle.context)
        self._handles.clear()
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def list_runtimes(self) -> list[ProviderRuntime]:
        runtimes: list[ProviderRuntime] = []
        for config in self.store.list():
            handle = self._handles.get(config.name)
            runtimes.append(self._runtime(config, handle))
        return runtimes

    async def login(self, provider_name: str) -> ProviderRuntime:
        handle = await self._get_or_create(provider_name)
        async with handle.lock:
            handle.status = ProviderStatus.disconnected
            try:
                handle = await self._goto_provider(handle)
                handle.status = ProviderStatus.connected
                handle.error = None
            except Exception as exc:  # noqa: BLE001 - surfaced in dashboard and API.
                handle.status = ProviderStatus.error
                handle.error = str(exc)
            return self._runtime(handle.config, handle)

    async def save_session(self, provider_name: str) -> ProviderRuntime:
        handle = await self._get_or_create(provider_name)
        try:
            await self._save_session(handle)
            handle.status = ProviderStatus.connected
            handle.error = None
        except Exception as exc:  # noqa: BLE001 - surfaced in dashboard and API.
            handle.status = ProviderStatus.error
            handle.error = str(exc)
        return self._runtime(handle.config, handle)

    async def complete(self, provider_name: str, prompt: str) -> str:
        chunks: list[str] = []
        async for chunk in self.stream(provider_name, prompt):
            chunks.append(chunk)
        return "".join(chunks)

    async def stream(self, provider_name: str, prompt: str) -> AsyncIterator[str]:
        handle = await self._get_or_create(provider_name)
        async with handle.lock:
            handle.status = ProviderStatus.busy
            handle.error = None
            try:
                if handle.config.mode == ProviderMode.network:
                    async for chunk in self._network_then_dom_stream(handle, prompt):
                        yield chunk
                else:
                    async for chunk in self._dom_stream(handle, prompt):
                        yield chunk
                handle = self._handles.get(provider_name, handle)
                handle.status = ProviderStatus.connected
                await self._save_session(handle)
            except Exception as exc:  # noqa: BLE001 - surfaced to caller.
                handle.status = ProviderStatus.error
                handle.error = str(exc)
                raise

    async def _get_or_create(self, provider_name: str) -> ProviderHandle:
        async with self._engine_lock:
            handle = self._handles.get(provider_name)
            if handle is not None:
                if self._is_handle_alive(handle):
                    return handle
                await self._discard_handle(provider_name, handle)
            await self.start()
            return await self._create_handle(provider_name)

    async def _create_handle(self, provider_name: str) -> ProviderHandle:
        config = self.store.load(provider_name)
        assert self._playwright is not None
        user_data_dir = self._user_data_dir(config)
        context = await self._playwright.chromium.launch_persistent_context(
            executable_path="/usr/bin/chromium-browser",
            user_data_dir=str(user_data_dir),
            headless=settings.headless,
            viewport={"width": 1920, "height": 1080},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else await context.new_page()
        handle = ProviderHandle(
            config=config,
            context=context,
            page=page,
            lock=asyncio.Lock(),
        )
        self._handles[provider_name] = handle
        return handle

    async def _recreate_handle(self, provider_name: str, handle: ProviderHandle) -> ProviderHandle:
        async with self._engine_lock:
            current = self._handles.get(provider_name)
            if current is not None and current is not handle and self._is_handle_alive(current):
                return current
            if current is not None:
                await self._discard_handle(provider_name, current)
            await self.start()
            return await self._create_handle(provider_name)

    def _is_handle_alive(self, handle: ProviderHandle) -> bool:
        try:
            if handle.page.is_closed():
                return False
            return handle.page in handle.context.pages
        except Error as exc:
            if self._is_closed_error(exc):
                return False
            raise

    async def _discard_handle(self, provider_name: str, handle: ProviderHandle) -> None:
        self._handles.pop(provider_name, None)
        await self._close_context(handle.context)

    async def _close_context(self, context: BrowserContext) -> None:
        try:
            await context.close()
        except Error as exc:
            if not self._is_closed_error(exc):
                raise

    async def _goto_provider(self, handle: ProviderHandle) -> ProviderHandle:
        try:
            await handle.page.goto(str(handle.config.url), wait_until="domcontentloaded")
            await handle.page.bring_to_front()
            return handle
        except Error as exc:
            if not self._is_closed_error(exc):
                raise
            handle = await self._recreate_handle(handle.config.name, handle)
            await handle.page.goto(str(handle.config.url), wait_until="domcontentloaded")
            await handle.page.bring_to_front()
            return handle

    @staticmethod
    def _is_closed_error(exc: Error) -> bool:
        return CLOSED_BROWSER_ERROR in str(exc)

    async def _dom_stream(self, handle: ProviderHandle, prompt: str) -> AsyncIterator[str]:
        page = handle.page
        if page.is_closed():
            handle = await self._recreate_handle(handle.config.name, handle)
            page = handle.page

        if not page.url or page.url == "about:blank":
            handle = await self._goto_provider(handle)
            page = handle.page

        previous_count = await self._response_count(page, handle.config)
        await self._fill_prompt(page, handle.config, prompt)
        await self._send_prompt(page, handle.config)

        response_locator = page.locator(handle.config.response_selector)
        started_at = time.monotonic()
        last_text = ""
        last_change = time.monotonic()

        while True:
            await page.wait_for_timeout(250)
            current_count = await response_locator.count()
            if current_count <= previous_count:
                if time.monotonic() - started_at > settings.response_timeout_seconds:
                    raise TimeoutError("Timed out waiting for provider response to start")
                continue

            text = await self._latest_response_text(page, handle.config)
            if text.startswith(last_text):
                delta = text[len(last_text) :]
            else:
                delta = text

            if delta:
                yield delta
                last_text = text
                last_change = time.monotonic()

            idle_for = time.monotonic() - last_change
            timed_out = time.monotonic() - started_at > settings.response_timeout_seconds
            if last_text and idle_for >= settings.response_idle_seconds:
                break
            if timed_out:
                raise TimeoutError("Timed out waiting for provider response to finish")

    async def _network_then_dom_stream(
        self, handle: ProviderHandle, prompt: str
    ) -> AsyncIterator[str]:
        # Provider network protocols change frequently. This hook keeps the public
        # mode available while DOM streaming remains the dependable fallback.
        async for chunk in self._dom_stream(handle, prompt):
            yield chunk

    async def _fill_prompt(self, page: Page, config: ProviderConfig, prompt: str) -> None:
        locator = page.locator(config.input_selector).last
        await locator.wait_for(state="visible", timeout=30_000)
        try:
            await locator.fill(prompt)
        except Error:
            await locator.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.type(prompt)

    async def _send_prompt(self, page: Page, config: ProviderConfig) -> None:
        if config.send_button_selector:
            button = page.locator(config.send_button_selector).last
            try:
                await button.click(timeout=5_000)
                return
            except Error:
                pass
        await page.keyboard.press("Enter")

    async def _response_count(self, page: Page, config: ProviderConfig) -> int:
        try:
            return await page.locator(config.response_selector).count()
        except Error:
            return 0

    async def _latest_response_text(self, page: Page, config: ProviderConfig) -> str:
        selector = config.response_text_selector or config.response_selector
        locator = page.locator(selector).last
        try:
            return (await locator.inner_text(timeout=1_000)).strip()
        except Error:
            return ""

    async def _save_session(self, handle: ProviderHandle) -> None:
        session_path = self._session_path(handle.config)
        await handle.context.storage_state(path=str(session_path))

    def _runtime(
        self, config: ProviderConfig, handle: ProviderHandle | None
    ) -> ProviderRuntime:
        status = handle.status if handle else ProviderStatus.disconnected
        error = handle.error if handle else None
        return ProviderRuntime(
            name=config.name,
            display_name=config.display_name,
            url=str(config.url),
            mode=config.mode,
            status=status,
            error=error,
        )

    def _session_path(self, config: ProviderConfig) -> Path:
        return SESSIONS_DIR / f"{config.name}.json"

    def _user_data_dir(self, config: ProviderConfig) -> Path:
        configured = Path(config.user_data_dir) if config.user_data_dir else None
        return configured or BROWSER_DIR / config.name
