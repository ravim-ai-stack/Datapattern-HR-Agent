const $ = (id) => document.getElementById(id);
const selection = Draft.load();

if (!selection || !selection.letter_type) {
  window.location.href = "/step1";
} else {
  $("letter-type-badge").textContent = selection.letter_name;
}

// Experience, relieving, and IT asset letters only collect Title, Full Name,
// Role/Designation, and the relevant date(s) -- location/duration/salary
// don't apply, and experience additionally needs a distinct end date. The IT
// asset forms don't collect a date at all -- their date field is left blank
// on the form for manual sign-off.
const REDUCED_DETAIL_TYPES = {
  experience: { dateLabel: "Start Date *", showEndDate: true },
  relieving: { dateLabel: "Last Date *", showEndDate: false },
  internship_certificate: { dateLabel: "From Date *", showEndDate: true },
  it_asset_issuance_onboarding: { hideDate: true },
  it_asset_return_clearance: { hideDate: true },
  appraisal: { dateLabel: "Letter Date *", showEndDate: false, appraisal: true },
};
const ANNEX_KEYS = ["basic", "hra", "conveyance", "medical_allowance", "special_allowance", "gross", "pf", "medical_insurance", "ctc"];
const APPRAISAL_FIELDS = ["rating", "effective_date", ...ANNEX_KEYS.flatMap((k) => [`${k}_month`, `${k}_year`])];
const EARNINGS = ["basic", "hra", "conveyance", "medical_allowance", "special_allowance"];

// Per Annum and the totals are pre-filled from what's typed, until the user
// types into that cell themselves (their value is then left alone).
function amount(id) {
  const n = parseFloat(($(id).value || "").replace(/,/g, ""));
  return Number.isNaN(n) ? 0 : n;
}
function setAuto(id, value) {
  if ($(id).dataset.manual) return;
  $(id).value = value ? (Math.round(value * 100) / 100).toString() : "";
}
function recalcAnnexure() {
  ["month", "year"].forEach((col) => {
    if (col === "year") ANNEX_KEYS.forEach((k) => { if (k !== "gross" && k !== "ctc") setAuto(`${k}_year`, amount(`${k}_month`) * 12); });
    const gross = EARNINGS.reduce((sum, k) => sum + amount(`${k}_${col}`), 0);
    setAuto(`gross_${col}`, gross);
    setAuto(`ctc_${col}`, gross + amount(`pf_${col}`) + amount(`medical_insurance_${col}`));
  });
}
document.querySelectorAll("[data-annex]").forEach((input) => {
  input.addEventListener("input", () => {
    input.dataset.manual = input.value.trim() ? "1" : "";
    recalcAnnexure();
  });
});
const detailConfig = selection && REDUCED_DETAIL_TYPES[selection.letter_type];

document.querySelectorAll('[data-field="location"], [data-field="duration"], [data-field="salary"]').forEach((el) => {
  el.classList.toggle("hidden", Boolean(detailConfig));
});
document.querySelector('[data-field="joining_date"]').classList.toggle("hidden", Boolean(detailConfig && detailConfig.hideDate));
document.querySelector('[data-field="end_date"]').classList.toggle("hidden", !(detailConfig && detailConfig.showEndDate));
$("joining-date-label").textContent = (detailConfig && detailConfig.dateLabel) || "Joining Date";

document.querySelector('[data-field="role"]').classList.toggle("hidden", Boolean(detailConfig && detailConfig.appraisal));
document.querySelector('[data-field="appraisal"]').classList.toggle("hidden", !(detailConfig && detailConfig.appraisal));

function syncSalaryState() {
  $("salary").classList.toggle("salary-pending", !$("salary").value.trim());
}

["name", "role", "location"].forEach((id) => {
  $(id).addEventListener("blur", () => {
    $(id).value = $(id).value.trim();
  });
});

$("salary").addEventListener("input", syncSalaryState);
$("salary").addEventListener("blur", syncSalaryState);
$("btn-edit-salary").addEventListener("click", () => {
  $("salary").focus();
  syncSalaryState();
});
syncSalaryState();

async function generateDraft() {
  const name = $("name").value.trim();
  const role = $("role").value.trim();
  const location = $("location").value.trim();

  $("name").value = name;
  $("role").value = role;
  $("location").value = location;

  const roleNeeded = !(detailConfig && detailConfig.appraisal);
  if (!name || (roleNeeded && !role)) {
    showToast(roleNeeded ? "Please fill in the Candidate Name and Role." : "Please fill in the Candidate Name.", "error");
    return;
  }

  if (detailConfig && !detailConfig.hideDate) {
    if (!$("joining_date").value) {
      showToast(`Please fill in the ${detailConfig.dateLabel.replace(" *", "")}.`, "error");
      return;
    }
    if (detailConfig.showEndDate && !$("end_date").value) {
      showToast("Please fill in the End Date.", "error");
      return;
    }
  }

  const appraisalFields = {};
  if (detailConfig && detailConfig.appraisal) {
    APPRAISAL_FIELDS.forEach((id) => { appraisalFields[id] = $(id).value.trim(); });
    if (APPRAISAL_FIELDS.some((id) => !appraisalFields[id])) {
      showToast("Please fill in the appraisal rating, effective date and all Annexure A amounts (Per Month and Per Annum).", "error");
      return;
    }
  }

  const btn = $("btn-generate");
  btn.disabled = true;
  btn.textContent = "Generating...";
  showLoading("Generating Letter...", "Please wait while we prepare your letter.<br><br><small>This may take a few seconds.</small>");
  let navigating = false;

  try {
    const res = await fetch("/api/generate-draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...selection,
        title: $("title").value,
        name,
        role,
        location,
        joining_date: toLetterDate($("joining_date").value),
        end_date: toLetterDate($("end_date").value),
        duration: $("duration").value.trim(),
        salary: $("salary").value.trim(),
        ...appraisalFields,
      }),
    });
    const data = await res.json();
    if (!res.ok || !data.success) {
      showToast(data.error || "Failed to generate letter.", "error");
      return;
    }
    Draft.save({
      ...selection,
      filename: data.filename,
      role,
      receiver_name: data.receiver_name,
      welcome_message: data.welcome_message,
      letter_content: data.letter_content,
      details: data.details,
      preview_html: data.preview_html,
      body_html: data.body_html,
    });
    navigating = true;
    window.location.href = "/step3";
  } catch (_) {
    showToast("Network error while generating the letter.", "error");
  } finally {
    if (!navigating) hideLoading();  // keep the overlay up while the next page loads
    btn.disabled = false;
    btn.textContent = "Generate letter";
  }
}

$("btn-generate").addEventListener("click", generateDraft);
