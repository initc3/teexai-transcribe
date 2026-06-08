const Q = new URLSearchParams(location.search);
const ROLE = Q.get('role'), ROOM = Q.get('room') || 'e2eeroom', KEY = Q.get('key') || '';

function log(...a) {
  const m = a.map(x => typeof x === 'object' ? JSON.stringify(x) : x).join(' ');
  console.log(m);
  try { fetch('http://asr:8000/log', { method: 'POST', mode: 'no-cors', body: ROLE + ': ' + m }); } catch (e) {}
}
window.onerror = (m, s, l, c, e) => log('ERROR', m, l + ':' + c, (e && e.stack) || '');

const J = JitsiMeetJS;
J.setLogLevel(J.logLevels.ERROR);
J.init({ disableAudioLevels: true });

const options = {
  hosts: { domain: 'meet.jitsi', muc: 'muc.meet.jitsi' },
  serviceUrl: `wss://web/xmpp-websocket?room=${ROOM}`,
};
const CE = J.events.connection, CF = J.events.conference;

let conf, connAttempt = 0;
function startConnection() {
  const connection = new J.JitsiConnection(null, null, options);
  connection.addEventListener(CE.CONNECTION_ESTABLISHED, () => onConn(connection));
  connection.addEventListener(CE.CONNECTION_FAILED, e => {
    log('CONNECTION_FAILED', e, 'attempt', connAttempt);
    if (connAttempt++ < 15) setTimeout(() => { try { connection.disconnect(); } catch (_) {} startConnection(); }, 3000);
  });
  connection.connect();
}
log('connecting', options.serviceUrl);
startConnection();

function onConn(connection) {
  log('xmpp established; joining', ROOM);
  conf = connection.initJitsiConference(ROOM, { e2ee: { externallyManagedKey: true } });
  conf.on(CF.CONFERENCE_JOINED, onJoined);
  conf.on(CF.CONFERENCE_FAILED, onConfFailed);
  conf.on(CF.TRACK_ADDED, onTrack);
  conf.join();
}

let retries = 0;
function onConfFailed(e) {
  log('CONFERENCE_FAILED', e, 'retry', retries);
  if (retries++ < 10) setTimeout(() => conf.join(), 3000);
}

async function setKey() {
  if (!KEY) { log('eavesdropper: no key, E2EE OFF'); return; }
  const raw = Uint8Array.from(KEY.match(/../g).map(h => parseInt(h, 16)));
  const k = await crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['encrypt', 'decrypt']);
  conf.toggleE2EE(true);
  conf.setMediaEncryptionKey({ encryptionKey: k, index: 0 });
  log('E2EE enabled; supported=', conf.isE2EESupported());
}

async function onJoined() {
  log('JOINED; e2eeSupported=', conf.isE2EESupported());
  await setKey();
  if (ROLE === 'publisher') {
    const tr = await J.createLocalTracks({ devices: ['audio'] });
    await conf.addTrack(tr[0]);
    log('publishing audio track');
  }
}

let pcmStarted = false;
function onTrack(track) {
  if (track.isLocal() || track.getType() !== 'audio') return;
  log('remote audio track from', track.getParticipantId());
  const native = track.getTrack();
  const el = document.createElement('audio');
  el.autoplay = true; el.muted = true; document.body.appendChild(el);
  try { track.attach(el); } catch (e) { log('attach err', e); }
  if (ROLE === 'publisher' || pcmStarted) return;
  pcmStarted = true;
  startPCM(new MediaStream([native]));
}

async function startPCM(stream) {
  const ctx = new AudioContext({ sampleRate: 16000 });
  await ctx.audioWorklet.addModule('/pcm-worklet.js');
  const src = ctx.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(ctx, 'pcm');
  src.connect(node); node.connect(ctx.destination);
  const ws = new WebSocket('ws://asr:8000/pcm?role=' + ROLE);
  ws.binaryType = 'arraybuffer';
  ws.onopen = () => log('pcm ws open');
  ws.onerror = e => log('pcm ws error');
  let sent = 0;
  node.port.onmessage = e => {
    if (ws.readyState === 1) { ws.send(e.data); if (++sent % 400 === 0) log('pcm frames', sent); }
  };
  log('pcm pipeline started @', ctx.sampleRate, 'Hz');
}
