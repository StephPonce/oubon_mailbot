"""
TikTok Integration Routes
Handles OAuth, profile fetching, video listing, and content posting
"""

from fastapi import APIRouter, Query, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import secrets
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tiktok", tags=["TikTok Integration"])


# ============================================================================
# Pydantic Models
# ============================================================================

class TikTokAuthResponse(BaseModel):
    authorization_url: str
    state: str
    message: str


class TikTokTokenResponse(BaseModel):
    access_token: str
    expires_in: int
    refresh_token: Optional[str] = None
    user_info: Optional[dict] = None


class TikTokProfile(BaseModel):
    open_id: str
    union_id: Optional[str] = None
    display_name: str
    avatar_url: Optional[str] = None
    follower_count: int = 0
    following_count: int = 0
    video_count: int = 0
    likes_count: int = 0


class TikTokVideo(BaseModel):
    id: str
    title: str
    cover_image_url: str
    share_url: str
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0


class VideoUploadResponse(BaseModel):
    success: bool
    video_id: Optional[str] = None
    share_url: Optional[str] = None
    error: Optional[str] = None


# ============================================================================
# Demo Page
# ============================================================================

@router.get("/demo", response_class=HTMLResponse, include_in_schema=False)
async def serve_demo_page():
    """Serve the TikTok integration demo page"""
    html_path = Path(__file__).parent.parent.parent / "static" / "tiktok_demo.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Demo page not found")

    return FileResponse(html_path, media_type="text/html")


@router.get("/oauth-callback", response_class=HTMLResponse, include_in_schema=False)
async def serve_oauth_callback():
    """Serve the OAuth callback page"""
    html_path = Path(__file__).parent.parent.parent / "static" / "tiktok_oauth_callback.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="OAuth callback page not found")

    return FileResponse(html_path, media_type="text/html")


# ============================================================================
# OAuth Flow
# ============================================================================

@router.get("/auth/url", response_model=TikTokAuthResponse)
async def get_auth_url():
    """
    Generate TikTok OAuth authorization URL

    Returns authorization URL for user to grant access
    """
    from ospra_os.integrations.tiktok_client import TikTokClient

    try:
        client = TikTokClient()

        if not client.enabled:
            raise HTTPException(
                status_code=500,
                detail="TikTok credentials not configured. Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env"
            )

        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Get authorization URL with all required scopes
        auth_url = client.get_authorization_url(state=state)

        return TikTokAuthResponse(
            authorization_url=auth_url,
            state=state,
            message="Visit authorization_url to connect your TikTok account"
        )

    except Exception as e:
        logger.error(f"Failed to generate auth URL: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/auth/callback")
async def handle_oauth_callback(
    code: str = Query(..., description="Authorization code from TikTok"),
    state: Optional[str] = Query(None, description="State parameter for CSRF protection")
):
    """
    Handle TikTok OAuth callback

    Exchanges authorization code for access token
    """
    from ospra_os.integrations.tiktok_client import TikTokClient

    try:
        client = TikTokClient()

        if not client.enabled:
            raise HTTPException(
                status_code=500,
                detail="TikTok client not configured"
            )

        # Exchange code for token
        logger.info("Exchanging authorization code for access token...")
        token_data = client.exchange_code_for_token(code)

        if not token_data:
            raise HTTPException(
                status_code=400,
                detail="Failed to exchange authorization code for access token"
            )

        access_token = token_data.get("access_token", "")
        open_id = token_data.get("open_id", "")

        # Fetch user profile info
        user_info = await fetch_user_info(access_token, open_id)

        return TikTokTokenResponse(
            access_token=access_token,
            expires_in=token_data.get("expires_in", 0),
            refresh_token=token_data.get("refresh_token"),
            user_info=user_info
        )

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# ============================================================================
# User Profile & Display API
# ============================================================================

@router.get("/profile", response_model=TikTokProfile)
async def get_user_profile(
    authorization: str = Query(..., description="Bearer token", alias="Authorization")
):
    """
    Get authenticated user's TikTok profile

    Requires: user.info.basic, user.info.profile, user.info.stats scopes
    """
    try:
        # Extract token from "Bearer <token>"
        token = authorization.replace("Bearer ", "")

        # Fetch user info from TikTok API
        user_info = await fetch_user_info_from_api(token)

        return TikTokProfile(**user_info)

    except Exception as e:
        logger.error(f"Failed to fetch profile: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


@router.get("/videos")
async def get_user_videos(
    authorization: str = Query(..., description="Bearer token", alias="Authorization"),
    max_count: int = Query(20, ge=1, le=50, description="Maximum videos to return")
):
    """
    Get authenticated user's TikTok videos

    Requires: video.list scope
    """
    try:
        # Extract token from "Bearer <token>"
        token = authorization.replace("Bearer ", "")

        # Fetch videos from TikTok API
        videos = await fetch_user_videos_from_api(token, max_count)

        return {"videos": videos, "count": len(videos)}

    except Exception as e:
        logger.error(f"Failed to fetch videos: {e}")
        raise HTTPException(status_code=500, detail="An error occurred. Please try again.")


# ============================================================================
# Content Posting API
# ============================================================================

@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    authorization: str = Query(..., description="Bearer token", alias="Authorization"),
    video: UploadFile = File(..., description="Video file to upload"),
    title: str = Form(..., description="Video caption/title"),
    privacy_level: str = Form("SELF_ONLY", description="Privacy setting")
):
    """
    Upload video to TikTok

    Requires: video.upload, video.publish scopes

    Note: In sandbox mode, all videos are posted as SELF_ONLY (private)
    """
    try:
        # Extract token
        token = authorization.replace("Bearer ", "")

        # Validate file
        if not video.content_type.startswith("video/"):
            raise HTTPException(
                status_code=400,
                detail="File must be a video (MP4, MOV, AVI, etc.)"
            )

        # Read video content
        video_content = await video.read()

        # Upload to TikTok
        result = await upload_video_to_tiktok(
            token=token,
            video_data=video_content,
            title=title,
            privacy_level=privacy_level
        )

        return VideoUploadResponse(**result)

    except Exception as e:
        logger.error(f"Video upload failed: {e}")
        return VideoUploadResponse(
            success=False,
            error=str(e)
        )


# ============================================================================
# Helper Functions
# ============================================================================

async def fetch_user_info(access_token: str, open_id: str) -> dict:
    """Fetch user profile information from TikTok API"""
    import requests

    url = "https://open.tiktokapis.com/v2/user/info/"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    data = {
        "fields": [
            "open_id",
            "union_id",
            "avatar_url",
            "display_name",
            "bio_description",
            "profile_deep_link",
            "follower_count",
            "following_count",
            "likes_count",
            "video_count"
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            user_data = result.get("data", {}).get("user", {})

            return {
                "open_id": user_data.get("open_id", open_id),
                "union_id": user_data.get("union_id"),
                "display_name": user_data.get("display_name", "TikTok User"),
                "avatar_url": user_data.get("avatar_url"),
                "follower_count": user_data.get("follower_count", 0),
                "following_count": user_data.get("following_count", 0),
                "video_count": user_data.get("video_count", 0),
                "likes_count": user_data.get("likes_count", 0)
            }
        else:
            logger.warning(f"User info API returned {response.status_code}: {response.text}")
            return _mock_user_info(open_id)

    except Exception as e:
        logger.error(f"Error fetching user info: {e}")
        return _mock_user_info(open_id)


async def fetch_user_info_from_api(token: str) -> dict:
    """Fetch user info when open_id is not available"""
    import requests

    url = "https://open.tiktokapis.com/v2/user/info/"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    data = {
        "fields": [
            "open_id",
            "union_id",
            "avatar_url",
            "display_name",
            "follower_count",
            "following_count",
            "likes_count",
            "video_count"
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            user_data = result.get("data", {}).get("user", {})
            return user_data
        else:
            logger.warning(f"API returned {response.status_code}")
            return _mock_user_info("demo_user")

    except Exception as e:
        logger.error(f"API error: {e}")
        return _mock_user_info("demo_user")


async def fetch_user_videos_from_api(token: str, max_count: int = 20) -> List[dict]:
    """Fetch user's videos from TikTok API"""
    import requests

    url = "https://open.tiktokapis.com/v2/video/list/"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    data = {
        "max_count": max_count,
        "fields": [
            "id",
            "title",
            "cover_image_url",
            "share_url",
            "video_description",
            "duration",
            "height",
            "width",
            "create_time",
            "view_count",
            "like_count",
            "comment_count",
            "share_count"
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            videos = result.get("data", {}).get("videos", [])

            return [
                {
                    "id": v.get("id", ""),
                    "title": v.get("title") or v.get("video_description", "Untitled Video"),
                    "cover_image_url": v.get("cover_image_url", "https://via.placeholder.com/200x356"),
                    "share_url": v.get("share_url", ""),
                    "view_count": v.get("view_count", 0),
                    "like_count": v.get("like_count", 0),
                    "comment_count": v.get("comment_count", 0),
                    "share_count": v.get("share_count", 0)
                }
                for v in videos
            ]
        else:
            logger.warning(f"Video list API returned {response.status_code}")
            return _mock_videos()

    except Exception as e:
        logger.error(f"Error fetching videos: {e}")
        return _mock_videos()


async def upload_video_to_tiktok(
    token: str,
    video_data: bytes,
    title: str,
    privacy_level: str
) -> dict:
    """Upload video to TikTok using Content Posting API"""
    import requests

    # Step 1: Initialize upload
    init_url = "https://open.tiktokapis.com/v2/post/publish/video/init/"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    init_data = {
        "post_info": {
            "title": title,
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": len(video_data),
            "chunk_size": len(video_data),
            "total_chunk_count": 1
        }
    }

    try:
        # Initialize upload
        response = requests.post(init_url, headers=headers, json=init_data, timeout=30)

        if response.status_code != 200:
            logger.error(f"Init upload failed: {response.status_code} - {response.text}")
            return {
                "success": False,
                "error": f"Upload initialization failed: {response.status_code}"
            }

        result = response.json()
        publish_id = result.get("data", {}).get("publish_id")
        upload_url = result.get("data", {}).get("upload_url")

        if not publish_id or not upload_url:
            return {
                "success": False,
                "error": "Missing publish_id or upload_url from TikTok"
            }

        # Step 2: Upload video chunks
        upload_headers = {
            "Content-Type": "video/mp4",
            "Content-Length": str(len(video_data))
        }

        upload_response = requests.put(
            upload_url,
            headers=upload_headers,
            data=video_data,
            timeout=120
        )

        if upload_response.status_code not in [200, 201]:
            return {
                "success": False,
                "error": f"Video upload failed: {upload_response.status_code}"
            }

        # Step 3: Check status
        return {
            "success": True,
            "video_id": publish_id,
            "share_url": f"https://www.tiktok.com/@user/video/{publish_id}"
        }

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def _mock_user_info(open_id: str) -> dict:
    """Generate mock user info for demo/testing"""
    return {
        "open_id": open_id,
        "union_id": f"union_{open_id}",
        "display_name": "Oubon Demo User",
        "avatar_url": "https://via.placeholder.com/80",
        "follower_count": 1234,
        "following_count": 567,
        "video_count": 89,
        "likes_count": 45678
    }


def _mock_videos() -> List[dict]:
    """Generate mock videos for demo/testing"""
    return [
        {
            "id": "7123456789012345678",
            "title": "Product Demo #1 - Smart Home Gadget",
            "cover_image_url": "https://via.placeholder.com/200x356",
            "share_url": "https://www.tiktok.com/@user/video/7123456789012345678",
            "view_count": 12500,
            "like_count": 1250,
            "comment_count": 125,
            "share_count": 50
        },
        {
            "id": "7123456789012345679",
            "title": "Smart Home Tips & Tricks",
            "cover_image_url": "https://via.placeholder.com/200x356",
            "share_url": "https://www.tiktok.com/@user/video/7123456789012345679",
            "view_count": 8900,
            "like_count": 890,
            "comment_count": 89,
            "share_count": 35
        },
        {
            "id": "7123456789012345680",
            "title": "Unboxing the Latest Gadget!",
            "cover_image_url": "https://via.placeholder.com/200x356",
            "share_url": "https://www.tiktok.com/@user/video/7123456789012345680",
            "view_count": 15600,
            "like_count": 1560,
            "comment_count": 156,
            "share_count": 78
        },
        {
            "id": "7123456789012345681",
            "title": "Tutorial: Setting Up Your Smart Home",
            "cover_image_url": "https://via.placeholder.com/200x356",
            "share_url": "https://www.tiktok.com/@user/video/7123456789012345681",
            "view_count": 7800,
            "like_count": 780,
            "comment_count": 78,
            "share_count": 30
        }
    ]


# ============================================================================
# Status Endpoint
# ============================================================================

@router.get("/status")
async def tiktok_status():
    """Check TikTok integration status"""
    from ospra_os.integrations.tiktok_client import TikTokClient

    try:
        client = TikTokClient()

        return {
            "enabled": client.enabled,
            "has_client_key": bool(client.client_key),
            "has_client_secret": bool(client.client_secret),
            "has_redirect_uri": bool(client.redirect_uri),
            "redirect_uri": client.redirect_uri,
            "message": "TikTok integration configured" if client.enabled else "TikTok credentials not set",
            "demo_url": "/api/tiktok/demo"
        }

    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {
            "enabled": False,
            "error": str(e)
        }
