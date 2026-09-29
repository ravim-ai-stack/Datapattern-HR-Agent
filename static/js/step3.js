const $ = (id) => document.getElementById(id);
const draft = Draft.requireOrRedirect("/step1");

// Helper to show/hide loading overlay
function showLoading(formatName) {
  // Remove any existing overlay first
  hideLoading();
  
  const overlay = document.createElement("div");
  overlay.id = "loading-overlay";
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(15, 23, 42, 0.85);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
  `;
  
  const content = document.createElement("div");
  content.style.cssText = `
    background: white;
    border-radius: 12px;
    padding: 40px 50px;
    text-align: center;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3);
    max-width: 400px;
  `;
  
  const spinner = document.createElement("div");
  spinner.style.cssText = `
    width: 64px;
    height: 64px;
    border: 6px solid #eef2ff;
    border-top-color: #1d4ed8;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 24px;
  `;
  
  const heading = document.createElement("h3");
  heading.style.cssText = `
    margin: 0 0 12px;
    color: #1e3a8a;
    font-size: 20px;
  `;
  heading.textContent = "Generating Document...";
  
  const message = document.createElement("p");
  message.style.cssText = `
    margin: 0;
    color: #6b7280;
    font-size: 14px;
    line-height: 1.5;
  `;
  message.innerHTML = `Please wait while we generate your <strong style="color: #f97316;">${formatName}</strong> document.<br><br><small>This may take up to 30 seconds for PDF files.</small>`;
  
  // Add CSS animation for spinner
  if (!document.getElementById("loading-spinner-style")) {
    const style = document.createElement("style");
    style.id = "loading-spinner-style";
    style.textContent = `
      @keyframes spin {
        to { transform: rotate(360deg); }
      }
    `;
    document.head.appendChild(style);
  }
  
  content.appendChild(spinner);
  content.appendChild(heading);
  content.appendChild(message);
  overlay.appendChild(content);
  document.body.appendChild(overlay);
}

function hideLoading() {
  const overlay = document.getElementById("loading-overlay");
  if (overlay) {
    overlay.remove();
  }
}

if (draft) {
  $("candidate-summary").textContent = [
    draft.details.letter_name,
    draft.receiver_name,
    draft.role,
    draft.details.salary || "Salary not defined",
  ].filter(Boolean).join(" | ");
  $("letter_content").innerHTML = draft.body_html || "";
  $("letter_content").dataset.letterType = draft.details && draft.details.letter_type || "";
  resizeLetterEditor();
  $("letter-preview").innerHTML = draft.preview_html || "";
  $("signature-snippet-name").textContent = draft.receiver_name || "Employee Name";
  $("btn-download-jpeg").classList.toggle("hidden", draft.details.letter_type !== "internship_certificate");
}

function resizeLetterEditor() {
  const editor = $("letter_content");
  if (!editor) return;
  editor.style.height = "297mm";
  const pageHeight = 1122; // A4 height at 96 CSS pixels per inch.
  const required = Math.max(pageHeight, editor.scrollHeight + 24);
  const minimumPages = editor.dataset.letterType === "internship_offer" ? 2 : 1;
  const pages = Math.max(minimumPages, Math.ceil(required / pageHeight));
  editor.style.height = `${pages * pageHeight}px`;
}

$("letter_content").addEventListener("input", resizeLetterEditor);

function employeeSignatureText() {
  return `Employee Name: ${draft.receiver_name || ""}\nSignature:`;
}

function extractLetterBlocks(container) {
  const blocks = [];
  Array.from(container.children).forEach((node) => {
    if (node.tagName === "TABLE") {
      const rows = Array.from(node.rows).map((row) =>
        Array.from(row.cells).map((cell) => cell.innerText.trim())
      );
      if (rows.some((row) => row.some((cell) => cell))) blocks.push({ type: "table", rows });
      return;
    }
    const text = node.innerText.trim();
    if (text) blocks.push({ type: "p", text });
  });
  return blocks;
}

function blocksToText(blocks) {
  return blocks
    .map((block) => (block.type === "table" ? block.rows.map((row) => row.join(" | ")).join("\n") : block.text))
    .join("\n\n");
}

function placeCaretForDrop(event) {
  let range = null;
  if (document.caretRangeFromPoint) {
    range = document.caretRangeFromPoint(event.clientX, event.clientY);
  } else if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(event.clientX, event.clientY);
    if (pos) {
      range = document.createRange();
      range.setStart(pos.offsetNode, pos.offset);
      range.collapse(true);
    }
  }
  if (!range) return;
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
}

function insertAtCursor(text) {
  const editor = $("letter_content");
  editor.focus();
  const selection = window.getSelection();
  let range;
  if (selection.rangeCount && editor.contains(selection.anchorNode)) {
    range = selection.getRangeAt(0);
  } else {
    range = document.createRange();
    range.selectNodeContents(editor);
    range.collapse(false);
  }
  range.deleteContents();
  const p = document.createElement("p");
  text.split("\n").forEach((line, index) => {
    if (index > 0) p.appendChild(document.createElement("br"));
    p.appendChild(document.createTextNode(line));
  });
  range.insertNode(p);
  range.setStartAfter(p);
  range.collapse(true);
  selection.removeAllRanges();
  selection.addRange(range);
  resizeLetterEditor();
}

$("btn-add-signature").addEventListener("click", () => insertAtCursor(employeeSignatureText()));
$("signature-snippet").addEventListener("dragstart", (event) => {
  event.dataTransfer.setData("text/plain", employeeSignatureText());
});
$("letter_content").addEventListener("dragover", (event) => event.preventDefault());
$("letter_content").addEventListener("drop", (event) => {
  event.preventDefault();
  placeCaretForDrop(event);
  insertAtCursor(event.dataTransfer.getData("text/plain") || employeeSignatureText());
});

async function saveLetter() {
  const letterBlocks = extractLetterBlocks($("letter_content"));
  const letterContent = blocksToText(letterBlocks);
  const response = await fetch("/api/update-draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ details: draft.details, letter_content: letterContent, letter_blocks: letterBlocks }),
  });
  const data = await response.json();
  if (!response.ok || !data.success) throw new Error(data.error || "Unable to update letter.");
  Draft.update({ letter_content: letterContent, preview_html: data.preview_html, body_html: data.body_html, filename: data.filename });
  $("letter-preview").innerHTML = data.preview_html;
  return data;
}

$("btn-preview").addEventListener("click", async () => {
  try {
    await saveLetter();
    $("preview-modal").classList.remove("hidden");
  } catch (e) {
    showToast(e.message, "error");
  }
});

$("btn-close-preview").addEventListener("click", () => $("preview-modal").classList.add("hidden"));
$("preview-modal").addEventListener("click", (e) => {
  if (e.target === $("preview-modal")) $("preview-modal").classList.add("hidden");
});
$("btn-download").addEventListener("click", () => $("download-menu").classList.toggle("hidden"));

async function downloadLetter(format) {
  const formatName = format === "pdf" ? "PDF" : format === "jpeg" ? "JPEG" : "Word";
  
  try {
    // Show loading overlay
    showLoading(formatName);
    
    await saveLetter();
    
    const letterBlocks = extractLetterBlocks($("letter_content"));
    const response = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ details: draft.details, letter_content: blocksToText(letterBlocks), letter_blocks: letterBlocks, format }),
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || "Unable to download the letter.");
    }
    
    const file = await response.blob();
    const extension = format === "pdf" ? ".pdf" : format === "jpeg" ? ".jpg" : ".docx";
    const link = document.createElement("a");
    link.href = URL.createObjectURL(file);
    link.download = (draft.filename || "letter.docx").replace(/\.docx$/i, extension);
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    
    showToast(`${formatName} downloaded successfully!`, "success");
  } catch (e) {
    showToast(e.message, "error");
  } finally {
    // Hide loading overlay
    hideLoading();
  }
}

document.querySelectorAll("[data-format]").forEach((button) => button.addEventListener("click", async () => {
  $("download-menu").classList.add("hidden");
  await downloadLetter(button.dataset.format);
}));

$("btn-continue").addEventListener("click", async () => {
  try {
    await saveLetter();
    window.location.href = "/step4";
  } catch (e) {
    showToast(e.message, "error");
  }
});
