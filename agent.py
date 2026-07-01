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
import clarification


def _system_prompt(settings: dict, past_context: str) -> str:
    name = settings.get("llm name", "Swift")
    user = settings.get("user_first_name", "there")
    now = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

    prompt = (
        f"You are {name}, an AI voice assistant for macOS. "
        f"The user's name is {user}. "
        "Your responses will be read aloud, so keep them to 1-2 concise sentences. "
        "Speak naturally and never use technical words such as 'query', 'tool', 'API', or 'parameter' in your replies. "
        "Use the available tools to fulfill requests. "
        "For any weather question, including current weather, forecasts, hourly weather, rain, temperature, or outdoor timing, use get_weather instead of web_search. "
        "Use web_search for current events, sports scores, news, or facts that may have changed recently. "
        "After web_search returns useful results, answer from those results instead of searching again unless the result is clearly irrelevant. "
        "For music requests, preserve the user's requested mood or genre exactly when possible; do not replace vague phrases like background music with study music unless the user asked for studying. "
        "When the user asks to find a recipe, article, page, product, or source they will likely want to view, "
        "call web_search with open_first_result=true so the best result opens in their browser. "
        "If required information is missing or the request is ambiguous, use ask_clarification instead of guessing. "
        "After a tool executes successfully, confirm what was done in one sentence. "
        "If you cannot fulfill a request, say so briefly. "
        f"Current date and time: {now}. "
        f"User settings: {json.dumps(settings)}"
    )
    if past_context:
        prompt += f"\n\n{past_context}"
    return prompt


def run(user_input: str, settings: dict) -> tuple[str, bool]:
    # Returns (response_text, done). done=False means the assistant is waiting on
    # the user (a clarification or a confirmation) and the session should continue.
    start = time.time()
    clarified = clarification.resolve(user_input)
    if clarified.get("matched"):
        if not clarified.get("resolved"):
            eval.log(user_input, "clarification", success=False, latency_ms=int((time.time()-start)*1000), error=clarified["message"])
            return clarified["message"], False
        if clarified.get("action_name"):
            tool_used = clarified["action_name"]
            args = clarified["args"]
            policy_result = policy.check_policy(tool_used, args)
            if policy_result["decision"] == "allow":
                tool_result = execute_tool(tool_used, args)
                eval.log(
                    user_input,
                    tool_used,
                    success=tool_result["success"],
                    latency_ms=int((time.time()-start)*1000),
                    error=tool_result["message"] if not tool_result["success"] else None,
                )
                return tool_result["message"], True
            if policy_result["decision"] == "confirm":
                eval.log(
                    user_input,
                    tool_used,
                    success=False,
                    latency_ms=int((time.time()-start)*1000),
                    error=policy_result["message"],
                )
                return policy_result["message"], False
            if policy_result["decision"] == "block":
                eval.log(
                    user_input,
                    tool_used,
                    success=False,
                    latency_ms=int((time.time()-start)*1000),
                    error=policy_result["message"],
                )
                return policy_result["message"], True
            if policy_result["decision"] == "clarify":
                clarification.ask_tool(tool_used, args, policy_result["message"])
                eval.log(
                    user_input,
                    tool_used,
                    success=False,
                    latency_ms=int((time.time()-start)*1000),
                    error=policy_result["message"],
                )
                return policy_result["message"], False
        user_input = f"{user_input}\n{clarified['message']}"

    confirmation = policy.resolve_confirmation(user_input)
    if confirmation.get("matched"):
        if not confirmation.get("approved"):
            eval.log(user_input, "policy_confirmation", success=True, latency_ms=int((time.time()-start)*1000))
            return confirmation["message"], True
        tool_used = confirmation["name"]
        tool_result = execute_tool(tool_used, confirmation["args"])
        eval.log(
            user_input,
            tool_used,
            success=tool_result["success"],
            latency_ms=int((time.time()-start)*1000),
            error=tool_result["message"] if not tool_result["success"] else None,
        )
        return tool_result["message"], True

    # context enrichment and RAG retrieval run in parallel
    with ThreadPoolExecutor(max_workers=2) as ex:
        ctx_future = ex.submit(context.build_context, user_input)
        rag_future = ex.submit(memory.load_context, user_input)

    augmented_input, screenshot = ctx_future.result()
    past_context = rag_future.result()
    system_prompt = _system_prompt(settings, past_context)
    tool_used = None

    history = get_history()
    if history and history[-1].get("role") == "user" and history[-1].get("content") == user_input:
        history = history[:-1]

    contents = []
    for entry in history:
        contents.append(types.Content(
            role="model" if entry["role"] == "assistant" else entry["role"],
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
        last_tool_result = None
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
                # If a tool needs confirmation, the model is asking the user to
                # approve; keep the session open to receive their yes/no.
                return result, not policy.has_pending_action()

            contents.append(candidate.content)

            result_parts = []
            for fc in function_calls:
                args = dict(fc.args)
                tool_used = fc.name
                print(f"[Tool] {fc.name}({args})")
                if fc.name == "ask_clarification":
                    question = args.get("question", "Could you clarify what you mean?")
                    eval.log(user_input, "ask_clarification", success=True, latency_ms=int((time.time() - start) * 1000))
                    return question, False

                policy_result = policy.check_policy(fc.name, args)
                if policy_result["decision"] == "allow":
                    tool_result = execute_tool(fc.name, args)
                elif policy_result["decision"] == "confirm":
                    eval.log(
                        user_input, fc.name,
                        success=False,
                        latency_ms=int((time.time() - start) * 1000),
                        error=policy_result["message"],
                    )
                    return policy_result["message"], False
                elif policy_result["decision"] == "block":
                    eval.log(
                        user_input, fc.name,
                        success=False,
                        latency_ms=int((time.time() - start) * 1000),
                        error=policy_result["message"],
                    )
                    return policy_result["message"], True
                elif policy_result["decision"] == "clarify":
                    clarification.ask_tool(fc.name, args, policy_result["message"])
                    eval.log(
                        user_input, fc.name,
                        success=False,
                        latency_ms=int((time.time() - start) * 1000),
                        error=policy_result["message"],
                    )
                    return policy_result["message"], False
                else:
                    tool_result = {"success": False, "message": policy_result["message"]}
                print(f"[Tool] → {tool_result}")
                if tool_result.get("success"):
                    last_tool_result = tool_result["message"]
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
    if last_tool_result:
        return last_tool_result, True
    return "I wasn't able to complete that request.", True
