const chatMessages = document.getElementById("hrChatMessages");
const chatInput = document.getElementById("hrChatInput");
const chatForm = document.getElementById("hrChatForm");
const history = [];

function scrollDown() { chatMessages.scrollTop = chatMessages.scrollHeight; }

function addChatMessage(text, who) {
  const el = document.createElement("div");
  el.className = "chat-msg " + who;
  el.textContent = text;
  chatMessages.appendChild(el);
  scrollDown();
  return el;
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

// After the PDF is downloaded, ask whether to email it: Yes -> mail page, No -> fresh chat page.
function askToSendMail(letter, filename, pdfBlob) {
  const overlay = document.createElement("div");
  overlay.className = "send-dialog-backdrop";
  overlay.innerHTML = `<div class="send-dialog" role="dialog" aria-modal="true">
    <h3>PDF downloaded</h3>
    <p>Do you want to send this letter by email?</p>
    <div class="send-dialog-actions"><button type="button" class="send-no">No</button><button type="button" class="send-yes">Yes, send mail</button></div>
  </div>`;
  overlay.querySelector(".send-no").addEventListener("click", () => { window.location.href = "/hr-studio"; });
  overlay.querySelector(".send-yes").addEventListener("click", async () => {
    const pdf_base64 = await blobToBase64(pdfBlob);
    Draft.save({
      receiver_name: letter.recipient_name,
      role: letter.letter_name,
      letter_content: letter.body,
      details: { letter_type: "custom", letter_name: letter.letter_name, name: letter.recipient_name },
      pdf_base64,
      pdf_name: filename,
    });
    window.location.href = "/step4";
  });
  document.body.appendChild(overlay);
}

async function download(letter, format) {
  showLoading("Preparing PDF...", "Please wait while we prepare your letter.<br><br><small>This may take a few seconds.</small>");
  let result = null;
  try {
    const res = await fetch("/api/chat/download", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...letter, format }) });
    if (!res.ok) { const err = await res.json().catch(() => ({})); showToast(err.error || "Download failed.", "error"); return; }
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
    const filename = match ? decodeURIComponent(match[1]) : "letter.pdf";
    const blob = await res.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
    result = { filename, blob };
  } catch (err) {
    showToast("Download failed. Please try again.", "error");
  } finally {
    hideLoading();
  }
  if (result) askToSendMail(letter, result.filename, result.blob);
}

const studioPreview = document.getElementById("studioPreview");
const studioTitle = document.getElementById("studioTitle");
const studioDownload = document.getElementById("studioDownload");
let currentLetter = null;

function showLetter(letter, previewHtml) {
  document.getElementById("studio").classList.remove("no-letter");
  currentLetter = letter;
  studioPreview.innerHTML = previewHtml;
  studioTitle.textContent = letter.letter_name + " - " + letter.recipient_name;
  studioDownload.disabled = false;
}

studioDownload.addEventListener("click", () => { if (currentLetter) download(currentLetter, "pdf"); });

// Renders the model's requested details as a fill-in form inside the chat.
function addDetailsForm(fields) {
  const form = document.createElement("form");
  form.className = "chat-details";
  const note = document.createElement("small");
  note.textContent = "Fill what you have. Blank fields are skipped.";
  form.appendChild(note);
  const inputs = fields.map((field) => {
    const label = document.createElement("label");
    label.textContent = field.label;
    const input = field.type === "textarea" ? document.createElement("textarea") : document.createElement("input");
    if (field.type !== "textarea") input.type = field.type === "date" ? "date" : field.type === "number" ? "number" : "text";
    else input.rows = 3;
    label.appendChild(input);
    form.appendChild(label);
    return { field, input };
  });
  const submit = document.createElement("button");
  submit.type = "submit";
  submit.textContent = "Continue";
  form.appendChild(submit);
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const parts = inputs.map(({ field, input }) => {
      const value = field.type === "date" && input.value ? toLetterDate(input.value) : input.value.trim();
      return `${field.label}: ${value || "(skipped)"}`;
    });
    inputs.forEach(({ input }) => { input.disabled = true; });
    submit.remove();
    sendMessage("Details: " + parts.join("; "), parts.join("\n"));
  });
  chatMessages.appendChild(form);
  scrollDown();
  const first = form.querySelector("input, textarea");
  if (first) first.focus();
}

async function sendMessage(text, displayText) {
  addChatMessage(displayText || text, "user");
  history.push({ role: "user", content: text });
  chatForm.querySelector("button").disabled = true;
  const typing = addChatMessage("Thinking...", "bot typing");
  try {
    const res = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ messages: history }) });
    const data = await res.json();
    typing.remove();
    if (!res.ok || !data.success) { addChatMessage(data.error || "Something went wrong.", "bot error"); history.pop(); return; }
    addChatMessage(data.reply, "bot");
    if (data.redirect) {
      Draft.save({ letter_type: data.redirect.letter_type, letter_name: data.redirect.letter_name, duration: "", salary: "" });
      setTimeout(() => { window.location.href = "/step2"; }, 1200);
      return;
    }
    history.push({ role: "assistant", content: data.history_text || data.reply });
    if (data.fields && data.fields.length) addDetailsForm(data.fields);
    if (data.letter) showLetter(data.letter, data.preview_html);
  } catch (err) {
    typing.remove();
    addChatMessage("Network error. Please try again.", "bot error");
    history.pop();
  } finally {
    chatForm.querySelector("button").disabled = false;
  }
}

chatForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";
  sendMessage(text).then(() => chatInput.focus());
});
