# Agent loop. Calls Gemini with all tools, executes whatever tool it picks,
# feeds the result back, and repeats until Gemini returns plain text.

import json, time, base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from google.genai import types
from model import generate, get_history
from tools import TOOLS, execute_tool
import memory
import eval
import context
import policy


def _system_prompt(settings: dict, past_context: str) -> str:
    name = settings.get("llm name", "Swift")
    user = settings.get("user_first_name", "there")
    now = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

    prompt = (
        f"You are {name}, an AI voice assistant for macOS. "
        f"The user's name is {user}. "
        "Your responses will be read aloud, so keep them to 1-2 concise sentences. "
        "Use the available tools to fulfill requests. "
        "After a tool executes successfully, confirm what was done in one sentence. "
        "If you cannot fulfill a request, say so briefly. "
        f"Current date and time: {now}. "
        f"User settings: {json.dumps(settings)}"
    )
    if past_context:
        prompt += f"\n\n{past_context}"
    return prompt


def run(user_input: str, settings: dict) -> str:
    start = time.time()
    confirmation = policy.resolve_confirmation(user_input)
    if confirmation.get("matched"):
        if not confirmation.get("approved"):
            eval.log(user_input, "policy_confirmation", success=True, latency_ms=int((time.time()-start)*1000))
            return confirmation["message"]
        tool_used = confirmation["name"]
        tool_result = execute_tool(tool_used, confirmation["args"])
        eval.log(
            user_input,
            tool_used,
            success=tool_result["success"],
            latency_ms=int((time.time()-start)*1000),
            error=tool_result["message"] if not tool_result["success"] else None,
        )
        return tool_result["message"]

    # context enrichment and RAG retrieval run in parallel
    with ThreadPoolExecutor(max_workers=2) as ex:
        ctx_future = ex.submit(context.build_context, user_input)
        rag_future = ex.submit(memory.load_context, user_input)

    augmented_input, screenshot = ctx_future.result()
    past_context = rag_future.result()
    system_prompt = _system_prompt(settings, past_context)
    tool_used = None

    contents = []
    for entry in get_history():
        contents.append(types.Content(
            role=entry["role"],
            parts=[types.Part.from_text(text=entry["content"])]
        ))

    # Build the user turn — attach screenshot as image if present
    user_parts = [types.Part.from_text(text=augmented_input)]
    if screenshot:
        user_parts.append(types.Part.from_bytes(
            data=base64.b64decode(screenshot),
            mime_type="image/png"
        ))
    contents.append(types.Content(role="user", parts=user_parts))

    try:
        for _ in range(5):
            response = generate(contents, tools=TOOLS, system_instruction=system_prompt)
            candidate = response.candidates[0]

            function_calls = []
            text_parts = []
            for part in candidate.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    function_calls.append(part.function_call)
                elif hasattr(part, "text") and part.text:
                    text_parts.append(part.text)

            if not function_calls:
                result = "".join(text_parts).strip()
                eval.log(user_input, tool_used or "llm", success=True, latency_ms=int((time.time()-start)*1000))
                return result

            contents.append(candidate.content)

            result_parts = []
            for fc in function_calls:
                args = dict(fc.args)
                tool_used = fc.name
                print(f"[Tool] {fc.name}({args})")
                policy_result = policy.check_policy(fc.name, args)
                if policy_result["decision"] == "allow":
                    tool_result = execute_tool(fc.name, args)
                else:
                    tool_result = {"success": False, "message": policy_result["message"]}
                print(f"[Tool] → {tool_result}")
                eval.log(
                    user_input, fc.name,
                    success=tool_result["success"],
                    latency_ms=int((time.time() - start) * 1000),
                    error=tool_result["message"] if not tool_result["success"] else None,
                )
                result_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": tool_result["message"]},
                        )
                    )
                )

            contents.append(types.Content(role="user", parts=result_parts))

    except Exception as e:
        eval.log(user_input, tool_used or "llm", success=False, latency_ms=int((time.time()-start)*1000), error=str(e))
        raise

    eval.log(user_input, tool_used or "llm", success=False, latency_ms=int((time.time()-start)*1000), error="max iterations reached")
    return "I wasn't able to complete that request."
