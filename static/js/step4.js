const $ = (id) => document.getElementById(id);
const draft = Draft.requireOrRedirect("/step1");

function displayDate(dateText) {
  return (dateText || "").replace(/-/g, " ");
}

function candidateFirstName() {
  return (draft.receiver_name || "Candidate").split(" ")[0];
}

function defaultMailSubject() {
  const letterName = draft.details.letter_name || "Letter";
  const candidateName = draft.receiver_name || "Candidate";
  return `${letterName} - ${candidateName}`;
}

const HR_SIGNOFF = `Regards,
Mirthula R,
HR Executive,
9042977445
www.datapattern.ai`;

function pronouns(title) {
  const normalized = (title || "").trim().toLowerCase();
  if (normalized === "ms." || normalized === "mrs.") return { subject: "she", subjectCap: "She", object: "her", possessive: "her" };
  if (normalized === "mr.") return { subject: "he", subjectCap: "He", object: "him", possessive: "his" };
  return { subject: "they", subjectCap: "They", object: "them", possessive: "their" };
}

function candidateWithTitle() {
  const title = draft.details.title || "";
  const fullName = draft.receiver_name || "Candidate";
  return title ? `${title} ${fullName}` : fullName;
}

function defaultMailContent() {
  const name = candidateFirstName();
  const fullName = draft.receiver_name || "Candidate";
  const role = draft.role || "Intern";
  const joiningDate = displayDate(draft.details.joining_date);
  const duration = draft.details.duration || "the agreed period";
  const letterType = draft.details.letter_type;

  if (letterType === "offer") {
    return `Dear ${name},

Congratulations on being selected to join DataPattern!

We are delighted to welcome you to the team and are confident that you will have a successful and rewarding journey with us.

Please find your offer letter attached for your reference. Your joining date is ${joiningDate || "as mentioned in the attached letter"}.

Kindly review the offer letter, sign it digitally, and return the signed copy to us at the earliest. We request you to complete this process before your joining date.

We look forward to welcoming you in DataPattern.

${HR_SIGNOFF}`;
  }

  if (letterType === "relieving" || letterType === "experience") {
    return `Dear ${fullName},

Please find your attached relieving and experience letter for your records.

On behalf of the organization, I would like to thank you for your contributions and wish you continued success in your future endeavors.

Should you require any further assistance, please feel free to reach out.

Wishing you all the very best for the future.

${HR_SIGNOFF}`;
  }

  if (letterType === "internship_offer") {
    return `Dear ${name},

We are pleased to offer you the position of Intern at DataPattern. Congratulations on your selection.

Please find attached your internship offer letter containing the details of your internship, including the duration, joining date, and terms and conditions. We request you to review the document carefully and confirm your acceptance by replying to this email within 3 days.

If you have any questions or require further clarification, please feel free to contact us.

We look forward to having you join our team and wish you a successful internship experience with us.

${HR_SIGNOFF}`;
  }

  if (letterType === "internship_certificate") {
    const p = pronouns(draft.details.title);
    const candidate = candidateWithTitle();
    const fromDate = joiningDate || "the start date";
    const toDate = displayDate(draft.details.end_date) || "the completion date";
    return `This is to certify that ${candidate} has successfully completed ${p.possessive} internship at DataPattern from ${fromDate} to ${toDate}.

During the internship period, ${p.subject} worked with dedication and sincerity, demonstrating a positive attitude, willingness to learn, and professionalism in carrying out the tasks assigned to ${p.object}. ${p.subjectCap} actively participated in the assigned activities and completed ${p.possessive} responsibilities to the satisfaction of the organization.

We appreciate ${p.possessive} contribution during the internship and wish ${p.object} every success in ${p.possessive} future academic and professional endeavors.

${HR_SIGNOFF}`;
  }

  if (letterType === "completion") {
    return `This is to certify that ${fullName} has successfully completed the internship at DataPattern from ${joiningDate || "the joining date"} for ${duration}.

During the internship period, the intern worked with dedication and sincerity, demonstrating a positive attitude, willingness to learn, and professionalism in carrying out the tasks assigned. The intern actively participated in the assigned activities and completed the responsibilities to the satisfaction of the organization.

We appreciate the contribution during the internship and wish every success in future academic and professional endeavors.`;
  }

  if (letterType === "it_asset_return_clearance") {
    return `Dear ${name},

Please find the attached IT Asset Return & Clearance letter for your records.

Kindly check the document carefully and fill in the required details regarding the return of company IT assets.

Please contact the HR or administration team if any clarification is required.

${HR_SIGNOFF}`;
  }

  if (letterType === "it_asset_issuance_onboarding") {
    return `Dear ${name},

Please find the attached IT Asset Issuance & Onboarding letter for your records.

Kindly check the document carefully and fill in the required details of the IT assets and resources issued to you.

Please contact the HR or administration team if any clarification is required.

${HR_SIGNOFF}`;
  }

  return draft.welcome_message || `Dear ${name},\n\nPlease find the attached letter for your reference.`;
}

if (draft) {
  $("candidate-summary").textContent = [
    draft.details.letter_name,
    draft.receiver_name,
    draft.role,
    draft.details.salary || "Salary not defined",
  ].filter(Boolean).join(" | ");
  $("email_subject").value = draft.email_subject || defaultMailSubject();
  $("email_message").value = draft.email_message || defaultMailContent();
}

async function sendEmail() {
  const files = Array.from($("attachment").files);
  const recipient = $("recipient_email").value.trim();
  const subject = $("email_subject").value.trim();
  const message = $("email_message").value.trim();

  if (!files.length) return showToast("Please upload the final document.", "error");
  if (!subject) return showToast("Please enter the email subject.", "error");
  if (!message) return showToast("Please enter the mail content.", "error");
  if (!recipient) return showToast("Please enter the recipient email.", "error");

  Draft.update({ email_subject: subject, email_message: message });

  const form = new FormData();
  ["sender_email", "recipient_email", "cc_email"].forEach((id) => form.append(id, $(id).value.trim()));
  form.append("receiver_name", draft.receiver_name);
  form.append("email_subject", subject);
  form.append("welcome_message", message);
  form.append("role", draft.role);
  form.append("letter_type", draft.details.letter_type);
  files.forEach((file) => form.append("attachment", file));

  const btn = $("btn-send");
  btn.disabled = true;
  btn.textContent = "Sending...";

  try {
    const res = await fetch("/api/send-email", { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok || !data.success) return showToast(data.message || "Failed to send email.", "error");
    showToast(data.message, "success");
    Draft.clear();
    setTimeout(() => window.location.href = "/step1", 2200);
  } catch (_) {
    showToast("Network error while sending email.", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Send letter email";
  }
}

$("btn-send").addEventListener("click", sendEmail);
