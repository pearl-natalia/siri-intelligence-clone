import subprocess, re
from model import model


def run_applescript(script: str) -> tuple:
    # Returns (success, output, error)
    clean = re.search(r"```applescript\n?(.*?)(```|$)", script.strip(), re.DOTALL)
    if clean:
        script = clean.group(1).strip()
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.returncode == 0, r.stdout.strip(), r.stderr.strip()


def applescript_loop(task: str, system_context: str = "", max_steps: int = 5) -> dict:
    """
    ReAct loop for AppleScript tasks.
    Generates a script, runs it, feeds errors back, retries until success or max_steps.
    Returns {"success": bool, "message": str}
    """
    observations = []

    for step in range(max_steps):
        history = ""
        if observations:
            history = "\nPrevious attempts and errors:\n" + "\n".join(
                f"Step {i+1}: {o}" for i, o in enumerate(observations)
            )

        prompt = f"""You are an expert at writing AppleScript for macOS.
Generate an AppleScript to complete the following task: {task}
{system_context}
{history}
Only output the AppleScript, nothing else. If the task cannot be done via AppleScript, output "cannot generate script"."""

        script = model(prompt, 1.0)

        if script.strip().lower() == "cannot generate script":
            return {"success": False, "message": "I can't do that via system commands."}

        success, output, error = run_applescript(script)

        if success:
            return {"success": True, "message": output or "Done."}

        observations.append(f"Script failed with error: {error}")

    return {"success": False, "message": f"Failed after {max_steps} attempts: {observations[-1]}"}
