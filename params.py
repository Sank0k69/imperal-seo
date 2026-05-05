"""Pydantic parameter models for all chat functions."""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class CreateContentParams(BaseModel):
    keyword: str = Field(..., description="Target keyword for this content")
    type: str = Field("blog", description="'blog' or 'newsletter'")
    title: str = Field("", description="Content title (optional, AI can generate)")
    volume: int = Field(0, description="Monthly search volume from SE Ranking")
    difficulty: int = Field(0, description="Keyword difficulty 0-100")


class SaveDraftParams(BaseModel):
    content_id: str = Field("", description="Content item ID — leave empty to use currently open item")
    title: str = Field("", description="Article or newsletter title")
    content: str = Field("", description="HTML content from the editor")
    subject: str = Field("", description="Email subject line (newsletter only)")


class UpdateStatusParams(BaseModel):
    content_id: str = Field("", description="Content item ID — leave empty to use currently open item")
    status: str = Field(..., description="New status: idea|writing|review|published")


class DeleteContentParams(BaseModel):
    content_id: str = Field(..., description="Content item ID to delete")


class OpenEditorParams(BaseModel):
    content_id: str = Field(..., description="Content item ID to open in editor")


class SetEditorModeParams(BaseModel):
    mode: str = Field(..., description="'edit' or 'preview'")


class AiBriefParams(BaseModel):
    content_id: str = Field("", description="Content item ID — leave empty to use currently open item")
    extra: str = Field("", description="Additional context or instructions for the AI")


class SaveBriefParams(BaseModel):
    content_id: str = Field("", description="Content item ID — leave empty to use currently open item")
    brief_text: str = Field("", description="Brief content to save")


class AiWriteParams(BaseModel):
    content_id: str = Field("", description="Content item ID — leave empty to use currently open item")
    section: str = Field("full", description="'full' or 'improve'")
    article_type: str = Field("", description="blog | comparison | tutorial | pillar | news | review — overrides item type")


class ImproveArticleParams(BaseModel):
    content_id: str = Field("", description="Content item ID — leave empty to use currently open item")
    instruction: str = Field("", description="Optional specific improvement instruction")


class FetchKeywordsParams(BaseModel):
    domain: str = Field("", description="Domain to analyse — leave empty to use domain from Settings")
    source: str = Field("", description="Regional database code, e.g. 'us', 'gb' — empty = use Settings")
    limit: int = Field(80, description="Number of keywords to return (max 100)")
    min_volume: int = Field(50, description="Minimum monthly search volume")
    max_difficulty: int = Field(70, description="Maximum keyword difficulty")


class FetchGapsParams(BaseModel):
    competitor: str = Field(..., description="Competitor domain to compare against")
    source: str = Field("us", description="Regional database code")
    limit: int = Field(30, description="Number of gap keywords to return")


class PublishWpParams(BaseModel):
    content_id: str = Field("", description="Content item ID — leave empty to use currently open item")
    status: str = Field("draft", description="WP post status: 'draft' or 'publish'")


class SetWpSeoParams(BaseModel):
    content_id: str = Field("", description="Content item ID — leave empty to use currently open item")
    meta_description: str = Field("", description="SEO meta description (120-155 chars) — leave empty to auto-generate")
    focus_keyword: str = Field("", description="Rank Math focus keyword — leave empty to use item's keyword")


class EmptyParams(BaseModel):
    pass


class FetchRankingsParams(BaseModel):
    pass


class ListProjectsParams(BaseModel):
    pass


class UploadDocParams(BaseModel):
    files: Optional[list] = Field(None, description="Base64-encoded files from FileUpload component")


class DeleteDocParams(BaseModel):
    doc_id: str = Field(..., description="Store ID of the doc to delete")


class GenerateNewsletterParams(BaseModel):
    content_id: str = Field("", description="Newsletter content item ID — leave empty to use currently open item")
    news_text: str = Field(..., description="The news, update, or topic to write the newsletter about")
    tone_note: str = Field("", description="Optional tone instruction, e.g. 'more urgent', 'focus on price'")


class BuildPlanParams(BaseModel):
    competitor: Optional[str] = Field("", description="Competitor domain for gap analysis — empty = use Settings")
    language: str = Field("en", description="Content language: 'en' or 'ru'")


class SaveSettingsParams(BaseModel):
    # SE Ranking
    seranking_data_key: Optional[str] = None
    seranking_project_key: Optional[str] = None
    seranking_project_id: Optional[str] = None
    seranking_domain: Optional[str] = None
    seranking_source: Optional[str] = None
    seranking_competitor: Optional[str] = None
    # WordPress
    wp_url: Optional[str] = None
    wp_username: Optional[str] = None
    wp_app_password: Optional[str] = None
    wp_author_id: Optional[int] = None
    # Matomo analytics
    matomo_url: Optional[str] = None
    matomo_token: Optional[str] = None
    matomo_site_id: Optional[int] = None
    # Brand identity
    company_name: Optional[str] = None
    brand_description: Optional[str] = None
    brand_voice: Optional[str] = None
    newsletter_cta: Optional[str] = None
    site_url: Optional[str] = None
    blog_url: Optional[str] = None
    tg_url: Optional[str] = None
    community_url: Optional[str] = None
