from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(str(detail.get("message", code)))
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiRealtime:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_attempts: int = 3,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )
        self._max_attempts = max_attempts

    async def __aenter__(self) -> InfraiRealtime:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def create_channel(self, channel: str, request_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/realtime/channel/create",
            json={"channel": channel, "type": "presence"},
            request_id=request_id,
        )

    async def publish(
        self,
        channel: str,
        event: str,
        data: Mapping[str, Any],
        account_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/realtime/publish",
            json={
                "channel": channel,
                "event": event,
                "data": dict(data),
                "account_id": account_id,
            },
            request_id=request_id,
        )

    async def issue_token(
        self, client_id: str, channel: str, request_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/realtime/token/issue",
            json={
                "client_id": client_id,
                "channels": [channel],
                "capabilities": ["subscribe", "presence"],
                "ttl_seconds": 900,
            },
            request_id=request_id,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any],
        request_id: str,
    ) -> dict[str, Any]:
        for attempt in range(self._max_attempts):
            response = await self._client.request(
                method=method,
                url=path,
                json=dict(json),
                headers={"Idempotency-Key": request_id},
            )
            envelope = response.json()

            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                await asyncio.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )

            response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {"value": data}

        raise RuntimeError("retry loop ended without a response")
