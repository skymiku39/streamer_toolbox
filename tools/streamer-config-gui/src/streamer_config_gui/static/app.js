const editors = {
  "bot-responses": document.getElementById("bot-editor"),
  "redemption-responses": document.getElementById("redemption-editor"),
  "llm-subscriber": document.getElementById("llm-config-editor"),
  "sub-visual": document.getElementById("visual-editor"),
};

const statusEl = document.getElementById("status");
const restartHintsEl = document.getElementById("restart-hints");
const knowledgeSelect = document.getElementById("knowledge-select");
const knowledgeEditor = document.getElementById("knowledge-editor");

function setStatus(message, kind = "") {
  statusEl.textContent = message;
  statusEl.className = `status ${kind}`.trim();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errors = data.detail?.errors || [data.detail || response.statusText];
    throw new Error(Array.isArray(errors) ? errors.join("；") : String(errors));
  }
  return data;
}

async function loadMeta() {
  const meta = await api("/api/meta");
  document.getElementById("config-root").textContent = meta.paths.root;
  document.getElementById("channel-name").textContent = meta.channel || "（未設定 TWITCH_CHANNEL）";
  restartHintsEl.innerHTML = meta.restart_hints
    .map((item) => `<li>${item.file} → 重啟 <code>${item.process}</code></li>`)
    .join("");
  if (meta.knowledge_file) {
    document.getElementById("knowledge-title").textContent = meta.knowledge_file;
  }
}

async function loadResource(name) {
  const data = await api(`/api/${name}`);
  editors[name].value = data.content;
}

async function saveResource(name) {
  const content = editors[name].value;
  const result = await api(`/api/${name}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
  setStatus(`已儲存，請重啟 ${result.restart}`, "ok");
}

async function loadKnowledgeList() {
  const data = await api("/api/knowledge");
  knowledgeSelect.innerHTML = "";
  for (const file of data.files) {
    const option = document.createElement("option");
    option.value = file;
    option.textContent = file;
    knowledgeSelect.appendChild(option);
  }
  if (data.files.length > 0) {
    await loadKnowledgeFile(data.files[0]);
  } else {
    knowledgeEditor.value = "";
  }
}

async function loadKnowledgeFile(filename) {
  const data = await api(`/api/knowledge/${encodeURIComponent(filename)}`);
  knowledgeEditor.value = data.content;
}

async function saveKnowledgeFile() {
  const filename = knowledgeSelect.value;
  if (!filename) {
    setStatus("沒有可儲存的知識庫檔案", "error");
    return;
  }
  const result = await api(`/api/knowledge/${encodeURIComponent(filename)}`, {
    method: "PUT",
    body: JSON.stringify({ content: knowledgeEditor.value }),
  });
  setStatus(`知識庫已儲存，請重啟 ${result.restart}`, "ok");
}

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    document.querySelector(`[data-panel="${button.dataset.tab}"]`).classList.add("active");
  });
});

document.querySelectorAll("[data-save]").forEach((button) => {
  button.addEventListener("click", async () => {
    try {
      await saveResource(button.dataset.save);
    } catch (error) {
      setStatus(`儲存失敗：${error.message}`, "error");
    }
  });
});

document.querySelectorAll("[data-reload]").forEach((button) => {
  button.addEventListener("click", async () => {
    try {
      await loadResource(button.dataset.reload);
      setStatus("已重新載入", "ok");
    } catch (error) {
      setStatus(`載入失敗：${error.message}`, "error");
    }
  });
});

document.querySelector("[data-save-knowledge]").addEventListener("click", async () => {
  try {
    await saveKnowledgeFile();
  } catch (error) {
    setStatus(`儲存失敗：${error.message}`, "error");
  }
});

document.querySelector("[data-reload-knowledge]").addEventListener("click", async () => {
  try {
    await loadKnowledgeFile(knowledgeSelect.value);
    setStatus("已重新載入", "ok");
  } catch (error) {
    setStatus(`載入失敗：${error.message}`, "error");
  }
});

knowledgeSelect.addEventListener("change", async () => {
  try {
    await loadKnowledgeFile(knowledgeSelect.value);
  } catch (error) {
    setStatus(`載入失敗：${error.message}`, "error");
  }
});

document.getElementById("bootstrap-btn").addEventListener("click", async () => {
  try {
    const result = await api("/api/bootstrap", { method: "POST" });
    setStatus(`初始化完成（新增 ${result.created.length} 個檔案）`, "ok");
    await Promise.all([
      loadResource("bot-responses"),
      loadResource("redemption-responses"),
      loadResource("llm-subscriber"),
      loadResource("sub-visual"),
      loadKnowledgeList(),
    ]);
  } catch (error) {
    setStatus(`初始化失敗：${error.message}`, "error");
  }
});

async function init() {
  try {
    await loadMeta();
    await Promise.all([
      loadResource("bot-responses"),
      loadResource("redemption-responses"),
      loadResource("llm-subscriber"),
      loadResource("sub-visual"),
      loadKnowledgeList(),
    ]);
    setStatus("就緒", "ok");
  } catch (error) {
    setStatus(`載入失敗：${error.message}（可先按「初始化範例檔」）`, "error");
  }
}

init();
