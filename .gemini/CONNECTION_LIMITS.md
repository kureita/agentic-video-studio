# Connection Limits for Video Generator Inputs

## Overview
Added validation to restrict the number of connections allowed to specific input handles on the Video Generator node.

## Connection Limits

### Single Connection Allowed (Max 1)
The following handles can only accept **ONE** connection at a time:
- ✅ `start_image` - First frame for video generation
- ✅ `end_image` - Last frame for interpolation
- ✅ `ref_video` / `reference_video` - Reference video input

**Behavior:**
- When attempting to connect a second edge to these handles, the connection will be **rejected**
- Visual feedback: The connection line won't snap to the handle
- Console log: `[FlowEditor] Connection rejected: {handleId} already has a connection`

### Multiple Connections Allowed
The following handles can accept **MULTIPLE** connections:
- ✅ `reference_images` - Style/asset reference images
- ✅ `text` - Text/prompt input (can aggregate multiple text sources)

## Implementation Details

### Location
`apps/web/src/components/workflow/flow-editor.tsx`

### How It Works

1. **Connection Validation** - The `isValidConnection` callback now checks:
   - Type compatibility (image → image, video → video, etc.)
   - Existing connections to the target handle
   - Whether the handle is in the `singleConnectionHandles` list

2. **Handle Identification** - Handles are identified by the second part of the handle ID:
   ```
   Format: "type|handleId"
   Example: "image|start_image"
             ↑       ↑
           type   handleId
   ```

3. **Edge Counting** - Before allowing a new connection:
   - Searches all existing edges for connections to the same target handle
   - If found and the handle only allows single connections → reject
   - Uses `connectionId` check to avoid counting the same edge during updates

### Code Snippet
```typescript
const singleConnectionHandles = ['ref_video', 'reference_video', 'start_image', 'end_image'];

if (targetHandleId && singleConnectionHandles.includes(targetHandleId)) {
    const connectionId = 'id' in connection ? connection.id : null;
    const existingConnection = edges.find(
        (edge) =>
            edge.target === connection.target &&
            edge.targetHandle?.split('|')[1] === targetHandleId &&
            edge.id !== connectionId
    );
    
    if (existingConnection) {
        return false; // Reject connection
    }
}
```

## User Experience

### Example Scenarios

**❌ Rejected Connection:**
```
ImageGen(A) → VideoGen(start_image)
ImageGen(B) → VideoGen(start_image)  ← REJECTED! Already connected
```

**✅ Allowed Connection:**
```
ImageGen(A) → VideoGen(reference_images)
ImageGen(B) → VideoGen(reference_images)  ← ALLOWED! Multiple refs OK
ImageGen(C) → VideoGen(reference_images)  ← ALLOWED!
```

**✅ Different Handles:**
```
ImageGen(A) → VideoGen(start_image)   ← ALLOWED
ImageGen(B) → VideoGen(end_image)     ← ALLOWED (different handle)
```

## Benefits

1. **Prevents Invalid Configurations**
   - Can't have multiple start images (doesn't make sense)
   - Can't have multiple end images (would create confusion)
   - Can't have multiple reference videos (API limitation)

2. **Clearer User Intent**
   - Forces users to be explicit about which image is start vs end
   - Makes the workflow graph easier to understand

3. **API Compatibility**
   - Veo API expects single start/end frames
   - Reference images API accepts arrays (multiple OK)

## Edge Cases Handled

- ✅ Reconnecting the same edge (updates allowed)
- ✅ Type checking still enforced (image → image only)
- ✅ Handles with no restrictions (text, reference_images)
- ✅ TypeScript safety ('id' in connection check)

## Testing Checklist

- [ ] Try connecting 2 images to `start_image` → Should reject 2nd
- [ ] Try connecting 2 images to `end_image` → Should reject 2nd
- [ ] Try connecting 2+ images to `reference_images` → Should allow all
- [ ] Delete a connection and reconnect → Should work
- [ ] Check console for rejection messages

## Files Modified

- ✅ `apps/web/src/components/workflow/flow-editor.tsx`

## Future Enhancements

Consider adding:
- Visual indication on handles showing max connection limit (e.g., badge "1" or "∞")
- Toast notification when connection is rejected
- Automatically remove old connection when dragging new one to single-connection handle
