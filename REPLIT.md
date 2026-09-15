# Develop Swift in Replit, run native actions on Mac

Swift has two entry points:

- **Browser demo:** `web_app.py`, runs in Replit and works without a download. Supports conversational voice, Gemini, weather, search and clickable links.
- **Mac app:** `desktop.py`, runs on the user's Mac and uses the existing native action tools. Users speak inside the Mac app after downloading it. Replit is the development workspace; the final `.app` build runs on macOS.

The browser never exposes a remote control endpoint into the Mac. A desktop download is a standalone app, not a browser helper.

## Mac development and packaging

The [Intel Mac developer preview](https://github.com/pearl-natalia/siri-intelligence-clone/releases/tag/v0.1.0-mac-preview) includes the app download and setup notes. The browser's Download Mac preview button redirects to its verified GitHub release asset. No large app archive or developer credentials need to be uploaded to Replit.

On a Mac with Python 3.12, run `./run-mac.command`. The launcher creates an isolated environment and installs `packaging/requirements-mac.txt`. Configure your own keys in the app's first-run settings. Gemini is required; ElevenLabs and WeatherAPI are optional. No developer keys are included in the download.

To build a self-contained app, install `packaging/requirements-build.txt`, then run `SWIFT_BUILD_PYTHON=/path/to/venv/bin/python ./packaging/build-mac.sh`. The ZIP contains `Swift.app`; a user's Mac does not need Python. Build separately on Apple Silicon and Intel Macs. The current dependency set includes an older PyTorch version for Intel compatibility.

The packaged app uses searchable SQLite memory, avoiding the legacy Chroma/Transformers dependencies in the download. Existing source checkouts with a `memory_db` directory keep using `memory_legacy.py` and their existing dependencies/data.

The packaged app stores settings and memory in `~/Library/Application Support/Swift` and credentials in macOS Keychain. Source runs retain the checkout's existing settings and database. Whisper downloads its speech model on first use. Audio recognition runs locally; requests and relevant tool context go to Gemini. ElevenLabs receives reply text when configured, with macOS speech as fallback.

Start begins a conversational loop: listen, transcribe, act/respond, speak, listen again. Stop cancels recording/playback and prevents further turns; an action already executing may finish. Native access is subject to macOS microphone, Automation, Accessibility and, for requested screen context, Screen Recording permissions.

For a public installer, sign with Developer ID and notarize on macOS. `SWIFT_CODESIGN_IDENTITY` can select an existing signing identity. Without it, the artifact is an ad-hoc development preview, not a notarized public release. Do not embed signing credentials or API keys in this repository.

## Browser demo

## Run

Click **Run** in Replit. `bash run-web.sh` creates an isolated `.venv-web`, installs the small `requirements-web.txt` set, and starts Gunicorn on port 5000. First startup takes longer while dependencies install. The original `requirements-desktop.txt` is for the desktop edition and is not needed for this web runtime.

In **Replit Secrets**, add `GEMINI_API_KEY`, then restart the app. Optionally add `WEATHER_API` (WeatherAPI.com) for city weather and `GEMINI_MODEL` to override the model ID from the existing `model.py`. Never put keys in frontend files or chat messages.

Open Preview. For microphone access, open the preview in its own browser tab, use HTTPS and allow the microphone. Chrome supports browser speech recognition; other browsers may offer text input only. Click Start voice chat once: speech is sent automatically after a pause, Swift replies aloud, then listens for the next turn. Listening pauses during playback to avoid self-transcription. End voice chat, Stop voice & audio, hiding the tab, or saying “end voice chat” ends the loop. Typed messages remain available. Three empty listening turns pause the microphone. Recognition may send audio to the browser provider. AI text goes to Gemini. Add ELEVENLABS_API_KEY to enable ElevenLabs spoken replies (eleven_v3, original voice dtSEyYGNJqjrtBArPCVZ). ELEVENLABS_VOICE_ID and ELEVENLABS_MODEL_ID are optional overrides. Reply text goes to ElevenLabs only when Read aloud is enabled. Browser speech is the fallback if ElevenLabs is unavailable. Keys stay on the server; speech requests are limited to 4,000 characters and 10 per minute per process.

## Supported here

- Gemini conversation with the current tab's short-term history.
- Browser speech input and spoken replies.
- Time in the browser's timezone, including without a Gemini key.
- Existing weather and web-search helpers, with named cities and desktop opening disabled.
- Clickable Spotify search, Google Maps and HTTPS browser links. Links do not automatically start playback.

Mac app control, AppleScript, iMessage, Apple Calendar, contacts, Mac screen/clipboard capture, and desktop persistent memory are available only in the original macOS edition. The browser edition does not import that execution loop. Conversations are held in tab memory and reset on refresh/New chat, with no shared server conversation history. Provider errors are sanitized; repository and secret files are not served.

## Validation

` .venv-web/bin/python -m unittest test_web -v ` covers startup/setup, time, request validation, cross-origin protection, blocked desktop execution, link handling, secret-safe failures, isolated history input and a mocked Gemini function-call round trip. `node --check web_static/app.js` checks the browser script. `node --test test_voice.cjs` verifies voice turn-taking, cancellation, permission failures and silence handling. Live Gemini, weather and microphone behavior require their respective key or browser permission.

Run is the development preview. Public publishing, account access controls and production deployment are separate actions.
