const text = process.argv[2];
const speaker = process.argv[3] ?? "";
const sessionId = process.env.CUE_SESSION_ID ?? "demo";
const url = process.env.CUE_SERVER_URL ?? "http://localhost:8798";

if (!text) {
  console.error("usage: node post-transcript-segment.mjs <text> [speaker]");
  process.exit(2);
}

const observation = {
  type: "transcript.segment",
  source: "teexai-transcribe",
  payload: {
    text,
    speaker,
    isFinal: true,
    confidence: 0.9
  }
};

const response = await fetch(`${url}/sessions/${sessionId}/observations`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(observation)
});

const body = await response.text();
if (!response.ok) {
  console.error(body);
  process.exit(1);
}

console.log(body);

