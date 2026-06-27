"""
Tool-calling agent loop.

Single entry point: agent.run(user_input, settings) → spoken response string.

Flow:
  1. Build contents from conversation history + user input
  2. Call Gemini with all tool declarations
  3. If Gemini picks a tool → execute it → feed result back → repeat (max 5 iterations)
  4. When Gemini returns plain text → that's the spoken response
"""

import json
from datetime import datetime
from google.genai import types
from model import generate, get_history
from tools import TOOLS, execute_tool


def _system_prompt(settings: dict) -> str:
    name = settings.get("llm name", "Swift")
    user = settings.get("user_first_name", "there")
    now = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    return (
        f"You are {name}, an AI voice assistant for macOS. "
        f"The user's name is {user}. "
        "Your responses will be read aloud, so keep them to 1-2 concise sentences. "
        "Use the available tools to fulfill requests. "
        "After a tool executes successfully, confirm what was done in one sentence. "
        "If you cannot fulfill a request, say so briefly. "
        f"Current date and time: {now}. "
        f"User settings: {json.dumps(settings)}"
    )


def run(user_input: str, settings: dict) -> str:
    """
    Run the agent for a single user turn. Returns the spoken response string.
    Supports multi-tool chaining (e.g. 'cancel meeting AND text John').
    """
    system_prompt = _system_prompt(settings)

    # Build conversation contents from short-term history
    contents = []
    for entry in get_history():
        contents.append(types.Content(
            role=entry["role"],
            parts=[types.Part.from_text(text=entry["content"])]
        ))
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=user_input)]
    ))

    for iteration in range(5):
        response = generate(contents, tools=TOOLS, system_instruction=system_prompt)
        candidate = response.candidates[0]

        # Parse the response parts
        function_calls = []
        text_parts = []
        for part in candidate.content.parts:
            if hasattr(part, "function_call") and part.function_call:
                function_calls.append(part.function_call)
            elif hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        # No tool calls → final spoken response
        if not function_calls:
            return "".join(text_parts).strip()

        # Add the model's response (with function calls) to contents
        contents.append(candidate.content)

        # Execute every tool call and collect results
        result_parts = []
        for fc in function_calls:
            args = dict(fc.args)
            print(f"[Tool] {fc.name}({args})")
            result = execute_tool(fc.name, args)
            print(f"[Tool] → {result}")
            result_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    )
                )
            )

        contents.append(types.Content(role="user", parts=result_parts))

    return "I wasn't able to complete that request."
