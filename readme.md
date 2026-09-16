# Swift

A voice assistant with a browser demo and a standalone Mac app. Start a conversation, speak, pause, and Swift replies aloud before listening again.

[Try the web demo](https://siri-intelligence-clone--pearlnatalia.replit.app/) · [Mac preview and release notes](https://github.com/pearl-natalia/siri-intelligence-clone/releases/tag/v0.1.0-mac-preview) · [Development and packaging](REPLIT.md)

## Two ways to use it

| | Browser demo | Mac app |
| --- | --- | --- |
| Runs on | Replit | Your Mac |
| Voice input | Browser speech recognition | Local Whisper transcription |
| Reasoning | Gemini, through the web server | Gemini, using your own key |
| Spoken replies | ElevenLabs with browser speech fallback | ElevenLabs with macOS speech fallback |
| Actions | Search, city weather, time, music and map links | Native app controls through AppleScript and macOS permissions |
| Memory | Private cross-chat facts in Replit PostgreSQL when signed in; temporary context for guests | Local SQLite full-text search |

The browser does not remotely control your Mac. Downloading the app provides a separate desktop conversation. The Mac app stores credentials in macOS Keychain and settings and memory in `~/Library/Application Support/Swift`. Existing source checkouts with Chroma data retain the legacy backend.

## Try the browser demo

Click **Start voice chat** and allow the microphone. Speech is sent automatically after a pause. Swift stops listening while preparing and playing its reply, then listens again. Click **End voice chat**, or say “end voice chat”, to stop. Typed messages and example requests are also available.

Optional Replit sign-in saves your chats, voice preference, and lasting facts across conversations. Open **Saved chats → Memory** to review or remove facts, or pause memory. Browser and Mac memory are separate.

Voice recognition depends on browser support. The page offers text input when recognition is unavailable. Browser conversations go to Gemini; speech recognition may send audio to the browser provider. ElevenLabs receives reply text when configured.

## Develop in Replit

1. Import this source into Replit.
2. Add `GEMINI_API_KEY` in Replit Secrets. Optional: `ELEVENLABS_API_KEY` and `WEATHER_API`.
3. Run `bash run-web.sh`. The browser runtime uses `requirements-web.txt` in its own virtual environment.

The production server serves only `web_static/` and the explicit API routes. Provider keys stay on the server. Optional Replit Auth uses OpenID Connect and PKCE; private chats and memory use Replit PostgreSQL. Configure `DATABASE_URL`, the Replit-supplied `REPL_ID`, and a random `SESSION_SECRET` of at least 32 characters to enable accounts. Guests can chat without signing in.

## Run or build on a Mac

With Python 3.12 installed, run `./run-mac.command` and enter your own Gemini key in Settings. ElevenLabs and WeatherAPI are optional. Local speech models download on first use.

For a self-contained app, use `packaging/requirements-build.txt` and `packaging/build-mac.sh`; see [REPLIT.md](REPLIT.md). Build separately for each Mac architecture.

The published download is an **Intel Mac developer preview**, ad-hoc signed and **not Apple-notarized**. macOS may block its first launch. Review the release notes before testing it. Live microphone conversations and native actions still need testing on the receiving Mac. Native access requires the relevant macOS permissions; Stop prevents additional turns, but an action already executing may finish.

Developer ID signing and Apple notarization remain required work for a smoother public download experience. The older Intel PyTorch dependency and legacy desktop dependencies also need a separate compatibility and dependency review before a production release.

## Verify

```sh
.venv-web/bin/python -m unittest test_memory test_accounts test_web test_speech test_desktop -q
node --test test_voice.cjs
```

The checks cover cross-chat memory, account isolation, signed login validation, pause/remove controls, API validation, secret-safe errors, isolation of browser actions from desktop execution, local memory isolation, voice turn-taking, provider fallback, and cancellation. They use mocks for native actions and speech providers. Passing these checks does not replace microphone and permission testing on a Mac.
