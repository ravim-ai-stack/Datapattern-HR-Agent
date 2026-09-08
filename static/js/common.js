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
