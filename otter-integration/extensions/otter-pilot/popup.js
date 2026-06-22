const urlInput = document.getElementById("url");
const sendBtn = document.getElementById("send");
const statusEl = document.getElementById("status");

function setStatus(text, cls) {
  statusEl.textContent = text;
  statusEl.className = cls || "";
}

chrome.storage.local.get("onboardUrl").then(({ onboardUrl }) => {
  if (onboardUrl) urlInput.value = onboardUrl;
});

sendBtn.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  if (!url) return setStatus("Paste your Copilot onboarding URL first.", "err");
  await chrome.storage.local.set({ onboardUrl: url });

  const cookies = await chrome.cookies.getAll({ domain: "otter.ai" });
  const sessionid = cookies.find((c) => c.name === "sessionid")?.value;
  const csrftoken = cookies.find((c) => c.name === "csrftoken")?.value;
  if (!sessionid || !csrftoken)
    return setStatus("Not logged into otter.ai — open otter.ai and sign in first.", "err");

  setStatus("Sending…");
  let res;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ sessionid, csrftoken }),
    });
  } catch (e) {
    return setStatus("Network error: " + e.message, "err");
  }

  const data = await res.json();
  if (res.ok && data.connected) setStatus("✓ connected as " + data.identity, "ok");
  else setStatus(data.error || "Unexpected response: " + JSON.stringify(data), "err");
});
