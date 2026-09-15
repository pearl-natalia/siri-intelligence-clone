'use strict';
const $ = (id) => document.getElementById(id);
let history = [], busy = false, voice;
let account = null, csrf = '', conversation = null, savedLoading = false, accountLoaded = false;
$('speak').disabled = true;
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
  $('mic').disabled = !accountLoaded || !Recognition || (busy && !voice?.active);
  $('mic').classList.toggle('listening', Boolean(voice?.active));
  $('mic-label').textContent = voice?.active ? 'End voice chat' : 'Start voice chat';
  $('mic').setAttribute('aria-pressed', String(Boolean(voice?.active)));
}
function setBusy(value) {
  busy = value; $('send').disabled = value; $('clear').disabled = value;
  $('saved-chats').disabled = value; $('sign-out').disabled = value; $('sign-in').disabled = value;
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
    await accountReady;
    const response = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRF-Token':csrf}, body:JSON.stringify({message, history:account ? [] : history, account_required:Boolean(account), conversation_id:conversation?.id, revision:conversation?.revision, timezone:Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'}), signal:controller.signal});
    const data = await response.json();
    if (response.status === 401) $('sign-in').hidden = false;
    if (!response.ok) throw new Error(data.error || 'Swift could not respond.');
    addMessage('assistant', data.reply, data.links);
    if (data.conversation) {conversation = data.conversation; accountNotice('Saved to your account.');}
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
function resetConversation() {voice?.stop(); history = []; conversation = null; $('messages').replaceChildren(); $('empty-state').hidden=false; $('message').value=''; resizeMessage(); stopSpeech(); setState('Ready');}
$('clear').addEventListener('click', () => {if(busy)return; resetConversation(); accountNotice(account ? 'New chat · saves to your account.' : 'Guest chat · not saved.');});
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
    savePreference();
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

function accountNotice(text) {
  $('account-status').textContent = text;
  $('account-status').hidden = !text;
}
function renderAccount(enabled) {
  $('sign-in').hidden = !enabled || Boolean(account);
  $('sign-out').hidden = !account;
  $('account-name').hidden = !account;
  $('account-name').textContent = account?.name || '';
  $('saved-chats').hidden = !account;
  accountNotice(account ? 'Signed in · chats save to your account.' : enabled ? 'Guest chat · sign in to save conversations.' : '');
}
async function accountRequest(path, options = {}) {
  const response = await fetch(path, {...options, headers:{'Content-Type':'application/json', 'X-CSRF-Token':csrf}});
  const data = await response.json();
  if (response.status === 401) $('sign-in').hidden = false;
  if (!response.ok) throw new Error(data.error || 'Saved chats are unavailable. Try again shortly.');
  return data;
}
const accountReady = (async () => {
  try {
    const data = await accountRequest('/api/account');
    account = data.user; csrf = data.csrf || '';
    if (account) $('speak').checked = data.preferences.speak;
    renderAccount(data.enabled);
  } catch (_) {renderAccount(false);}
  accountLoaded = true; $('speak').disabled = false; updateMic();
  const params = new URLSearchParams(window.location.search);
  if (params.has('signin')) {
    accountNotice('Sign-in didn’t finish. You can try again or keep chatting as a guest.');
    window.history.replaceState(null, '', window.location.pathname);
  }
})();
$('sign-in').addEventListener('click', () => {if (voice?.active) voice.stop(); stopSpeech(); $('sign-in-dialog').showModal();});
document.querySelectorAll('[data-close-dialog]').forEach(button => button.addEventListener('click', () => $(button.dataset.closeDialog).close()));
$('sign-out').addEventListener('click', async () => {
  if (busy) return;
  voice?.stop(); stopSpeech(); setBusy(true);
  try {
    await accountRequest('/api/auth/logout', {method:'POST'});
    account = null; csrf = ''; $('speak').checked = true;
    resetConversation(); renderAccount(true);
    accountNotice('Signed out · this guest chat won’t be saved.');
  } catch (error) {accountNotice(error.message);}
  finally {setBusy(false);}
});
let preferenceQueue = Promise.resolve();
function savePreference() {
  const value = $('speak').checked;
  preferenceQueue = preferenceQueue.then(async () => {
    await accountReady;
    if (!account) return;
    try {await accountRequest('/api/account/preferences', {method:'PATCH',body:JSON.stringify({speak:value})});}
    catch (error) {accountNotice('Voice preference wasn’t saved. ' + error.message);}
  });
}
$('speak').addEventListener('change', savePreference);
async function refreshSavedChats() {
  const data = await accountRequest('/api/conversations');
  $('saved-list').replaceChildren();
  if (!data.conversations.length) {
    const empty = document.createElement('p'); empty.textContent = 'No saved conversations yet.'; $('saved-list').append(empty);
  }
  for (const item of data.conversations) {
    const row = document.createElement('div'); row.className = 'saved-row';
    const open = document.createElement('button'); open.type = 'button'; open.className = 'saved-open';
    open.textContent = item.title;
    const date = document.createElement('small'); date.textContent = new Date(item.updated * 1000).toLocaleDateString(); open.append(date);
    open.addEventListener('click', async () => {
      if (savedLoading || busy) return;
      savedLoading = true; setBusy(true); voice?.stop(); stopSpeech();
      try {
        const data = await accountRequest('/api/conversations/' + encodeURIComponent(item.id));
        resetConversation(); conversation = {id:data.id,revision:data.revision};
        history = data.messages.slice(-20).map(item => ({role:item.role,text:item.text}));
        for (const item of data.messages) addMessage(item.role === 'user' ? 'user' : 'assistant', item.text, item.links);
        accountNotice('Saved to your account.'); $('saved-dialog').close(); $('message').focus();
      } catch (error) {$('saved-error').textContent = error.message; $('saved-error').hidden = false;}
      finally {savedLoading = false; setBusy(false);}
    });
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'text-button'; remove.textContent = 'Delete';
    remove.setAttribute('aria-label', 'Delete conversation: ' + item.title);
    remove.addEventListener('click', async () => {
      if (savedLoading || busy || !window.confirm('Delete this saved conversation? This can’t be undone.')) return;
      savedLoading = true; setBusy(true);
      try {
        await accountRequest('/api/conversations/' + encodeURIComponent(item.id), {method:'DELETE'});
        if (conversation?.id === item.id) resetConversation();
        await refreshSavedChats();
      } catch (error) {$('saved-error').textContent = error.message; $('saved-error').hidden = false;}
      finally {savedLoading = false; setBusy(false);}
    });
    row.append(open, remove); $('saved-list').append(row);
  }
}
$('saved-chats').addEventListener('click', async () => {
  if (busy) return;
  voice?.stop(); stopSpeech(); setBusy(true);
  $('saved-error').hidden = true; $('saved-list').textContent = 'Loading…'; $('saved-dialog').showModal();
  try {await refreshSavedChats();}
  catch (error) {$('saved-list').textContent = ''; $('saved-error').textContent = error.message; $('saved-error').hidden = false;}
  finally {setBusy(false);}
});
