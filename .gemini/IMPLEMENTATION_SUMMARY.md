# Implementation Summary: Recursive Node Execution & Reference Image Support

## Overview
This implementation addresses the user's request to:
1. Support reference images in image generation
2. Automatically run upstream dependencies when executing a node
3. Add a "Clear Output" option to generator nodes
4. Fix the 1:1 aspect ratio display issue

## Changes Made

### 1. Backend Changes

#### A. `apps/api/app/services/node_runner.py`
- **Modified `_run_image_gen_node`**: Now extracts `reference_image` from inputs and passes it to the image generator
- **Added validation**: Accepts either prompt or reference image (or both)
- **Default prompt**: If only image is provided, uses "Variation of this image" as prompt

#### B. `apps/api/app/services/image_generator.py`
- **Added `httpx` import** for fetching remote images
- **New method `_fetch_image`**: Asynchronously downloads image bytes from URL
- **Updated `generate_image`**: 
  - Accepts optional `reference_image` parameter
  - Fetches image bytes if provided
  - Constructs multimodal content for Gemini API (text + image)
  - Detects MIME type based on file extension

### 2. Frontend Store Changes

#### `apps/web/src/lib/workflow-store.ts`
- **Added `clearNodeOutput` action**: Removes output for a specific node
- **Completely rewrote `runNode`**: 
  - Implements recursive dependency checking
  - Automatically runs upstream nodes if they're missing outputs
  - Uses topological traversal with cycle detection
  - Maintains visited set to prevent infinite loops
  - Only re-runs nodes that are missing outputs (skips nodes with existing outputs)

**Algorithm**: 
```
runNode(nodeId):
  1. Save workflow first
  2. ensureDependencies(nodeId):
     - Find all upstream nodes via edges
     - For each dependency:
       - If output missing → recursively ensure ITS dependencies → run it
       - If output exists → skip (reuse existing output)
  3. Execute target node (always runs the explicitly requested node)
```

### 3. UI Component Changes

#### A. `apps/web/src/components/workflow/node-wrapper.tsx`
- **Added `Eraser` icon import** from lucide-react
- **New prop `onClear`**: Optional callback for clearing node output
- **New Clear button**: Renders amber-colored Eraser button in action bar when `onClear` is provided

#### B. `apps/web/src/components/workflow/nodes/image-gen-node.tsx`
- **Imported `useWorkflowStore`**
- **Switched to store state**: 
  - `isRunning = runningNodeId === id` (instead of `data.isRunning`)
  - `output = outputs[id]` (instead of `data.output`)
- **Connected actions**:
  - `onRun={() => runNode(id)}`
  - `onClear={output ? () => clearNodeOutput(id) : undefined}`
- **Updated `BASE_DIM` to 300px** (matches NodeWrapper min-width for proper 1:1 aspect ratio)

#### C. `apps/web/src/components/workflow/nodes/video-gen-node.tsx`
- **Same updates as ImageGenNode**
- Changed from `data.isRunning` and `data.output` to store state
- Added `onClear` handler
- Updated `BASE_DIM` to 300px

### 4. Bug Fixes

#### Aspect Ratio Display (1:1 ratio)
- **Root cause**: `BASE_DIM` was 280px but NodeWrapper enforces `min-width: 300px`
- **Solution**: Changed `BASE_DIM` to 300px in both ImageGenNode and VideoGenNode
- **Result**: 1:1 aspect ratio now renders as a perfect square (300x300px)

## How It Works

### Scenario 1: Reference Image Usage
```
TextNode("make beach") → ImageGenNode(A) → ImageGenNode(B)
                          (Frog with hat)   (uses A as reference)
```

**Before**: When running ImageGenNode(B), the reference image from A was ignored.

**After**: 
1. User clicks Run on ImageGenNode(B)
2. System checks: Does ImageGenNode(A) have output?
3. If NO: Automatically runs A first, waits for result
4. If YES: Skips A (reuses existing output)
5. Runs B with reference image from A's output
6. Backend fetches A's image, passes to Gemini as multimodal input

### Scenario 2: Clearing Outputs
**User Action**: Click the Eraser (🧹) button on any generator node

**Effect**:
1. Removes output from `useWorkflowStore.outputs[nodeId]`
2. Node displays "Waiting for input..." state
3. Next time a downstream node runs, this node will be re-executed

### Scenario 3: Deep Dependency Chain
```
Text → ImageGen(A) → ImageGen(B) → VideoGen(C)
```

**User clicks Run on VideoGen(C):**
1. Check B's output → Missing
2. Recursively check A's output → Missing
3. Recursively check Text's output → Missing
4. Execute Text
5. Execute A (with Text's output)
6. Execute B (with A's output as reference)
7. Execute C (with B's output as reference image)

## Testing Checklist

- [ ] **Test 1**: Generate image, use as reference for another image
  - Create TextNode → ImageGenNode(A) → ImageGenNode(B)
  - Connect text to A's prompt
  - Connect A's output to B's "Ref Image" input
  - Add text prompt to B
  - Click Run on B → Should auto-run A first if needed

- [ ] **Test 2**: Clear output functionality
  - Generate an image
  - Click Eraser button
  - Image should disappear
  - Node shows "Waiting for input..."

- [ ] **Test 3**: Aspect ratio display
  - Create ImageGenNode
  - Change ratio to 1:1
  - Node should be perfectly square (not rectangular)

- [ ] **Test 4**: Recursive execution prevention
  - Create workflow with existing outputs
  - Run downstream node
  - Upstream nodes with outputs should NOT re-run

- [ ] **Test 5**: Video generation with image reference
  - ImageGenNode → VideoGenNode
  - Connect image output to video's "Image" input
  - Run video node → Should use image as starting frame

## API Changes

No API endpoint changes. All modifications are internal to existing endpoints:
- `POST /api/workflow/{id}/nodes/{node_id}/run` - Now supports recursive execution
- Existing image generation service enhanced with multimodal support

## Known Limitations

1. **Cycle Detection**: If workflow has cycles, visited set prevents infinite recursion but doesn't warn user
2. **Progress Indication**: When auto-running multiple dependencies, only shows the currently executing node
3. **Error Propagation**: If a dependency fails, the entire chain stops (by design)
4. **State Sync**: Relies on store state rather than ReactFlow node data - ensure consistency

## Files Modified

**Backend (3 files)**:
- `apps/api/app/services/node_runner.py`
- `apps/api/app/services/image_generator.py`

**Frontend (4 files)**:
- `apps/web/src/lib/workflow-store.ts`
- `apps/web/src/components/workflow/node-wrapper.tsx`
- `apps/web/src/components/workflow/nodes/image-gen-node.tsx`
- `apps/web/src/components/workflow/nodes/video-gen-node.tsx`

## Next Steps

1. Test the workflow with the scenarios above
2. Verify backend logs show reference image fetching
3. Ensure Clear button appears when hovering over nodes with output
4. Check console for recursive execution logs (`[Workflow] Dependency X missing output. Recursively running...`)
