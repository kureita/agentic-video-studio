
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
This thinking field should describe:
1. What the user is asking for
2. What approach you'll take (brainstorm vs generate)
3. Key decisions (aspect ratio, scene count, character refs needed, etc.)
4. Any tools/capabilities you're using (e.g. search_web if you needed real-time info)

# Output Format (JSON only):
{{
    "thinking": "Your reasoning and planning here...",
    "tool_calls": [
        {{"name": "search_web", "args": {{"query": "latest AI news"}}, "result": "Search results snippet..."}}
    ],
    "message": "Response to user",
    "nodes": [ ... ],
    "edges": [ ... ]
}}
"""
        
        try:
            start_time = time.time()
            
            response_text = ""
            
            if "Gemini" in model:
                # Map frontend string to actual model string
                mapped_model = 'gemini-3.1-pro' if '(High)' in model else 'gemini-3-flash' if '(Medium)' in model else 'gemini-2.5-flash-lite'
                
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
                    max_tokens=4096,
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
                        max_tokens=4096,
                        messages=messages,
                        tools=tools
                    )

                # Extract the text content from Anthropic's response blocks
                response_text = ""
                for block in response.content:
                    if block.type == 'text':
                        response_text += block.text
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            if not response_text:
                return {"success": False, "message": "Empty response from AI", "thinking": None, "thinking_duration_ms": None, "tool_calls": []}

            # If anthropic includes markdown tags by accident, strip them
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # ── Robust JSON repair ──────────────────────────────────────
            import re

            def _repair_json(text: str) -> str:
                """Fix common LLM JSON issues that cause 'Unterminated string' errors."""
                # 1. Replace literal (unescaped) newlines/tabs inside JSON string values.
                #    Walk through char-by-char tracking whether we're inside a string.
                out = []
                in_string = False
                i = 0
                while i < len(text):
                    ch = text[i]
                    if ch == '\\' and in_string:
                        # Escaped character — keep as-is and skip next char
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

                # 2. Remove trailing commas before ] or }
                text = re.sub(r',\s*([\]}])', r'\1', text)

                # 3. If the JSON was truncated (common with long outputs), try to close it
                open_braces = text.count('{') - text.count('}')
                open_brackets = text.count('[') - text.count(']')
                if open_brackets > 0 or open_braces > 0:
                    text = text.rstrip().rstrip(',')
                    text += ']' * max(0, open_brackets)
                    text += '}' * max(0, open_braces)

                return text

            response_text = _repair_json(response_text)

            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as parse_err:
                print(f"[AgentService] JSON parse error after repair: {parse_err}")
                print(f"[AgentService] Response text (first 500 chars): {response_text[:500]}")
                # Last-resort: try to extract nodes/edges arrays with regex
                nodes_match = re.search(r'"nodes"\s*:\s*(\[[\s\S]*?\])\s*[,}]', response_text)
                edges_match = re.search(r'"edges"\s*:\s*(\[[\s\S]*?\])\s*[,}]', response_text)
                result = {
                    "thinking": "JSON repair failed — extracted partial data",
                    "message": "Workflow generated (recovered from partial response)",
                    "nodes": json.loads(nodes_match.group(1)) if nodes_match else [],
                    "edges": json.loads(edges_match.group(1)) if edges_match else [],
                    "tool_calls": []
                }
            
            # Extract thinking and tool_calls from the response
            thinking = result.get("thinking", None)
            tool_calls = result.get("tool_calls", [])
            
            # Sanitize tool_calls to ensure proper format
            sanitized_tool_calls = []
            for tc in tool_calls:
                sanitized_tool_calls.append({
                    "name": tc.get("name", "unknown"),
                    "status": "completed",
                    "args": tc.get("args", {}),
                    "result": tc.get("result", None)
                })
            
            return {
                "success": True,
                "message": result.get("message", "Workflow generated"),
                "thinking": thinking,
                "thinking_duration_ms": elapsed_ms,
                "tool_calls": sanitized_tool_calls,
                "nodes": result.get("nodes", []),
                "edges": result.get("edges", [])
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
