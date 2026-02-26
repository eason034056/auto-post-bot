"""
Threads API client - placeholder for future auto-posting.

Requires:
- THREADS_ACCESS_TOKEN
- THREADS_USER_ID
- Meta Developer App with threads_content_publish permission

API: https://developers.facebook.com/docs/threads/posts/
"""
from .config import THREADS_ACCESS_TOKEN, THREADS_USER_ID


def publish_post(media_urls: list[str], caption: str = "") -> str | None:
    """
    Publish a post to Threads (two-step: create container, then publish).

    Args:
        media_urls: List of publicly accessible image URLs
        caption: Post caption text

    Returns:
        Post ID if successful, else None
    """
    if not THREADS_ACCESS_TOKEN or not THREADS_USER_ID:
        return None

    # TODO: Implement Threads API two-step flow
    # 1. POST /{user_id}/threads with media_type=IMAGE, image_url, text
    # 2. Wait ~30s for processing
    # 3. POST /{user_id}/threads_publish with creation_id
    raise NotImplementedError("Threads API integration - add when Meta App is approved")


def post_and_pin_comment(post_id: str, comment_text: str) -> str | None:
    """
    Post a comment and pin it.

    Args:
        post_id: The Threads post ID
        comment_text: CTA + short URL text

    Returns:
        Comment ID if successful, else None
    """
    if not THREADS_ACCESS_TOKEN:
        return None

    # TODO: Implement Threads API comment + pin
    raise NotImplementedError("Threads API comment/pin - add when available")
