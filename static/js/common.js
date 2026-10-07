// static/js/common.js
// Shared helpers used across all three pages.

function showToast(message, type) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 5000);
}

function toLetterDate(isoDate) {
  if (!isoDate) return "";
  const [y, m, d] = isoDate.split("-");
  const month = new Date(`${isoDate}T00:00:00`).toLocaleString("en-US", { month: "long" });
  return `${d} ${month} ${y}`;
}

const Draft = {
  KEY: "offerDraft",

  save(data) {
    sessionStorage.setItem(Draft.KEY, JSON.stringify(data));
  },

  load() {
    const raw = sessionStorage.getItem(Draft.KEY);
    return raw ? JSON.parse(raw) : null;
  },

  update(partial) {
    const current = Draft.load() || {};
    Draft.save({ ...current, ...partial });
  },

  clear() {
    sessionStorage.removeItem(Draft.KEY);
  },

  requireOrRedirect(redirectTo) {
    const data = Draft.load();
    if (!data || !data.details || !data.letter_content) {
      window.location.href = redirectTo;
      return null;
    }
    return data;
  },
};


// Full-screen loading overlay shared by the details, review and send steps.
function showLoading(heading, messageHtml) {
  hideLoading();
  if (!document.getElementById("loading-spinner-style")) {
    const style = document.createElement("style");
    style.id = "loading-spinner-style";
    style.textContent = "@keyframes spin { to { transform: rotate(360deg); } }";
    document.head.appendChild(style);
  }
  const overlay = document.createElement("div");
  overlay.id = "loading-overlay";
  overlay.style.cssText = "position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(15,23,42,0.85);z-index:99999;display:flex;align-items:center;justify-content:center;";
  overlay.innerHTML = `
    <div style="background:white;border-radius:12px;padding:40px 50px;text-align:center;box-shadow:0 20px 50px rgba(0,0,0,0.3);max-width:400px;">
      <div style="width:64px;height:64px;border:6px solid #eef2ff;border-top-color:#1d4ed8;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 24px;"></div>
      <h3 style="margin:0 0 12px;color:#1e3a8a;font-size:20px;">${heading}</h3>
      <p style="margin:0;color:#6b7280;font-size:14px;line-height:1.5;">${messageHtml}</p>
    </div>`;
  document.body.appendChild(overlay);
}

function hideLoading() {
  const overlay = document.getElementById("loading-overlay");
  if (overlay) overlay.remove();
}
