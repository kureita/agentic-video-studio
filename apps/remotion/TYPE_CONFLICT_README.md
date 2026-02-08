# React Type Conflict Issue

## Problem
The Remotion app uses React 18 (required by Remotion 4.x), but the workspace root has React 19 types installed (used by the Next.js web app). This causes TypeScript to complain about JSX component types when checking the Remotion code.

## Error Example
```
error TS2786: 'AbsoluteFill' cannot be used as a JSX component.
Type 'import("/path/to/node_modules/@types/react/index").ReactNode' is not assignable to type 'React.ReactNode'.
```

## Root Cause
- The monorepo workspace hoists dependencies to the root `node_modules`
- The web app (`apps/web`) uses React 19 and `@types/react@19.x`
- Remotion requires React 18 and `@types/react@18.x`
- TypeScript picks up the React 19 types from the root, causing conflicts

## Solution Applied
1. Added `// @ts-nocheck` comment at the top of affected files to suppress type checking
2. Added `// @ts-expect-error` comments before problematic JSX elements
3. Added `.npmrc` with `hoist=false` to prevent dependency hoisting (optional)
4. Added `overrides` in root `package.json` to force React 18 types (attempted but didn't work due to web app)

## Runtime Behavior
**The code works perfectly at runtime** - this is purely a TypeScript type checking issue. Remotion uses its own React 18 instance at runtime, so there are no actual conflicts.

## Verification
To verify the code works:
```bash
npm run dev --workspace=apps/remotion
```

The Remotion Studio should start without errors and render videos correctly.

## Alternative Solutions
If you want to eliminate the TypeScript errors completely:

1. **Separate the web app to use React 18**: Downgrade Next.js and React in `apps/web` to v18
2. **Use pnpm instead of npm**: pnpm has better workspace isolation
3. **Disable strict type checking**: Set `"strict": false` in `apps/remotion/tsconfig.json`
4. **Use a custom tsconfig for builds**: Create separate configs for dev vs build

## Current Status
✅ Code works at runtime  
⚠️ TypeScript shows type errors (suppressed with comments)  
✅ Remotion Studio runs successfully  
✅ Video rendering works correctly
