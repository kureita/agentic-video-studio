"""Video Composer Service - Uses Remotion for video composition."""

import httpx
from typing import Optional

from app.core.config import settings


class VideoComposer:
    """Composes videos using the Remotion rendering service."""

    def __init__(self):
        self.remotion_url = settings.remotion_url
        self.timeout = 600  # 10 minutes for rendering

    async def compose_video(
        self,
        project_id: str,
        scenes: list,
        brand_profile: dict,
        story: dict,
        output_filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        Compose a video using Remotion.
        
        Args:
            project_id: The project ID
            scenes: List of scene data with asset_url
            brand_profile: Brand information for styling
            story: Story data with call_to_action
            output_filename: Optional output filename
            
        Returns:
            URL to the composed video
        """
        if not scenes:
            print("[VideoComposer] No scenes to compose")
            return None
        
        # Check if Remotion service is available
        if not self.remotion_url:
            print("[VideoComposer] Remotion URL not configured, using first video")
            return self._get_first_video(scenes)
        
        try:
            print(f"[VideoComposer] Sending {len(scenes)} scenes to Remotion...")
            for i, s in enumerate(scenes):
                video_url = s.get("asset_url") or s.get("video_url") if isinstance(s, dict) else getattr(s, "asset_url", None) or getattr(s, "video_url", None)
                print(f"[VideoComposer]   Scene {i+1} video: {video_url[:80] if video_url else 'NONE'}...")
            
            # Prepare request payload
            payload = {
                "project_id": project_id,
                "scenes": [
                    {
                        "id": s.get("id") or s.id if hasattr(s, "id") else i,
                        "start_time": s.get("start_time") or (s.start_time if hasattr(s, "start_time") else 0),
                        "end_time": s.get("end_time") or (s.end_time if hasattr(s, "end_time") else 8),
                        "description": s.get("description", "") or (s.description if hasattr(s, "description") else ""),
                        "visual_prompt": s.get("visual_prompt", "") or (s.visual_prompt if hasattr(s, "visual_prompt") else ""),
                        "voiceover_text": s.get("voiceover_text") or (s.voiceover_text if hasattr(s, "voiceover_text") else None),
                        "on_screen_text": s.get("on_screen_text") or (s.on_screen_text if hasattr(s, "on_screen_text") else None),
                        # Support both asset_url and video_url (canvas pipeline uses video_url)
                        "asset_url": s.get("asset_url") or s.get("video_url") or (s.asset_url if hasattr(s, "asset_url") else None) or (s.video_url if hasattr(s, "video_url") else None),
                    }
                    for i, s in enumerate(scenes)
                ],
                "brand": {
                    "name": brand_profile.get("name", "Brand"),
                    "tagline": brand_profile.get("tagline"),
                    "primary_colors": brand_profile.get("primary_colors", []),
                    "logo_url": brand_profile.get("logo_url"),
                    "tone": brand_profile.get("tone", "professional"),
                },
                "story": {
                    "title": story.get("title", ""),
                    "call_to_action": story.get("call_to_action", ""),
                },
            }
            
            if output_filename:
                payload["output_filename"] = output_filename
            
            # Call Remotion service
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.remotion_url}/render",
                    json=payload,
                )
                
                if response.status_code == 200:
                    result = response.json()
                    output_path = result.get("output_path")
                    filename = result.get("filename")
                    
                    print(f"[VideoComposer] Remotion render complete: {filename}")
                    
                    # Return the video URL
                    # Remotion saves to its output folder, we need to serve it
                    return f"{settings.api_base_url}/static/videos/{filename}"
                else:
                    error = response.json().get("error", "Unknown error")
                    print(f"[VideoComposer] Remotion error: {error}")
                    return self._get_first_video(scenes)
                    
        except httpx.TimeoutException:
            print("[VideoComposer] Remotion request timed out")
            return self._get_first_video(scenes)
        except Exception as e:
            print(f"[VideoComposer] Error calling Remotion: {e}")
            return self._get_first_video(scenes)

    def _get_first_video(self, scenes: list) -> Optional[str]:
        """Fallback: return the first scene's video URL."""
        for scene in scenes:
            if isinstance(scene, dict):
                url = scene.get("asset_url") or scene.get("video_url")
            else:
                url = getattr(scene, "asset_url", None) or getattr(scene, "video_url", None)
            if url:
                return url
        return None
