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
    content_id: str = Field(..., description="Content item ID")
    title: str = Field("", description="Article or newsletter title")
    content: str = Field("", description="HTML content from the editor")
    subject: str = Field("", description="Email subject line (newsletter only)")


class UpdateStatusParams(BaseModel):
    content_id: str = Field(..., description="Content item ID")
    status: str = Field(..., description="New status: idea|writing|review|published")


class DeleteContentParams(BaseModel):
    content_id: str = Field(..., description="Content item ID to delete")


class OpenEditorParams(BaseModel):
    content_id: str = Field(..., description="Content item ID to open in editor")


class SetEditorModeParams(BaseModel):
    mode: str = Field(..., description="'edit' or 'preview'")


class AiBriefParams(BaseModel):
    content_id: str = Field(..., description="Content item ID")
    extra: str = Field("", description="Additional context or instructions for the AI")


class AiWriteParams(BaseModel):
    content_id: str = Field(..., description="Content item ID")
    section: str = Field("full", description="'full', 'intro', 'conclusion', or 'improve'")


class FetchKeywordsParams(BaseModel):
    domain: str = Field("blog.webhostmost.com", description="Domain to analyse")
    source: str = Field("us", description="Regional database code, e.g. 'us', 'gb'")
    limit: int = Field(50, description="Number of keywords to return (max 100)")
    min_volume: int = Field(100, description="Minimum monthly search volume")
    max_difficulty: int = Field(60, description="Maximum keyword difficulty")


class FetchGapsParams(BaseModel):
    competitor: str = Field(..., description="Competitor domain to compare against")
    source: str = Field("us", description="Regional database code")
    limit: int = Field(30, description="Number of gap keywords to return")


class PublishWpParams(BaseModel):
    content_id: str = Field(..., description="Content item ID to publish")
    status: str = Field("draft", description="WP post status: 'draft' or 'publish'")


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
    content_id: str = Field(..., description="Newsletter content item ID")
    news_text: str = Field(..., description="The news, update, or topic to write the newsletter about")
    tone_note: str = Field("", description="Optional tone instruction, e.g. 'more urgent', 'focus on price'")


class SaveSettingsParams(BaseModel):
    # SE Ranking
    seranking_data_key: Optional[str] = None
    seranking_project_key: Optional[str] = None
    seranking_project_id: Optional[str] = None
    seranking_domain: Optional[str] = None
    seranking_source: Optional[str] = None
    # WordPress
    wp_url: Optional[str] = None
    wp_username: Optional[str] = None
    wp_app_password: Optional[str] = None
    wp_author_id: Optional[int] = None
    # Brand identity
    company_name: Optional[str] = None
    brand_description: Optional[str] = None
    brand_voice: Optional[str] = None
    newsletter_cta: Optional[str] = None
    site_url: Optional[str] = None
    blog_url: Optional[str] = None
    tg_url: Optional[str] = None
    community_url: Optional[str] = None
