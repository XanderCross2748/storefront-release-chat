import pytest
from pydantic import ValidationError

from storefront_release_chat.release_room import BuildReport, plan_room_event


def test_failed_checkout_build_becomes_diagnostic_room_event() -> None:
    report = BuildReport(
        shop_id="linen-and-lamp",
        build_id="build-1842",
        git_sha="7ca91e2",
        status="failed",
        operation="deploy",
        developer_id="dev-mira",
        diagnostic="Checkout bundle exceeds its size budget",
    )

    event = plan_room_event(report)

    assert event.channel == "storefront:linen-and-lamp:releases"
    assert event.name == "build.failed"
    assert event.data["operation"] == "deploy"
    assert event.data["diagnostic"] == "Checkout bundle exceeds its size budget"


def test_failed_build_without_diagnostic_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BuildReport(
            shop_id="linen-and-lamp",
            build_id="build-1843",
            git_sha="7ca91e2",
            status="failed",
            developer_id="dev-mira",
        )

