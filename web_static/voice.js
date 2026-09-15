'use strict';

// A fresh recognizer per turn keeps late browser events out of the next turn.
class VoiceConversation {
  constructor({Recognition, send, speak, stopSpeech, onState, onActive, onTranscript}) {
    Object.assign(this, {Recognition, send, speak, stopSpeech, onState, onActive, onTranscript});
    this.active = false;
    this.generation = 0;
    this.emptyTurns = 0;
  }
  start() {
    if (this.active) return;
    this.active = true;
    this.emptyTurns = 0;
    const generation = ++this.generation;
    this.stopSpeech();
    this.onActive(true);
    this.listen(generation);
  }
  current(generation) { return this.active && generation === this.generation; }
  stop(message = 'Voice chat ended') {
    this.active = false;
    this.generation++;
    clearTimeout(this.restartTimer);
    const recognition = this.recognition;
    this.recognition = null;
    if (recognition) {
      recognition.onend = recognition.onresult = recognition.onerror = recognition.onstart = recognition.onspeechend = null;
      try { recognition.abort(); } catch (_) { /* Already stopped. */ }
    }
    this.stopSpeech();
    this.onActive(false);
    this.onTranscript('');
    this.onState(message);
  }
  listen(generation) {
    if (!this.current(generation)) return;
    const recognition = new this.Recognition();
    this.recognition = recognition;
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.continuous = false;
    let transcript = '', ended = false;
    const current = () => this.current(generation) && this.recognition === recognition && !ended;
    recognition.onstart = () => { if (current()) this.onState('Listening…'); };
    recognition.onresult = (event) => {
      if (!current()) return;
      const results = Array.from(event.results);
      transcript = results.filter(result => result.isFinal).map(result => result[0].transcript).join(' ').trim().slice(0, 4000);
      this.onTranscript(results.map(result => result[0].transcript).join(' ').slice(0, 4000));
    };
    recognition.onspeechend = () => {
      if (current()) { try { recognition.stop(); } catch (_) { /* Ending already. */ } }
    };
    recognition.onerror = (event) => {
      if (!current() || event.error === 'no-speech') return;
      const messages = {
        'not-allowed': 'Microphone blocked. Allow microphone access, then start voice chat again.',
        'service-not-allowed': 'Voice recognition is blocked by this browser. You can type below.',
        'audio-capture': 'No microphone found. Connect one or type below.',
        'network': 'Voice connection lost. Start voice chat again or type below.',
      };
      this.stop(messages[event.error] || 'Voice stopped. Start voice chat again or type below.');
    };
    recognition.onend = async () => {
      if (!current()) return;
      ended = true;
      this.recognition = null;
      this.onTranscript('');
      if (!transcript) {
        if (++this.emptyTurns >= 3) { this.stop('Voice paused after silence. Start voice chat to continue.'); return; }
        this.onState('Still listening…');
        this.restartTimer = setTimeout(() => this.listen(generation), 750);
        return;
      }
      this.emptyTurns = 0;
      if (/^(stop|end|exit) voice chat[.!?]*$/i.test(transcript)) { this.stop(); return; }
      try {
        this.onState('Thinking…');
        const reply = await this.send(transcript);
        if (!this.current(generation)) return;
        const played = await this.speak(reply);
        if (!this.current(generation)) return;
        if (!played) { this.stop('Audio unavailable. Start voice chat again or type below.'); return; }
        this.onState('Listening next…');
        // Let the speaker's last syllable finish before reopening the microphone.
        this.restartTimer = setTimeout(() => this.listen(generation), 450);
      } catch (_) {
        if (this.current(generation)) this.stop('Voice paused. Try again when you are ready.');
      }
    };
    this.onState('Connecting microphone…');
    try { recognition.start(); }
    catch (_) { this.stop('Voice could not start. Try again or type below.'); }
  }
}
window.VoiceConversation = VoiceConversation;
