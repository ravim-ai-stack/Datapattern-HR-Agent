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
};
const detailConfig = selection && REDUCED_DETAIL_TYPES[selection.letter_type];

document.querySelectorAll('[data-field="location"], [data-field="duration"], [data-field="salary"]').forEach((el) => {
  el.classList.toggle("hidden", Boolean(detailConfig));
});
document.querySelector('[data-field="joining_date"]').classList.toggle("hidden", Boolean(detailConfig && detailConfig.hideDate));
document.querySelector('[data-field="end_date"]').classList.toggle("hidden", !(detailConfig && detailConfig.showEndDate));
$("joining-date-label").textContent = (detailConfig && detailConfig.dateLabel) || "Joining Date";

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

  if (!name || !role) {
    showToast("Please fill in the Candidate Name and Role.", "error");
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

  const btn = $("btn-generate");
  btn.disabled = true;
  btn.textContent = "Generating...";

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
    window.location.href = "/step3";
  } catch (_) {
    showToast("Network error while generating the letter.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate letter";
  }
}

$("btn-generate").addEventListener("click", generateDraft);
