'use strict';
const $ = (id) => document.getElementById(id);
let history = [], busy = false, voice;
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const synth = window.speechSynthesis;
function resizeMessage() {
  $('message').style.height = '34px';
  $('message').style.height = Math.min($('message').scrollHeight, 120) + 'px';
}
$('message').addEventListener('input', resizeMessage);
function setState(text) { $('state').textContent = text; }
function addMessage(role, text, links = []) {
  const bubble = document.createElement('article');
  bubble.className = 'bubble ' + role;
  const label = document.createElement('small');
  label.textContent = role === 'user' ? 'You' : role === 'error' ? 'Could not respond' : 'Swift';
  bubble.append(label, document.createTextNode(text));
  for (const link of links) {
    try {
      const url = new URL(link.url);
      if (url.protocol !== 'https:' || url.username || url.password) continue;
      const anchor = document.createElement('a');
      anchor.href = url.href; anchor.textContent = link.label + (link.kind === 'mac_download' ? '' : ' ↗');
      if (link.kind === 'mac_download') anchor.className = 'download-action';
      anchor.target = '_blank'; anchor.rel = 'noopener noreferrer'; bubble.append(anchor);
    } catch (_) { /* Ignore malformed links. */ }
  }
  $('empty-state').hidden = true;
  $('messages').append(bubble);
  $('messages').scrollTop = $('messages').scrollHeight;
}
function updateMic() {
  $('mic').disabled = !Recognition || (busy && !voice?.active);
  $('mic').classList.toggle('listening', Boolean(voice?.active));
  $('mic-label').textContent = voice?.active ? 'End voice chat' : 'Start voice chat';
  $('mic').setAttribute('aria-pressed', String(Boolean(voice?.active)));
}
function setBusy(value) {
  busy = value; $('send').disabled = value; $('clear').disabled = value;
  updateMic();
}
let ttsConfigured = false, ttsRetryAfter = 0, speechController, speechAudio, speechUrl, speechVersion = 0, finishSpeech;
function stopSpeech() {
  speechVersion++; speechController?.abort(); speechController = undefined;
  if (speechAudio) { speechAudio.onended = speechAudio.onerror = null; speechAudio.pause(); speechAudio = undefined; }
  if (speechUrl) { URL.revokeObjectURL(speechUrl); speechUrl = undefined; }
  synth?.cancel();
  finishSpeech?.(false); finishSpeech = undefined;
}
function browserSpeak(text, version) {
  if (!synth || version !== speechVersion) return Promise.resolve(false);
  return new Promise(resolve => {
    let done = false;
    const finish = (played) => {
      if (done) return;
      done = true; clearTimeout(timer);
      if (finishSpeech === finish) finishSpeech = undefined;
      resolve(played);
    };
    const timer = setTimeout(() => {if (version === speechVersion) stopSpeech(); finish(false);}, 180000);
    finishSpeech = finish;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.onstart = () => {if(version === speechVersion)setState('Speaking…');};
    utterance.onend = () => finish(version === speechVersion);
    utterance.onerror = () => finish(false);
    try { synth.speak(utterance); } catch (_) { finish(false); }
  });
}
async function speak(text) {
  stopSpeech(); const version = speechVersion;
  if (ttsConfigured && Date.now() >= ttsRetryAfter) {
    speechController = new AbortController();
    const timer = setTimeout(() => {if(version === speechVersion)speechController?.abort();}, 12000);
    setState('Preparing voice…');
    try {
      const response = await fetch('/api/speech', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:text.slice(0,4000)}), signal:speechController.signal});
      if (!response.ok) throw new Error('Speech unavailable');
      const blob = await response.blob();
      if (version !== speechVersion) return false;
      clearTimeout(timer);
      speechUrl = URL.createObjectURL(blob); speechAudio = new Audio(speechUrl);
      const played = await new Promise(resolve => {
        let done = false;
        const finish = (value) => {
          if (done) return;
          done = true; clearTimeout(playbackTimer);
          if (finishSpeech === finish) finishSpeech = undefined;
          resolve(value);
        };
        const playbackTimer = setTimeout(() => finish(false), 180000);
        finishSpeech = finish;
        speechAudio.onended = () => finish(version === speechVersion);
        speechAudio.onerror = () => finish(false);
        speechAudio.play().then(() => {if(version === speechVersion)setState('Speaking…');}).catch(() => finish(false));
      });
      if (version !== speechVersion) return false;
      speechAudio.onended = speechAudio.onerror = null; speechAudio.pause(); speechAudio = undefined;
      URL.revokeObjectURL(speechUrl); speechUrl = undefined;
      if (played) return true;
      throw new Error('Playback unavailable');
    } catch (_) {
      if (version !== speechVersion) return false;
      // Avoid repeating a failed provider request on every conversational turn.
      ttsRetryAfter = Date.now() + 300000;
      setState('Preparing audio…');
    } finally {clearTimeout(timer);}
  }
  return browserSpeak(text, version);
}
async function sendMessage(message) {
  if (busy) throw new Error('Swift is still replying.');
  setBusy(true); setState('Thinking…');
  addMessage('user', message);
  const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 140000);
  try {
    const response = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message, history, timezone:Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'}), signal:controller.signal});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Swift could not respond.');
    addMessage('assistant', data.reply, data.links);
    if (data.mode !== 'setup') history = [...history, {role:'user',text:message}, {role:'model',text:data.reply.slice(0,8000)}].slice(-20);
    setState('Reply ready');
    return data.reply;
  } catch (error) {
    addMessage('error', error.name === 'AbortError' ? 'That took too long. Please try again.' : error.message);
    setState('Ready to try again');
    throw error;
  } finally { clearTimeout(timer); setBusy(false); }
}
$('chat-form').addEventListener('submit', async (event) => {
  event.preventDefault(); const message = $('message').value.trim();
  if (!message || busy) return;
  voice?.stop('Thinking…'); stopSpeech(); const version = speechVersion; $('message').value = ''; resizeMessage();
  try {
    const reply = await sendMessage(message);
    if (version !== speechVersion) return;
    if ($('speak').checked) {
      const played = await speak(reply);
      if (!voice?.active && (played || speechVersion === version + 1)) setState(played ? 'Ready when you are' : 'Reply ready · audio stopped');
    } else { setState('Ready when you are'); }
  } catch (_) { if (!$('message').value) {$('message').value = message; resizeMessage();} }
});
$('message').addEventListener('keydown', (event) => {if(event.key === 'Enter' && !event.shiftKey){event.preventDefault(); $('chat-form').requestSubmit();}});
document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => {
  if (busy) return;
  $('message').value = button.dataset.prompt;
  $('chat-form').requestSubmit();
}));
$('stop').addEventListener('click', () => {voice?.stop(busy ? 'Thinking · voice ended' : 'Voice and audio stopped'); stopSpeech();});
$('speak').addEventListener('change', () => {if (!$('speak').checked) {voice?.stop('Voice chat ended');stopSpeech();setState(busy ? 'Thinking…' : 'Ready when you are');}});
$('clear').addEventListener('click', () => {if(busy)return; voice?.stop(); history = []; $('messages').replaceChildren(); $('empty-state').hidden=false; $('message').value=''; resizeMessage(); stopSpeech(); setState('Ready');});
if (Recognition) {
  voice = new window.VoiceConversation({
    Recognition, send: sendMessage, speak, stopSpeech, onState: setState,
    onActive: updateMic,
    onTranscript: text => {$('transcript').textContent = text; $('transcript').hidden = !text;},
  });
  $('mic').addEventListener('click', () => {
    if (voice.active) { voice.stop(busy ? 'Thinking · voice ended' : 'Voice chat ended'); return; }
    if (busy) return;
    $('speak').checked = true;
    voice.start();
  });
} else {
  $('voice-hint').textContent='Voice input is not supported in this browser. Type below, or use Chrome.';
}
updateMic();
document.addEventListener('visibilitychange', () => {if(document.hidden) {if(voice?.active) voice.stop('Voice paused while this tab is hidden');stopSpeech();}});
window.addEventListener('pagehide', () => {voice?.stop();stopSpeech();});
fetch('/api/status').then(response=>{if(!response.ok)throw new Error(); return response.json();}).then(data=>{
  ttsConfigured = Boolean(data.tts_configured);
  if (!busy && !voice?.active) setState('Ready');
  if(!data.ai_configured){$('setup').hidden=false;$('setup').textContent='AI replies are temporarily unavailable. You can still check the time or download the Mac preview.';}
}).catch(()=>setState('Connection unavailable · refresh to reconnect'));
