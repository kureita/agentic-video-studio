# Node System Refactor Summary

## Changes Made

### 1. Renamed Assistant Node → Vision Node
- **File**: `apps/web/src/components/workflow/nodes/vision-node.tsx` (new)
- **Old File**: `apps/web/src/components/workflow/nodes/assistant-node.tsx` (kept for backward compatibility)
- **Changes**:
  - Icon changed from `Bot` to `Eye`
  - Model updated from "Gemini 1.5 Pro" to "Gemini 2.0 Flash"
  - New layout with 2/3 split:
    - Top 2/3: Read-only output area (displays text output after running)
    - Bottom 1/3: Editable instruction area
  - Inputs: `text`, `ref_images`, `ref_videos`
  - Output: `text` (can be used as prompt for next nodes)

### 2. Created Editor Agent Node
- **File**: `apps/web/src/components/workflow/nodes/editor-agent-node.tsx` (new)
- **Purpose**: Uses Remotion to stitch videos together and perform editing tasks
- **Features**:
  - Video preview area at the top
  - Instruction textarea for editing tasks
  - Inputs: `text`, `ref_images`, `ref_videos`
  - Output: `video` only
  - Badge shows "Remotion" as the engine

### 3. Created Media Upload Node
- **File**: `apps/web/src/components/workflow/nodes/media-upload-node.tsx` (new)
- **Purpose**: Upload either images or videos
- **Features**:
  - Dynamic output type based on uploaded media
  - If image uploaded → output type is `image`
  - If video uploaded → output type is `video`
  - Preview area shows the uploaded media
  - Badge indicates media type (Image/Video)
  - Supports JPG, PNG, MP4, MOV formats

### 4. Removed Nodes from Add Menu
- **Removed**: Image Upscaler node
- **Removed**: Camera Angle node
- **File**: `apps/web/src/components/workflow/node-selector.tsx`

### 5. Removed Upload/Media Buttons from Toolbar
- **File**: `apps/web/src/components/workflow/node-selector.tsx`
- Removed the "Upload" and "Media" buttons from the node selector header
- Users now use the Media Upload node instead

### 6. Updated Node Registry
- **File**: `apps/web/src/components/workflow/flow-editor.tsx`
- Registered new nodes: `vision`, `editorAgent`, `mediaUpload`
- Kept `assistant` as alias for `vision` for backward compatibility
- Removed: `upscaler` node type

### 7. Backend Updates
- **File**: `apps/api/app/services/node_runner.py`
- Added `_run_vision_node()` - placeholder for Gemini chat model integration
- Added `_run_editor_agent_node()` - placeholder for Remotion integration
- Added `_run_media_upload_node()` - handles media upload output
- Updated node type routing to handle new nodes
- Kept legacy `assistant` node handler that redirects to vision node

## Node Comparison

### Before
- Text Node
- Image Generator Node
- Video Generator Node
- Assistant Node (simple textarea)
- Image Upscaler Node
- Camera Angle Node (never implemented)
- Upload Node

### After
- Text Node
- Image Generator Node
- Video Generator Node
- **Vision Node** (chat-based with output display)
- **Editor Agent Node** (video editing with Remotion)
- **Media Upload Node** (dynamic image/video upload)
- Upload Node (kept for backward compatibility)

## Implementation Status

### ✅ Completed
- Frontend node components created
- Node selector updated
- Flow editor updated with new node types
- Backend node runner structure updated
- Backward compatibility maintained

### 🚧 To Be Implemented
- Vision Node: Gemini 2.0 Flash chat model integration
- Editor Agent Node: Remotion video editing integration
- Media Upload Node: File upload handling and storage

## Migration Notes

- Existing workflows with "assistant" nodes will automatically use the new Vision node
- The upscaler node is deprecated but kept in backend for existing workflows
- Camera angle node was never implemented, so no migration needed
