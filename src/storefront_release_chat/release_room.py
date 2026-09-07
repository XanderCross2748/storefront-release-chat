from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from .infrai_realtime import InfraiError, InfraiRealtime


class BuildReport(BaseModel):
    shop_id: str = Field(min_length=1)
    build_id: str = Field(min_length=1)
    git_sha: str = Field(min_length=7)
    status: Literal["passed", "failed"]
    operation: Literal["deploy", "rollback"] = "deploy"
    developer_id: str = Field(min_length=1)
    diagnostic: str | None = None

    @model_validator(mode="after")
    def failed_build_has_diagnostic(self) -> BuildReport:
        if self.status == "failed" and not self.diagnostic:
            raise ValueError("a failed build needs a developer-facing diagnostic")
        return self


class ReleaseRoomResponse(BaseModel):
    channel: str
    event: Literal["release.ready", "build.failed"]
    token: str
    expires_in_seconds: int = 900


@dataclass(frozen=True)
class RoomEvent:
    channel: str
    name: Literal["release.ready", "build.failed"]
    data: dict[str, str]


def plan_room_event(report: BuildReport) -> RoomEvent:
    name: Literal["release.ready", "build.failed"] = (
        "release.ready" if report.status == "passed" else "build.failed"
    )
    data = {
        "shop_id": report.shop_id,
        "build_id": report.build_id,
        "git_sha": report.git_sha,
        "operation": report.operation,
        "status": report.status,
    }
    if report.diagnostic:
        data["diagnostic"] = report.diagnostic
    return RoomEvent(
        channel=f"storefront:{report.shop_id}:releases",
        name=name,
        data=data,
    )


app = FastAPI(title="Storefront release chat")


@app.post("/release-room", response_model=ReleaseRoomResponse)
async def open_release_room(report: BuildReport) -> ReleaseRoomResponse:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is not configured")

    planned = plan_room_event(report)
    try:
        async with InfraiRealtime(api_key) as realtime:
            await realtime.create_channel(planned.channel, f"{report.build_id}:channel")
            await realtime.publish(
                planned.channel,
                planned.name,
                planned.data,
                report.shop_id,
                f"{report.build_id}:event:{planned.name}",
            )
            token_data = await realtime.issue_token(
                report.developer_id,
                planned.channel,
                f"{report.build_id}:token:{report.developer_id}",
            )
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return ReleaseRoomResponse(
        channel=planned.channel,
        event=planned.name,
        token=str(token_data["token"]),
    )

