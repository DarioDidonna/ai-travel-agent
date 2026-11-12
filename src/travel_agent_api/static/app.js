"use strict";

const API_URL = "/chat/travel-agent";
const KEY_STORAGE = "travel-agent-api-key";

const history = [];
const chat = document.getElementById("chat");
const messages = document.getElementById("messages");
const welcome = document.getElementById("welcome");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const send = document.getElementById("send");
const keyRow = document.getElementById("key-row");
const keyInput = document.getElementById("api-key");

// La chiave è facoltativa: il campo compare solo se il server risponde 401
try {
  const saved = localStorage.getItem(KEY_STORAGE);
  if (saved) {
    keyInput.value = saved;
    keyRow.hidden = false;
  }
} catch (_) { /* localStorage non disponibile */ }

// Il testo del modello non è fidato: markdown -> HTML, poi sanificato con DOMPurify
function renderMarkdown(text) {
  const html = marked.parse(text, { breaks: true });
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } });
}

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer");
  }
  if (node.tagName === "IMG") {
    node.setAttribute("loading", "lazy");
    node.setAttribute("referrerpolicy", "no-referrer");
  }
});

function addMessage(kind, content) {
  welcome.hidden = true;
  const row = document.createElement("div");
  row.className = `message ${kind}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (kind === "assistant") {
    bubble.innerHTML = renderMarkdown(content);
  } else {
    bubble.textContent = content;
  }
  row.appendChild(bubble);
  messages.appendChild(row);
  if (kind === "assistant" && content) {
    // Le risposte sono lunghe: si parte a leggere dall'inizio, non dalla fine
    row.scrollIntoView({ block: "start" });
  } else {
    chat.scrollTop = chat.scrollHeight;
  }
  return bubble;
}

function startTyping() {
  const bubble = addMessage("assistant", "");
  bubble.classList.add("typing");
  const started = Date.now();
  const update = () => {
    const seconds = Math.round((Date.now() - started) / 1000);
    bubble.textContent = `L'agente sta lavorando… ${seconds}s`;
  };
  update();
  const timer = setInterval(update, 1000);
  return () => {
    clearInterval(timer);
    bubble.parentElement.remove();
  };
}

async function errorMessage(response) {
  let detail = "";
  try {
    const body = await response.json();
    detail = typeof body.detail === "string" ? body.detail : "";
  } catch (_) { /* risposta non JSON */ }

  switch (response.status) {
    case 401:
      keyRow.hidden = false;
      keyInput.focus();
      return "Serve la chiave di accesso: inseriscila nel campo qui sotto e riprova.";
    case 422:
      return "Il messaggio non è valido (massimo 4000 caratteri).";
    case 429: {
      const wait = response.headers.get("Retry-After");
      return `Troppe richieste. Riprova tra ${wait || "qualche"} secondi.`;
    }
    default:
      return detail || "Si è verificato un errore. Riprova più tardi.";
  }
}

async function ask(text) {
  history.push({ role: "user", content: text });
  addMessage("user", text);
  send.disabled = true;
  const stopTyping = startTyping();

  const headers = { "Content-Type": "application/json" };
  const key = keyInput.value.trim();
  if (key) {
    headers["X-API-Key"] = key;
    try { localStorage.setItem(KEY_STORAGE, key); } catch (_) { /* ignora */ }
  }

  try {
    // Lo storico tiene al massimo 30 messaggi, come richiesto dall'API
    const response = await fetch(API_URL, {
      method: "POST",
      headers,
      body: JSON.stringify({ messages: history.slice(-30) }),
    });
    stopTyping();
    if (!response.ok) {
      history.pop();
      addMessage("error", await errorMessage(response));
      return;
    }
    const reply = await response.json();
    history.push({ role: "assistant", content: reply.content });
    addMessage("assistant", reply.content);
  } catch (_) {
    stopTyping();
    history.pop();
    addMessage("error", "Impossibile contattare il server. Controlla che sia in esecuzione.");
  } finally {
    send.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text || send.disabled) return;
  input.value = "";
  input.style.height = "";
  ask(text);
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${input.scrollHeight}px`;
});

document.querySelectorAll(".example").forEach((button) => {
  button.addEventListener("click", () => {
    if (!send.disabled) ask(button.textContent.trim());
  });
});

document.getElementById("new-chat").addEventListener("click", () => {
  history.length = 0;
  messages.replaceChildren();
  welcome.hidden = false;
  input.focus();
});
