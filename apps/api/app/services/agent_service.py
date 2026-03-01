
import json
import os
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.firecrawl_service import FirecrawlService

class AgentService:
    def __init__(self):
        self.google_api_key = settings.google_ai_key
        self.openai_api_key = settings.openai_api_key
        self.anthropic_api_key = settings.anthropic_api_key
        
        self.google_client = None
        if self.google_api_key:
            os.environ["GEMINI_API_KEY"] = self.google_api_key
            self.google_client = genai.Client()
            
        self.openai_client = None
        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            
        self.anthropic_client = None
        if self.anthropic_api_key:
            self.anthropic_client = AsyncAnthropic(api_key=self.anthropic_api_key)
            
        self.firecrawl_service = FirecrawlService()
            
    async def generate_workflow(self, prompt: str, model: str = "Gemini 2.5 Flash", current_nodes: List[Dict] = [], current_edges: List[Dict] = [], chat_history: List[Dict] = []) -> Dict[str, Any]:
        """
        Generate a workflow based on a user prompt using the selected model.
        """
        # Define default API failure response
        failure_response = {
            "success": False,
            "message": "The selected model's API key is not configured.",
            "thinking": None,
            "thinking_duration_ms": None,
            "tool_calls": [],
            "nodes": [],
            "edges": []
        }
        
        # Verify Key Availability
        if "Gemini" in model and not self.google_client:
             return failure_response
        if "GPT" in model and not self.openai_client:
             return failure_response
        if "Claude" in model and not self.anthropic_client:
             return failure_response

        start_prompt = f"""
You are an expert AI Video Agent that builds workflows for a visual node-based video generation studio.
The user describes a video they want to create, and you generate nodes and edges for a workflow editor.

# Available Node Types and Their Handles:

1. **text** - Text prompt node for writing prompts/scripts
   - Outputs: "text|text" (type: text)
   - Data: {{ "label": "Scene X Prompt", "text": "The actual prompt text here" }}

2. **imageGen** - Image Generator (Imagen 4)
   - Inputs: "text|prompt" (type: text), "image|image" (type: image, optional reference)
   - Outputs: "image|image" (type: image)
   - Data: {{ "label": "Start Frame Scene X", "prompt": "Description", "width": 1024, "height": 576, "ratio": "16:9", "model": "Imagen 4" }}

3. **videoGen** - Video Generator (Multiple models via Runware)
   - Inputs: "text|text" (type: text), "image|start_image" (type: image), "image|end_image" (type: image, optional)
   - Outputs: "video|video" (type: video), "image|start_frame" (type: image, first frame), "image|end_frame" (type: image, last frame)
   - Data: {{ "label": "Video Scene X", "prompt": "Motion description", "duration": "5s", "ratio": "16:9", "model": "Kling 3.0 Standard" }}
   - **Available Models**: "Veo 3.1", "Veo 3.1 Fast", "Veo 3", "Veo 3 Fast", "Veo 2", "Kling 3.0 Standard", "Kling 3.0 Pro", "Kling 2.1 Master", "Kling Lip Sync", "Runway Gen-4.5", "Runway Gen-4 Turbo", "Seedance 1.5 Pro", "Seedance 1.0 Pro", "Seedance 1.0 Pro Fast", "Seedance 1.0 Lite", "Wan2.6", "Wan2.6 Flash", "Hailuo 2.3", "Hailuo 2.3 Fast", "PixVerse V5.6"
   - **Duration Constraints**: Veo 3/3.1 variants: "8s" only. Veo 2: "5s"-"8s". Kling: "5s"/"10s". Runway Gen-4.5: "5s"/"8s"/"10s". Runway Gen-4 Turbo: "2s"-"10s". Seedance: "4s"-"12s". Wan2.6: "5s"/"10s"/"15s". Wan2.6 Flash: "3s"/"5s"/"10s". Hailuo: "6s"/"10s". PixVerse: "5s"/"8s"/"10s".

4. **editorAgent** - AI Editor (Stitches videos)
   - Inputs: "text|text", "video|ref_videos" (Multiple)
   - Outputs: "video|output"
   - Data: {{ "label": "Editor", "instruction": "Stitching instructions. NOTE: Use this ONLY for basic video stitching and simple motion graphics. NOT for creative generation." }}

6. **mediaUpload** - Asset Upload (User Files)
   - Outputs: "image|output" OR "video|output"
   - Data: {{ "label": "Upload [Name]", "mediaType": "image" or "video", "output": "URL_IF_KNOWN" }}

# CORE RULES (MUST FOLLOW STRICTLY):

## 1. BRAINSTORM FIRST (Decision Gate)
**Check**: Is the user's request a high-level concept (e.g., "Make a coffee ad", "Funny cat video")?
- **IF YES**:
  - Return `nodes: []`, `edges: []`.
  - **Message**: "I can help with that! Let's agree on a script first. How about [Brief Idea]? Or do you have a specific scene in mind?"
  - **STOP HERE.** Do not generate nodes.
- **IF NO** (Request is specific/confirmed, e.g., "Use that script", "Scene 1 is..."):
  - Proceed to generate workflow.

## 2. CHARACTER & ASSET FIRST (Consistency)
**Check**: Does the video involve a repeating character, person, or specific setting?
- **IF YES**:
  - **Rule**: You MUST create `imageGen` nodes for these assets **at the very beginning** (Sequence 0).
  - **Label**: "Character Reference" or "Background Reference".
  - **Action**: Connect these nodes to the `image|start_image` or `image|image` (reference) inputs of your Scene nodes.
  - **Never** just generate "a person" in every scene independently. Use the reference!

## 3. ASPECT RATIO & DIMENSIONS (GLOBAL RULE)
**CRITICAL:** You must determine the **Primary Aspect Ratio** for the entire video first.
- **Video Ads / Default**: 16:9
- **Social (TikTok/Shorts)**: 9:16
- **Square**: 1:1

**ALL** nodes in the workflow MUST follow this ratio.
- **IF 16:9**:
  - ALL `videoGen` nodes: `"ratio": "16:9"`
  - ALL `imageGen` nodes: `"width": 1024, "height": 576`, `"ratio": "16:9"` (NEVER 1024x1024!)
- **IF 9:16**:
  - ALL `videoGen` nodes: `"ratio": "9:16"`
  - ALL `imageGen` nodes: `"width": 576, "height": 1024`, `"ratio": "9:16"`
- **IF 1:1**:
  - ALL `videoGen` nodes: `"ratio": "1:1"`
  - ALL `imageGen` nodes: `"width": 1024, "height": 1024`, `"ratio": "1:1"`

**STRICT FORBIDDEN ACTION**:
- Do **NOT** create 1:1 (Square) images for a 16:9 or 9:16 video.
- All Character References, Backgrounds, and Start/End frames MUST match the video dimensions exactly.

## 4. TEXT NODE REFERENCING (CRITICAL)
When a **text** node is connected to a generator node (imageGen, videoGen, editorAgent, vision, audioGen),
the generator node's prompt/instruction field MUST reference the connected text node using the `@Text #N` syntax.

**How it works:**
- Text nodes are numbered sequentially: Text #1, Text #2, Text #3, etc. (based on their order in the nodes array).
- When you connect a text node to a generator node AND want that generator to use the text content, put `@Text #N` in the generator's prompt/instruction field.
- At runtime, `@Text #N` gets replaced with the actual text content from the referenced text node.

**Example:**
- You create a text node (Text #1) with content "A golden retriever playing in a field of sunflowers"
- You connect it to an imageGen node
- The imageGen node's `prompt` field should be: `"@Text #1"` (or `"@Text #1, cinematic lighting"` if you want to add extra details)
- You connect the same text node to a videoGen node
- The videoGen node's `prompt` field should be: `"@Text #1"`

**Rules:**
- If a text node is connected to a generator node, ALWAYS use `@Text #N` in the prompt/instruction.
- Do NOT duplicate the text content directly in the generator's prompt field if a text node is connected.
- The `@Text #N` number corresponds to the text node's position among ALL text nodes (1-indexed).
  - If you create 3 text nodes, they are Text #1, Text #2, Text #3 (in the order they appear in the nodes array).
- For `editorAgent` nodes, use `@Text #N` in the `instruction` field.
- For `imageGen`, `videoGen`, and `audioGen` nodes, use `@Text #N` in the `prompt` field.

## 5. PROACTIVE WEB SEARCH (MANDATORY)
**RULE: If the user mentions ANY website URL or domain name (e.g., "regulify.ai", "example.com", https://...), you MUST call the `search_web` tool IMMEDIATELY to fetch and read its content. Do NOT ask the user for permission. Do NOT skip this step.**
- **Query format**: Pass ONLY the bare domain or URL as the query — e.g., `"regulify.ai"` or `"https://regulify.ai"`. Do NOT add `site:` operators, `OR`, or any other modifiers. The backend handles scraping automatically.
- Use the scraped content (brand, tagline, features, visuals) to ground your response in real, accurate information.
- After fetching, summarize what you found in your `thinking` field, and reference it in your `message`.
- Similarly, if the user asks about current events, news, or time-sensitive data, call `search_web` with a clear, concise query.

## 6. LAYOUT GRID (Prevent Overlap)
You must use a strict GRID coordinate system based on ROW and COLUMN indices.
- **Horizontal Grid Unit (X spacing)**: 700px between columns.
- **Vertical Grid Unit (Y spacing)**: 600px between rows.
- **Node Width**: Nodes can be up to ~580px wide (16:9 imageGen/videoGen). **Minimum gap**: 120px.

**Algorithm**:
1. Assign each **Scene** or **Logical Step** to a unique `Row Index` (0, 1, 2...).
2. Assign each **Node** within that step to a unique `Column Index` (0, 1, 2...).
3. Calculate: `x = col_index * 700`, `y = row_index * 600`.

**Standard Layout Map**:
- **Row 0 (Assets)**: Character Refs, Backgrounds. (x=0, x=700, x=1400...)
- **Row 1 (Scene 1)**: Text (x=0) -> Start Image (x=700) -> Video (x=1400)
- **Row 2 (Scene 2)**: Text (x=0) -> Start Image (x=700) -> Video (x=1400)
- ...
- **Row N (Final)**: Editor / Compilation Node.

**CRITICAL**:
- **NEVER** output two nodes with the same (x, y).
- **ALWAYS** increment `row_index` for a new scene.
- **ALWAYS** increment `col_index` for the next node in a sequence.
- **NEVER** use gaps smaller than 700px for X or 600px for Y.

# Current Workflow State:
Nodes: {json.dumps(current_nodes)}
Edges: {json.dumps(current_edges)}

# Chat History:
{json.dumps(chat_history)}

# User Request:
"{prompt}"

# IMPORTANT: Your response MUST include a "thinking" field that contains your reasoning/plan BEFORE generating the workflow.
CRITICAL Token Limit Constraint: KEEP YOUR `thinking` AND `message` FIELDS EXTREMELY CONCISE (max 3-4 short sentences). Do NOT write out every node's prompt, plan, or position in the thinking field. You must save your output tokens for the actual JSON nodes/edges!

This thinking field should briefly describe:
1. What the user is asking for
2. What approach you'll take
3. Key decisions (aspect ratio, scene count, references)

# Output Format (JSON only):
{{
    "thinking": "Your reasoning and planning here...",
    "tool_calls": [
        {{"name": "search_web", "args": {{"query": "latest AI news"}}, "result": "Search results snippet..."}}
    ],
    "message": "Response to user",
    "action": "replace_all OR update",
    "nodes": [ {{ "id": "n1", "type": "text", "position": {{ "x": 0, "y": 0 }}, "data": {{ "text": "Hello" }} }} ], 
    "edges": [ {{ "id": "e1", "source": "n1", "target": "n2", "sourceHandle": "text|text", "targetHandle": "text|prompt" }} ],
    "updates": {{
        "add_nodes": [ ... ],
        "update_nodes": [ {{ "id": "node-to-update", "data": {{ "prompt": "new text" }} }} ],
        "delete_nodes": [ "node-id-to-delete" ],
        "add_edges": [ {{ "id": "e2", "source": "n3", "target": "n4", "sourceHandle": "image|image", "targetHandle": "image|start_image" }} ],
        "delete_edges": [ "edge-id-to-delete" ]
    }}
}}
Note: If `action` is "update", you ONLY need to return the `updates` object. Leave `nodes` and `edges` empty. Use this for small fixes to save time and tokens! If it's a completely new workflow, use "replace_all" and fill out `nodes` and `edges`.

"""
        
        try:
            start_time = time.time()
            
            token_usage = {"input": 0, "output": 0}
            
            if "Gemini" in model:
                # Map frontend string to actual valid genai model string
                mapped_model = 'gemini-3.1-pro-preview' if '(High)' in model else 'gemini-3-pro-preview' if '(Medium)' in model else 'gemini-3-flash-preview'
                
                # Gemini native tool calling requires a python function reference
                async def search_web(query: str) -> str:
                    """Searches the web for current information, news, or facts to help answer user queries or build context."""
                    return await self.firecrawl_service.search_web(query)

                # First pass - might just return text, or might return a function call
                response = self.google_client.models.generate_content(
                    model=mapped_model,
                    contents=start_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type='application/json',
                        max_output_tokens=65536,
                        tools=[search_web]
                    )
                )

                # Check if Gemini actually decided to call the tool
                if response.function_calls:
                    for function_call in response.function_calls:
                        if function_call.name == "search_web":
                            query = function_call.args.get("query")
                            print(f"[Gemini] Executing Tool Call: search_web(query='{query}')")
                            
                            # Execute the search
                            search_result = await self.firecrawl_service.search_web(query)
                            
                            # Second pass - send the result back to Gemini
                            # Constructing the expected structure for Gemini's function response
                            function_response_part = types.Part.from_function_response(
                                name="search_web",
                                response={"result": search_result}
                            )
                            
                            response = self.google_client.models.generate_content(
                                model=mapped_model,
                                contents=[
                                    start_prompt,
                                    types.Part.from_function_call(name="search_web", args={"query": query}),
                                    function_response_part
                                ],
                                config=types.GenerateContentConfig(
                                    response_mime_type='application/json',
                                    max_output_tokens=65536,
                                    tools=[search_web]
                                )
                            )
                
                if hasattr(response, 'usage_metadata') and response.usage_metadata:
                    token_usage["input"] += getattr(response.usage_metadata, 'prompt_token_count', 0)
                    token_usage["output"] += getattr(response.usage_metadata, 'candidates_token_count', 0)
                
                response_text = response.text
                
            elif "GPT" in model:
                # Map frontend string to actual model string
                mapped_model = 'gpt-5.2-pro' if '(High)' in model else 'gpt-5-mini' if '(Medium)' in model else 'gpt-4.1-nano'
                
                tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": "search_web",
                            "description": "Searches the web for current information, news, or facts to help answer user queries or build context.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "The search query to look up on the internet."
                                    }
                                },
                                "required": ["query"]
                            }
                        }
                    }
                ]

                messages = [
                    {"role": "system", "content": "You must respond with valid JSON only."},
                    {"role": "user", "content": start_prompt}
                ]
                
                response = await self.openai_client.chat.completions.create(
                    model=mapped_model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    tools=tools
                )
                
                # Check for tool call
                response_message = response.choices[0].message
                if response_message.tool_calls:
                    messages.append(response_message)
                    
                    for tool_call in response_message.tool_calls:
                        if tool_call.function.name == "search_web":
                            args = json.loads(tool_call.function.arguments)
                            query = args.get("query")
                            print(f"[OpenAI] Executing Tool Call: search_web(query='{query}')")
                            
                            # Execute search
                            search_result = await self.firecrawl_service.search_web(query)
                            
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": "search_web",
                                "content": search_result
                            })
                            
                    # Second pass
                    response = await self.openai_client.chat.completions.create(
                        model=mapped_model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        tools=tools
                    )
                
                if hasattr(response, 'usage') and response.usage:
                    token_usage["input"] += getattr(response.usage, 'prompt_tokens', 0)
                    token_usage["output"] += getattr(response.usage, 'completion_tokens', 0)
                
                response_text = response.choices[0].message.content
                
            elif "Claude" in model:
                # Map frontend string to actual model string
                mapped_model = 'claude-opus-4-6' if '(High)' in model else 'claude-sonnet-4-6' if '(Medium)' in model else 'claude-haiku-4-5'
                
                # Claude doesn't have native JSON mode in this endpoint format but strictly follows instructions
                claude_prompt = start_prompt + "\n\nCRITICAL: You must return ONLY the raw JSON object. Do not wrap it in markdown block quotes (```json...```). Return just the JSON structure starting with {"
                
                tools = [
                    {
                        "name": "search_web",
                        "description": "Searches the web for current information, news, or facts.",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query to look up on the internet."
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ]
                
                messages = [{"role": "user", "content": claude_prompt}]
                
                response = await self.anthropic_client.messages.create(
                    model=mapped_model,
                    max_tokens=8192,
                    messages=messages,
                    tools=tools
                )
                
                if response.stop_reason == "tool_use":
                    # Append assistant's tool use message to history
                    messages.append({"role": "assistant", "content": response.content})
                    
                    tool_results = []
                    for content_block in response.content:
                        if content_block.type == "tool_use" and content_block.name == "search_web":
                            query = content_block.input["query"]
                            print(f"[Claude] Executing Tool Call: search_web(query='{query}')")
                            
                            search_result = await self.firecrawl_service.search_web(query)
                            
                            # Provide the tool result
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": content_block.id,
                                "content": search_result
                            })
                    
                    # Add results to messages
                    messages.append({"role": "user", "content": tool_results})
                    
                    # Ping claude again for final answer
                    response = await self.anthropic_client.messages.create(
                        model=mapped_model,
                        max_tokens=8192,
                        messages=messages,
                        tools=tools
                    )

                # Extract the text content from Anthropic's response blocks
                response_text = ""
                for block in response.content:
                    if block.type == 'text':
                        response_text += block.text
                        
                if hasattr(response, 'usage') and response.usage:
                    token_usage["input"] += getattr(response.usage, 'input_tokens', 0)
                    token_usage["output"] += getattr(response.usage, 'output_tokens', 0)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # --- DEBUG LOGS ADDED FOR USER ---
            print("\n" + "="*80)
            print(f"[DEBUG] MODEL USED: {model}")
            print("[DEBUG] RAW AI RESPONSE TEXT ALMOST EXACTLY AS RECEIVED:")
            print("-" * 40)
            print(response_text)
            print("-" * 40)
            print("="*80 + "\n")
            # ---------------------------------

            if not response_text:
                return {"success": False, "message": "Empty response from AI", "thinking": None, "thinking_duration_ms": None, "tool_calls": []}

            # ── Clean up response text ──────────────────────────────────────
            # Extract JSON block if it's wrapped in markdown or conversational text
            response_text = response_text.strip()
            import re
            markdown_match = re.search(r'```(?:json)?(.*?)```', response_text, re.DOTALL)
            if markdown_match:
                response_text = markdown_match.group(1).strip()
                print("\n[DEBUG] Extracted JSON via Markdown block match.")
            else:
                # If no markdown block, try to find the outermost JSON object
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    response_text = json_match.group(0)
                    print("\n[DEBUG] Extracted JSON via JSON bracket Match.")
            
            print("\n[DEBUG] EXTRACTED TEXT (Before Repair):")
            print(response_text)
            print("="*80 + "\n")
            
            # ── Robust JSON repair ──────────────────────────────────────
            def _repair_json(text: str) -> str:
                """Fix common LLM JSON issues that cause decoding errors."""
                out = []
                in_string = False
                i = 0
                while i < len(text):
                    ch = text[i]
                    if ch == '\\' and in_string:
                        out.append(ch)
                        if i + 1 < len(text):
                            out.append(text[i + 1])
                        i += 2
                        continue
                    if ch == '"':
                        in_string = not in_string
                        out.append(ch)
                    elif in_string and ch == '\n':
                        out.append('\\n')
                    elif in_string and ch == '\r':
                        out.append('\\r')
                    elif in_string and ch == '\t':
                        out.append('\\t')
                    else:
                        out.append(ch)
                    i += 1
                text = ''.join(out)

                # Remove trailing commas before ] or }
                text = re.sub(r',\s*([\]}])', r'\1', text)
                
                # Close potentially truncated JSON without breaking strings
                in_str = False
                esc = False
                stack = []
                for char in text:
                    if esc:
                        esc = False
                        continue
                    if char == '\\':
                        esc = True
                        continue
                    if char == '"':
                        in_str = not in_str
                    elif not in_str:
                        if char == '{':
                            stack.append('}')
                        elif char == '[':
                            stack.append(']')
                        elif char == '}' and stack and stack[-1] == '}':
                            stack.pop()
                        elif char == ']' and stack and stack[-1] == ']':
                            stack.pop()
                            
                text = text.rstrip().rstrip(',')
                if in_str:
                    text += '"'  # Close any unclosed string
                
                while stack:
                    text += stack.pop()

                return text

            response_text = _repair_json(response_text)

            print("\n[DEBUG] FINAL REPAIRED JSON:")
            print(response_text)
            print("="*80 + "\n")

            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as parse_err:
                print(f"[AgentService] JSON parse error after repair: {parse_err}")
                print(f"[AgentService] Response text (first 500 chars): {response_text[:500]}")
                
                # Last-resort fallback with more robust regex that handles nested brackets better
                nodes = []
                edges = []
                try:
                    # Look for nodes array more safely
                    nodes_match = re.search(r'"nodes"\s*:\s*(\[(?:[^\[\]]|\[[^\[\]]*\])*\])', response_text)
                    if nodes_match:
                        nodes = json.loads(nodes_match.group(1))
                        
                    edges_match = re.search(r'"edges"\s*:\s*(\[(?:[^\[\]]|\[[^\[\]]*\])*\])', response_text)
                    if edges_match:
                        edges = json.loads(edges_match.group(1))
                except Exception as inner_err:
                    print(f"[AgentService] Fallback regex extraction failed: {inner_err}")
                    
                result = {
                    "thinking": "JSON repair failed — extracted partial data",
                    "message": "Workflow generated (recovered from partial response)",
                    "nodes": nodes,
                    "edges": edges,
                    "tool_calls": []
                }
            
            # Extract thinking and tool_calls from the response
            thinking = result.get("thinking", None)
            tool_calls = result.get("tool_calls", [])
            action = result.get("action", "replace_all")
            
            # Sanitize tool_calls to ensure proper format
            sanitized_tool_calls = []
            for tc in tool_calls:
                sanitized_tool_calls.append({
                    "name": tc.get("name", "unknown"),
                    "status": "completed",
                    "args": tc.get("args", {}),
                    "result": tc.get("result", None)
                })
                
            # Process partial updates vs full replace
            if action == "update" and "updates" in result:
                final_nodes = {n["id"]: n for n in current_nodes}
                final_edges = {e["id"]: e for e in current_edges}
                
                updates = result["updates"]
                
                for n in updates.get("add_nodes", []):
                    final_nodes[n["id"]] = n
                
                for update in updates.get("update_nodes", []):
                    nid = update.get("id")
                    if nid in final_nodes:
                        if "data" in update:
                            for key, val in update["data"].items():
                                final_nodes[nid]["data"][key] = val
                        if "position" in update:
                            final_nodes[nid]["position"] = update["position"]
                        if "type" in update:
                            final_nodes[nid]["type"] = update["type"]
                            
                for nid in updates.get("delete_nodes", []):
                    if nid in final_nodes:
                        del final_nodes[nid]
                        
                for e in updates.get("add_edges", []):
                    # Enforce camelCase for React Flow
                    if "source_handle" in e:
                        e["sourceHandle"] = e.pop("source_handle")
                    if "target_handle" in e:
                        e["targetHandle"] = e.pop("target_handle")
                    final_edges[e["id"]] = e
                    
                for eid in updates.get("delete_edges", []):
                    if eid in final_edges:
                        del final_edges[eid]
                        
                result_nodes = list(final_nodes.values())
                result_edges = list(final_edges.values())
            else:
                result_nodes = result.get("nodes", [])
                result_edges = result.get("edges", [])
                
                # Enforce camelCase for all edges in replace_all
                for e in result_edges:
                    if "source_handle" in e:
                        e["sourceHandle"] = e.pop("source_handle")
                    if "target_handle" in e:
                        e["targetHandle"] = e.pop("target_handle")
            
            return {
                "success": True,
                "message": result.get("message", "Workflow generated"),
                "thinking": thinking,
                "thinking_duration_ms": elapsed_ms,
                "tool_calls": sanitized_tool_calls,
                "nodes": result_nodes,
                "edges": result_edges,
                "token_usage": token_usage
            }
            
        except Exception as e:
            print(f"Error generating workflow: {e}")
            return {
                "success": False,
                "message": f"Error generating workflow: {str(e)}",
                "thinking": None,
                "thinking_duration_ms": None,
                "tool_calls": [],
                "nodes": [],
                "edges": []
            }
