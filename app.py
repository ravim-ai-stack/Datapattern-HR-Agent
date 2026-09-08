"""DataPattern HR letter generator."""
import os
from io import BytesIO
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, send_file
from modules.offer_letter import build_letter_body_html, build_letter_html, dispatch_offer_email, generate_letter_docx, generate_letter_jpeg, generate_letter_pdf, letter_content, validate_letter_details
load_dotenv(); app = Flask(__name__); app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
LETTER_TYPES = {"internship_offer": {"name": "Internship Offer Letter"}, "internship_certificate": {"name": "Internship Completion Certificate"}, "completion": {"name": "Employee Confirmation Letter"}, "offer": {"name": "Offer Letter"}, "it_asset_return_clearance": {"name": "IT Asset Return & Clearance Letter"}, "it_asset_issuance_onboarding": {"name": "IT Asset Issuance & Onboarding Letter"}, "relieving": {"name": "Relieving Letter"}, "experience": {"name": "Experience Letter"}}
def _welcome_message(role, letter_name): return f"We are pleased to share your {letter_name} for the position of {role} at DataPattern.\nPlease review the attached letter and let us know if you have any questions."
@app.route("/")
def index(): return redirect("/step1")
@app.route("/step1")
def step1(): return render_template("step1.html", active_step=1, letter_types=LETTER_TYPES)
@app.route("/step2")
def step2(): return render_template("step2.html", active_step=2)
@app.route("/step3")
def step3(): return render_template("step3.html", active_step=3)
@app.route("/step4")
def step4(): return render_template("step4.html", active_step=4, sender_email=os.getenv("SYSTEM_SENDER_EMAIL", ""))
@app.route("/api/generate-draft", methods=["POST"])
def generate_draft():
    data = request.get_json(force=True) or {}; kind = (data.get("letter_type") or "").strip(); terms = LETTER_TYPES.get(kind); name, role = (data.get("name") or "").strip(), (data.get("role") or "").strip()
    if not terms: return jsonify(success=False, error="Please select a letter type first."), 400
    if not name or not role: return jsonify(success=False, error="Candidate Name and Role are required."), 400
    details = {"title": (data.get("title") or "Mr.").strip(), "name": name, "role": role, "location": (data.get("location") or "").strip(), "joining_date": (data.get("joining_date") or "").strip(), "end_date": (data.get("end_date") or "").strip(), "letter_type": kind, "letter_name": terms["name"], "duration": (data.get("duration") or "").strip(), "salary": (data.get("salary") or "").strip()}
    content = letter_content(details); validation = validate_letter_details(details, content)
    if not validation["valid"]: return jsonify(success=False, error=" ".join(validation["errors"]), validation=validation), 422
    filename = f"{name.replace(' ', '_')}_{terms['name'].replace(' ', '_')}.docx"
    return jsonify(success=True, filename=filename, receiver_name=name, welcome_message=_welcome_message(role, terms["name"]), letter_content=content, details=details, validation=validation, preview_html=build_letter_html(details, content), body_html=build_letter_body_html(details, content))
@app.route("/api/update-draft", methods=["POST"])
def update_draft():
    data = request.get_json(force=True) or {}; details, content, edits = data.get("details") or {}, (data.get("letter_content") or "").strip(), data.get("letter_blocks") or []
    if not details.get("name") or not details.get("letter_type") or not content: return jsonify(success=False, error="Letter details or content are missing."), 400
    validation = validate_letter_details(details, letter_content(details) if details.get("letter_type") in {"internship_offer", "internship_certificate", "offer", "relieving", "experience", "it_asset_return_clearance", "it_asset_issuance_onboarding"} else content)
    if not validation["valid"]: return jsonify(success=False, error=" ".join(validation["errors"]), validation=validation), 422
    filename = f"{details['name'].replace(' ', '_')}_{details['letter_name'].replace(' ', '_')}.docx"
    return jsonify(success=True, preview_html=build_letter_html(details, content, edits), body_html=build_letter_body_html(details, content, edits), filename=filename)
@app.route("/api/download", methods=["POST"])
def download_draft():
    data = request.get_json(force=True) or {}; details, content, edits = data.get("details") or {}, (data.get("letter_content") or "").strip(), data.get("letter_blocks") or []
    if not details.get("name") or not details.get("letter_type") or not content: return jsonify(success=False, error="Letter details or content are missing."), 400
    validation = validate_letter_details(details, letter_content(details) if details.get("letter_type") in {"internship_offer", "internship_certificate", "offer", "relieving", "experience", "it_asset_return_clearance", "it_asset_issuance_onboarding"} else content)
    if not validation["valid"]: return jsonify(success=False, error=" ".join(validation["errors"]), validation=validation), 422
    fmt = data.get("format", "word").lower()
    try:
        if fmt == "jpeg":
            jpeg, filename = generate_letter_jpeg(details)
            return send_file(BytesIO(jpeg), as_attachment=True, download_name=filename, mimetype="image/jpeg")
        docx, filename = generate_letter_docx(details, content, edits)
        if fmt == "pdf": return send_file(BytesIO(generate_letter_pdf(details, content, edits)), as_attachment=True, download_name=filename.replace(".docx", ".pdf"), mimetype="application/pdf")
        return send_file(BytesIO(docx), as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    except Exception as exc: return jsonify(success=False, error=f"Unable to create the download: {exc}"), 500
@app.route("/api/send-email", methods=["POST"])
def send_email():
    uploads = [f for f in request.files.getlist("attachment") if f.filename]
    if not uploads: return jsonify(success=False, message="Please upload the final document."), 400
    attachments = [(f.filename, f.read()) for f in uploads]
    if sum(len(data) for _, data in attachments) > app.config["MAX_CONTENT_LENGTH"]: return jsonify(success=False, message="Files exceed the 10MB limit."), 400
    result = dispatch_offer_email(recipient_email=request.form.get("recipient_email", ""), cc_email=request.form.get("cc_email", ""), candidate_name=request.form.get("receiver_name", ""), role=request.form.get("role", ""), attachments=attachments, sender_email=request.form.get("sender_email", ""), subject=request.form.get("email_subject", ""), custom_message=request.form.get("welcome_message", ""))
    return jsonify(result), 200 if result["success"] else 400
if __name__ == "__main__": app.run(debug=True, use_reloader=False, host="0.0.0.0", port=int(os.getenv("PORT", 5050)))
