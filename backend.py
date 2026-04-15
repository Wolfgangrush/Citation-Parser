import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pdfplumber
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, text
from werkzeug.utils import secure_filename

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "./instance/citations.db"))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BASE_DIR / DATABASE_PATH
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

PDF_STORAGE = Path(os.getenv("PDF_STORAGE_PATH", "./pdfs_received"))
if not PDF_STORAGE.is_absolute():
    PDF_STORAGE = BASE_DIR / PDF_STORAGE
PDF_STORAGE.mkdir(parents=True, exist_ok=True)

DELETE_PDF_AFTER_PROCESSING = os.getenv("DELETE_PDF_AFTER_PROCESSING", "true").lower() == "true"
AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").lower()
AI_MAX_CHARS = int(os.getenv("AI_MAX_CHARS", "350000"))

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DATABASE_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
CORS(app)
db = SQLAlchemy(app)


class Citation(db.Model):
    __tablename__ = "citations"

    id = db.Column(db.Integer, primary_key=True)
    citation_name = db.Column(db.String(500), nullable=False, index=True)
    normalized_name = db.Column(db.String(500), nullable=False, index=True)
    original_filename = db.Column(db.String(500), index=True)
    normalized_filename = db.Column(db.String(500), index=True)
    file_path = db.Column(db.String(500))

    court = db.Column(db.String(200), index=True)
    year = db.Column(db.Integer, index=True)
    petition_type = db.Column(db.String(100), index=True)
    case_number = db.Column(db.String(200), index=True)
    neutral_citation = db.Column(db.String(200), index=True)
    bench = db.Column(db.JSON)
    party_names = db.Column(db.JSON)
    disposition = db.Column(db.String(300), index=True)
    cited_cases = db.Column(db.JSON)
    detected_format = db.Column(db.String(80), index=True)
    acts_referred = db.Column(db.JSON)
    headnote = db.Column(db.Text)
    important_principles = db.Column(db.JSON)
    subsections = db.Column(db.JSON)
    brief_facts = db.Column(db.Text)
    appearances = db.Column(db.JSON)
    order_type = db.Column(db.String(120), index=True)
    directions = db.Column(db.JSON)
    next_hearing_date = db.Column(db.String(50), index=True)

    sections = db.Column(db.JSON)
    laws = db.Column(db.JSON)
    holding = db.Column(db.Text)
    ratio = db.Column(db.Text)
    headnotes = db.Column(db.JSON)
    key_quotes = db.Column(db.JSON)
    judges = db.Column(db.JSON)
    date_judgment = db.Column(db.String(50), index=True)
    pdf_text = db.Column(db.Text)
    tags = db.Column(db.JSON)
    notes = db.Column(db.Text)

    scc_citation = db.Column(db.String(200), index=True)
    manupatra_citation = db.Column(db.String(200), index=True)
    indian_kanoon_url = db.Column(db.String(500), index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "citation_name": self.citation_name,
            "original_filename": self.original_filename,
            "court": self.court,
            "year": self.year,
            "petition_type": self.petition_type,
            "case_number": self.case_number,
            "neutral_citation": self.neutral_citation,
            "bench": self.bench or [],
            "party_names": self.party_names or [],
            "disposition": self.disposition,
            "cited_cases": self.cited_cases or [],
            "detected_format": self.detected_format,
            "acts_referred": self.acts_referred or [],
            "headnote": self.headnote,
            "important_principles": self.important_principles or [],
            "subsections": self.subsections or {},
            "brief_facts": self.brief_facts,
            "appearances": self.appearances or [],
            "order_type": self.order_type,
            "directions": self.directions or [],
            "next_hearing_date": self.next_hearing_date,
            "sections": self.sections or [],
            "laws": self.laws or [],
            "holding": self.holding,
            "ratio": self.ratio,
            "headnotes": self.headnotes or [],
            "key_quotes": self.key_quotes or [],
            "judges": self.judges or [],
            "date_judgment": self.date_judgment,
            "tags": self.tags or [],
            "notes": self.notes,
            "scc_citation": self.scc_citation,
            "manupatra_citation": self.manupatra_citation,
            "indian_kanoon_url": self.indian_kanoon_url,
            "decision_brief": decision_brief_for(self),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LegalProvision(db.Model):
    __tablename__ = "legal_provisions"

    id = db.Column(db.Integer, primary_key=True)
    act_key = db.Column(db.String(80), nullable=False, index=True)
    act_name = db.Column(db.String(300), nullable=False, index=True)
    section_no = db.Column(db.String(40), nullable=False, index=True)
    title = db.Column(db.String(500))
    text = db.Column(db.Text, nullable=False)
    source_file = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("act_key", "section_no", name="uq_legal_provision_act_section"),)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "act_key": self.act_key,
            "act_name": self.act_name,
            "section_no": self.section_no,
            "title": self.title,
            "text": self.text,
            "source_file": self.source_file,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


ACT_ALIASES = {
    "IPC": [
        "IPC",
        "Indian Penal Code",
        "Indian Penal Code, 1860",
    ],
    "CrPC": [
        "CrPC",
        "Cr.P.C.",
        "Code of Criminal Procedure",
        "Criminal Procedure Code",
        "Code of Criminal Procedure, 1973",
        "Criminal Procedure Code, 1973",
    ],
    "CPC": [
        "CPC",
        "C.P.C.",
        "Code of Civil Procedure",
        "Civil Procedure Code",
        "Code of Civil Procedure, 1908",
        "Civil Procedure Code, 1908",
    ],
    "BNS": [
        "BNS",
        "Bharatiya Nyaya Sanhita",
        "Bharatiya Nyaya Sanhita, 2023",
    ],
    "BNSS": [
        "BNSS",
        "Bharatiya Nagarik Suraksha Sanhita",
        "Bharatiya Nagarik Suraksha Sanhita, 2023",
    ],
    "BSA": [
        "BSA",
        "Bharatiya Sakshya Adhiniyam",
        "Bharatiya Sakshya Adhiniyam, 2023",
    ],
    "Evidence Act": [
        "Evidence Act",
        "Indian Evidence Act",
        "Indian Evidence Act, 1872",
    ],
    "Specific Relief Act": [
        "SRA",
        "Specific Relief Act",
        "Specific Relief Act, 1963",
    ],
    "RP Act": [
        "RP Act",
        "R.P. Act",
        "Representation of People Act",
        "Representation of People Act, 1951",
        "Representation of the People Act",
        "Representation of the People Act, 1951",
    ],
    "Maharashtra Co-operative Societies Act": [
        "MCS Act",
        "Maharashtra Cooperative Societies Act",
        "Maharashtra Cooperative Societies Act, 1960",
        "Maharashtra Co-operative Societies Act",
        "Maharashtra Co-operative Societies Act, 1960",
        "Maharashtra Societies Act",
    ],
    "Maharashtra Zilla Parishads Act": [
        "MZP Act",
        "Maharashtra Zilla Parishad Act",
        "Maharashtra Zilla Parishad Act, 1961",
        "Maharashtra Zilla Parishads Act",
        "Maharashtra Zilla Parishads Act, 1961",
        "Maharashtra Zilla Parishads and Panchayat Samitis Act",
        "Maharashtra Zilla Parishads and Panchayat Samitis Act, 1961",
    ],
}

ACT_DISPLAY_NAMES = {
    "IPC": "Indian Penal Code, 1860",
    "CrPC": "Code of Criminal Procedure, 1973",
    "CPC": "Code of Civil Procedure, 1908",
    "BNS": "Bharatiya Nyaya Sanhita, 2023",
    "BNSS": "Bharatiya Nagarik Suraksha Sanhita, 2023",
    "BSA": "Bharatiya Sakshya Adhiniyam, 2023",
    "Evidence Act": "Indian Evidence Act, 1872",
    "Specific Relief Act": "Specific Relief Act, 1963",
    "RP Act": "Representation of the People Act, 1951",
    "Maharashtra Co-operative Societies Act": "Maharashtra Co-operative Societies Act, 1960",
    "Maharashtra Zilla Parishads Act": "Maharashtra Zilla Parishads and Panchayat Samitis Act, 1961",
}

CASE_TYPES = [
    ("AA", "Arbitration Appeals"),
    ("ABA", "Cr. Anticipatory Bail Applications"),
    ("ACB", "Application For Cancellation Of Bail"),
    ("ALP", "Appln. For Leave to Appeal By Pvt. Party"),
    ("ALS", "Appln. For Leave to Appeal By State"),
    ("AO", "Appeal from Order"),
    ("APEAL", "Criminal Appeal"),
    ("APL", "Cr. Application U/s 482"),
    ("APPA", "Cr. Application in Appeal"),
    ("APPCO", "Application in Cr. Conf."),
    ("APPP", "Application in Cr. Cont. Petn."),
    ("APPCR", "Application in Cr. Reference"),
    ("APPLN", "Criminal Application"),
    ("APP", "Cr. Application in Application"),
    ("APPR", "Cr. Application in Revision"),
    ("APPW", "Cr. Application in Writ Petition"),
    ("ARA", "Arbitration Application"),
    ("ARP", "Arbitration Petition"),
    ("BA", "Cr. Bail Applications"),
    ("CA", "Civil Application"),
    ("CAA", "Civil Application in AO"),
    ("CAC", "Civil Application in CRA"),
    ("CAE", "Civil Application in Civil Reference"),
    ("CAF", "Civil Application in FA"),
    ("CAL", "Company Application"),
    ("CALCR", "Company Applications (Criminal)"),
    ("CAM", "Civil Application in AA"),
    ("CAN", "Civil Application in CP"),
    ("CAO", "CA in Others (MCA/EP/CA/XOB/CMP)"),
    ("CAP", "Company Appeal"),
    ("CAPL", "Custom Appeal"),
    ("CAS", "Civil Application in SA"),
    ("CAT", "Civil Application in Tax Matters"),
    ("CAW", "Civil Application in WP"),
    ("CAZ", "Civil Application in LPA"),
    ("CEL", "Central Excise Appeal"),
    ("CER", "Central Excise Reference"),
    ("CMP", "Company Petition"),
    ("COMAP", "Commercial Appeal"),
    ("CONF", "Criminal Confirmation Case"),
    ("CONP", "Criminal Contempt Petition"),
    ("CP", "Contempt Petition"),
    ("CPL", "Contempt Appeal"),
    ("CRA", "Civil Revision Application"),
    ("C.REF", "Civil References"),
    ("CRPIL", "Cr. Public Interest Litigation"),
    ("CS", "Civil Suits (Transfer Civil Suit)"),
    ("EDR", "Estate Duty Reference"),
    ("EP", "Election Petition"),
    ("FA", "First Appeal"),
    ("FCA", "Family Court Appeal"),
    ("GTA", "Gift Tax Application"),
    ("GTR", "Gift Tax Reference"),
    ("ITA", "Income Tax Application"),
    ("ITL", "Income Tax Appeal"),
    ("ITR", "Income Tax Reference"),
    ("LPA", "Letter Patent Appeal"),
    ("MCA", "Misc. Civil Application"),
    ("OLR", "Official Liquidator Report"),
    ("PIL", "Public Interest Litigation"),
    ("RAP", "Review Petn. in ARA"),
    ("RC", "Rejected Case"),
    ("REF", "Criminal Reference"),
    ("REVN", "Criminal Revision Application"),
    ("RPA", "Review Petn. in AO"),
    ("RPC", "Review Petn. in CRA/FCA"),
    ("RPF", "Review Petn. in FA"),
    ("RPL", "Review Petn. in LPA"),
    ("RPN", "Review Petn. in CP"),
    ("RPR", "Review Petn. in ARP"),
    ("RPS", "Review Petn. in SA"),
    ("RPT", "Review Petn. in CAPL"),
    ("RPW", "Review Petn. in WP"),
    ("SA", "Second Appeal"),
    ("SMAP", "Suo Motu Application"),
    ("SMAP-CR", "Cr. Suo Motu Application"),
    ("SMC", "Suo Motu Contempt Petition"),
    ("SMCP", "Cr. Suo Motu Contempt Petition"),
    ("SMP", "Suo Motu Cr. PIL"),
    ("SMPIL", "Suo Motu PIL"),
    ("SMWP-CR", "Suo Motu Cr. Writ Petition"),
    ("SMWP", "Suo Motu Writ Petition"),
    ("SPLCA", "Special Civil Application"),
    ("STA", "Sales Tax Application"),
    ("STR", "Sales Tax Reference"),
    ("STXA", "Sales Tax Appeal"),
    ("WP-CR", "Criminal Writ Petition"),
    ("WP", "Writ Petition"),
    ("WTA", "Wealth Tax Application"),
    ("WTL", "Wealth Tax Appeal"),
    ("WTR", "Wealth Tax Reference"),
    ("XOB", "Cross Objection"),
    ("SLP", "Special Leave Petition"),
    ("Other", "Other"),
]

CASE_TYPE_LABELS = {code: f"{code} - {label}" if code != label else code for code, label in CASE_TYPES}
CASE_TYPE_BY_CODE = {code: label for code, label in CASE_TYPES}


CITATION_SCHEMA = {
    "citation_name": "string",
    "court": "string",
    "year": "integer or null",
    "petition_type": "court case type/code, e.g. APL, APEAL, WP, WP-CR, FA, CRA, BA, PIL, SLP, Other",
    "case_number": "string or null",
    "neutral_citation": "string or null",
    "detected_format": "digilegal_scc, law_finder, high_court_order, supreme_court_order, scc_reporter, manupatra, indian_kanoon, or generic",
    "bench": ["string"],
    "party_names": ["string"],
    "disposition": "string or null",
    "cited_cases": ["string"],
    "acts_referred": ["string"],
    "headnote": "full DigiLegal/SCC headnote text or null",
    "important_principles": ["string"],
    "subsections": {"A": "string", "B": "string"},
    "brief_facts": "string or null",
    "appearances": ["string"],
    "order_type": "order, judgment, interim order, final order, or null",
    "directions": ["operative directions from the court"],
    "next_hearing_date": "DD-MM-YYYY or null",
    "sections": ["string"],
    "laws": ["string"],
    "holding": "2-3 sentence string",
    "ratio": "2-3 sentence string",
    "headnotes": ["string"],
    "key_quotes": ["short direct quote, max 20 words"],
    "judges": ["string"],
    "date_judgment": "DD-MM-YYYY or null",
    "scc_citation": "SCC reporter citation e.g. (2024) 10 SCC 456",
    "manupatra_citation": "Manupatra citation e.g. Manu/SC/2024/123",
    "indian_kanoon_url": "Indian Kanoon URL if available",
}

REQUIRED_LIST_FIELDS = [
    "bench",
    "party_names",
    "cited_cases",
    "acts_referred",
    "important_principles",
    "appearances",
    "directions",
    "sections",
    "laws",
    "headnotes",
    "key_quotes",
    "judges",
]


def normalize_text(value: str | None) -> str:
    value = value or ""
    value = value.lower()
    value = re.sub(r"\.pdf$", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def safe_year(value: Any) -> int | None:
    try:
        year = int(value)
        return year if 1800 <= year <= 2200 else None
    except (TypeError, ValueError):
        return None


def normalize_section_ref(value: str) -> str:
    value = compact_lines(value)
    act_key, section_no = provision_reference_from_text(value)
    if act_key and section_no:
        return f"{act_key} §{section_no}"
    for key, aliases in ACT_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            reverse = rf"(?:Section|Sec\.?|S\.|§)\s*(\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?(?:-[A-Za-z])?)\s+(?:of\s+)?(?:the\s+)?{re.escape(alias)}"
            match = re.search(reverse, value, re.I)
            if match:
                return f"{key} §{normalize_section_no(match.group(1))}"
            with_keyword = rf"{re.escape(alias)}\s*,?\s*(?:Section|Sec\.?|S\.|§)\s*(\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?(?:-[A-Za-z])?)"
            match = re.search(with_keyword, value, re.I)
            if match:
                return f"{key} §{normalize_section_no(match.group(1))}"
            if alias.isupper() or "." in alias:
                direct = rf"\b{re.escape(alias)}\b\s*§?\s*(\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?(?:-[A-Za-z])?)"
                match = re.search(direct, value, re.I)
                if match:
                    return f"{key} §{normalize_section_no(match.group(1))}"
    act = re.search(r"(.+?Act(?:,\s*\d{4})?)\s*,?\s*(?:Section|S\.|§)\s*(\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?)", value, re.I)
    if act:
        return f"{compact_lines(act.group(1))} §{act.group(2)}"
    return value


def safe_filename(filename: str) -> str:
    stem = secure_filename(Path(filename or "citation.pdf").stem) or "citation"
    return f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}_{stem}.pdf"


def extract_pdf_text(file_path: Path) -> str:
    parts = []
    with pdfplumber.open(str(file_path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                parts.append(f"\n\n--- Page {index} ---\n{text}")
    return "\n".join(parts).strip()


def compact_lines(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_section_no(value: str | None) -> str:
    value = compact_lines(value)
    value = value.replace("§", "")
    value = re.sub(r"^(?:section|sec\.?|s\.)\s*", "", value, flags=re.I)
    value = re.sub(r"^(\d+)\(([A-Za-z])\)$", r"\1\2", value)
    value = re.sub(r"\([^)]*\)", "", value)
    value = re.sub(r"[-\s]+", "", value)
    return value.upper()


def canonical_act_key(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if not normalized:
        return None
    alias_pairs = [
        (key, alias)
        for key, aliases in ACT_ALIASES.items()
        for alias in aliases
    ]
    for key, alias in sorted(alias_pairs, key=lambda item: len(normalize_text(item[1])), reverse=True):
            alias_norm = normalize_text(alias)
            if normalized == alias_norm or alias_norm in normalized:
                return key
    return None


def act_metadata_from_filename(filename: str) -> tuple[str, str]:
    stem = Path(filename).stem
    key = canonical_act_key(stem)
    if key:
        return key, ACT_DISPLAY_NAMES.get(key, stem)
    cleaned = compact_lines(stem.replace("_", " ").replace("-", " "))
    return cleaned, cleaned


def act_metadata_from_text(pdf_text: str, filename: str) -> tuple[str, str]:
    sample = pdf_text[:20000]
    compact_sample = re.sub(r"\s+", "", sample).lower()
    title_signatures = [
        ("BNSS", ["bharatiyanagariksurakshasanhita,2023", "bharatiyanagariksurakshasanhita"]),
        ("BNS", ["bharatiyanyayasanhita,2023", "bharatiyanyayasanhita"]),
        ("BSA", ["bharatiyasakshyaadhiniyam,2023", "bharatiyasakshyaadhiniyam"]),
        ("IPC", ["theindianpenalcode"]),
        ("CrPC", ["thecodeofcriminalprocedure,1973", "thecodeofcriminalprocedure"]),
        ("CPC", ["thecodeofcivilprocedure,1908", "thecodeofcivilprocedure"]),
        ("Evidence Act", ["theindianevidenceact,1872", "theindianevidenceact"]),
        ("Specific Relief Act", ["thespecificreliefact,1963", "thespecificreliefact"]),
        ("Maharashtra Co-operative Societies Act", ["themaharashtraco-operativesocietiesact,1960", "themaharashtracooperativesocietiesact,1960"]),
        ("Maharashtra Zilla Parishads Act", ["maharashtrazillaparishadsandpanchayatsamitisact,1961"]),
    ]
    matches = []
    for key, signatures in title_signatures:
        positions = [compact_sample.find(signature) for signature in signatures if compact_sample.find(signature) >= 0]
        if positions:
            matches.append((min(positions), key))
    if matches:
        _, key = min(matches, key=lambda item: item[0])
        return key, ACT_DISPLAY_NAMES.get(key, key)
    return act_metadata_from_filename(filename)


def provision_reference_from_text(value: str | None) -> tuple[str | None, str | None]:
    value = compact_lines(value)
    if not value:
        return None, None
    act_key = canonical_act_key(value)
    section_patterns = [
        r"(?:section|sec\.?|s\.|§)\s*(\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?(?:-[A-Za-z])?)",
        r"\b(?:IPC|CrPC|CPC|BNS|BNSS|BSA)\s*§?\s*(\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?(?:-[A-Za-z])?)\b",
        r"\b(\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?(?:-[A-Za-z])?)\s+of\s+(?:the\s+)?[A-Z][A-Za-z .,-]*(?:Act|Code|Sanhita|Adhiniyam)\b",
    ]
    for pattern in section_patterns:
        match = re.search(pattern, value, re.I)
        if match:
            return act_key, normalize_section_no(match.group(1))
    return act_key, None


def is_section_reference(value: str | None) -> bool:
    act_key, section_no = provision_reference_from_text(value)
    if not section_no:
        return False
    value = compact_lines(value)
    return bool(act_key or re.search(r"\b(?:section|sec\.?|s\.|§)\b", value, re.I))


def section_references(values: list[str]) -> list[str]:
    refs = []
    for value in values:
        if is_section_reference(value):
            refs.append(normalize_section_ref(value))
    return unique_items(refs)


def case_type_label(value: str | None) -> str:
    value = compact_lines(value)
    if not value:
        return "Other"
    code = value.split(" - ", 1)[0].strip().upper()
    if code in CASE_TYPE_BY_CODE:
        return CASE_TYPE_LABELS[code]
    for known_code, known_label in CASE_TYPES:
        if normalize_text(value) in {normalize_text(known_label), normalize_text(CASE_TYPE_LABELS[known_code])}:
            return CASE_TYPE_LABELS[known_code]
    return value


def infer_case_type_from_text(*values: str | None) -> str | None:
    text_value = " ".join(compact_lines(value) for value in values if value)
    if not text_value:
        return None
    normalized = normalize_text(text_value)
    upper = text_value.upper()

    for code, _label in sorted(CASE_TYPES, key=lambda item: len(item[0]), reverse=True):
        if code == "Other":
            continue
        code_pattern = re.escape(code).replace("\\-", "[- ]")
        if re.search(rf"\b{code_pattern}\b\s*(?:NO|NO\.|NUMBER|/|\d)", upper):
            return CASE_TYPE_LABELS[code]
        if re.search(rf"\b{code_pattern}\b", upper) and code in {"APL", "APEAL", "BA", "FA", "CRA", "WP", "PIL", "SLP"}:
            return CASE_TYPE_LABELS[code]

    phrase_map = [
        ("criminal application", "APL"),
        ("criminal appeal", "APEAL"),
        ("criminal writ petition", "WP-CR"),
        ("writ petition", "WP"),
        ("civil appeal", "FA"),
        ("first appeal", "FA"),
        ("civil revision", "CRA"),
        ("bail application", "BA"),
        ("anticipatory bail", "ABA"),
        ("public interest litigation", "PIL"),
        ("arbitration petition", "ARP"),
        ("arbitration application", "ARA"),
        ("company petition", "CMP"),
        ("commercial appeal", "COMAP"),
        ("letter patent appeal", "LPA"),
        ("second appeal", "SA"),
        ("election petition", "EP"),
        ("special leave petition", "SLP"),
    ]
    for phrase, code in phrase_map:
        if phrase in normalized:
            return CASE_TYPE_LABELS[code]
    return None


def case_type_filter_terms(value: str | None) -> list[str]:
    value = compact_lines(value)
    if not value:
        return []
    terms = [value]
    labeled = case_type_label(value)
    terms.append(labeled)
    code = labeled.split(" - ", 1)[0].strip()
    if code:
        terms.append(code)
    inferred = infer_case_type_from_text(value)
    if inferred:
        terms.append(inferred)
    return unique_items(terms)


def clean_provision_text(value: str) -> str:
    value = value.replace("\x00", " ")
    value = re.sub(r"\n\s*\d+\s*\n", "\n", value)
    value = re.sub(r"THE GAZETTE OF INDIA EXTRAORDINARY.*?\n", "\n", value, flags=re.I)
    value = re.sub(r"\[Part\s*II.*?\n", "\n", value, flags=re.I)
    value = re.sub(r"_{8,}", " ", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def extract_provisions_from_text(pdf_text: str, filename: str) -> list[dict[str, str]]:
    act_key, act_name = act_metadata_from_text(pdf_text, filename)
    marker = re.search(r"\b(?:BE\s+it\s+enacted|Be\s+itenacted|WHEREAS|An\s+Act\s+to)\b", pdf_text, re.I)
    body = pdf_text[marker.start() :] if marker else pdf_text

    header_pattern = re.compile(
        r"(?m)^(?P<line>.{0,120}?\b(?P<section>\d+[A-Z]?)\.\s*(?P<after>(?:\(\d+\)\s*)?[^\n]{2,220}))$"
    )
    headers = []
    for match in header_pattern.finditer(body):
        line = compact_lines(match.group("line"))
        section = normalize_section_no(match.group("section"))
        prefix = line[: match.group("line").find(match.group("section"))]
        if not re.match(r"^\d+[A-Z]?$", section):
            continue
        if re.search(r"\b(?:Exception|Explanation|Illustration|Provided|Clause)\b", prefix, re.I):
            continue
        if re.search(r"\b(?:FORM\s+NO|SCHEDULE|APPENDIX|TABLE)\b", line, re.I):
            continue
        if len(line) > 170 and not re.search(r"\(\d+\)", match.group("after")):
            continue
        headers.append((match.start(), section, line))

    provisions: dict[str, dict[str, str]] = {}
    for index, (start, section, line) in enumerate(headers):
        end = headers[index + 1][0] if index + 1 < len(headers) else len(body)
        chunk = clean_provision_text(body[start:end])
        if len(chunk) < 30:
            continue
        first_line = compact_lines(chunk.splitlines()[0])
        title = re.sub(r"^.*?\b" + re.escape(section) + r"\.\s*", "", first_line, flags=re.I)
        title = re.sub(r"^\(\d+\)\s*", "", title).strip(" .:-")
        old = provisions.get(section)
        if old and len(old["text"]) > len(chunk):
            continue
        provisions[section] = {
            "act_key": act_key,
            "act_name": act_name,
            "section_no": section,
            "title": title[:500] or f"Section {section}",
            "text": chunk,
            "source_file": filename,
        }
    return list(provisions.values())


def short_text(value: str | None, limit: int = 520) -> str | None:
    value = compact_lines(value)
    if not value:
        return None
    if len(value) <= limit:
        return value
    return value[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "."


def unique_items(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = compact_lines(value)
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def infer_result_label(citation: "Citation") -> str:
    text_value = " ".join(
        [
            citation.disposition or "",
            citation.holding or "",
            " ".join(citation.directions or []),
            citation.headnote or "",
            " ".join(citation.headnotes or []),
        ]
    ).lower()
    if re.search(r"\bpartly\s+allowed\b|\bpartially\s+allowed\b", text_value):
        return "Partly allowed"
    if re.search(r"\bappeal\s+(?:stands\s+)?allowed\b|\bapplication\s+(?:is\s+)?allowed\b|\bpetition\s+(?:is\s+)?allowed\b|\ballowed\b", text_value):
        return "Allowed"
    if re.search(r"\bappeal\s+(?:is\s+)?dismissed\b|\bapplication\s+(?:is\s+)?dismissed\b|\bpetition\s+(?:is\s+)?dismissed\b|\bdismissed\b", text_value):
        return "Dismissed"
    if re.search(r"\bdisposed\s+of\b|\bstands\s+disposed\b", text_value):
        return "Disposed of"
    if re.search(r"\bquashed\b|\bset\s+aside\b", text_value):
        return "Allowed"
    if citation.disposition:
        return citation.disposition
    return "Needs review"


def infer_plea_summary(citation: "Citation") -> str:
    name = citation.case_number or citation.petition_type or "the matter"
    text_value = citation.pdf_text or ""
    plea_patterns = [
        r"(?:has|have)\s+filed\s+the\s+present\s+(?:application|appeal|petition)\s+for\s+(.+?)(?:\.\s|\n\d+\.|\n[A-Z])",
        r"(?:seeking|sought)\s+(.+?)(?:\.\s|\n\d+\.|\n[A-Z])",
        r"(?:preferred|filed)\s+by\s+.+?\s+for\s+(.+?)(?:\.\s|\n\d+\.|\n[A-Z])",
    ]
    for pattern in plea_patterns:
        match = re.search(pattern, text_value[:15000], re.I | re.S)
        if match:
            return short_text(match.group(1), 420) or f"Plea in {name}."
    case_type = normalize_text(citation.petition_type)
    if "criminal appeal" in case_type or case_type.startswith("apeal"):
        return f"Appellant challenged the conviction/order in {name}."
    if "civil appeal" in case_type or case_type.startswith("fa first appeal"):
        return f"Appellant challenged the civil judgment/order in {name}."
    if "writ petition" in case_type:
        return f"Petitioner sought writ relief in {name}."
    if case_type.startswith("apl"):
        return f"Applicant sought relief in {name}."
    return short_text(citation.brief_facts, 420) or f"Plea extracted from {name}."


def decision_brief_for(citation: "Citation") -> dict[str, Any]:
    court_action = unique_items(citation.directions or [])
    if not court_action and citation.disposition:
        court_action = [citation.disposition]
    if not court_action and citation.holding:
        court_action = [short_text(citation.holding, 420) or citation.holding]

    grounds = []
    grounds.extend(citation.headnotes or [])
    grounds.extend(citation.important_principles or [])
    grounds.extend((citation.subsections or {}).values())
    if citation.ratio:
        grounds.append(citation.ratio)
    if not grounds and citation.holding:
        grounds.append(citation.holding)
    grounds = [short_text(item, 420) for item in unique_items(grounds)]
    grounds = [item for item in grounds if item]

    provisions = [
        ref
        for ref in section_references((citation.sections or []) + (citation.acts_referred or []))
        if resolve_legal_provision(ref)
    ]
    source = citation.detected_format or "generic"
    source_label = {
        "high_court_order": "High Court Order",
        "supreme_court_order": "Supreme Court Order",
        "law_finder": "Law Finder",
        "digilegal_scc": "DigiLegal/SCC",
        "scc_reporter": "SCC Reporter",
        "manupatra": "Manupatra",
        "indian_kanoon": "Indian Kanoon",
        "generic": "Generic",
    }.get(source, source)

    # Also include sections that aren't in bare acts but were referenced
    for ref in citation.sections or []:
        if ref not in provisions and re.search(r"[A-Z]{2,4}\s+§", ref):
            provisions.append(ref)

    return {
        "result": infer_result_label(citation),
        "plea": infer_plea_summary(citation),
        "court_action": court_action,
        "grounds": grounds[:8],
        "provisions": provisions,
        "source_label": source_label,
    }


def detect_scc_reporter_citation(pdf_text: str) -> dict[str, Any] | None:
    """Extract SCC (Supreme Court Cases) reporter citation.
    Format: (Year) SCC Volume Page
    Example: (2024) 10 SCC 456
    Also SCC OnLine format: 2024 SCC OnLine SC 1234
    """
    scc_patterns = [
        r"\((\d{4})\)\s+SCC\s+(\d+)\s+(\d+)",  # (2024) 10 SCC 456
        r"(\d{4})\s+SCC\s+OnLine\s+(SC|DEL|BOM|MAD|CAL|KAR|ALL|GUJ|ORI|RAJ|PAT|KER)\s+(\d+)",  # 2024 SCC OnLine SC 1234
        r"(\d{4})\s+SCC\s+OnLine\s+(\w+)\s+(\d+)",  # Generic SCC OnLine
        r"\bSCC\s+(\d+)\s+\((\d{4})\)\s+(\d+)",  # SCC 10 (2024) 456
    ]
    for pattern in scc_patterns:
        match = re.search(pattern, pdf_text, re.I)
        if match:
            groups = match.groups()
            if "(" in pattern:
                year = int(groups[0])
                if "OnLine" in pattern:
                    court_code = groups[1]
                    page_no = groups[2]
                    citation = f"{year} SCC OnLine {court_code} {page_no}"
                else:
                    volume = groups[1]
                    page = groups[2]
                    citation = f"({year}) SCC {volume} {page}"
            else:
                volume = int(groups[0])
                year = int(groups[1])
                page = groups[2]
                citation = f"({year}) SCC {volume} {page}"
            return {"year": year, "scc_citation": citation, "detected_format": "scc_reporter"}
    return None


def detect_manupatra_citation(pdf_text: str) -> dict[str, Any] | None:
    """Extract Manupatra citation.
    Format: Manu/CourtCode/Year/Number
    Examples: Manu/SC/2024/123, Manu/PH/2024/456 (Delhi High Court)
    Court codes: SC (Supreme Court), PH, DB (Delhi), MH (Bombay), TN (Madras),
                 KA (Karnataka), CAL (Calcutta), GUJ (Gujarat), ORI (Orissa),
                 RAJ (Rajasthan), PAT (Patna), KER (Kerala), etc.
    """
    manupatra_patterns = [
        r"\bManu/(SC|PH|DB|MH|TN|KA|CAL|GUJ|ORI|RAJ|PAT|KER|MP|CG|UP|UK|HP|JK|JH|GA|GHA|CH|JK|TRI|MEG|MAN|NAG|MIZ|SIK|AND|ARP|GUA|PUD|LAK|PNB|HRY|PUN|RAJ|TRP|MAD|KAR|ALL|WST|NE|EA|SA)/(\d{4})/(\d+)\b",
        r"\bManu\s*/\s*(\w{2,4})\s*/\s*(\d{4})\s*/\s*(\d+)\b",
    ]
    for pattern in manupatra_patterns:
        match = re.search(pattern, pdf_text, re.I)
        if match:
            groups = match.groups()
            court_code = groups[0].upper()
            year = int(groups[1])
            number = groups[2]
            citation = f"Manu/{court_code}/{year}/{number}"
            return {
                "year": year,
                "manupatra_citation": citation,
                "detected_format": "manupatra",
                "court_code": court_code,
            }
    return None


def detect_indian_kanoon_format(pdf_text: str) -> dict[str, Any] | None:
    """Extract Indian Kanoon citation elements.
    Indian Kanoon uses neutral citations and may include URLs.
    Format examples:
    - 2024 SCC OnLine SC 1234
    - https://indiankanoon.org/doc/123456789/
    - Neutral citation: 2024:SC:567
    """
    result = {}
    # Check for Indian Kanoon URL
    url_match = re.search(r"https?://(?:www\.)?indiankanoon\.org/doc/(\d+)/", pdf_text, re.I)
    if url_match:
        result["indian_kanoon_url"] = url_match.group(0)
        result["detected_format"] = "indian_kanoon"
    # Check for neutral citation format (Year:Court:Number)
    neutral_patterns = [
        r"\b(\d{4}):(SC|SUPREME|SUPREME COURT):(\d+)\b",
        r"\b(\d{4}):(BOM|MAD|DEL|CAL|KAR|ALL|GUJ|ORI|RAJ|PAT|KER|MP|CG|UP|UK|HP|JK|JH|GA|CH|TRI|MEG|MAN|NAG|MIZ|SIK|AND|ARP|GUA|PUD|LAK|PNB|HRY|PUN|WST|NE|EA|SA|GHA|PH|DB|MH|TN|KA|CAL|GUJ|ORI|RAJ|PAT|KER)(?:-([A-Z]+))?:(\d+)\b",
    ]
    for pattern in neutral_patterns:
        match = re.search(pattern, pdf_text, re.I)
        if match:
            groups = match.groups()
            year = int(groups[0])
            court = groups[1].upper()
            number = groups[-1]
            bench = groups[2] if len(groups) > 3 and groups[2] else None
            neutral_cit = f"{year}:{court}:{number}"
            if bench:
                neutral_cit += f"-{bench}"
            result.update({
                "year": year,
                "neutral_citation": neutral_cit,
                "detected_format": "indian_kanoon",
            })
            break
    # Check for Indian Kanoon style citation mentions
    if re.search(r"\bIndian\s+Kanoon\b", pdf_text, re.I) or re.search(r"\bindiankanoon\.org\b", pdf_text, re.I):
        result["detected_format"] = "indian_kanoon"
    return result if result else None


def detect_supreme_court_order_format(pdf_text: str) -> dict[str, Any] | None:
    """Extract Supreme Court neutral citation elements.

    Format examples:
    - 2026 INSC 244
    - Neutral Citation: 2026 INSC 244
    """
    match = re.search(r"^\s*(?:Neutral\s+Citation\s*[:.-]\s*)?(\d{4})\s+INSC\s+(\d+)\s*$", pdf_text, re.I | re.M)
    if not match:
        return None
    year = int(match.group(1))
    number = match.group(2)
    return {
        "year": year,
        "neutral_citation": f"{year} INSC {number}",
        "detected_format": "supreme_court_order",
        "court": "Supreme Court of India",
    }


def detect_citation_format(pdf_text: str) -> str:
    lowered = pdf_text.lower()
    # Check for Supreme Court neutral citation format
    if re.search(r"^\s*(?:Neutral\s+Citation\s*[:.-]\s*)?\d{4}\s+INSC\s+\d+\s*$", pdf_text, re.I | re.M):
        return "supreme_court_order"
    if (
        re.search(r"^\s*\d{4}:[A-Z-]+:\d+\s*$", pdf_text[:5000], re.M)
        and re.search(r"\bIN\s+THE\s+HIGH\s+COURT\b", pdf_text[:12000], re.I)
    ):
        return "high_court_order"
    # Check for SCC reporter format
    if re.search(r"\(\d{4}\)\s+SCC\s+\d+", pdf_text) or re.search(r"\d{4}\s+SCC\s+OnLine", pdf_text, re.I):
        return "scc_reporter"
    # Check for Manupatra format
    if re.search(r"\bManu/\w+/\d{4}/\d+\b", pdf_text, re.I):
        return "manupatra"
    # Check for Indian Kanoon
    if re.search(r"\bindian\s+kanoon\b", lowered) or re.search(r"\b\d{4}:(SC|SUPREME|BOM|MAD|DEL|CAL|KAR|ALL|GUJ|ORI|RAJ|PAT|KER|MP|CG|UP|UK|HP|JK|JH|GA|CH|TRI|MEG|MAN|NAG|MIZ|SIK|AND|ARP|GUA|PUD|LAK|PNB|HRY|PUN|WST|NE|EA|SA|GHA|PH|DB|MH|TN|KA)(?:-[A-Z]+)?:\d+\b", pdf_text, re.I):
        return "indian_kanoon"
    # Original detections
    if "# headnote #" in lowered or ("acts referred" in lowered and "dgls" in lowered):
        return "digilegal_scc"
    if re.search(r"\bimportant\b", pdf_text, re.I) and (
        re.search(r"\bbrief facts\b", pdf_text, re.I) or re.search(r"\bD/d\.?\s*\d{1,2}[.-]\d{1,2}[.-]\d{4}", pdf_text)
    ):
        return "law_finder"
    if re.search(r"\bIN\s+THE\s+HIGH\s+COURT\b", pdf_text, re.I) and re.search(r"\bCORAM\s*:", pdf_text, re.I):
        return "high_court_order"
    if re.search(r"^\s*\d{4}:[A-Z-]+:\d+", pdf_text, re.M) and re.search(r"\bDATE\s*:", pdf_text, re.I):
        return "high_court_order"
    return "generic"


def section_between(pdf_text: str, start_pattern: str, end_patterns: list[str], max_chars: int = 8000) -> str | None:
    start = re.search(start_pattern, pdf_text, re.I | re.M)
    if not start:
        return None
    remainder = pdf_text[start.end() :]
    end_positions = []
    for pattern in end_patterns:
        match = re.search(pattern, remainder, re.I | re.M)
        if match:
            end_positions.append(match.start())
    end = min(end_positions) if end_positions else min(len(remainder), max_chars)
    return remainder[:end].strip(" \n:-")


def extract_case_number(pdf_text: str) -> str | None:
    patterns = [
        r"\b(?:Criminal|Civil)\s+Appeal\s+No(?:\(s\))?\.?\s*[^\n]*?\bof\s+\d{4}\b(?:\s*\n\s*\(Arising\s+out\s+of\s+SLP[^\n]+\))?",
        r"\b(?:Criminal|Civil)\s+Appeal\s+No\.?\s*[\w./ -]+?\s+of\s+\d{4}\b",
        r"\bApplication\s*\(L\)\s+No\.?\s*[\w./ -]+?\s+of\s+\d{4}\b(?:\s+in\s+Election\s+Petition\s+No\.?\s*[\w./ -]+?\s+of\s+\d{4}\b)?",
        r"\bElection\s+Petition\s+No\.?\s*[\w./ -]+?\s+of\s+\d{4}\b",
        r"\b(?:Writ\s+Petition|Special\s+Leave\s+Petition|SLP|APL)\s+No\.?\s*[\w./ -]+?\s+of\s+\d{4}\b",
        r"\bWRIT\s+PETITION\s+NO\.?\s*[\w./ -]+?\s+OF\s+\d{4}\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, pdf_text, re.I)
        if match:
            return compact_lines(match.group(0)).rstrip(".")
    return None


def infer_petition_type(case_number: str | None) -> str | None:
    value = (case_number or "").lower()
    if "election petition" in value:
        return CASE_TYPE_LABELS["EP"]
    if "criminal appeal" in value:
        return CASE_TYPE_LABELS["APEAL"]
    if "civil appeal" in value:
        return CASE_TYPE_LABELS["FA"]
    if "writ petition" in value:
        return CASE_TYPE_LABELS["WP"]
    if re.search(r"\bapl\b", value):
        return CASE_TYPE_LABELS["APL"]
    if "slp" in value or "special leave petition" in value:
        return CASE_TYPE_LABELS["SLP"]
    inferred = infer_case_type_from_text(case_number)
    if inferred:
        return inferred
    return None


def extract_date(pdf_text: str) -> str | None:
    patterns = [
        r"Date\s+of\s+Decision\s*[:-]\s*(\d{1,2}[-.]\d{1,2}[-.]\d{4})",
        r"D/d\.?\s*(\d{1,2}[-.]\d{1,2}[-.]\d{4})",
        r"\bDATE\s*:\s*(\d{1,2}[-.]\d{1,2}[-.]\d{4})",
        r"Judg(?:e)?ment\s+dated\s*(\d{1,2}[-.]\d{1,2}[-.]\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, pdf_text, re.I)
        if match:
            return normalize_date(match.group(1))
    pronounced_match = re.search(
        r"\bPronounced\s+on\s*:\s*(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December),?\s+(\d{4})\b",
        pdf_text[:12000],
        re.I,
    )
    if pronounced_match:
        month_no = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }[pronounced_match.group(2).lower()]
        return f"{int(pronounced_match.group(1)):02d}-{month_no:02d}-{pronounced_match.group(3)}"
    month_match = re.search(
        r"\b(JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+(\d{1,2}),\s*(\d{4})\b",
        tail_text(pdf_text, 4000),
        re.I,
    )
    if month_match:
        month_no = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }[month_match.group(1).lower()]
        return f"{int(month_match.group(2)):02d}-{month_no:02d}-{month_match.group(3)}"
    return None


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    parts = re.split(r"[-.]", value.strip())
    if len(parts) != 3:
        return value
    try:
        day, month, year = parts
        return f"{int(day):02d}-{int(month):02d}-{year}"
    except (ValueError, TypeError):
        return value


def extract_neutral_citation(pdf_text: str) -> str | None:
    match = re.search(r"^\s*(\d{4}:[A-Z-]+:\d+(?:-[A-Z]+)?)\s*$", pdf_text, re.M)
    if match:
        return match.group(1)
    insc_match = re.search(r"^\s*(?:Neutral\s+Citation\s*[:.-]\s*)?(\d{4}\s+INSC\s+\d+)\s*$", pdf_text, re.I | re.M)
    return re.sub(r"\s+", " ", insc_match.group(1).upper()) if insc_match else None


def extract_court_and_bench(pdf_text: str) -> tuple[str | None, list[str]]:
    court = None
    bench = []
    if re.search(r"\bIN\s+THE\s+SUPREME\s+COURT\s+OF\s+INDIA\b", pdf_text, re.I):
        court = "Supreme Court of India"
    court_match = re.search(r"\bIN\s+THE\s+HIGH\s+COURT\s+OF\s+.+", pdf_text, re.I)
    if court_match:
        court = compact_lines(court_match.group(0)).title()
        court = re.sub(r"^In The High Court Of Judicature At ", "", court)
        court = re.sub(r"^In The High Court Of ", "", court)
        if court.lower() in {"bombay", "judicature at bombay"}:
            court = "Bombay High Court"
    bench_match = re.search(r"^\s*([A-Z ]+BENCH,\s*[A-Z ]+)\.?\s*$", pdf_text, re.M)
    if bench_match:
        bench.append(compact_lines(bench_match.group(1)).title())
    return court, bench


def extract_parties(pdf_text: str) -> list[str]:
    supreme_court_header = re.search(
        r"(?mis)^\s*([^\n]+?)\s*[.\u2026]*\s*APPELLANT\(S\)\s*\n\s*VERSUS\s*\n\s*(.+?)\s*[.\u2026]*\s*RESPONDENT\(S\)",
        pdf_text[:12000],
    )
    if supreme_court_header:
        return [
            compact_lines(supreme_court_header.group(1)).strip(" .\u2026"),
            compact_lines(supreme_court_header.group(2)).strip(" .\u2026"),
        ]
    matter = re.search(
        r"In\s+the\s+matter\s+of\s*:\s*\n\s*([A-Z][A-Za-z .'-]+?)(?:,|\s*\])[\s\S]{0,1800}?\n\s*Versus\s*\n\s*1\.\s*([A-Z][A-Za-z .'-]+?)(?:,|\s*\])",
        pdf_text[:12000],
        re.I,
    )
    if matter:
        return [
            compact_lines(matter.group(1)).strip(" ."),
            compact_lines(matter.group(2)).strip(" ."),
        ]
    bracket = re.search(r"\[([^\]]+\bvs\.?\b[^\]]+)\]", pdf_text, re.I | re.S)
    if bracket:
        value = compact_lines(bracket.group(1))
        return [part.strip(" .") for part in re.split(r"\s+v(?:s\.?|ersus)\s+", value, flags=re.I) if part.strip(" .")]
    versus = re.search(
        r"(?:Before\s*[:-].*?\n)?\s*([^\n]{2,180}?)\s*\n\s*(?:Versus|Vs\.?|V\.)\s*\n\s*([^\n]{2,180}?)(?:\n\s*Case\s+No\.|\n\s*Date\s+of\s+Decision|\n)",
        pdf_text[:12000],
        re.I | re.S,
    )
    if versus:
        return [compact_lines(versus.group(1)).strip(" ."), compact_lines(versus.group(2)).strip(" .")]
    return []


def extract_appearances(pdf_text: str) -> list[str]:
    section = section_between(
        pdf_text,
        r"Registrar's\s+orders\.\s*-+",
        [r"\bCORAM\s*:"],
        max_chars=2500,
    )
    if not section:
        court_appearance = re.search(
            r"(?:Respondents?|Applicants?|Petitioners?)\s*\n\s*[—-]{4,}\s*(.+?)\s*[—-]{4,}\s*\n\s*Coram\s*:",
            pdf_text[:15000],
            re.I | re.S,
        )
        if court_appearance:
            section = court_appearance.group(1)
    if not section:
        # Fallback: take advocate lines immediately before CORAM.
        coram = re.search(r"\bCORAM\s*:", pdf_text, re.I)
        if not coram:
            return []
        section = pdf_text[max(0, coram.start() - 2000) : coram.start()]
    appearances = []
    for line in section.splitlines():
        cleaned = compact_lines(line)
        if re.search(r"\bAge\s*:", cleaned, re.I):
            continue
        if re.match(r"^(?:Mr|Ms|Mrs|Dr|Smt)\.?\s+", cleaned) or re.search(r"\b(Advocate|AGP|Counsel|Solicitor)\b", cleaned, re.I):
            appearances.append(cleaned)
        elif appearances and re.search(r"\b(?:for\s+)?(?:Petitioner|Respondent|Applicant)\b", cleaned, re.I):
            appearances[-1] = f"{appearances[-1]} {cleaned}"
    return appearances


def extract_order_type(pdf_text: str) -> str | None:
    if re.search(r"\bjudg(?:e)?ment\s*:", pdf_text, re.I) or re.search(r"\bPronounced\s+on\s*:", pdf_text, re.I):
        return "judgment"
    if re.search(r"\binterim\b", pdf_text, re.I):
        return "interim order"
    if re.search(r"\bdisposed\s+of\b|\bpetition\s+is\s+accordingly\s+disposed\b", pdf_text, re.I):
        return "final order"
    if re.search(r"\border\b", pdf_text, re.I):
        return "order"
    return None


def extract_directions(pdf_text: str) -> list[str]:
    directions = []
    operative_text = tail_text(pdf_text, 8000)
    patterns = [
        r"the\s+Petition\s+fails\s+to\s+disclose\s+any\s+cause\s+of\s+action[^.]+\.",
        r"the\s+same\s+is\s+liable\s+to\s+be\s+dismissed[^.]+\.",
        r"Interim\s+Application\s+is\s+allowed\.",
        r"Resultantly,\s+Election\s+Petition\s+stands\s+dismissed[^.]+\.",
        r"the\s+impugned\s+order\s+dated\s+[^.]+?\s+is\s+set\s+aside\.",
        r"FIR\s+No\.[^.]+?\s+and\s+all\s+proceedings\s+[^.]+?\s+are\s+quashed\.",
        r"The\s+appeal\s+stands\s+allowed\s+accordingly\.",
        r"Pending\s+application\(s\),\s+if\s+any,\s+shall\s+stand\s+disposed\s+of\.",
        r"We\s+accordingly\s+refer\s+the\s+matter\s+to\s+the\s+Bar\s+Council[^.]+Mr\.\s*S\.\s*D\.\s*Chande,\s*Advocate\.",
        r"The\s+Bar\s+Council\s+of\s+Maharashtra\s+and\s+Goa\s+shall\s+take\s+note[^.]+(?:\.[^.]+){0,1}\.",
        r"The\s+copy\s+of\s+the\s+petition[^.]+shall\s+be\s+forwarded[^.]+\.",
        r"unauthorized\s+structure[^.]+shall\s+be\s+removed[^.]+\.",
        r"The\s+petition\s+is\s+accordingly\s+disposed\s+of\.",
        r"the\s+proceedings\s+shall\s+be\s+listed[^.]+\.",
        r"liberty\s+to\s+file\s+appropriate\s+application[^.]+\.",
        r"The\s+copy\s+of\s+the\s+order\s+shall\s+be\s+forwarded[^.]+\.",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, operative_text, re.I):
            cleaned = compact_lines(match.group(0))
            if cleaned and "JUDGE" not in cleaned and cleaned not in directions:
                directions.append(cleaned)
    return directions


def extract_next_hearing_date(pdf_text: str) -> str | None:
    match = re.search(r"listed\s+before\s+us\s+on\s+(\d{1,2}[-.]\d{1,2}[-.]\d{4})", pdf_text, re.I)
    return normalize_date(match.group(1)) if match else None


def extract_judges(pdf_text: str, detected_format: str) -> list[str]:
    if detected_format == "supreme_court_order":
        names = []
        for match in re.finditer(r"^\s*\(([A-Z][A-Z .'-]+)\)\s*$", tail_text(pdf_text, 3000), re.M):
            name = compact_lines(match.group(1)).title()
            if name and name not in names:
                names.append(name)
        if names:
            return names
        judge_line = re.search(r"^\s*([A-Z][A-Za-z .'-]+),\s*J\.\s*$", pdf_text[:12000], re.M)
        return [compact_lines(judge_line.group(1)).title()] if judge_line else []
    if detected_format == "high_court_order":
        coram = section_between(pdf_text, r"\bCORAM\s*:", [r"\bDATE\s*:", r"\bReserved\s+on\s*:", r"\bPronounced\s+on\s*:", r"\bJudg(?:e)?ment\s*:"])
        if coram:
            value = compact_lines(coram)
            value = re.sub(r"\bJ{1,2}\.?\b", "", value, flags=re.I)
            parts = re.split(r"\s+AND\s+|\s+and\s+|,|;", value)
            return [part.strip(" .:-").title() for part in parts if part.strip(" .:-")]
    before = re.search(
        r"Before\s*[:-]\s*(.+?)(?:\n|Case\s+No\.|Criminal\s+Appeal|Civil\s+Appeal)",
        pdf_text,
        re.I | re.S,
    )
    if not before:
        return []
    value = compact_lines(before.group(1))
    value = re.sub(r"\bJ{1,2}\.?\b", "", value, flags=re.I)
    parts = re.split(r"\s*:\s*|\s+and\s+|,|;", value)
    return [part.strip(" .:-") for part in parts if part.strip(" .:-")]


def extract_acts_referred(pdf_text: str) -> list[str]:
    # First try the structured "Acts Referred:" section
    section = section_between(
        pdf_text,
        r"Acts\s+Referred\s*[:-]?",
        [r"#\s*HEADNOTE\s*#", r"Cases\s+Referred", r"\n\s*JUDGMENT\b"],
    )
    acts = []
    if section:
        for line in section.splitlines():
            cleaned = compact_lines(re.sub(r"^[•*\-\d.)\s]+", "", line))
            if cleaned and re.search(r"\b(Act|Code|Constitution|IPC|CrPC|Art\.|S\.)\b", cleaned, re.I):
                acts.append(cleaned)
        if acts:
            return acts

    # Fallback: Extract all act/section references from the entire text
    # Matches patterns like: "Section 120", "IPC 409", "BNS §359", "Section 376(2)"
    act_patterns = [
        r"(?:Section|Sec\.?|S\.|§)\s*\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?(?:\s+of\s+(?:the\s+)?(?:Bharatiya\s+[A-Za-z\s]+Sanhita|IPC|CrPC|CPC|Code|Act))?",
        r"\b(BNS|BNSS|BSA|IPC|CrPC|CPC)\s*(?:§|Section|Sec\.?|S\.?)\s*\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?",
        r"\b(Bharatiya\s+(?:Nyaya|Nagarik\s+Suraksha|Sakshya)\s+Sanhita)\s*,?\s*\d{4}",
        r"\b(?:Indian\s+)?(?:Penal|Evidence|Criminal\s+Procedure|Civil\s+Procedure)(?:\s+Code)?(?:,\s*\d{4})?",
    ]

    found_acts = {}
    for pattern in act_patterns:
        for match in re.finditer(pattern, pdf_text, re.I):
            act_ref = compact_lines(match.group(0))
            # Normalize the reference
            if re.match(r"^Section|^Sec\.|^S\.", act_ref, re.I):
                # Extract the section number
                sec_match = re.search(r"\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?", act_ref)
                if sec_match:
                    section_no = normalize_section_no(sec_match.group(0))
                    # Try to find the act name from nearby context
                    context_start = max(0, match.start() - 100)
                    context = pdf_text[context_start:match.end() + 50]
                    act_key = canonical_act_key(context) or "Unknown Act"
                    act_ref = f"{act_key} §{section_no}"
            # Use a dictionary to deduplicate while preserving order
            found_acts[act_ref] = act_ref

    return list(found_acts.keys())


def extract_headnote(pdf_text: str) -> str | None:
    headnote = section_between(
        pdf_text,
        r"#\s*HEADNOTE\s*#",
        [r"Cases\s+Referred", r"\n\s*JUDGMENT\b", r"\n\s*[A-Z][A-Za-z .]+,\s*J\."],
    )
    return compact_lines(headnote) if headnote else None


def extract_cases_referred(pdf_text: str) -> list[str]:
    section = section_between(
        pdf_text,
        r"Cases\s+Referred\s*[:-]?",
        [r"Brief\s+Facts", r"\n\s*JUDGMENT\b", r"\n\s*[A-Z][A-Za-z .]+,\s*J\.", r"\n\s*\d+\."],
    )
    if not section:
        cases = []
        for match in re.finditer(r"in\s+the\s+case\s+of\s+(.+?\s+V(?:s\.?|\.|ersus)\s+.+?)(?:,|\s+while|\s*\[)", pdf_text, re.I | re.S):
            cleaned = compact_lines(match.group(1))
            citation_after = re.search(r"\[([^\]]+)\]", pdf_text[match.end() : match.end() + 80])
            if citation_after:
                cleaned = f"{cleaned} [{citation_after.group(1)}]"
            if cleaned and cleaned not in cases:
                cases.append(cleaned)
        return cases
    cases = []
    for line in section.splitlines():
        cleaned = compact_lines(re.sub(r"^[•*\-\d.)\s]+", "", line))
        if cleaned and re.search(r"\bv(?:s\.?|\.|ersus)\b", cleaned, re.I):
            cases.append(cleaned)
    return cases


def extract_important_principles(pdf_text: str) -> list[str]:
    matches = list(re.finditer(r"\bIMPORTANT\b", pdf_text, re.I))
    principles = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else min(len(pdf_text), start + 1500)
        chunk = pdf_text[start:end]
        end_match = re.search(r"\n\s*[A-D]\.\s+|Cases\s+Referred|Brief\s+Facts|JUDGMENT", chunk, re.I)
        if end_match:
            chunk = chunk[: end_match.start()]
        cleaned = compact_lines(chunk)
        if cleaned:
            principles.append(cleaned)
    return principles


def extract_subsections(pdf_text: str) -> dict[str, str]:
    result = {}
    matches = list(re.finditer(r"(?m)^\s*([A-D])\.\s+(.+)", pdf_text))
    for index, match in enumerate(matches):
        label = match.group(1)
        start = match.start(2)
        end = matches[index + 1].start() if index + 1 < len(matches) else min(len(pdf_text), start + 2500)
        chunk = pdf_text[start:end]
        end_match = re.search(r"Cases\s+Referred|Brief\s+Facts|JUDGMENT", chunk, re.I)
        if end_match:
            chunk = chunk[: end_match.start()]
        result[label] = compact_lines(chunk)
    return result


def extract_brief_facts(pdf_text: str) -> str | None:
    facts = section_between(
        pdf_text,
        r"Brief\s+Facts\s*[:-]?",
        [r"\n\s*JUDGMENT\b", r"\n\s*[A-Z][A-Za-z .]+,\s*J\."],
    )
    return compact_lines(facts) if facts else None


def extract_digilegal_facts(pdf_text: str) -> str | None:
    match = re.search(r"\bJUDGMENT\b(.+?)(?:\n\s*\d+\.\s+|\Z)", pdf_text, re.I | re.S)
    return short_text(match.group(1), 700) if match else None


def extract_key_quotes_from_text(pdf_text: str) -> list[str]:
    quotes = []
    for match in re.finditer(r"[“\"]([^”\"\n]{20,180})[”\"]", pdf_text):
        quote = compact_lines(match.group(1))
        if quote and len(quote.split()) <= 20:
            quotes.append(quote)
    return unique_items(quotes)[:6]


def extract_headnote_points(headnote: str | None) -> list[str]:
    if not headnote:
        return []
    parts = [compact_lines(part) for part in re.split(r"\s+-\s+", headnote)]
    return [part for part in parts if len(part) > 35][:8]


def extract_format_hints(pdf_text: str) -> dict[str, Any]:
    detected_format = detect_citation_format(pdf_text)
    case_number = extract_case_number(pdf_text)
    court, bench = extract_court_and_bench(pdf_text)
    judges = extract_judges(pdf_text, detected_format)
    if judges:
        bench = bench + [judge for judge in judges if judge not in bench]
    hints = {
        "detected_format": detected_format,
        "neutral_citation": extract_neutral_citation(pdf_text),
        "court": court,
        "case_number": case_number,
        "petition_type": infer_petition_type(case_number),
        "bench": bench,
        "party_names": extract_parties(pdf_text),
        "judges": judges,
        "date_judgment": extract_date(pdf_text),
        "acts_referred": extract_acts_referred(pdf_text),
        "headnote": extract_headnote(pdf_text),
        "important_principles": extract_important_principles(pdf_text),
        "subsections": extract_subsections(pdf_text),
        "brief_facts": extract_brief_facts(pdf_text),
        "cited_cases": extract_cases_referred(pdf_text),
        "appearances": extract_appearances(pdf_text),
        "order_type": extract_order_type(pdf_text),
        "directions": extract_directions(pdf_text),
        "next_hearing_date": extract_next_hearing_date(pdf_text),
    }
    if detected_format == "digilegal_scc":
        hints["brief_facts"] = hints.get("brief_facts") or extract_digilegal_facts(pdf_text)
        hints["important_principles"] = hints.get("important_principles") or extract_headnote_points(hints.get("headnote"))

    # Extract SCC reporter citation
    scc_info = detect_scc_reporter_citation(pdf_text)
    if scc_info and detected_format in {"scc_reporter", "generic"}:
        hints.update(scc_info)

    # Extract Manupatra citation
    manupatra_info = detect_manupatra_citation(pdf_text)
    if manupatra_info and detected_format in {"manupatra", "generic"}:
        hints.update(manupatra_info)

    # Extract Indian Kanoon citation
    kanoon_info = detect_indian_kanoon_format(pdf_text)
    if kanoon_info and detected_format in {"indian_kanoon", "generic"}:
        hints.update(kanoon_info)

    # Extract Supreme Court neutral citation
    supreme_court_info = detect_supreme_court_order_format(pdf_text)
    if supreme_court_info:
        hints.update(supreme_court_info)

    # For high court orders and other formats without structured acts sections,
    # also extract sections from the entire text
    if detected_format in {"high_court_order", "supreme_court_order", "generic", "manupatra", "indian_kanoon"}:
        sections_from_text = extract_sections_from_text(pdf_text)
        # Merge with existing sections
        existing_sections = hints.get("sections") or []
        all_sections = list(set(existing_sections + sections_from_text))
        hints["sections"] = all_sections

    return hints


def extract_sections_from_text(pdf_text: str) -> list[str]:
    """Extract all legal section references from judgment text."""
    sections = []

    # Pattern to match section references like:
    # "Section 376", "Sec. 409", "IPC §302", "BNS 359", "Section 120(1)"
    patterns = [
        r"(?:Section|Sec\.?|S\.|§)\s+(\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?)",
        r"\b(BNS|BNSS|BSA|IPC|CrPC|CPC)\s*(?:§|Section|Sec\.?|S\.?)\s*(\d+[A-Za-z]?(?:\([A-Za-z0-9]+\))?)",
    ]

    seen = set()
    for pattern in patterns:
        for match in re.finditer(pattern, pdf_text, re.I):
            if len(match.groups()) >= 2 and match.group(1) and match.group(2):
                act = match.group(1).upper()
                section_no = normalize_section_no(match.group(2))
                ref = f"{act} §{section_no}"
            elif len(match.groups()) >= 1:
                section_no = normalize_section_no(match.group(1) if match.lastindex else match.group(0))
                # Try to find the act name from context
                context_start = max(0, match.start() - 80)
                context = pdf_text[context_start:match.end() + 30]
                act_key = canonical_act_key(context)
                if act_key:
                    ref = f"{act_key} §{section_no}"
                else:
                    ref = f"§{section_no}"
            else:
                continue

            # Only add section numbers (not "Section" alone)
            if re.search(r"\d", ref):
                normalized = ref.replace("§", "§ ").strip()
                if normalized not in seen:
                    seen.add(normalized)
                    sections.append(normalized)

    return sections


def tail_text(pdf_text: str, limit: int = 18000) -> str:
    return pdf_text[-limit:] if len(pdf_text) > limit else pdf_text


def infer_matter_label(text_value: str, case_number: str | None = None, petition_type: str | None = None) -> str:
    source = " ".join([case_number or "", petition_type or "", text_value[:8000]])
    normalized = normalize_text(source)
    if "appeal" in normalized:
        return "Appeal"
    if "application" in normalized or re.search(r"\bAPL\b|\bBA\b|\bABA\b", source, re.I):
        return "Application"
    if "petition" in normalized or re.search(r"\bWP\b|\bSLP\b|\bPIL\b", source, re.I):
        return "Petition"
    if "suit" in normalized:
        return "Suit"
    return "Matter"


def extract_universal_outcome(pdf_text: str) -> dict[str, str | None]:
    """Infer the operative result from common Indian judgment/order phrasing."""
    operative = tail_text(pdf_text)
    matter = infer_matter_label(pdf_text)
    checks = [
        (r"\b(partly|partially)\s+allowed\b|\ballowed\s+in\s+part\b", f"{matter} partly allowed"),
        (r"\ballowed\b[^.]{0,220}\b(?:partly|partially)\b", f"{matter} partly allowed"),
        (r"\b(?:conviction|sentence|order|judgment|decree|proceedings|FIR)\s+(?:is|are|stands?|stood)?\s*(?:quashed|set\s+aside)\b", f"{matter} allowed"),
        (r"\b(?:quash(?:ed)?|set\s+aside|restore(?:d)?|remand(?:ed)?)\b", f"{matter} allowed"),
        (r"\b(?:appeal|application|petition|suit|writ\s+petition)\s+(?:is|stands?|stand|shall\s+stand)?\s*allowed\b", None),
        (r"\ballowed\b", f"{matter} allowed"),
        (r"\b(?:appeal|application|petition|suit|writ\s+petition)\s+(?:is|stands?|stand|shall\s+stand)?\s*dismissed\b", None),
        (r"\bdismissed\b|\brejected\b", f"{matter} dismissed"),
        (r"\b(?:appeal|application|petition|suit|writ\s+petition|proceedings)\s+(?:is|stands?|stand|shall\s+stand)?\s*disposed\s+of\b", None),
        (r"\bdisposed\s+of\b|\bstands?\s+disposed\b", f"{matter} disposed of"),
        (r"\bnotice\s+(?:is\s+)?(?:issued|returnable)\b", "Notice issued"),
    ]
    for pattern, fallback in checks:
        match = re.search(pattern, operative, re.I)
        if not match:
            continue
        if fallback:
            return {"disposition": fallback}
        phrase = compact_lines(match.group(0))
        phrase = re.sub(r"\s+", " ", phrase).strip(" .")
        return {"disposition": phrase[:1].upper() + phrase[1:]}
    return {"disposition": None}


def extract_universal_plea(pdf_text: str, case_number: str | None = None, petition_type: str | None = None) -> str | None:
    """Extract what relief the appellant/applicant/petitioner sought."""
    sample = pdf_text[:30000]
    patterns = [
        r"The\s+Applicant\s+seeks\s+(.+?)(?:\n\s*\d+\.)",
        r"The\s+Petition\s+inter\s+alia\s+seeks\s+(.+?)(?:\n\s*\d+\.)",
        r"(?:has|have)\s+(?:filed|preferred)\s+the\s+present\s+(?:application|appeal|petition|suit)\s+(?:seeking|for)\s+(.+?)(?:\.\s|\n\s*\d+\.|\n[A-Z][A-Za-z ]{2,40}:)",
        r"(?:present\s+(?:application|appeal|petition|suit)\s+is\s+filed\s+)(?:seeking|for)\s+(.+?)(?:\.\s|\n\s*\d+\.|\n[A-Z][A-Za-z ]{2,40}:)",
        r"\b(?:seeking|sought|prays?\s+for|praying\s+for)\s+(.+?)(?:\.\s|\n\s*\d+\.|\n[A-Z][A-Za-z ]{2,40}:)",
        r"\b(?:challenge(?:s|d|ing)?|assail(?:s|ed|ing)?)\s+(.+?)(?:\.\s|\n\s*\d+\.|\n[A-Z][A-Za-z ]{2,40}:)",
    ]
    for pattern in patterns:
        match = re.search(pattern, sample, re.I | re.S)
        if match:
            plea = short_text(match.group(1), 520)
            if plea and not re.search(r"\b(?:CORAM|DATE|JUDGE|Advocate)\b", plea, re.I):
                return plea
    matter = infer_matter_label(pdf_text, case_number, petition_type).lower()
    if case_number:
        return f"Relief sought in {case_number}."
    if petition_type:
        return f"Relief sought in the {petition_type}."
    return f"Relief sought in the {matter}."


def extract_universal_grounds(pdf_text: str, outcome: dict[str, str | None] | None = None) -> list[str]:
    """Collect concise reasoning sentences from the judgment text."""
    del outcome
    candidates = []
    body_match = re.search(r"\bJudg(?:e)?ment\s*:\s*(.+)", pdf_text, re.I | re.S)
    source_text = body_match.group(1) if body_match else pdf_text
    text_value = compact_lines(source_text)
    sentence_pattern = r"[^.?!]{20,420}[.?!]"
    ground_markers = (
        r"\b(?:held|find|found|considering|in\s+view\s+of|therefore|accordingly|"
        r"because|reason|ground|satisfied|no\s+merit|merit|illegal|contrary|"
        r"liable|entitled|proved|failed\s+to|unable\s+to)\b"
    )
    for match in re.finditer(sentence_pattern, text_value, re.I):
        sentence = compact_lines(match.group(0))
        if re.search(ground_markers, sentence, re.I) and not re.search(r"\b(?:appearance|advocate|coram|date\s*:)\b", sentence, re.I):
            candidates.append(sentence)
    if not candidates:
        for paragraph in re.split(r"\n\s*\d+\.\s+", tail_text(pdf_text, 12000)):
            cleaned = short_text(paragraph, 420)
            if cleaned and re.search(ground_markers, cleaned, re.I):
                candidates.append(cleaned)
    return unique_items([item for item in candidates if item])[:8]


def extract_universal_sections(pdf_text: str) -> list[str]:
    refs = extract_sections_from_text(pdf_text)
    refs.extend(extract_acts_referred(pdf_text))
    return section_references(refs)


def format_specific_rules(detected_format: str) -> str:
    if detected_format == "digilegal_scc":
        return (
            'Detected format: DigiLegal/SCC. Set detected_format to "digilegal_scc". '
            'Extract "Acts Referred" into acts_referred exactly as written. Extract the full text after '
            '"# HEADNOTE #" into headnote. Use headnote as the primary source for holding, ratio, '
            'headnotes, and key_quotes. Parse judges from "Before :- Judge1 : Judge2 :JJ". '
            'Extract cited_cases from "Cases Referred". Convert section references to include symbols, '
            'for example "IPC §302", "Specific Relief Act §16", "Limitation Act Art.54".'
        )
    if detected_format == "law_finder":
        return (
            'Detected format: Law Finder. Set detected_format to "law_finder". Extract every IMPORTANT '
            'block into important_principles. Extract lettered holdings A, B, C, D into subsections as an '
            'object keyed by letter. Extract "Brief Facts" into brief_facts. Parse judges from '
            '"Before:- Judge1 and Judge2, JJ.". Extract cited_cases from "Cases Referred". Convert '
            'section references to include symbols, for example "IPC §376", "IPC §323".'
        )
    if detected_format == "high_court_order":
        return (
            'Detected format: raw High Court order. Set detected_format to "high_court_order". '
            'Extract neutral_citation from the first neutral citation line such as "2026:BHC-NAG:5672-DB". '
            'Extract court, bench, case_number, party_names from the header, judges from CORAM, date_judgment '
            'from DATE, and appearances from advocate appearance lines before CORAM. There may be no headnote. '
            'Summarize holding from numbered order paragraphs, extract operative court directions into directions, '
            'identify next_hearing_date when the order says listed on a future date, and extract cited_cases from '
            'paragraphs that refer to precedents.'
        )
    if detected_format == "supreme_court_order":
        return (
            'Detected format: Supreme Court neutral citation/order. Set detected_format to "supreme_court_order". '
            'Extract neutral_citation from the top line such as "2026 INSC 244". Extract court as '
            '"Supreme Court of India", case_number and party_names from the header, judges from signature '
            'blocks, date_judgment from the place/date line at the end, and disposition/directions from the '
            'final numbered paragraphs. There may be no headnote.'
        )
    if detected_format == "scc_reporter":
        return (
            'Detected format: SCC (Supreme Court Cases) reporter. Set detected_format to "scc_reporter". '
            'Extract SCC citation in format "(Year) SCC Volume Page" or "Year SCC OnLine SC Number". '
            'Extract the standard case name, court (Supreme Court of India), year from citation, '
            'party_names from case name, judges from the judgment, date_judgment, disposition, '
            'holding, ratio, headnote, and key_quotes. Store the exact SCC citation in scc_citation field.'
        )
    if detected_format == "manupatra":
        return (
            'Detected format: Manupatra. Set detected_format to "manupatra". '
            'Extract Manupatra citation in format "Manu/CourtCode/Year/Number" (e.g., Manu/SC/2024/123). '
            'Court codes: SC (Supreme Court), PH/DB (Delhi), MH (Bombay), TN (Madras), KA (Karnataka), '
            'CAL (Calcutta), GUJ (Gujarat), etc. Extract case name, year from citation, court from court code, '
            'case_number, party_names, judges, date_judgment, disposition, holding, ratio. '
            'Store the exact Manupatra citation in manupatra_citation field.'
        )
    if detected_format == "indian_kanoon":
        return (
            'Detected format: Indian Kanoon. Set detected_format to "indian_kanoon". '
            'Indian Kanoon uses neutral citation format "Year:Court:Number" (e.g., 2024:SC:567 or 2024:BOM-NAG:123-DB). '
            'Extract neutral_citation, year from citation, court from court code (SC=Supreme Court, BOM=Bombay HC, etc.), '
            'party_names from case name, judges, date_judgment, disposition, holding, ratio. '
            'If Indian Kanoon URL is present, store it in indian_kanoon_url field.'
        )
    return 'Detected format: generic. Set detected_format to "generic" and use the closest available equivalents.'


def prompt_for(pdf_text: str, filename: str) -> str:
    hints = extract_format_hints(pdf_text)
    return f"""
You extract structured data from Indian court judgments and legal citations.

Return only one valid JSON object. Do not use markdown. Do not add commentary.
Use null for unknown scalar values and [] for unknown list values.

Schema:
{json.dumps(CITATION_SCHEMA, indent=2)}

Format-specific instructions:
{format_specific_rules(hints["detected_format"])}

Pre-extracted hints. Prefer these when non-empty unless the judgment text clearly contradicts them:
{json.dumps(hints, indent=2)}

Rules:
- First determine whether the appellant/applicant/petitioner's plea was allowed, dismissed, partly allowed, or disposed of.
- Put that outcome in disposition using plain language such as "Appeal allowed", "Application dismissed", or "Petition disposed of".
- Put the exact operative relief in directions, including quashing, conviction affirmed, decree restored, remand, costs, or next listing.
- Put the grounds for allowing or rejecting the plea in holding, ratio, headnotes, important_principles, or headnote as appropriate for the source format.
- Prioritize the user's reading order: result first, grounds next, then sections/orders/provisions, then case identity.
- Preserve exact case names, court names, case numbers, section references, and cited case names when available.
- date_judgment must be DD-MM-YYYY if a date is found.
- petition_type must be the court case type/code when available, such as APL, APEAL, WP, WP-CR, FA, CRA, BA, ABA, PIL, SLP, or Other. Prefer the code from the case number/header over a generic label.
- key_quotes must be direct quotes from the judgment and each quote must be 20 words or fewer.
- holding and ratio must be concise and useful for later search.

Filename: {filename}

Judgment text:
{pdf_text[:AI_MAX_CHARS]}
""".strip()


def parse_json_response(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def parse_with_gemini(pdf_text: str, filename: str) -> dict[str, Any]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise RuntimeError("GEMINI_API_KEY is not configured")

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
    model_path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt_for(pdf_text, filename)}]}],
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    }
    response = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=180,
    )
    if not response.ok:
        detail = response.text[:1500]
        raise RuntimeError(f"Gemini request failed with HTTP {response.status_code}: {detail}")
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return parse_json_response(text)


def parse_with_local_http(pdf_text: str, filename: str) -> dict[str, Any]:
    endpoint = os.getenv("LOCAL_AI_ENDPOINT", "http://localhost:11434/api/legal-citation-parse")
    response = requests.post(
        endpoint,
        json={"filename": filename, "text": pdf_text[:AI_MAX_CHARS], "schema": CITATION_SCHEMA},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def parse_with_ollama(pdf_text: str, filename: str) -> dict[str, Any]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "32768"))
    response = requests.post(
        f"{base_url}/api/generate",
        json={
            "model": model,
            "prompt": prompt_for(pdf_text, filename),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_ctx": num_ctx,
            },
        },
        timeout=600,
    )
    if not response.ok:
        raise RuntimeError(f"Ollama request failed with HTTP {response.status_code}: {response.text[:1500]}")
    data = response.json()
    return parse_json_response(data.get("response", ""))


def parse_with_codex_cli(pdf_text: str, filename: str) -> dict[str, Any]:
    command = os.getenv("CODEX_CLI_COMMAND", "codex")
    proc = subprocess.run(
        [command, "exec", "--skip-git-repo-check", prompt_for(pdf_text, filename)],
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "Codex CLI parser failed")
    return parse_json_response(proc.stdout)




def fallback_from_hints(hints: dict[str, Any], filename: str) -> dict[str, Any]:
    party_names = hints.get("party_names") or []
    if len(party_names) >= 2:
        citation_name = f"{party_names[0]} v. {party_names[1]}"
    else:
        citation_name = hints.get("neutral_citation") or Path(filename).stem
    date_judgment = hints.get("date_judgment")
    year = None
    if date_judgment:
        year_match = re.search(r"\b(\d{4})\b", date_judgment)
        year = int(year_match.group(1)) if year_match else None
    elif hints.get("neutral_citation"):
        year = safe_year(str(hints["neutral_citation"])[:4])

    # Extract outcome universally
    outcome = extract_universal_outcome(hints.get("pdf_text", ""))

    # Extract plea universally
    plea = extract_universal_plea(
        hints.get("pdf_text", ""),
        hints.get("case_number", ""),
        hints.get("petition_type", "")
    )

    # Extract grounds universally
    grounds = extract_universal_grounds(hints.get("pdf_text", ""), outcome)

    # Extract sections universally
    sections = extract_universal_sections(hints.get("pdf_text", ""))

    directions = hints.get("directions") or []
    headnote = hints.get("headnote")
    principles = hints.get("important_principles") or []
    acts_referred = hints.get("acts_referred") or []

    holding = (
        short_text(" ".join(directions[:3]), 520)
        or short_text(headnote, 520)
        or short_text(" ".join(principles[:2]), 520)
        or short_text(" ".join(grounds[:2]), 520)
        or "Order metadata extracted; manual review may be needed."
    )
    if hints.get("detected_format") in {"high_court_order", "supreme_court_order"} and directions:
        ratio = short_text(" ".join(directions), 520)
    else:
        ratio = short_text(" ".join(grounds[:2]), 520) or short_text(headnote, 520) or short_text(principles[0] if principles else "", 520)

    return {
        "citation_name": citation_name,
        "court": hints.get("court") or "Unknown",
        "year": year,
        "petition_type": case_type_label(hints.get("petition_type") or infer_case_type_from_text(hints.get("case_number"), filename) or "Other"),
        "case_number": hints.get("case_number"),
        "neutral_citation": hints.get("neutral_citation"),
        "detected_format": hints.get("detected_format") or "generic",
        "bench": hints.get("bench") or [],
        "party_names": party_names,
        "disposition": outcome.get("disposition"),
        "cited_cases": hints.get("cited_cases") or [],
        "acts_referred": acts_referred,
        "headnote": hints.get("headnote"),
        "important_principles": principles,
        "subsections": hints.get("subsections") or {},
        "brief_facts": hints.get("brief_facts") or plea,
        "appearances": hints.get("appearances") or [],
        "order_type": hints.get("order_type"),
        "directions": directions,
        "next_hearing_date": hints.get("next_hearing_date"),
        "sections": sections,
        "laws": [],
        "holding": holding,
        "ratio": ratio,
        "headnotes": [headnote] if headnote else [],
        "key_quotes": extract_key_quotes_from_text(headnote or ""),
        "judges": hints.get("judges") or [],
        "date_judgment": date_judgment,
    }


def normalize_parsed_data(parsed: dict[str, Any], filename: str) -> dict[str, Any]:
    parsed = dict(parsed or {})
    parsed["citation_name"] = parsed.get("citation_name") or Path(filename).stem
    parsed["court"] = parsed.get("court") or "Unknown"
    parsed["year"] = safe_year(parsed.get("year"))
    parsed["petition_type"] = case_type_label(
        infer_case_type_from_text(parsed.get("case_number"), parsed.get("petition_type"), filename)
        or parsed.get("petition_type")
        or "Other"
    )
    parsed["case_number"] = parsed.get("case_number")
    parsed["neutral_citation"] = parsed.get("neutral_citation")
    parsed["detected_format"] = parsed.get("detected_format") if parsed.get("detected_format") in {"digilegal_scc", "law_finder", "high_court_order", "supreme_court_order", "scc_reporter", "manupatra", "indian_kanoon", "generic"} else "generic"
    parsed["disposition"] = parsed.get("disposition")
    parsed["date_judgment"] = parsed.get("date_judgment")
    parsed["headnote"] = parsed.get("headnote")
    parsed["brief_facts"] = parsed.get("brief_facts")
    parsed["order_type"] = parsed.get("order_type")
    parsed["next_hearing_date"] = parsed.get("next_hearing_date")
    if not isinstance(parsed.get("subsections"), dict):
        parsed["subsections"] = {}
    for field in REQUIRED_LIST_FIELDS:
        value = parsed.get(field)
        if value is None:
            parsed[field] = []
        elif isinstance(value, str):
            parsed[field] = [value]
        elif not isinstance(value, list):
            parsed[field] = []
    parsed["sections"] = section_references(parsed.get("sections", []))
    return parsed


def parse_citation(pdf_text: str, filename: str) -> dict[str, Any]:
    hints = extract_format_hints(pdf_text)
    # Add pdf_text to hints for universal extraction functions
    hints["pdf_text"] = pdf_text
    fast_formats = {
        item.strip()
        for item in os.getenv("FAST_PARSE_FORMATS", "digilegal_scc,law_finder,high_court_order,supreme_court_order,scc_reporter,manupatra,indian_kanoon").split(",")
        if item.strip()
    }
    if hints.get("detected_format") in fast_formats and os.getenv("FORCE_AI_PARSE", "false").lower() != "true":
        return normalize_parsed_data(fallback_from_hints(hints, filename), filename)
    try:
        if AI_PROVIDER == "gemini":
            parsed = parse_with_gemini(pdf_text, filename)
        elif AI_PROVIDER == "ollama":
            parsed = parse_with_ollama(pdf_text, filename)
        elif AI_PROVIDER == "local_http":
            parsed = parse_with_local_http(pdf_text, filename)
        elif AI_PROVIDER == "codex_cli":
            parsed = parse_with_codex_cli(pdf_text, filename)
        else:
            raise RuntimeError(f"Unsupported AI_PROVIDER: {AI_PROVIDER}")
    except (RuntimeError, requests.RequestException, json.JSONDecodeError):
        if hints.get("detected_format") in {"high_court_order", "supreme_court_order"}:
            parsed = fallback_from_hints(hints, filename)
        else:
            raise
    parsed = normalize_parsed_data(parsed, filename)

    for field in [
        "detected_format",
        "neutral_citation",
        "court",
        "case_number",
        "petition_type",
        "date_judgment",
        "headnote",
        "brief_facts",
        "order_type",
        "next_hearing_date",
    ]:
        if hints.get(field) and not parsed.get(field):
            parsed[field] = hints[field]
    for field in ["bench", "party_names", "judges", "acts_referred", "important_principles", "cited_cases", "appearances", "directions"]:
        if hints.get(field) and not parsed.get(field):
            parsed[field] = hints[field]
    if hints.get("subsections") and not parsed.get("subsections"):
        parsed["subsections"] = hints["subsections"]
    if hints.get("detected_format") != "generic":
        parsed["detected_format"] = hints["detected_format"]
    if hints.get("case_number"):
        parsed["case_number"] = hints["case_number"]
    if hints.get("petition_type"):
        parsed["petition_type"] = case_type_label(hints["petition_type"])
    if hints.get("date_judgment"):
        parsed["date_judgment"] = hints["date_judgment"]
    if hints.get("neutral_citation"):
        parsed["neutral_citation"] = hints["neutral_citation"]
    if hints.get("court"):
        parsed["court"] = hints["court"]
    if hints.get("bench"):
        parsed["bench"] = hints["bench"]
    if hints.get("party_names"):
        parsed["party_names"] = hints["party_names"]
    if hints.get("detected_format") in {"high_court_order", "supreme_court_order"} and len(hints.get("party_names", [])) >= 2:
        if not parsed.get("citation_name") or parsed.get("citation_name") in {filename, Path(filename).stem, hints.get("neutral_citation")}:
            parsed["citation_name"] = f"{hints['party_names'][0]} v. {hints['party_names'][1]}"
    return normalize_parsed_data(parsed, filename)


def find_near_duplicate(parsed: dict[str, Any], filename: str) -> Citation | None:
    normalized_name = normalize_text(parsed.get("citation_name"))
    normalized_filename = normalize_text(filename)
    court = normalize_text(parsed.get("court"))
    year = parsed.get("year")
    case_number = normalize_text(parsed.get("case_number"))
    neutral_citation = normalize_text(parsed.get("neutral_citation"))

    candidates = Citation.query.filter(
        or_(
            Citation.normalized_name == normalized_name,
            Citation.normalized_filename == normalized_filename,
            Citation.neutral_citation == parsed.get("neutral_citation") if parsed.get("neutral_citation") else False,
            Citation.case_number == parsed.get("case_number") if parsed.get("case_number") else False,
        )
    ).all()

    for candidate in candidates:
        candidate_court = normalize_text(candidate.court)
        if normalized_filename and candidate.normalized_filename == normalized_filename:
            return candidate
        if neutral_citation and normalize_text(candidate.neutral_citation) == neutral_citation:
            return candidate
        if case_number and normalize_text(candidate.case_number) == case_number and (not court or candidate_court == court):
            return candidate
        if normalized_name and candidate.normalized_name == normalized_name and (not court or candidate_court == court):
            return candidate
        if normalized_name and candidate.normalized_name == normalized_name and year and candidate.year == year:
            return candidate
    return None


def citation_from(parsed: dict[str, Any], filename: str, saved_path: Path, pdf_text: str) -> Citation:
    return Citation(
        citation_name=parsed["citation_name"],
        normalized_name=normalize_text(parsed["citation_name"]),
        original_filename=filename,
        normalized_filename=normalize_text(filename),
        file_path=str(saved_path),
        court=parsed.get("court"),
        year=parsed.get("year"),
        petition_type=parsed.get("petition_type"),
        case_number=parsed.get("case_number"),
        neutral_citation=parsed.get("neutral_citation"),
        bench=parsed.get("bench", []),
        party_names=parsed.get("party_names", []),
        disposition=parsed.get("disposition"),
        cited_cases=parsed.get("cited_cases", []),
        detected_format=parsed.get("detected_format"),
        acts_referred=parsed.get("acts_referred", []),
        headnote=parsed.get("headnote"),
        important_principles=parsed.get("important_principles", []),
        subsections=parsed.get("subsections", {}),
        brief_facts=parsed.get("brief_facts"),
        appearances=parsed.get("appearances", []),
        order_type=parsed.get("order_type"),
        directions=parsed.get("directions", []),
        next_hearing_date=parsed.get("next_hearing_date"),
        sections=parsed.get("sections", []),
        laws=parsed.get("laws", []),
        holding=parsed.get("holding"),
        ratio=parsed.get("ratio"),
        headnotes=parsed.get("headnotes", []),
        key_quotes=parsed.get("key_quotes", []),
        judges=parsed.get("judges", []),
        date_judgment=parsed.get("date_judgment"),
        pdf_text=pdf_text[:100000],
        tags=[],
        scc_citation=parsed.get("scc_citation"),
        manupatra_citation=parsed.get("manupatra_citation"),
        indian_kanoon_url=parsed.get("indian_kanoon_url"),
    )


def citation_text_export(citations: list[Citation]) -> str:
    lines = [os.getenv("GOOGLE_DOC_TITLE", "Legal Citation Library"), ""]
    for c in citations:
        data = c.to_dict()
        lines.extend(
            [
                data["citation_name"] or "Untitled citation",
                f"Court: {data['court'] or 'N/A'}",
                f"Year: {data['year'] or 'N/A'}",
                f"Type: {data['petition_type'] or 'N/A'}",
                f"Case Number: {data['case_number'] or 'N/A'}",
                f"Neutral Citation: {data['neutral_citation'] or 'N/A'}",
                f"Judgment Date: {data['date_judgment'] or 'N/A'}",
                f"Disposition: {data['disposition'] or 'N/A'}",
                f"Detected Format: {data['detected_format'] or 'N/A'}",
                f"Order Type: {data['order_type'] or 'N/A'}",
                f"Next Hearing Date: {data['next_hearing_date'] or 'N/A'}",
                f"Bench: {', '.join(data['bench']) or 'N/A'}",
                f"Parties: {', '.join(data['party_names']) or 'N/A'}",
                f"Appearances: {'; '.join(data['appearances']) or 'N/A'}",
                f"Acts Referred: {', '.join(data['acts_referred']) or 'N/A'}",
                f"Sections: {', '.join(data['sections']) or 'N/A'}",
                f"Laws: {', '.join(data['laws']) or 'N/A'}",
                f"Headnote: {data['headnote'] or 'N/A'}",
                f"Important Principles: {'; '.join(data['important_principles']) or 'N/A'}",
                f"Brief Facts: {data['brief_facts'] or 'N/A'}",
                f"Directions: {'; '.join(data['directions']) or 'N/A'}",
                f"Holding: {data['holding'] or 'N/A'}",
                f"Ratio: {data['ratio'] or 'N/A'}",
                f"Cited Cases: {', '.join(data['cited_cases']) or 'N/A'}",
                f"Tags: {', '.join(data['tags']) or 'N/A'}",
                "",
            ]
        )
    return "\n".join(lines)


def export_google_doc() -> dict[str, Any]:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    scopes = ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive.file"]
    credentials_path = Path(os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH", "./google_credentials.json"))
    token_path = Path(os.getenv("GOOGLE_TOKEN_PATH", "./google_token.json"))
    if not credentials_path.is_absolute():
        credentials_path = BASE_DIR / credentials_path
    if not token_path.is_absolute():
        token_path = BASE_DIR / token_path

    if not credentials_path.exists():
        return {
            "error": "Google credentials file not found",
            "setup": f"Put your OAuth client JSON at {credentials_path}",
        }

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    docs = build("docs", "v1", credentials=creds)
    citations = Citation.query.order_by(Citation.year.desc().nullslast(), Citation.created_at.desc()).all()
    document_id = os.getenv("GOOGLE_DOC_ID", "").strip()
    if document_id:
        existing_doc = docs.documents().get(documentId=document_id).execute()
        content = existing_doc.get("body", {}).get("content", [])
        end_index = content[-1].get("endIndex", 1) if content else 1
        if end_index > 2:
            docs.documents().batchUpdate(
                documentId=document_id,
                body={"requests": [{"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index - 1}}}]},
            ).execute()
    else:
        body = {"title": os.getenv("GOOGLE_DOC_TITLE", "Legal Citation Library")}
        doc = docs.documents().create(body=body).execute()
        document_id = doc["documentId"]
    text = citation_text_export(citations)
    docs.documents().batchUpdate(
        documentId=document_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": text}}]},
    ).execute()
    return {
        "document_id": document_id,
        "url": f"https://docs.google.com/document/d/{document_id}/edit",
        "count": len(citations),
    }


def import_bare_act_pdf(path: Path) -> int:
    pdf_text = extract_pdf_text(path)
    provisions = extract_provisions_from_text(pdf_text, path.name)
    imported = 0
    for data in provisions:
        existing = LegalProvision.query.filter_by(act_key=data["act_key"], section_no=data["section_no"]).first()
        if existing:
            existing.act_name = data["act_name"]
            existing.title = data["title"]
            existing.text = data["text"]
            existing.source_file = data["source_file"]
        else:
            db.session.add(LegalProvision(**data))
        imported += 1
    db.session.commit()
    return imported


def import_bare_acts_folder(folder: Path) -> dict[str, int]:
    results = {}
    LegalProvision.query.delete()
    db.session.commit()
    for path in sorted(folder.glob("*.pdf")):
        results[path.name] = import_bare_act_pdf(path)
    return results


def resolve_legal_provision(ref: str) -> LegalProvision | None:
    act_key, section_no = provision_reference_from_text(ref)
    if not section_no:
        return None
    query = LegalProvision.query.filter_by(section_no=section_no)
    if act_key:
        return query.filter_by(act_key=act_key).first()
    matches = query.limit(2).all()
    return matches[0] if len(matches) == 1 else None


@app.route("/api/upload", methods=["POST"])
def upload_pdf():
    if "pdf" not in request.files:
        return jsonify({"error": "No PDF provided"}), 400

    pdf_file = request.files["pdf"]
    original_filename = request.form.get("filename") or pdf_file.filename or "citation.pdf"
    if not original_filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted"}), 400

    saved_path = PDF_STORAGE / safe_filename(original_filename)
    pdf_file.save(saved_path)

    try:
        pdf_text = extract_pdf_text(saved_path)
        if len(pdf_text) < 100:
            return jsonify({"error": "Could not extract enough text from this PDF"}), 400

        parsed = parse_citation(pdf_text, original_filename)
        duplicate = find_near_duplicate(parsed, original_filename)
        if duplicate:
            return jsonify({"error": "Near-duplicate citation detected", "existing": duplicate.to_dict()}), 409

        citation = citation_from(parsed, original_filename, saved_path, pdf_text)
        db.session.add(citation)
        db.session.commit()

        if DELETE_PDF_AFTER_PROCESSING and saved_path.exists():
            saved_path.unlink()
            citation.file_path = None
            db.session.commit()

        export_result = None
        if os.getenv("AUTO_EXPORT_GOOGLE_DOCS", "false").lower() == "true":
            export_result = export_google_doc()

        response = citation.to_dict()
        if export_result:
            response["google_export"] = export_result
        return jsonify(response), 201
    except requests.HTTPError as exc:
        db.session.rollback()
        return jsonify({"error": "AI provider request failed", "details": str(exc)}), 502
    except requests.RequestException as exc:
        db.session.rollback()
        return jsonify({"error": "AI provider request failed", "details": str(exc)}), 502
    except RuntimeError as exc:
        db.session.rollback()
        return jsonify({"error": "AI provider request failed", "details": str(exc)}), 502
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 500
    finally:
        if DELETE_PDF_AFTER_PROCESSING and saved_path.exists():
            saved_path.unlink()


@app.route("/api/citations", methods=["GET"])
def get_citations():
    query = Citation.query
    petition_type = request.args.get("petition_type")
    section = request.args.get("section")
    year = request.args.get("year")
    search = request.args.get("search")

    if petition_type:
        terms = case_type_filter_terms(petition_type)
        query = query.filter(or_(*[Citation.petition_type.ilike(f"%{term}%") for term in terms]))
    if year:
        query = query.filter(Citation.year == safe_year(year))
    if section:
        query = query.filter(Citation.sections.like(f"%{section}%"))
    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Citation.citation_name.ilike(term),
                Citation.court.ilike(term),
                Citation.case_number.ilike(term),
                Citation.neutral_citation.ilike(term),
                Citation.holding.ilike(term),
                Citation.ratio.ilike(term),
                Citation.headnote.ilike(term),
                Citation.brief_facts.ilike(term),
                Citation.pdf_text.ilike(term),
            )
        )

    citations = query.order_by(Citation.created_at.desc()).all()
    return jsonify([citation.to_dict() for citation in citations])


@app.route("/api/citations/<int:citation_id>", methods=["GET"])
def get_citation(citation_id: int):
    citation = db.session.get(Citation, citation_id)
    if not citation:
        return jsonify({"error": "Not found"}), 404
    return jsonify(citation.to_dict())


@app.route("/api/provisions", methods=["GET"])
def get_legal_provision():
    ref = request.args.get("ref", "")
    act = request.args.get("act", "")
    section = request.args.get("section", "")
    if section:
        act_key = canonical_act_key(act)
        section_no = normalize_section_no(section)
        query = LegalProvision.query.filter_by(section_no=section_no)
        provision = query.filter_by(act_key=act_key).first() if act_key else query.first()
    else:
        provision = resolve_legal_provision(ref)
    if not provision:
        return jsonify({"error": "Provision not found"}), 404
    return jsonify(provision.to_dict())


@app.route("/api/citations/<int:citation_id>", methods=["PUT"])
def update_citation(citation_id: int):
    citation = db.session.get(Citation, citation_id)
    if not citation:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json() or {}
    editable = [
        "citation_name",
        "court",
        "year",
        "petition_type",
        "case_number",
        "neutral_citation",
        "bench",
        "party_names",
        "disposition",
        "cited_cases",
        "detected_format",
        "acts_referred",
        "headnote",
        "important_principles",
        "subsections",
        "brief_facts",
        "appearances",
        "order_type",
        "directions",
        "next_hearing_date",
        "sections",
        "laws",
        "holding",
        "ratio",
        "headnotes",
        "key_quotes",
        "judges",
        "date_judgment",
        "tags",
        "notes",
        "scc_citation",
        "manupatra_citation",
        "indian_kanoon_url",
    ]
    for field in editable:
        if field in data:
            setattr(citation, field, safe_year(data[field]) if field == "year" else data[field])
    citation.normalized_name = normalize_text(citation.citation_name)
    db.session.commit()
    return jsonify(citation.to_dict())


@app.route("/api/delete/<int:citation_id>", methods=["DELETE"])
def delete_citation(citation_id: int):
    citation = db.session.get(Citation, citation_id)
    if not citation:
        return jsonify({"error": "Not found"}), 404
    if citation.file_path and Path(citation.file_path).exists():
        Path(citation.file_path).unlink()
    db.session.delete(citation)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    applications = Citation.query.filter(Citation.petition_type.ilike("%Application%")).count()
    petitions = Citation.query.filter(Citation.petition_type.ilike("%Petition%")).count()
    appeals = Citation.query.filter(Citation.petition_type.ilike("%Appeal%")).count()
    return jsonify(
        {
            "total_citations": Citation.query.count(),
            "application_count": applications,
            "petition_count": petitions,
            "appeal_count": appeals,
            "other_type_count": Citation.query.filter(
                ~Citation.petition_type.ilike("%Application%"),
                ~Citation.petition_type.ilike("%Petition%"),
                ~Citation.petition_type.ilike("%Appeal%"),
            ).count(),
        }
    )


@app.route("/api/export/google", methods=["POST"])
def export_to_google_docs():
    result = export_google_doc()
    status = 400 if "error" in result else 200
    return jsonify(result), status


@app.route("/")
def dashboard():
    citation_rows = Citation.query.order_by(Citation.created_at.desc()).all()
    citations = [citation.to_dict() for citation in citation_rows]
    stats = {
        "total": len(citations),
        "applications": len([c for c in citations if "application" in normalize_text(c.get("petition_type"))]),
        "petitions": len([c for c in citations if "petition" in normalize_text(c.get("petition_type"))]),
        "appeals": len([c for c in citations if "appeal" in normalize_text(c.get("petition_type"))]),
        "other_types": len(
            [
                c
                for c in citations
                if not re.search(r"\b(application|petition|appeal)\b", normalize_text(c.get("petition_type")))
            ]
        ),
    }
    case_types = [{"code": code, "label": label, "display": CASE_TYPE_LABELS[code]} for code, label in CASE_TYPES]
    return render_template("dashboard.html", citations=citations, stats=stats, ai_provider=AI_PROVIDER, case_types=case_types)


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(_):
    return jsonify({"error": "Server error"}), 500


def init_db() -> None:
    with app.app_context():
        db.create_all()
        existing = {row[1] for row in db.session.execute(text("PRAGMA table_info(citations)")).fetchall()}
        columns = {
            "detected_format": "VARCHAR(80)",
            "acts_referred": "JSON",
            "headnote": "TEXT",
            "important_principles": "JSON",
            "subsections": "JSON",
            "brief_facts": "TEXT",
            "neutral_citation": "VARCHAR(200)",
            "appearances": "JSON",
            "order_type": "VARCHAR(120)",
            "directions": "JSON",
            "next_hearing_date": "VARCHAR(50)",
            "scc_citation": "VARCHAR(200)",
            "manupatra_citation": "VARCHAR(200)",
            "indian_kanoon_url": "VARCHAR(500)",
        }
        for name, column_type in columns.items():
            if name not in existing:
                db.session.execute(text(f"ALTER TABLE citations ADD COLUMN {name} {column_type}"))
        db.session.commit()


if __name__ == "__main__":
    init_db()
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "5757"))
    print(f"Database: {DATABASE_PATH}")
    print(f"AI provider: {AI_PROVIDER}")
    print(f"Backend running on http://{host}:{port}")
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host=host, port=port, debug=debug)
