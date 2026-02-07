# Video Generator Node Updates

## Changes Summary

### Frontend Changes

#### 1. Video Generator Node Inputs (`video-gen-node.tsx`)
**Changed from:**
- `text` (Text/Prompt)
- `image` (generic Image input)

**Changed to:**
- `text` (Text/Prompt)
- `start_image` (Start Image) - First frame for video generation
- `end_image` (End Image) - Last frame for interpolation
- `reference_images` (Ref Images) - Style/asset reference images
- `reference_video` (Ref Video) - Reference video for extension

#### 2. Duration Options (`video-gen-node.tsx`)
**Changed from:** 5s, 8s, 10s (invalid for Veo)
**Changed to:** 4s, 6s, 8s (valid Veo 3.1 durations)
**Default:** 4s

### Backend Changes

#### 3. Node Runner (`node_runner.py`)
- **Updated `_run_video_gen_node`** to handle all new input types
- **Smart routing** based on which inputs are provided:
  - `start_image` + `end_image` → Interpolation (generates motion between two frames)
  - `start_image` only → Image-to-video (animates single image)
  - `reference_images` → Reference-based generation (style transfer)
  - `reference_video` → Placeholder (not fully implemented yet)
  - No media inputs → Text-to-video
- **Uses Veo 3.1 Fast** by default (`use_fast_model=True`)
- **Validates duration** to only allow 4, 6, or 8 seconds
- **Default prompts** when only media is provided

#### 4. Video Generator Service (`video_generator.py`)
- **Added `httpx` import** for downloading images
- **Added `tempfile` import** for temporary file handling
- **New method `_fetch_image_to_temp`**:
  - Downloads images from URLs to temporary files
  - Returns local file path for Veo API
  - Handles both URLs and local paths
  - Sets appropriate file extensions (.png or .jpg)
  
- **Updated Methods**:
  - `generate_from_image`: Now fetches images from URLs first, uses fast model
  - `generate_with_reference_images`: Fetches each reference image, uses fast model
  - `generate_with_interpolation`: Fetches both start and end images, uses fast model

## How to Use

### Example Workflows

#### 1. **Image-to-Video**
```
TextNode("Frog with a hat") → ImageGenNode → VideoGenNode
                                  (output)  →  (start_image)
```
The video will animate the generated image.

#### 2. **Interpolation (Morphing)**
```
ImageGenNode(A) → VideoGenNode ← ImageGenNode(B)
   (output)    → (start_image)      (output)
                   (end_image)    ←
```
The video will smoothly transition/interpolate between the two images.

#### 3. **Reference-based Generation**
```
ImageGenNode → VideoGenNode
   (style)  → (reference_images)
    
TextNode  → (text input)
("person dancing")
```
The video will use the reference image's style while following the text prompt.

#### 4. **Pure Text-to-Video**
```
TextNode → VideoGenNode
         → (text input only)
```
Generates video directly from text description.

## Technical Details

### Veo 3.1 Fast Model
- **Model ID**: `veo-3.1-fast-generate-preview`
- **Supported Durations**: 4s, 6s, 8s only
- **Aspect Ratios**: 16:9, 9:16, 1:1
- **Faster generation** compared to standard Veo 3.1

### Input Priority
When multiple inputs are provided, the system uses this priority:
1. Start + End image → Interpolation
2. Start image only → Image-to-video
3. Reference images → Reference-based
4. Reference video → Extension (not implemented)
5. None → Text-to-video

### Default Behavior
- **Model**: Veo 3.1 Fast (for faster workflow execution)
- **Duration**: 4 seconds (minimum for Veo)
- **Aspect Ratio**: 16:9 (landscape)
- **Default Prompts** are provided if only images are connected:
  - Start image: "Animate this image with natural motion"
  - Reference images: "Generate video using these reference images"
  - Reference video: "Generate video based on this reference video"

## Testing Checklist

- [ ] Test text-to-video generation (text input only)
- [ ] Test image-to-video (connect image to start_image)
- [ ] Test interpolation (connect images to start_image AND end_image)
- [ ] Test reference images (connect image to reference_images)
- [ ] Verify duration options show 4s, 6s, 8s only
- [ ] Verify default is 4s
- [ ] Check that remote images are properly downloaded
- [ ] Confirm Veo 3.1 Fast model is used

## Files Modified

**Frontend:**
- `apps/web/src/components/workflow/nodes/video-gen-node.tsx`

**Backend:**
- `apps/api/app/services/node_runner.py`
- `apps/api/app/services/video_generator.py`

## Notes

- **Reference video input** is defined in the UI but not fully implemented in the backend (requires video download and Veo API video object handling)
- All video generation methods now use **Veo 3.1 Fast** for better performance
- Images from URLs are automatically downloaded to temporary files for Veo API compatibility
- Temporary image files are not automatically cleaned up (OS will handle cleanup)
