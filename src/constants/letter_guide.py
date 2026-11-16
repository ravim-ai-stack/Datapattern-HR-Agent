"""Knowledge the HR Studio chatbot is taught: what each kind of letter needs, plus worked examples.

Edit this file to teach the chatbot new letter types or house rules; no other code change is needed.
"""

# letter kind -> (details worth asking for, what the letter must say / how it should read)
LETTER_GUIDE = {
    "Bonafide Certificate": (
        "role/department, joining date, purpose (optional)",
        "Certifies the person is currently employed/studying with DataPattern, since the joining date, in the given role. "
        "Neutral, factual, one or two paragraphs. Ends by stating it is issued on request for the stated purpose.",
    ),
    "Employment Verification Letter": (
        "role, joining date, employment type, current status",
        "Confirms employment facts only. No opinions on performance.",
    ),
    "Salary Certificate": (
        "role, monthly/annual salary, joining date, purpose",
        "States the gross salary exactly as given. Never estimate or invent a figure; if no salary is given, omit it.",
    ),
    "Address Proof Letter": (
        "role, joining date, residential address",
        "Confirms the employee's address on company records. Do not invent an address.",
    ),
    "No Objection Certificate (NOC)": (
        "role, what the NOC is for (visa, higher studies, another job, etc.), validity period",
        "States the company has no objection to the stated purpose. Mention the person remains bound by company policies.",
    ),
    "Appreciation Letter": (
        "role, what they achieved, project/period",
        "Warm, specific praise tied to the achievement given. End with encouragement.",
    ),
    "Warning Letter": (
        "role, the misconduct/issue, date(s), any earlier warnings, expected corrective action",
        "Firm, professional, non-abusive. States the issue, the policy concern, expected improvement and consequence of repetition.",
    ),
    "Recommendation Letter": (
        "role, duration worked, strengths, who it is addressed to",
        "Positive, specific, written from the company. Only mention strengths the user provided.",
    ),
    "Promotion Letter": (
        "old role, new role, effective date, revised salary (optional)",
        "Congratulates, states the new designation and effective date; terms otherwise unchanged unless stated.",
    ),
    "Transfer Letter": (
        "current location, new location, effective date, role",
        "States the transfer, effective date and reporting instructions.",
    ),
    "Resignation Acceptance Letter": (
        "role, resignation date, last working day",
        "Acknowledges the resignation, confirms the last working day, thanks the person, mentions handover and clearance.",
    ),
    "Notice / Circular": (
        "subject, audience, effective date, the message",
        "Addressed to 'All Employees' (or the given audience). Clear subject line, short numbered points if helpful.",
    ),
    "Experience-related or any other letter": (
        "whatever the purpose naturally requires",
        "Use the closest letter above as a pattern; keep it formal and brief.",
    ),
}

# Worked examples the model imitates for flow and tone.
EXAMPLES = """Example 1 -- enough information, so draft immediately
User: generate a bonafide for Ravi
Assistant: Please fill in these details, or leave blank to skip.
<ask>
Role / department
Joining date | date
</ask>
User: Details: Role / department: Software Engineer; Joining date: 3 March 2024
Assistant: Here is the Bonafide Certificate for Ravi.
<letter name="Bonafide Certificate" recipient="Ravi">
Date: 14 October 2026

To Whom It May Concern,

This is to certify that Ravi is employed with DataPattern as a Software Engineer and has been associated with the company since 3 March 2024.

This certificate is issued at their request for whatever lawful purpose it may serve.
</letter>

Example 2 -- the user skips details, so write the letter without them and do not ask again
User: salary certificate for Meena
Assistant: Please fill in these details, or leave blank to skip.
<ask>
Role
Monthly salary | number
</ask>
User: Details: Role: (skipped); Monthly salary: (skipped)
Assistant: Here is the Salary Certificate for Meena.
<letter name="Salary Certificate" recipient="Meena">
Date: 14 October 2026

To Whom It May Concern,

This is to certify that Meena is employed with DataPattern. This certificate is issued at their request.
</letter>

Example 3 -- an edit request, so return the complete revised letter
User: make it shorter and mention the Chennai office
Assistant: Done, here is the shorter version.
<letter name="Bonafide Certificate" recipient="Ravi">
...complete revised letter...
</letter>"""


def guide_text():
    lines = ["Knowledge about common letter types (details worth asking for | how the letter should read):"]
    for kind, (needs, style) in LETTER_GUIDE.items():
        lines.append(f"- {kind}: ask about [{needs}]. {style}")
    return "\n".join(lines)
