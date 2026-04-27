"""Tests for publish handlers — WP error paths and settings."""
import pytest
from imperal_sdk.testing import MockContext

import handlers_nav
import handlers_publish

_FAKE_PW = "fake-test-pw"        # nosec — not a real credential
_FAKE_KEY = "fake-test-data-key"  # nosec — not a real credential


@pytest.fixture
def ctx():
    return MockContext(role="admin")


async def test_publish_wp_no_key(ctx):
    """Returns error when WP app password not configured."""
    create_result = await handlers_nav.new_content(ctx, handlers_nav.CreateContentParams(
        keyword="test article", type="blog",
    ))
    content_id = create_result.data["id"]

    result = await handlers_publish.publish_wp(ctx, handlers_publish.PublishWpParams(
        content_id=content_id,
        status="draft",
    ))
    assert result.status == "error"
    assert "Application Password" in result.error


async def test_publish_wp_empty_content(ctx):
    """Returns error when content body is empty."""
    await handlers_publish.save_settings_fn(ctx, handlers_publish.SaveSettingsParams(
        wp_app_password=_FAKE_PW,
    ))
    create_result = await handlers_nav.new_content(ctx, handlers_nav.CreateContentParams(
        keyword="empty article", type="blog",
    ))
    content_id = create_result.data["id"]

    result = await handlers_publish.publish_wp(ctx, handlers_publish.PublishWpParams(
        content_id=content_id,
        status="draft",
    ))
    assert result.status == "error"
    assert "empty" in result.error.lower()


async def test_publish_wp_missing_item(ctx):
    """Returns error when content ID does not exist."""
    await handlers_publish.save_settings_fn(ctx, handlers_publish.SaveSettingsParams(
        wp_app_password=_FAKE_PW,
    ))
    result = await handlers_publish.publish_wp(ctx, handlers_publish.PublishWpParams(
        content_id="nonexistent_id",
        status="draft",
    ))
    assert result.status == "error"
    assert "not found" in result.error.lower()


async def test_save_settings(ctx):
    result = await handlers_publish.save_settings_fn(ctx, handlers_publish.SaveSettingsParams(
        seranking_data_key=_FAKE_KEY,
        wp_app_password=_FAKE_PW,
    ))
    assert result.status == "success"

    page = await ctx.store.query("seo_settings", limit=1)
    s = page.data[0].data
    assert s["seranking_data_key"] == _FAKE_KEY
    assert s["wp_app_password"] == _FAKE_PW


async def test_save_settings_partial_update(ctx):
    """Partial update merges with existing settings."""
    await handlers_publish.save_settings_fn(ctx, handlers_publish.SaveSettingsParams(
        seranking_data_key="key_one",  # nosec
    ))
    await handlers_publish.save_settings_fn(ctx, handlers_publish.SaveSettingsParams(
        wp_app_password="pw_two",  # nosec
    ))

    page = await ctx.store.query("seo_settings", limit=1)
    s = page.data[0].data
    assert s["seranking_data_key"] == "key_one"  # nosec
    assert s["wp_app_password"] == "pw_two"  # nosec
