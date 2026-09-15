const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('web_static/voice.js', 'utf8');
function deferred() {let resolve, reject;const promise = new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function setup() {
  const recognizers = [], requests = [], spoken = [], timers = new Map();
  let nextTimer = 0, state = '', active = false, transcript = '';
  class Recognition {
    constructor() {recognizers.push(this);}
    start() {this.started = true;this.onstart?.();}
    stop() {this.stopped = true;}
    abort() {this.aborted = true;}
    result(text, final = true) {const result = [{transcript:text}];result.isFinal=final;this.onresult?.({results:[result]});}
    end() {return this.onend?.();}
    error(error) {this.onerror?.({error});}
  }
  const context = {window:{},setTimeout:(fn)=>{timers.set(++nextTimer,fn);return nextTimer;},clearTimeout:id=>timers.delete(id)};
  vm.runInNewContext(source, context);
  const voice = new context.window.VoiceConversation({Recognition,
    send:text=>{const pending=deferred();requests.push({text,...pending});return pending.promise;},
    speak:text=>{const pending=deferred();spoken.push({text,...pending});return pending.promise;},
    stopSpeech:()=>{},onState:text=>state=text,onActive:value=>active=value,onTranscript:text=>transcript=text,
  });
  return {voice,recognizers,requests,spoken,timers,get state(){return state;},get active(){return active;},get transcript(){return transcript;},runTimer(){const [id,fn]=timers.entries().next().value;timers.delete(id);fn();}};
}
const tick = ()=>new Promise(resolve=>setImmediate(resolve));

test('a spoken turn auto-sends once, waits for the full reply, then listens again',async()=>{
  const f=setup();f.voice.start();const r=f.recognizers[0];
  r.result('What time',false);assert.equal(f.requests.length,0);assert.equal(f.transcript,'What time');
  r.result('What time is it?');r.onspeechend();assert.equal(r.stopped,true);
  const complete=r.end();r.end();assert.equal(f.requests.length,1);assert.equal(f.requests[0].text,'What time is it?');
  assert.equal(f.recognizers.length,1);f.requests[0].resolve('It is noon.');await tick();
  assert.equal(f.spoken[0].text,'It is noon.');assert.equal(f.timers.size,0);
  f.spoken[0].resolve(true);await complete;f.runTimer();assert.equal(f.recognizers.length,2);assert.equal(f.state,'Listening…');
});

test('ending voice chat while thinking suppresses speech and restart',async()=>{
  const f=setup();f.voice.start();const r=f.recognizers[0];r.result('Hello');const complete=r.end();
  f.voice.stop();f.requests[0].resolve('Hello back');await complete;
  assert.equal(f.spoken.length,0);assert.equal(f.timers.size,0);assert.equal(f.active,false);
});

test('late results from an aborted recognizer cannot submit into a new session',()=>{
  const f=setup();f.voice.start();const r=f.recognizers[0];const lateResult=r.onresult,lateEnd=r.onend;
  f.voice.stop();f.voice.start();const result=[{transcript:'stale command'}];result.isFinal=true;
  lateResult({results:[result]});lateEnd();assert.equal(f.requests.length,0);assert.equal(r.aborted,true);
});

test('stop during playback cancels the next listening turn',async()=>{
  const f=setup();f.voice.start();const r=f.recognizers[0];r.result('Hello');const complete=r.end();
  f.requests[0].resolve('Hello');await tick();f.voice.stop();f.spoken[0].resolve(true);await complete;
  assert.equal(f.timers.size,0);assert.equal(f.active,false);
});

test('permission rejection stops without repeated microphone prompts',()=>{
  const f=setup();f.voice.start();const r=f.recognizers[0];r.error('not-allowed');r.end();
  assert.equal(f.active,false);assert.match(f.state,/Microphone blocked/);assert.equal(f.timers.size,0);
});

test('three empty turns pause voice instead of listening indefinitely',async()=>{
  const f=setup();f.voice.start();for(let i=0;i<3;i++){await f.recognizers[i].end();if(i<2)f.runTimer();}
  assert.equal(f.active,false);assert.equal(f.requests.length,0);assert.match(f.state,/silence/);
});

test('interim-only transcription is never sent as a finished utterance',async()=>{
  const f=setup();f.voice.start();f.recognizers[0].result('unfinished',false);await f.recognizers[0].end();assert.equal(f.requests.length,0);
});

test('spoken end voice chat stops without an AI request',async()=>{
  const f=setup();f.voice.start();f.recognizers[0].result('End voice chat.');await f.recognizers[0].end();
  assert.equal(f.active,false);assert.equal(f.requests.length,0);
});

test('failed audio pauses instead of listening over a silent reply',async()=>{
  const f=setup();f.voice.start();f.recognizers[0].result('Hello');const complete=f.recognizers[0].end();
  f.requests[0].resolve('Hello');await tick();f.spoken[0].resolve(false);await complete;
  assert.equal(f.active,false);assert.match(f.state,/Audio unavailable/);assert.equal(f.timers.size,0);
});

test('failed chat pauses the microphone',async()=>{
  const f=setup();f.voice.start();f.recognizers[0].result('Hello');const complete=f.recognizers[0].end();
  f.requests[0].reject(new Error('offline'));await complete;assert.equal(f.active,false);assert.equal(f.timers.size,0);
});

function speechSetup({speechResponse} = {}) {
  const utterances = [], elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, {checked:true, value:'',hidden:true,classList:{toggle(){}},setAttribute(){},addEventListener(){},textContent:''});
    return elements.get(id);
  };
  const context = {console,URL,AbortController,Date,Intl,setTimeout,clearTimeout,window:{
    speechSynthesis:{speak:u=>utterances.push(u),cancel(){}},addEventListener(){},
  },document:{getElementById:element,querySelectorAll:()=>[],addEventListener(){}},
    SpeechSynthesisUtterance:class {constructor(text){this.text=text;}},
    fetch:async(url,options)=>url==='/api/status' ? {ok:true,json:async()=>({tts_configured:true,ai_configured:true})} : speechResponse(options),
  };
  vm.runInNewContext(fs.readFileSync('web_static/app.js','utf8'),context);
  return {context,utterances,element};
}

test('ElevenLabs failure falls back to browser audio and waits until it ends',async()=>{
  const f=speechSetup({speechResponse:async()=>({ok:false})});await tick();
  let completed=false;const speech=f.context.speak('Hello').then(value=>{completed=true;return value;});await tick();
  assert.equal(f.utterances[0].text,'Hello');assert.equal(completed,false);
  f.utterances[0].onend();assert.equal(await speech,true);
});

test('stopping during speech generation cannot start fallback audio later',async()=>{
  const response=deferred();const f=speechSetup({speechResponse:()=>response.promise});await tick();
  const speech=f.context.speak('Hello');f.context.stopSpeech();response.resolve({ok:false});
  assert.equal(await speech,false);assert.equal(f.utterances.length,0);
});

test('stopping browser audio settles playback and ignores its late end event',async()=>{
  const f=speechSetup({speechResponse:async()=>({ok:false})});await tick();
  const speech=f.context.speak('Hello');await tick();f.context.stopSpeech();
  assert.equal(await speech,false);f.utterances[0].onend();
});
