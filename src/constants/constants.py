"""Fixed values: status codes, letter types, layout and certificate constants."""


COMPANY_NAME = "DataPattern"


CERTIFICATE_NAVY = (10, 34, 74)


CERTIFICATE_BLACK = (20, 20, 20)


CERTIFICATE_TEXT_LEFT = 140


CERTIFICATE_TEXT_RIGHT = 1860


# Bounding boxes (matched to the reference certificate) that get whited-out and
# redrawn with the candidate's own details; everything outside them (title,
# border, seal, DataPattern logo, and Indhirajith's signature block) stays as-is.
CERTIFICATE_NAME_BAND = (CERTIFICATE_TEXT_LEFT, 565, CERTIFICATE_TEXT_RIGHT, 692)


CERTIFICATE_SENTENCE_BAND = (CERTIFICATE_TEXT_LEFT, 728, CERTIFICATE_TEXT_RIGHT, 826)


CERTIFICATE_APPRECIATION_BAND = (CERTIFICATE_TEXT_LEFT, 855, CERTIFICATE_TEXT_RIGHT, 895)


SIGNOFF_LINES = [
    "Regards,",
    "Mirthula R,",
    "HR Executive,",
    "9042977445",
    "www.datapattern.ai",
    "",
    "DataPattern",
]


PAGE_WIDTH = 1240


PAGE_HEIGHT = 1754


MARGIN_X = 90


MARGIN_Y = 90


# Matches the date formats baked into the source templates so they can be
# swapped for the candidate's actual joining date: "2 September 2026",
# "Sep 2, 2026", and the numeric "01-08-2026" / "01/08/2026" style.
TEMPLATE_DATE_PATTERN = r"\b(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]{3}\s+\d{1,2},\s+\d{4}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\b"


CERTIFICATE_FONT_CANDIDATES = {
    "bold": ["C:/Windows/Fonts/timesbd.ttf", "C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/arialbd.ttf"],
    "italic": ["C:/Windows/Fonts/timesi.ttf", "C:/Windows/Fonts/ariali.ttf", "C:/Windows/Fonts/arial.ttf"],
    "regular": ["C:/Windows/Fonts/times.ttf", "C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/arial.ttf"],
}


# Letter types whose template file isn't simply "<letter_type>.docx".
TEMPLATE_FILENAMES = {
    "offer": "DataPattern Offer Letter - Master 1.docx",
    "appraisal": "Appraisal LetterPad.docx",
}


# Appraisal letter: every Annexure A row takes a Per Month and a Per Annum
# amount from the form (key, Annexure A row label); fields are "<key>_month"
# and "<key>_year".
APPRAISAL_ROWS = [
    ("basic", "Basic"),
    ("hra", "HRA"),
    ("conveyance", "Conveyance"),
    ("medical_allowance", "Medical Allowance"),
    ("special_allowance", "Special Allowance"),
    ("gross", "Total Gross Salary"),
    ("pf", "Employer PF Contribution"),
    ("medical_insurance", "Medical Insurance"),
    ("ctc", "Total CTC"),
]
APPRAISAL_FIELD_LABELS = {"rating": "Appraisal Rating", "effective_date": "Effective From"}
for _key, _label in APPRAISAL_ROWS:
    APPRAISAL_FIELD_LABELS[f"{_key}_month"] = f"{_label} (Per Month)"
    APPRAISAL_FIELD_LABELS[f"{_key}_year"] = f"{_label} (Per Annum)"


# The two IT asset forms are fillable checkbox forms (all fields live in
# table cells), unlike the other templates which are prose letters with
# `[Bracket]` placeholders in paragraph text. They need their own field-fill
# logic instead of the generic bracket-replacement path.
IT_ASSET_FORM_DATE_LABELS = {
    "it_asset_issuance_onboarding": "Joining Date:",
    "it_asset_return_clearance": "Return Date:",
}


COMPANY_ADDRESS = "Address: No. G-1, Door/No: 4/608, V.O.C Street, O.M.R Road, Kottivakkam, Chennai-600041."


# HTTP status codes
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_UNPROCESSABLE = 422
HTTP_INTERNAL_ERROR = 500

# Request limits
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Letter types offered on step 1 (key -> display name)
LETTER_TYPES = {
    "internship_offer": {"name": "Internship Offer Letter"},
    "internship_certificate": {"name": "Internship Completion Certificate"},
    "completion": {"name": "Employee Confirmation Letter"},
    "offer": {"name": "Offer Letter"},
    "appraisal": {"name": "Appraisal Letter"},
    "it_asset_return_clearance": {"name": "IT Asset Return & Clearance Letter"},
    "it_asset_issuance_onboarding": {"name": "IT Asset Issuance & Onboarding Letter"},
    "relieving": {"name": "Relieving Letter"},
    "experience": {"name": "Experience Letter"},
}

# Letter types whose preview/validation is re-derived from the template
TEMPLATE_BACKED_LETTER_TYPES = {
    "internship_offer", "internship_certificate", "offer", "appraisal", "relieving", "experience",
    "it_asset_return_clearance", "it_asset_issuance_onboarding",
}

# Built-in templates the HR Studio chatbot reads for house style and wording.
CHAT_KNOWLEDGE_TEMPLATES = ["experience", "relieving", "internship_offer", "offer"]
CHAT_KNOWLEDGE_CHAR_LIMIT = 3500
CUSTOM_LETTER_TYPE = "custom"

DEFAULT_TITLE = "Mr."
MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MIME_PDF = "application/pdf"
MIME_JPEG = "image/jpeg"


# Phrases in a chatbot message that mean "one of the built-in letters"; those are sent to the
# step 2 details form instead of being drafted by the model. Order matters: most specific first.
BUILTIN_LETTER_PATTERNS = [
    ("internship_offer", r"internship\s+(offer|appointment)"),
    ("internship_certificate", r"(internship|intern)\s+(completion\s+)?certificate|completion\s+certificate"),
    ("it_asset_return_clearance", r"it\s+asset\s+(return|clearance)|asset\s+(return|clearance)"),
    ("it_asset_issuance_onboarding", r"it\s+asset\s+(issuance|issue|onboarding)|asset\s+(issuance|onboarding)"),
    ("completion", r"(employee\s+)?confirmation\s+letter|confirmation\s+of\s+employment\s+letter"),
    ("relieving", r"reliev(ing|e)\s+(letter|order)"),
    ("experience", r"experience\s+(letter|certificate)"),
    ("appraisal", r"apprais(al|e)\s+letter|increment\s+letter|salary\s+(revision|increment)\s+letter"),
    ("offer", r"offer\s+letter|appointment\s+letter|job\s+offer"),
]


# Typo-tolerant fallback: message word-groups are fuzzy-compared against these phrases.
BUILTIN_LETTER_PHRASES = {
    "internship_offer": ["internship offer letter", "internship offer", "internship appointment letter"],
    "internship_certificate": ["internship certificate", "internship completion certificate", "completion certificate"],
    "it_asset_return_clearance": ["it asset return", "it asset clearance", "asset return clearance"],
    "it_asset_issuance_onboarding": ["it asset issuance", "it asset onboarding", "asset issuance onboarding"],
    "completion": ["employee confirmation letter", "confirmation letter"],
    "relieving": ["relieving letter", "relieving", "releiving"],
    "experience": ["experience letter", "experience certificate"],
    "appraisal": ["appraisal letter", "increment letter", "salary revision letter"],
    "offer": ["offer letter", "appointment letter", "job offer"],
}
FUZZY_MATCH_THRESHOLD = 0.84


# Sign-off for chatbot (custom) letters, matching the internship offer letter.
CUSTOM_SIGNOFF_CLOSING = "Sincerely,"
CUSTOM_SIGNATORY_NAME = "Indhirajith K"
CUSTOM_SIGNATORY_TITLE = "Head Operations Coimbatore"
