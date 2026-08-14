from __future__ import annotations

import argparse
import configparser
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse


SITE_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = SITE_DIR.parent / "resources"
DOWNLOADS_DIR = SITE_DIR / "downloads"
ASSETS_DIR = SITE_DIR / "assets"
CATEGORIES_DIR = SITE_DIR / "categories"
ARCHIVE_PAGE_REL = Path("roundtable-archive.html")
ARCHIVE_SOURCE_PATH = SITE_DIR / "The Roundtable archive" / "page and instructions for importing the list archive into Mozilla Thunderbird.txt"
ARCHIVE_DOWNLOAD_URL = "https://drive.usercontent.google.com/download?id=1iuu-cuLNVUHtBxwHuudjLYXmcY5CdMqz&export=download&confirm=t"
GOOGLE_GROUP_URL = "https://groups.google.com/g/blindlanguageprofessionals"
PUBLISH_PATHS = (
    ".gitignore",
    ".nojekyll",
    "README.md",
    "index.html",
    "roundtable-archive.html",
    "search.html",
    "assets",
    "categories",
    "downloads",
    "tools/build_site.py",
)
ASSET_VERSIONS: dict[str, str] = {}


@dataclass(frozen=True)
class Resource:
    title: str
    source_rel: Path
    category: str
    subcategory: str
    kind: str
    href: str
    search_text: str
    type_label: str
    size_label: str = ""
    downloadable: bool = False
    download_name: str = ""


@dataclass(frozen=True)
class CategoryPage:
    source_dir: Path
    title: str
    page_rel: Path
    resource_count: int


@dataclass(frozen=True)
class PageNote:
    source_rel: Path
    target_dir: Path
    text: str


TYPE_LABELS = {
    ".doc": "Word document",
    ".docx": "Word document",
    ".pdf": "PDF",
    ".rtf": "RTF document",
}

EXCLUDED_SOURCE_EXTENSIONS = {".mbox"}
NOTE_URL_RE = re.compile(r"https?://[^\s<]+")
TRAILING_URL_PUNCTUATION = ".,;:!?)\"]}"
RESOURCE_TITLE_REPLACEMENTS = {
    "eole, audiobooks for French speakers": "Éole, audiobooks for French speakers",
    "eole, livres d'audio": "Éole, livres d'audio",
}
LANGUAGE_TITLE_SEGMENTS: dict[str, tuple[tuple[str, str], ...]] = {
    "2 Heures de Perdues": (("fr", "2 Heures de Perdues"),),
    "21 JOURS DANS LA PEAU D'UN AVEUGLE": (("fr", "21 JOURS DANS LA PEAU D'UN AVEUGLE"),),
    "Accesibilidad para no videntes en HTML - Leandro Benítez - YouTube": (
        ("es", "Accesibilidad para no videntes en HTML - Leandro Benítez - YouTube"),
    ),
    "acontece que no es poco": (("es", "acontece que no es poco"),),
    "Affaires sensibles": (("fr", "Affaires sensibles"),),
    "Banque de dépannage linguistique": (("fr", "Banque de dépannage linguistique"),),
    "Code braille français uniformisé": (("fr", "Code braille français uniformisé"),),
    "Conseils pratiques pour réussir votre carrière en Allemagne": (
        ("fr", "Conseils pratiques pour réussir votre carrière en Allemagne"),
    ),
    "Cosnautas, Spanish medical terminology": (
        ("es", "Cosnautas"),
        ("", ", Spanish medical terminology"),
    ),
    "Criminopatía": (("es", "Criminopatía"),),
    "Diccionario de la lengua española, Spanish monolingual dictionary": (
        ("es", "Diccionario de la lengua española"),
        ("", ", Spanish monolingual dictionary"),
    ),
    "Dictionnaire des cooccurrences, French collocations": (
        ("fr", "Dictionnaire des cooccurrences"),
        ("", ", French collocations"),
    ),
    "Duden, monolingual German dictionary": (
        ("de", "Duden"),
        ("", ", monolingual German dictionary"),
    ),
    "Die Übersetzerin Sonja Finck als Wortakrobatin": (
        ("de", "Die Übersetzerin Sonja Finck als Wortakrobatin"),
    ),
    "DBSV, YouTube": (("de", "DBSV, YouTube"),),
    "DBSV auf YouTube": (("de", "DBSV auf YouTube"),),
    "Documentos RNE": (("es", "Documentos RNE"),),
    "El Faro": (("es", "El Faro"),),
    "entrevue sur les nouvelles technologies et la déficience visuelle": (
        ("fr", "entrevue sur les nouvelles technologies et la déficience visuelle"),
    ),
    "Éole, audiobooks for French speakers": (("fr", "Éole, audiobooks for French speakers"),),
    "Éole, livres d'audio": (("fr", "Éole, livres d'audio"),),
    "Español con Juan": (("es", "Español con Juan"),),
    "Estirando el chicle": (("es", "Estirando el chicle"),),
    "FloodCast": (("fr", "FloodCast"),),
    "Greta, iOS and Android app for audio described films in German": (
        ("de", "Greta"),
        ("", ", iOS and Android app for audio described films in German"),
    ),
    "Groupes de Discussions, DV": (("fr", "Groupes de Discussions, DV"),),
    "Guide du Rédacteur, French writing guide": (
        ("fr", "Guide du Rédacteur"),
        ("", ", French writing guide"),
    ),
    "Hommage aux traducteurs et traductrices de par le monde": (
        ("fr", "Hommage aux traducteurs et traductrices de par le monde"),
    ),
    "Hoy en el País": (("es", "Hoy en el País"),),
    "Institut Nazareth et Louis-Braille (INLB)": (("fr", "Institut Nazareth et Louis-Braille (INLB)"),),
    "Interprète officiel, qui se cache derrière la voix de Donald Trump": (
        ("fr", "Interprète officiel, qui se cache derrière la voix de Donald Trump"),
    ),
    "JOURNAL EN FRANÇAIS FACILE": (("fr", "JOURNAL EN FRANÇAIS FACILE"),),
    "La Bibliothèque Braille Romande": (("fr", "La Bibliothèque Braille Romande"),),
    "La Escóbula de la Brújula": (("es", "La Escóbula de la Brújula"),),
    "La Ruina": (("es", "La Ruina"),),
    "La Vitrine linguistique de l'Office québécois de la langue française": (
        ("fr", "La Vitrine linguistique de l'Office québécois de la langue française"),
    ),
    "larousse": (("fr", "larousse"),),
    "Le braille, la «lecture par les doigts», en cinq dates clefs": (
        ("fr", "Le braille, la «lecture par les doigts», en cinq dates clefs"),
    ),
    "Le Robert, monolingual French dictionary": (
        ("fr", "Le Robert"),
        ("", ", monolingual French dictionary"),
    ),
    "leo.org": (("de", "leo.org"),),
    "Les Pieds sur terre": (("fr", "Les Pieds sur terre"),),
    "Légende, better to find the podcast episodes in a podcatcher": (
        ("fr", "Légende"),
        ("", ", better to find the podcast episodes in a podcatcher"),
    ),
    "L’anglais est faite d’emprunts au français, souligne Bernard Cerquiglini": (
        ("fr", "L’anglais est faite d’emprunts au français, souligne Bernard Cerquiglini"),
    ),
    "Mediengemeinschaft für blinde, seh- und lesebehinderte Menschen": (
        ("de", "Mediengemeinschaft für blinde, seh- und lesebehinderte Menschen"),
    ),
    "Nadie Sabe Nada": (("es", "Nadie Sabe Nada"),),
    "podcasts de RNE": (("es", "podcasts de RNE"),),
    "Polyglottes dans leur cerveau, un traitement étrange de la langue maternelle": (
        ("fr", "Polyglottes dans leur cerveau, un traitement étrange de la langue maternelle"),
    ),
    "pons": (("de", "pons"),),
    "Radio Ambulante": (("es", "Radio Ambulante"),),
    "Sofá Sonoro": (("es", "Sofá Sonoro"),),
    "Thomas Weiler, Er übersetzt die Stimmen Osteuropas": (
        ("de", "Thomas Weiler, Er übersetzt die Stimmen Osteuropas"),
    ),
    "tiflolibros, ebooks mainly in Spanish": (
        ("es", "tiflolibros"),
        ("", ", ebooks mainly in Spanish"),
    ),
    "Tiflonexos Servicios para personas con discapacidad visual": (
        ("es", "Tiflonexos Servicios para personas con discapacidad visual"),
    ),
    "Transfert": (("fr", "Transfert"),),
    "Video sobre la interpretación simultánea": (("es", "Video sobre la interpretación simultánea"),),
    "Winaide, French program for dictionaries": (
        ("fr", "Winaide"),
        ("", ", French program for dictionaries"),
    ),
}

for _title, _segments in LANGUAGE_TITLE_SEGMENTS.items():
    if "".join(text for _, text in _segments) != _title:
        raise ValueError(f"Language title segments do not match title: {_title}")

LANGUAGE_NAME_TO_CODE = {
    "afrikaans": "af",
    "albanian": "sq",
    "amharic": "am",
    "arabic": "ar",
    "armenian": "hy",
    "azerbaijani": "az",
    "basque": "eu",
    "belarusian": "be",
    "bengali": "bn",
    "bosnian": "bs",
    "bulgarian": "bg",
    "burmese": "my",
    "catalan": "ca",
    "chinese": "zh",
    "croatian": "hr",
    "czech": "cs",
    "danish": "da",
    "dutch": "nl",
    "english": "en",
    "estonian": "et",
    "farsi": "fa",
    "finnish": "fi",
    "french": "fr",
    "georgian": "ka",
    "german": "de",
    "greek": "el",
    "gujarati": "gu",
    "hebrew": "he",
    "hindi": "hi",
    "hungarian": "hu",
    "icelandic": "is",
    "indonesian": "id",
    "irish": "ga",
    "italian": "it",
    "japanese": "ja",
    "kannada": "kn",
    "khmer": "km",
    "korean": "ko",
    "lao": "lo",
    "latvian": "lv",
    "lithuanian": "lt",
    "macedonian": "mk",
    "malay": "ms",
    "malayalam": "ml",
    "mandarin": "zh",
    "marathi": "mr",
    "nepali": "ne",
    "norwegian": "no",
    "persian": "fa",
    "polish": "pl",
    "portuguese": "pt",
    "punjabi": "pa",
    "romanian": "ro",
    "russian": "ru",
    "serbian": "sr",
    "slovak": "sk",
    "slovenian": "sl",
    "spanish": "es",
    "swahili": "sw",
    "swedish": "sv",
    "tagalog": "tl",
    "tamil": "ta",
    "telugu": "te",
    "thai": "th",
    "turkish": "tr",
    "ukrainian": "uk",
    "urdu": "ur",
    "vietnamese": "vi",
    "welsh": "cy",
}

LANGUAGE_TLD_TO_CODE = {
    "ae": "ar",
    "am": "hy",
    "ar": "es",
    "at": "de",
    "be": "nl",
    "bg": "bg",
    "br": "pt",
    "ca": "fr",
    "ch": "de",
    "cl": "es",
    "cn": "zh",
    "co": "es",
    "cz": "cs",
    "de": "de",
    "dk": "da",
    "ee": "et",
    "eg": "ar",
    "es": "es",
    "fi": "fi",
    "fr": "fr",
    "gr": "el",
    "hk": "zh",
    "hu": "hu",
    "il": "he",
    "in": "hi",
    "ir": "fa",
    "is": "is",
    "it": "it",
    "jp": "ja",
    "kr": "ko",
    "lt": "lt",
    "lv": "lv",
    "mx": "es",
    "nl": "nl",
    "no": "no",
    "pl": "pl",
    "pt": "pt",
    "ro": "ro",
    "rs": "sr",
    "ru": "ru",
    "sa": "ar",
    "se": "sv",
    "si": "sl",
    "sk": "sk",
    "th": "th",
    "tr": "tr",
    "tw": "zh",
    "ua": "uk",
    "vn": "vi",
}

URL_LANGUAGE_PARAMS = {"hl", "lang", "language", "locale", "ui_locales"}
LATIN_LANGUAGE_CLUES = {
    "ca": {
        "chars": set("àçéèíïóòúü"),
        "words": {"aquest", "aquesta", "amb", "del", "dels", "els", "les", "per", "que"},
    },
    "cs": {
        "chars": set("áčďéěíňóřšťúůýž"),
        "words": {"cesky", "česky", "jako", "který", "pro", "se", "ve"},
    },
    "da": {
        "chars": set("æøå"),
        "words": {"at", "det", "en", "for", "med", "og", "på", "til"},
    },
    "de": {
        "chars": set("äöüß"),
        "words": {"als", "das", "dem", "den", "der", "des", "die", "ein", "eine", "für", "mit", "und", "von", "zum"},
    },
    "es": {
        "chars": set("áéíóúñü¿¡"),
        "words": {"con", "de", "del", "el", "en", "español", "la", "las", "los", "no", "para", "por", "que", "sobre", "una"},
    },
    "fi": {
        "chars": set("äö"),
        "words": {"että", "ja", "kanssa", "on", "sekä", "suomi", "suomen"},
    },
    "fr": {
        "chars": set("àâæçéèêëîïôœùûü"),
        "words": {"avec", "aux", "dans", "de", "des", "du", "en", "et", "français", "la", "langue", "le", "les", "par", "pour", "sur", "une"},
    },
    "hu": {
        "chars": set("áéíóöőúüű"),
        "words": {"az", "egy", "és", "hogy", "magyar", "nem", "van"},
    },
    "it": {
        "chars": set("àèéìòù"),
        "words": {"che", "con", "dei", "del", "della", "di", "gli", "il", "italiano", "la", "le", "per", "una"},
    },
    "nl": {
        "chars": set("áéíóúëï"),
        "words": {"de", "een", "en", "het", "met", "nederlands", "op", "voor", "van"},
    },
    "no": {
        "chars": set("æøå"),
        "words": {"det", "en", "for", "med", "norsk", "og", "på", "til"},
    },
    "pl": {
        "chars": set("ąćęłńóśźż"),
        "words": {"dla", "jest", "na", "polski", "się", "oraz", "w", "z"},
    },
    "pt": {
        "chars": set("áâãàçéêíóôõúü"),
        "words": {"com", "da", "das", "de", "do", "dos", "em", "não", "o", "os", "para", "português", "que", "uma"},
    },
    "ro": {
        "chars": set("ăâîșşțţ"),
        "words": {"cu", "de", "în", "la", "pentru", "română", "și", "sau"},
    },
    "sk": {
        "chars": set("áäčďéíĺľňóôŕšťúýž"),
        "words": {"je", "na", "pre", "sa", "slovensky", "v"},
    },
    "sv": {
        "chars": set("åäö"),
        "words": {"att", "den", "det", "för", "med", "och", "på", "svenska"},
    },
    "tr": {
        "chars": set("çğıİöşü"),
        "words": {"bir", "için", "ile", "türkçe", "ve"},
    },
    "vi": {
        "chars": set("ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ"),
        "words": {"của", "cho", "tiếng", "trong", "và", "với"},
    },
}

ENGLISH_TITLE_WORDS = {
    "accessibility",
    "accessible",
    "add",
    "and",
    "android",
    "app",
    "also",
    "audio",
    "audiobooks",
    "available",
    "best",
    "braille",
    "break",
    "coffee",
    "dictionary",
    "duolingo",
    "easy",
    "ebooks",
    "education",
    "english",
    "for",
    "free",
    "french",
    "from",
    "german",
    "grammar",
    "guide",
    "in",
    "italian",
    "language",
    "languages",
    "learn",
    "learning",
    "monolingual",
    "on",
    "podcast",
    "podcasts",
    "reader",
    "screen",
    "spanish",
    "speakers",
    "store",
    "the",
    "to",
    "with",
    "youtube",
}

SCRIPT_LANGUAGE_RANGES = (
    ("Greek", "el", {"el"}, ((0x0370, 0x03FF), (0x1F00, 0x1FFF))),
    ("Cyrillic", "ru", {"be", "bg", "kk", "ky", "mk", "mn", "ru", "sr", "tg", "uk", "uz"}, ((0x0400, 0x052F),)),
    ("Arabic", "ar", {"ar", "fa", "ps", "ur"}, ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF))),
    ("Hebrew", "he", {"he"}, ((0x0590, 0x05FF),)),
    ("Devanagari", "hi", {"hi", "mr", "ne", "sa"}, ((0x0900, 0x097F),)),
    ("Bengali", "bn", {"bn"}, ((0x0980, 0x09FF),)),
    ("Gurmukhi", "pa", {"pa"}, ((0x0A00, 0x0A7F),)),
    ("Gujarati", "gu", {"gu"}, ((0x0A80, 0x0AFF),)),
    ("Tamil", "ta", {"ta"}, ((0x0B80, 0x0BFF),)),
    ("Telugu", "te", {"te"}, ((0x0C00, 0x0C7F),)),
    ("Kannada", "kn", {"kn"}, ((0x0C80, 0x0CFF),)),
    ("Malayalam", "ml", {"ml"}, ((0x0D00, 0x0D7F),)),
    ("Thai", "th", {"th"}, ((0x0E00, 0x0E7F),)),
    ("Lao", "lo", {"lo"}, ((0x0E80, 0x0EFF),)),
    ("Georgian", "ka", {"ka"}, ((0x10A0, 0x10FF),)),
    ("Hangul", "ko", {"ko"}, ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF))),
    ("Ethiopic", "am", {"am"}, ((0x1200, 0x137F),)),
    ("Khmer", "km", {"km"}, ((0x1780, 0x17FF),)),
    ("Myanmar", "my", {"my"}, ((0x1000, 0x109F),)),
    ("Armenian", "hy", {"hy"}, ((0x0530, 0x058F),)),
)

HAN_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))
KANA_RANGES = ((0x3040, 0x309F), (0x30A0, 0x30FF))


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def read_shortcut_url(path: Path) -> str:
    text = read_text(path)
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        parser.read_string(text)
        if parser.has_section("InternetShortcut"):
            url = parser.get("InternetShortcut", "URL", fallback="").strip()
            if url:
                return url
    except configparser.Error:
        pass

    for line in text.splitlines():
        if line.startswith("URL="):
            return line[4:].strip()
    raise ValueError(f"No URL found in {path}")


def clean_title(stem: str) -> str:
    title = re.sub(r"\s+", " ", stem).strip()
    for suffix in (" - Google Chrome", " - Brave"):
        if title.endswith(suffix):
            title = title[: -len(suffix)].strip()
    return RESOURCE_TITLE_REPLACEMENTS.get(title, title)


def clean_download_title(stem: str) -> str:
    title = clean_title(stem)
    if " " not in title and re.search(r"[a-z][A-Z]", title):
        title = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", title)
    return title


def normalize_language_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^a-z]+", " ", value).strip()
    return value


def normalize_language_code(value: str) -> str:
    value = value.strip().replace("_", "-").casefold()
    match = re.match(r"([a-z]{2,3})(?:-[a-z0-9]+)?$", value)
    if not match:
        return ""
    code = match.group(1)
    return "" if code == "en" else code


def language_code_from_context(source_rel: Path | None) -> str:
    if source_rel is None:
        return ""
    for part in reversed(source_rel.parent.parts):
        code = LANGUAGE_NAME_TO_CODE.get(normalize_language_name(part), "")
        if code and code != "en":
            return code
    return ""


def language_code_from_url(href: str) -> str:
    if not href or not re.match(r"^[a-z][a-z0-9+.-]*:", href, flags=re.IGNORECASE):
        return ""

    try:
        parsed = urlparse(href)
    except ValueError:
        return ""

    query = parse_qs(parsed.query)
    for param in URL_LANGUAGE_PARAMS:
        for value in query.get(param, []):
            code = normalize_language_code(value)
            if code:
                return code

    for segment in parsed.path.split("/"):
        code = normalize_language_code(segment)
        if code:
            return code

    host = parsed.hostname or ""
    tld = host.rsplit(".", 1)[-1].casefold() if "." in host else ""
    return LANGUAGE_TLD_TO_CODE.get(tld, "")


def codepoint_in_ranges(codepoint: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= codepoint <= end for start, end in ranges)


def language_code_from_script(title: str, context_code: str) -> str:
    letter_count = sum(1 for char in title if char.isalpha())
    if letter_count == 0:
        return ""

    kana_count = sum(1 for char in title if codepoint_in_ranges(ord(char), KANA_RANGES))
    if kana_count:
        return "ja"

    han_count = sum(1 for char in title if codepoint_in_ranges(ord(char), HAN_RANGES))
    if han_count >= max(1, letter_count // 4):
        return context_code if context_code in {"ja", "ko", "zh"} else "zh"

    for _, default_code, context_codes, ranges in SCRIPT_LANGUAGE_RANGES:
        script_count = sum(1 for char in title if codepoint_in_ranges(ord(char), ranges))
        if script_count >= max(1, letter_count // 4):
            return context_code if context_code in context_codes else default_code
    return ""


def title_words(title: str) -> list[str]:
    return re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", title.casefold(), flags=re.UNICODE)


def title_has_latin_non_ascii(title: str) -> bool:
    for char in title:
        if not char.isalpha() or ord(char) < 128:
            continue
        if "LATIN" in unicodedata.name(char, ""):
            return True
    return False


def language_code_from_latin_clues(title: str, context_code: str, url_code: str) -> str:
    tokens = title_words(title)
    if not tokens:
        return ""

    title_lower = title.casefold()
    scores: dict[str, float] = defaultdict(float)
    for code, clues in LATIN_LANGUAGE_CLUES.items():
        scores[code] += sum(3 for char in set(title_lower) if char in clues["chars"])
        scores[code] += sum(2 for token in tokens if token in clues["words"])

    if context_code in scores and scores[context_code] > 0:
        scores[context_code] += 1.5
    if url_code in scores and scores[url_code] > 0:
        scores[url_code] += 1

    english_score = sum(1 for token in tokens if token in ENGLISH_TITLE_WORDS)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_code, best_score = ranked[0] if ranked else ("", 0)
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if best_score >= 4 and (best_score - second_score >= 2 or best_code in {context_code, url_code}):
        if best_code not in {context_code, url_code} and not title_has_latin_non_ascii(title) and best_score < 6:
            return ""
        if english_score >= best_score and best_code not in {context_code, url_code}:
            return ""
        return best_code

    if context_code and scores.get(context_code, 0) >= 2:
        if english_score >= scores[context_code] + 1:
            return ""
        return context_code

    if url_code and scores.get(url_code, 0) >= 3:
        if english_score >= scores[url_code] + 1:
            return ""
        return url_code

    if context_code and context_code == url_code and len(tokens) >= 2 and english_score == 0:
        return context_code

    if context_code and title_has_latin_non_ascii(title) and english_score == 0:
        return context_code

    return ""


def inferred_title_language(title: str, source_rel: Path | None = None, href: str = "") -> str:
    context_code = language_code_from_context(source_rel)
    script_code = language_code_from_script(title, context_code)
    if script_code:
        return script_code

    url_code = language_code_from_url(href)
    return language_code_from_latin_clues(title, context_code, url_code)


def title_language_segments(title: str, source_rel: Path | None = None, href: str = "") -> tuple[tuple[str, str], ...]:
    segments = LANGUAGE_TITLE_SEGMENTS.get(title, ())
    if segments:
        return segments

    language_code = inferred_title_language(title, source_rel, href)
    if not language_code:
        return ()
    return ((language_code, title),)


def render_title_text(title: str, source_rel: Path | None = None, href: str = "") -> tuple[str, str]:
    segments = title_language_segments(title, source_rel, href)
    if not segments:
        return html.escape(title), ""

    if len(segments) == 1 and segments[0][0]:
        lang, text = segments[0]
        return html.escape(text), f' lang="{html.escape(lang, quote=True)}"'

    markup = "".join(
        f'<span lang="{html.escape(lang, quote=True)}">{html.escape(text)}</span>'
        if lang
        else html.escape(text)
        for lang, text in segments
    )
    return markup, ""


def search_title_segments(title: str, source_rel: Path | None = None, href: str = "") -> list[dict[str, str]]:
    return [{"lang": lang, "text": text} for lang, text in title_language_segments(title, source_rel, href)]


def clean_category(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "resource"


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} bytes"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def safe_download_stem(title: str) -> str:
    title = unicodedata.normalize("NFKC", title)
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", title)
    title = re.sub(r"\s+", " ", title).strip(" .")
    return title or "download"


def unique_download_path(source: Path, title: str, used_names: set[str]) -> tuple[Path, str]:
    rel = source.relative_to(SOURCE_DIR)
    parts = [slugify(part) for part in rel.parts[:-1]]
    file_stem = safe_download_stem(title)
    suffix = source.suffix.lower()
    folder = DOWNLOADS_DIR.joinpath(*parts)
    candidate = folder / f"{file_stem}{suffix}"
    download_name = candidate.name
    counter = 2
    while str(candidate.relative_to(DOWNLOADS_DIR)).lower() in used_names:
        candidate = folder / f"{file_stem}-{counter}{suffix}"
        download_name = candidate.name
        counter += 1
    used_names.add(str(candidate.relative_to(DOWNLOADS_DIR)).lower())
    return candidate, download_name


def href_for(path: Path) -> str:
    return quote(path.as_posix(), safe="/")


def relative_href(from_page: Path, to_path: Path) -> str:
    start = (SITE_DIR / from_page).parent
    target = SITE_DIR / to_path
    rel = os.path.relpath(target, start=start).replace(os.sep, "/")
    return quote(rel, safe="/")


def content_version(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def asset_href(from_page: Path, to_path: Path) -> str:
    href = relative_href(from_page, to_path)
    version = ASSET_VERSIONS.get(to_path.name)
    return f"{href}?v={version}" if version else href


def site_root_href(from_page: Path) -> str:
    start = (SITE_DIR / from_page).parent
    rel = os.path.relpath(SITE_DIR, start=start).replace(os.sep, "/")
    if rel == ".":
        return "./"
    return quote(rel.rstrip("/") + "/", safe="/")


def folder_page_rel(source_dir: Path) -> Path:
    return Path("categories").joinpath(*(slugify(part) for part in source_dir.parts), "index.html")


def is_inside_dir(path: Path, folder: Path) -> bool:
    path_parts = path.parts
    folder_parts = folder.parts
    return path_parts[: len(folder_parts)] == folder_parts


def ancestor_scopes(folder: Path) -> list[str]:
    scopes: list[str] = []
    current = Path()
    for part in folder.parts:
        current = current / part
        scopes.append(current.as_posix())
    return scopes


def make_resource(path: Path, used_download_names: set[str]) -> Resource:
    rel = path.relative_to(SOURCE_DIR)
    parts = rel.parts
    category = clean_category(parts[0]) if len(parts) > 1 else "Resources"
    subcategory = " / ".join(clean_category(part) for part in parts[1:-1])
    title = clean_title(path.stem)

    if path.suffix.lower() == ".url":
        url = read_shortcut_url(path)
        type_label = "External link"
        return Resource(
            title=title,
            source_rel=rel,
            category=category,
            subcategory=subcategory,
            kind="link",
            href=url,
            search_text=" ".join((title, url)).casefold(),
            type_label=type_label,
        )

    title = clean_download_title(path.stem)
    download_path, download_name = unique_download_path(path, title, used_download_names)
    download_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, download_path)
    download_rel = download_path.relative_to(SITE_DIR)
    type_label = TYPE_LABELS.get(path.suffix.lower(), f"{path.suffix.upper().lstrip('.')} file")
    size_label = format_size(path.stat().st_size)
    return Resource(
        title=title,
        source_rel=rel,
        category=category,
        subcategory=subcategory,
        kind="download",
        href=download_rel.as_posix(),
        search_text=" ".join((title, type_label, path.suffix.lower().lstrip("."))).casefold(),
        type_label=f"{type_label} download",
        size_label=size_label,
        downloadable=True,
        download_name=download_name,
    )


def load_resources() -> list[Resource]:
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Could not find source folder: {SOURCE_DIR}")

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    used_download_names: set[str] = set()
    resources: list[Resource] = []
    for path in sorted(SOURCE_DIR.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not path.is_file():
            continue
        if path.suffix.lower() == ".txt":
            continue
        if path.suffix.lower() in EXCLUDED_SOURCE_EXTENSIONS:
            continue
        resources.append(make_resource(path, used_download_names))
    remove_stale_downloads(used_download_names)
    return resources


def load_page_notes() -> list[PageNote]:
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"Could not find source folder: {SOURCE_DIR}")

    notes: list[PageNote] = []
    for path in sorted(SOURCE_DIR.rglob("*.txt"), key=lambda item: item.as_posix().casefold()):
        if not path.is_file():
            continue
        rel = path.relative_to(SOURCE_DIR)
        text = read_text(path).strip()
        if not text:
            continue
        target_dir = rel.parent if rel.parent != Path(".") else Path()
        notes.append(PageNote(source_rel=rel, target_dir=target_dir, text=text))
    return notes


def remove_stale_downloads(used_download_names: set[str]) -> None:
    if not DOWNLOADS_DIR.exists():
        return

    for path in sorted(DOWNLOADS_DIR.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_file():
            rel = str(path.relative_to(DOWNLOADS_DIR)).lower()
            if rel not in used_download_names:
                path.unlink()
        elif path.is_dir():
            try:
                next(path.iterdir())
            except StopIteration:
                try:
                    path.rmdir()
                except OSError:
                    pass


def load_category_pages(resources: list[Resource], notes: list[PageNote]) -> list[CategoryPage]:
    source_dirs = sorted(
        (path.relative_to(SOURCE_DIR) for path in SOURCE_DIR.rglob("*") if path.is_dir()),
        key=lambda path: path.as_posix().casefold(),
    )
    pages: list[CategoryPage] = []
    for source_dir in source_dirs:
        count = sum(1 for resource in resources if is_inside_dir(resource.source_rel.parent, source_dir))
        note_count = sum(1 for note in notes if is_inside_dir(note.target_dir, source_dir))
        if count == 0 and note_count == 0:
            continue
        pages.append(
            CategoryPage(
                source_dir=source_dir,
                title=clean_category(source_dir.name),
                page_rel=folder_page_rel(source_dir),
                resource_count=count,
            )
        )
    return pages


def render_resource(resource: Resource, from_page: Path, show_subcategory: bool = True) -> str:
    meta_parts = []
    if resource.downloadable:
        meta_parts.append(resource.type_label)
        if resource.size_label:
            meta_parts.append(resource.size_label)
    meta = " - ".join(html.escape(part) for part in meta_parts)
    href = relative_href(from_page, Path(resource.href)) if resource.downloadable else resource.href
    download_attr = f' download="{html.escape(resource.download_name, quote=True)}"' if resource.downloadable else ""
    link_attrs = "" if resource.downloadable else ' target="_blank" rel="noopener noreferrer"'
    title_markup, title_lang_attr = render_title_text(resource.title, resource.source_rel, resource.href)
    meta_line = f'\n  <span class="resource-meta">{meta}</span>' if meta else ""
    return "\n".join(
        (
            f'<li class="resource-item" data-resource data-search="{html.escape(resource.search_text, quote=True)}">',
            f'  <a href="{html.escape(href, quote=True)}"{download_attr}{link_attrs}{title_lang_attr}>{title_markup}</a>{meta_line}',
            "</li>",
        )
    )


def group_label_for(resource: Resource, base_dir: Path) -> str:
    resource_dir = resource.source_rel.parent
    if resource_dir == base_dir:
        return ""
    rel = resource_dir.relative_to(base_dir)
    return " / ".join(clean_category(part) for part in rel.parts)


def render_subgroups(resources: list[Resource], from_page: Path, base_dir: Path | None = None) -> str:
    by_subcategory: dict[str, list[Resource]] = defaultdict(list)
    for resource in resources:
        label = resource.subcategory if base_dir is None else group_label_for(resource, base_dir)
        by_subcategory[label].append(resource)

    blocks: list[str] = []
    for subcategory in sorted(by_subcategory, key=lambda value: (value == "", value.casefold())):
        group = sorted(by_subcategory[subcategory], key=lambda item: item.title.casefold())
        if subcategory:
            heading_id = f"sub-{slugify(subcategory)}"
            blocks.append(f'<section class="subcategory" aria-labelledby="{heading_id}" data-subcategory-section>')
            blocks.append(f'  <h3 id="{heading_id}">{html.escape(subcategory)}</h3>')
            blocks.append('  <ul class="resource-list">')
            blocks.extend("  " + render_resource(item, from_page, show_subcategory=base_dir is None).replace("\n", "\n  ") for item in group)
            blocks.append("  </ul>")
            blocks.append("</section>")
        else:
            blocks.append('<ul class="resource-list">')
            blocks.extend(render_resource(item, from_page, show_subcategory=base_dir is None) for item in group)
            blocks.append("</ul>")
    return "\n".join(blocks)


def render_page_shell(
    *,
    title: str,
    description: str,
    content: str,
    from_page: Path,
    skip_text: str = "Skip to main content",
    skip_href: str = "#main",
    extra_skip_links: list[tuple[str, str]] | None = None,
    header_extra: str = "",
    back_href: str = "",
) -> str:
    asset_styles = asset_href(from_page, Path("assets/styles.css"))
    asset_data = asset_href(from_page, Path("assets/search-data.js"))
    asset_script = asset_href(from_page, Path("assets/site.js"))
    asset_icon = relative_href(from_page, Path("assets/favicon.svg"))
    asset_mark = relative_href(from_page, Path("assets/site-mark.svg"))
    home_href = relative_href(from_page, Path("index.html"))
    root_href = site_root_href(from_page)
    back_attr = f' data-back-href="{html.escape(back_href, quote=True)}"' if back_href else ""
    intro = f'\n        <p class="intro">{html.escape(description)}</p>' if description else ""
    intro = f"{intro}{header_extra}"
    meta_description = description or title
    skip_links = [(skip_text, skip_href)]
    skip_links.extend(extra_skip_links or [])
    if all(href != "#search-heading" for _, href in skip_links):
        skip_links.append(("Skip to search", "#search-heading"))
    skip_link_markup = "\n".join(
        f'    <a class="skip-link" href="{html.escape(href, quote=True)}">{html.escape(text)}</a>'
        for text, href in skip_links
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(meta_description, quote=True)}">
  <link rel="icon" href="{asset_icon}" type="image/svg+xml">
  <script>
    (() => {{
      try {{
        const theme = localStorage.getItem("roundtable-theme");
        if (theme === "dark" || theme === "light-contrast") {{
          document.documentElement.dataset.theme = theme;
        }}
        const comfort = localStorage.getItem("roundtable-comfort");
        if (comfort === "large" || comfort === "xlarge") {{
          document.documentElement.dataset.comfort = comfort;
        }}
      }} catch (error) {{}}
    }})();
  </script>
  <link rel="stylesheet" href="{asset_styles}">
  <script src="{asset_data}" defer></script>
  <script src="{asset_script}" defer></script>
</head>
<body data-site-root="{root_href}"{back_attr}>
  <div id="navigation-status" class="visually-hidden" role="status" aria-live="polite" aria-atomic="true"></div>
  <nav class="skip-links" aria-label="Skip links">
{skip_link_markup}
  </nav>
  <details class="vision-menu">
    <summary>Low-vision settings</summary>
    <div class="vision-menu-panel">
      <fieldset class="vision-theme-group">
        <legend>Colour theme</legend>
        <label class="vision-option" for="theme-standard">
          <input type="radio" id="theme-standard" class="vision-option-input" name="colour-theme" value="standard" data-theme-choice checked>
          <span>Standard theme</span>
        </label>
        <label class="vision-option" for="theme-dark">
          <input type="radio" id="theme-dark" class="vision-option-input" name="colour-theme" value="dark" data-theme-choice>
          <span>Dark high-contrast theme</span>
        </label>
        <label class="vision-option" for="theme-light-contrast">
          <input type="radio" id="theme-light-contrast" class="vision-option-input" name="colour-theme" value="light-contrast" data-theme-choice>
          <span>Light high-contrast theme</span>
        </label>
      </fieldset>
      <fieldset class="vision-theme-group">
        <legend>Text size and spacing</legend>
        <label class="vision-option" for="comfort-normal">
          <input type="radio" id="comfort-normal" class="vision-option-input" name="text-comfort" value="normal" data-comfort-choice checked>
          <span>Normal text</span>
        </label>
        <label class="vision-option" for="comfort-large">
          <input type="radio" id="comfort-large" class="vision-option-input" name="text-comfort" value="large" data-comfort-choice>
          <span>Large text and comfortable spacing</span>
        </label>
        <label class="vision-option" for="comfort-xlarge">
          <input type="radio" id="comfort-xlarge" class="vision-option-input" name="text-comfort" value="xlarge" data-comfort-choice>
          <span>Extra large text and comfortable spacing</span>
        </label>
      </fieldset>
    </div>
  </details>
  <header class="site-header">
    <div class="header-inner">
      <img class="site-mark" src="{asset_mark}" alt="" aria-hidden="true" width="64" height="64">
      <div>
        <p class="eyebrow">The RoundTable</p>
        <nav class="site-home-nav" aria-label="Homepage">
          <a href="{home_href}">Home page</a>
        </nav>
        <h1 id="page-title" tabindex="-1">{html.escape(title)}</h1>{intro}
      </div>
    </div>
  </header>

  <main id="main">
    {content}
    <p class="back-to-top"><a href="#page-title">Back to top</a></p>
  </main>

</body>
</html>
"""


def filter_label_for(page: CategoryPage, has_children: bool) -> str:
    if has_children:
        return f"All {page.title}"
    return page.title


def render_filter_option(page: CategoryPage, child_options: str = "", has_children: bool = False) -> str:
    filter_id = f"filter-{slugify(page.source_dir.as_posix())}"
    return "\n".join(
        (
            '<li>',
            f'  <label for="{filter_id}">',
            f'    <input type="checkbox" id="{filter_id}" name="scope" data-search-filter value="{html.escape(page.source_dir.as_posix(), quote=True)}">',
            f'    <span>{html.escape(filter_label_for(page, has_children))}</span>',
            "  </label>",
            child_options,
            "</li>",
        )
    )


def render_filter_options(pages: list[CategoryPage]) -> str:
    children_by_parent: dict[Path, list[CategoryPage]] = defaultdict(list)
    for page in pages:
        children_by_parent[page.source_dir.parent].append(page)
    for children in children_by_parent.values():
        children.sort(key=lambda item: item.title.casefold())

    def render_branch(page: CategoryPage) -> str:
        children = children_by_parent.get(page.source_dir, [])
        has_children = bool(children)
        child_options = ""
        if has_children:
            child_options = (
                '<ul class="filter-sublist">'
                + "".join(render_branch(child) for child in children)
                + "</ul>"
            )
        return render_filter_option(page, child_options, has_children)

    options: list[str] = []
    for page in sorted(children_by_parent.get(Path(), []), key=lambda item: item.title.casefold()):
        options.append(render_branch(page))
    return "\n".join(options)


def render_search_results_section() -> str:
    return """
      <section id="search-results-section" class="search-results-panel" aria-labelledby="search-results-heading">
        <h2 id="search-results-heading" tabindex="-1">Search results</h2>
        <p id="result-count" class="status" role="status" aria-live="polite" aria-atomic="true"></p>
        <p id="no-results" class="no-results" hidden>No matching resources.</p>
        <ul id="search-results" class="resource-list search-results" hidden></ul>
        <div data-search-pagination-bottom></div>
      </section>
"""


def render_search_panel(pages: list[CategoryPage], from_page: Path, include_results: bool = False) -> str:
    action = f"{relative_href(from_page, Path('search.html'))}#search-results-heading"
    results = render_search_results_section() if include_results else ""
    return f"""
    <section class="search-panel" aria-labelledby="search-heading">
      <h2 id="search-heading" tabindex="-1">Search Resources</h2>
      <form role="search" class="search-form" method="get" action="{action}">
        <label for="resource-search">Search by keyword</label>
        <div class="search-row">
          <input id="resource-search" name="q" type="search" autocomplete="off" spellcheck="false">
          <div class="search-actions">
            <button type="submit" id="run-search">Search</button>
            <button type="button" id="clear-search">Clear</button>
          </div>
        </div>
        <fieldset class="filter-panel">
          <legend>Where to search</legend>
          <label class="whole-site-option" for="search-all">
            <input type="checkbox" id="search-all" aria-controls="category-filter-details" aria-expanded="false" checked>
            <span>Search the whole site</span>
          </label>
          <details id="category-filter-details" class="filter-details" data-category-filter-details hidden>
            <summary>Choose categories and subcategories</summary>
            <ul class="filter-list">
              {render_filter_options(pages)}
            </ul>
          </details>
        </fieldset>
      </form>
      {results}
    </section>
"""


def child_pages_for(page: CategoryPage, pages: list[CategoryPage]) -> list[CategoryPage]:
    return sorted(
        [candidate for candidate in pages if candidate.source_dir.parent == page.source_dir],
        key=lambda item: item.title.casefold(),
    )


def top_level_pages(pages: list[CategoryPage]) -> list[CategoryPage]:
    return sorted(
        [page for page in pages if len(page.source_dir.parts) == 1],
        key=lambda item: item.title.casefold(),
    )


def render_category_cards(pages: list[CategoryPage], from_page: Path) -> str:
    if not pages:
        return ""
    items = []
    for page in pages:
        href = relative_href(from_page, page.page_rel)
        items.append(
            "\n".join(
                (
                    '<li class="category-card">',
                    f'  <a href="{href}">{html.escape(page.title)}</a>',
                    "</li>",
                )
            )
        )
    return f"""
    <nav class="category-nav" aria-labelledby="category-nav-heading">
      <h2 id="category-nav-heading" tabindex="-1">Categories</h2>
      <ul class="category-grid">
        {"".join(items)}
      </ul>
    </nav>
"""


def render_breadcrumbs(page: CategoryPage, pages_by_dir: dict[Path, CategoryPage]) -> str:
    home_target = Path("index.html")
    if page.source_dir.parts:
        home_href = f"{relative_href(page.page_rel, home_target)}#{slugify(page.source_dir.parts[0])}"
    else:
        home_href = relative_href(page.page_rel, home_target)
    crumbs = [f'<a href="{home_href}">Home</a>']
    current = Path()
    for part in page.source_dir.parts[:-1]:
        current = current / part
        parent_page = pages_by_dir.get(current)
        if parent_page:
            crumbs.append(f'<a href="{relative_href(page.page_rel, parent_page.page_rel)}">{html.escape(parent_page.title)}</a>')
    crumbs.append(f'<span aria-current="page">{html.escape(page.title)}</span>')
    crumb_items = []
    for index, crumb in enumerate(crumbs):
        separator = ' <span class="breadcrumb-separator" aria-hidden="true">/</span>' if index < len(crumbs) - 1 else ""
        crumb_items.append(f"<li>{crumb}{separator}</li>")
    return f"""
    <nav class="breadcrumbs" aria-label="Breadcrumb">
      <ol>
        {"".join(crumb_items)}
      </ol>
    </nav>
"""


def back_href_for_category_page(page: CategoryPage, pages_by_dir: dict[Path, CategoryPage]) -> str:
    parent = page.source_dir.parent
    parent_page = pages_by_dir.get(parent)
    if parent.parts and parent_page:
        return relative_href(page.page_rel, parent_page.page_rel)
    if page.source_dir.parts:
        return f"{relative_href(page.page_rel, Path('index.html'))}#{slugify(page.source_dir.parts[0])}"
    return relative_href(page.page_rel, Path("index.html"))


def render_archive_home_link(from_page: Path) -> str:
    href = relative_href(from_page, ARCHIVE_PAGE_REL)
    return f"""
    <section class="archive-panel" aria-labelledby="archive-heading">
      <h2 id="archive-heading" tabindex="-1">The RoundTable archive</h2>
      <p>Read the instructions for downloading and importing the complete RoundTable list archive from January 2015 to July 2026 into Mozilla Thunderbird.</p>
      <p><a href="{href}" target="_blank" rel="noopener noreferrer">The RoundTable archive from January 2015 to July 2026</a></p>
    </section>
"""


def render_community_home_link() -> str:
    group_href = html.escape(GOOGLE_GROUP_URL, quote=True)
    return f"""
    <section class="community-panel" aria-labelledby="community-heading">
      <h2 id="community-heading" tabindex="-1">The RoundTable mailing list</h2>
      <p>Join the Google Group for blind and low vision translators, interpreters, language professionals, students, teachers and interested colleagues.</p>
      <p><a href="{group_href}" target="_blank" rel="noopener noreferrer">Visit the RoundTable Google Group</a></p>
    </section>
"""


TEXT_EMAIL_RE = re.compile(r"[\w.!#$%&'*+/=?^_`{|}~-]+@(?:[\w-]+\.)+[\w-]{2,63}")


def normalize_archive_line(line: str) -> str:
    return line.replace("â€¢", "•").strip()


def render_archive_inline(text: str) -> str:
    output: list[str] = []
    position = 0
    for match in TEXT_EMAIL_RE.finditer(text):
        output.append(html.escape(text[position:match.start()]))
        email_address = match.group(0)
        escaped_email = html.escape(email_address)
        output.append(f'<a href="mailto:{html.escape(email_address, quote=True)}">{escaped_email}</a>')
        position = match.end()
    output.append(html.escape(text[position:]))
    return "".join(output)


def load_archive_source() -> tuple[list[str], str, str]:
    if not ARCHIVE_SOURCE_PATH.is_file():
        raise RuntimeError(f"Archive page source file is missing: {ARCHIVE_SOURCE_PATH}")

    lines = [normalize_archive_line(line) for line in read_text(ARCHIVE_SOURCE_PATH).splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise RuntimeError(f"Archive page source file is empty: {ARCHIVE_SOURCE_PATH}")

    download_url = ARCHIVE_DOWNLOAD_URL
    intro_lines: list[str] = []
    instruction_lines: list[str] = []
    found_download_url = False
    for line in lines:
        if line.startswith(("http://", "https://")) and not found_download_url:
            download_url = line
            found_download_url = True
            continue
        if found_download_url:
            instruction_lines.append(line)
        else:
            intro_lines.append(line)

    return intro_lines, download_url, render_archive_instructions(instruction_lines)


def render_archive_instructions(lines: list[str]) -> str:
    items: list[dict[str, object]] = []
    paragraphs: list[str] = []
    current: dict[str, object] | None = None
    pending_bullet = False

    def flush_current() -> None:
        nonlocal current
        if current is not None:
            items.append(current)
            current = None

    for line in lines:
        number_match = re.match(r"^\d+\.\s*(.*)$", line)
        if number_match:
            flush_current()
            current = {"text": number_match.group(1).strip(), "bullets": []}
            pending_bullet = False
            continue

        if line == "•":
            pending_bullet = True
            continue

        if pending_bullet:
            if current is None:
                current = {"text": "", "bullets": []}
            current["bullets"].append(line)  # type: ignore[index, union-attr]
            pending_bullet = False
            continue

        if current is not None and not current["text"]:
            current["text"] = line
            continue

        if current is not None and current["bullets"]:
            flush_current()
            paragraphs.append(line)
            continue

        if current is not None:
            current["text"] = f'{current["text"]} {line}'
            continue

        paragraphs.append(line)

    flush_current()

    blocks: list[str] = []
    if items:
        blocks.append('      <ol class="instruction-list">')
        for item in items:
            text = render_archive_inline(str(item["text"]))
            bullets = item["bullets"]
            if bullets:
                bullet_items = "\n".join(f"            <li>{render_archive_inline(str(bullet))}</li>" for bullet in bullets)
                blocks.append(
                    "\n".join(
                        (
                            f"        <li>{text}",
                            "          <ul>",
                            bullet_items,
                            "          </ul>",
                            "        </li>",
                        )
                    )
                )
            else:
                blocks.append(f"        <li>{text}</li>")
        blocks.append("      </ol>")

    blocks.extend(f"      <p>{render_archive_inline(paragraph)}</p>" for paragraph in paragraphs)
    return "\n".join(blocks)


def render_archive_page() -> str:
    intro_lines, download_url, instructions = load_archive_source()
    intro = "\n".join(f"      <p>{render_archive_inline(line)}</p>" for line in intro_lines)
    download_href = html.escape(download_url, quote=True)
    content = f"""
    <nav class="breadcrumbs" aria-label="Breadcrumb">
      <ol>
        <li><a href="index.html">Home</a></li>
        <li><span aria-current="page">The RoundTable archive</span></li>
      </ol>
    </nav>
    <article class="archive-page" aria-labelledby="archive-instructions">
      <h2 id="archive-instructions" tabindex="-1">Download and import the archive</h2>
{intro}
      <p><a class="download-link" href="{download_href}">Download the RoundTable archive MBOX file</a></p>

{instructions}
    </article>
"""
    return render_page_shell(
        title="The RoundTable archive from January 2015 to July 2026",
        description="Download and import the complete RoundTable list archive into Mozilla Thunderbird.",
        content=content,
        from_page=ARCHIVE_PAGE_REL,
        skip_text="Skip to archive instructions",
        skip_href="#archive-instructions",
        back_href="index.html",
    )


def notes_by_target_dir(notes: list[PageNote]) -> dict[Path, list[PageNote]]:
    grouped: dict[Path, list[PageNote]] = defaultdict(list)
    for note in notes:
        grouped[note.target_dir].append(note)
    for group in grouped.values():
        group.sort(key=lambda item: item.source_rel.name.casefold())
    return grouped


def render_note_inline(text: str) -> str:
    output: list[str] = []
    position = 0
    for match in NOTE_URL_RE.finditer(text):
        output.append(html.escape(text[position:match.start()]))
        url = match.group(0)
        trailing = ""
        while url and url[-1] in TRAILING_URL_PUNCTUATION:
            trailing = url[-1] + trailing
            url = url[:-1]
        escaped_url = html.escape(url)
        output.append(
            f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{escaped_url}</a>'
        )
        output.append(html.escape(trailing))
        position = match.end()
    output.append(html.escape(text[position:]))
    return "".join(output)


def render_page_notes(notes: list[PageNote]) -> str:
    if not notes:
        return ""

    paragraphs: list[str] = []
    for note in notes:
        lines = [line.strip() for line in note.text.splitlines() if line.strip()]
        paragraphs.extend(f"      <p>{render_note_inline(line)}</p>" for line in lines)
    if not paragraphs:
        return ""

    return f"""
    <section class="page-notes" aria-labelledby="page-notes-heading">
      <h2 id="page-notes-heading" tabindex="-1">Notes</h2>
{chr(10).join(paragraphs)}
    </section>
"""


def render_intro_notes(notes: list[PageNote]) -> str:
    paragraphs: list[str] = []
    for note in notes:
        lines = [line.strip() for line in note.text.splitlines() if line.strip()]
        paragraphs.extend(
            f'\n        <p class="intro intro-note">{render_note_inline(line)}</p>' for line in lines
        )
    return "".join(paragraphs)


def note_search_text(notes: list[PageNote]) -> str:
    return re.sub(r"\s+", " ", " ".join(note.text for note in notes)).strip().casefold()


def render_index(resources: list[Resource], pages: list[CategoryPage], notes: list[PageNote]) -> str:
    notes_by_dir = notes_by_target_dir(notes)
    homepage_notes = notes_by_dir.get(Path(), [])
    content = f"""
    {render_search_panel(pages, Path("index.html"))}
    {render_category_cards(top_level_pages(pages), Path("index.html"))}
    {render_community_home_link()}
    {render_archive_home_link(Path("index.html"))}
"""
    return render_page_shell(
        title="The RoundTable Resources",
        description="A searchable directory of links and downloads for language learning, translation, interpreting, accessibility, screen readers, braille, and related tools.",
        content=content,
        from_page=Path("index.html"),
        skip_text="Skip to categories",
        skip_href="#category-nav-heading",
        header_extra=render_intro_notes(homepage_notes),
    )


def render_category_page(page: CategoryPage, pages: list[CategoryPage], pages_by_dir: dict[Path, CategoryPage], resources: list[Resource], notes: list[PageNote]) -> str:
    notes_by_dir = notes_by_target_dir(notes)
    page_notes = render_page_notes(notes_by_dir.get(page.source_dir, []))
    page_resources = sorted(
        [resource for resource in resources if resource.source_rel.parent == page.source_dir],
        key=lambda item: item.title.casefold(),
    )
    children = child_pages_for(page, pages)
    child_nav = ""
    if children:
        child_nav = render_category_cards(children, page.page_rel).replace("Categories", "Subcategories", 1)
    resource_section = ""
    if page_resources:
        resource_section = f"""
    <section class="category" aria-labelledby="resources-heading" data-resource-pagination>
      <div class="category-heading">
        <h2 id="resources-heading" tabindex="-1">Resources</h2>
      </div>
      {render_subgroups(page_resources, page.page_rel, page.source_dir)}
      <div data-pagination-bottom></div>
    </section>
"""
    if children:
        content = f"""
    {render_breadcrumbs(page, pages_by_dir)}
    {page_notes}
    {child_nav}
    {render_search_panel(pages, page.page_rel)}
    {resource_section}
"""
        skip_text = "Skip to category resources" if page_resources else "Skip to subcategories"
        skip_href = "#resources-heading" if page_resources else "#category-nav-heading"
        extra_skip_links = [("Skip to subcategories", "#category-nav-heading")] if page_resources else []
    else:
        content = f"""
    {render_breadcrumbs(page, pages_by_dir)}
    {page_notes}
    {render_search_panel(pages, page.page_rel)}
    {resource_section}
"""
        skip_text = "Skip to category resources"
        skip_href = "#resources-heading"
        extra_skip_links = []
    return render_page_shell(
        title=f"{page.title} - The RoundTable Resources",
        description="",
        content=content,
        from_page=page.page_rel,
        skip_text=skip_text,
        skip_href=skip_href,
        extra_skip_links=extra_skip_links,
        back_href=back_href_for_category_page(page, pages_by_dir),
    )


def render_search_page(pages: list[CategoryPage]) -> str:
    content = f"""
    <nav class="breadcrumbs" aria-label="Breadcrumb">
      <ol>
        <li><a href="index.html">Home</a></li>
        <li><span aria-current="page">Search results</span></li>
      </ol>
    </nav>
    {render_search_panel(pages, Path("search.html"), include_results=True)}
"""
    return render_page_shell(
        title="Search results - The RoundTable Resources",
        description="Search all RoundTable resources, or narrow the search with category and subcategory filters.",
        content=content,
        from_page=Path("search.html"),
        skip_text="Skip to search",
        skip_href="#search-heading",
        back_href="index.html",
    )


def category_path_label(resource: Resource) -> str:
    folder = resource.source_rel.parent
    if not folder.parts:
        return "Resources"
    return " / ".join(clean_category(part) for part in folder.parts)


def parent_category_label(page: CategoryPage) -> str:
    parent = page.source_dir.parent
    if not parent.parts:
        return ""
    return " / ".join(clean_category(part) for part in parent.parts)


def search_data_for(resources: list[Resource], pages: list[CategoryPage], notes: list[PageNote]) -> list[dict[str, object]]:
    data: list[dict[str, object]] = []
    item_id = 1
    notes_by_dir = notes_by_target_dir(notes)
    home_note_text = note_search_text(notes_by_dir.get(Path(), []))
    if home_note_text:
        data.append(
            {
                "id": f"page-{item_id}",
                "resultType": "page",
                "sortGroup": 1,
                "title": "The RoundTable Resources",
                "href": "index.html",
                "downloadable": False,
                "category": "",
                "fileInfo": "Page",
                "searchText": f"the roundtable resources {home_note_text}".strip().casefold(),
                "scopes": [],
            }
        )
        item_id += 1

    for page in sorted(pages, key=lambda item: (len(item.source_dir.parts), item.title.casefold())):
        is_subcategory = len(page.source_dir.parts) > 1
        page_note_text = note_search_text(notes_by_dir.get(page.source_dir, []))
        data.append(
            {
                "id": f"category-{item_id}",
                "resultType": "subcategory" if is_subcategory else "category",
                "sortGroup": 2 if is_subcategory else 1,
                "title": page.title,
                "href": href_for(page.page_rel),
                "downloadable": False,
                "category": parent_category_label(page),
                "fileInfo": "Subcategory" if is_subcategory else "Category",
                "searchText": " ".join(part for part in (page.title, page_note_text) if part).casefold(),
                "scopes": ancestor_scopes(page.source_dir),
            }
        )
        item_id += 1

    data.append(
        {
            "id": f"page-{item_id}",
            "resultType": "page",
            "sortGroup": 1,
            "title": "The RoundTable mailing list",
            "href": GOOGLE_GROUP_URL,
            "downloadable": False,
            "category": "",
            "fileInfo": "Google Group",
            "searchText": "roundtable mailing list google group blind low vision translators interpreters language professionals",
            "scopes": [],
        }
    )
    item_id += 1

    data.append(
        {
            "id": f"page-{item_id}",
            "resultType": "page",
            "sortGroup": 1,
            "title": "The RoundTable archive from January 2015 to July 2026",
            "href": ARCHIVE_PAGE_REL.as_posix(),
            "downloadable": False,
            "category": "",
            "fileInfo": "Page",
            "searchText": "roundtable archive january 2015 july 2026 thunderbird mbox import download list archive",
            "scopes": [],
        }
    )
    item_id += 1

    for resource in sorted(resources, key=lambda item: item.title.casefold()):
        folder = resource.source_rel.parent
        file_info = ""
        if resource.downloadable:
            file_parts = [resource.type_label]
            if resource.size_label:
                file_parts.append(resource.size_label)
            file_info = " - ".join(file_parts)
        item = {
            "id": f"resource-{item_id}",
            "resultType": "resource",
            "sortGroup": 3,
            "title": resource.title,
            "href": resource.href,
            "downloadable": resource.downloadable,
            "downloadName": resource.download_name if resource.downloadable else "",
            "category": category_path_label(resource),
            "fileInfo": file_info,
            "searchText": resource.search_text,
            "scopes": ancestor_scopes(folder),
        }
        title_segments = search_title_segments(resource.title, resource.source_rel, resource.href)
        if title_segments:
            item["titleSegments"] = title_segments
        data.append(item)
        item_id += 1
    return data


def write_static_assets(resources: list[Resource], pages: list[CategoryPage], notes: list[PageNote]) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    search_json = json.dumps(search_data_for(resources, pages, notes), ensure_ascii=False, separators=(",", ":"))
    search_script = f"window.ROUND_TABLE_RESOURCES = {search_json};\n"
    ASSET_VERSIONS.update(
        {
            "search-data.js": content_version(search_script),
            "styles.css": content_version(STYLES_CSS),
            "site.js": content_version(SITE_JS),
        }
    )
    (ASSETS_DIR / "search-data.js").write_text(
        search_script,
        encoding="utf-8",
    )
    (ASSETS_DIR / "styles.css").write_text(STYLES_CSS, encoding="utf-8")
    (ASSETS_DIR / "site.js").write_text(SITE_JS, encoding="utf-8")
    (ASSETS_DIR / "site-mark.svg").write_text(SITE_MARK_SVG, encoding="utf-8")
    (ASSETS_DIR / "favicon.svg").write_text(FAVICON_SVG, encoding="utf-8")
    (SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")


STYLES_CSS = r""":root {
  color-scheme: light;
  --page: #f7f5ef;
  --surface: #ffffff;
  --text: #171717;
  --muted: #555555;
  --line: #d8d2c4;
  --teal: #006a67;
  --teal-dark: #004f4d;
  --plum: #6d275c;
  --gold: #f2b632;
  --focus: #8a4b00;
  --focus-bg: #fff4bd;
  --focus-text: #171717;
  --shadow: 0 1px 4px rgb(0 0 0 / 12%);
  --resource-bg: #fbfaf6;
  --input-bg: #ffffff;
  --input-border: #767676;
  --button-text: #ffffff;
  --skip-bg: #171717;
  --skip-text: #ffffff;
  --current-bg: #f2b632;
  --current-text: #171717;
}

:root[data-theme="dark"] {
  color-scheme: dark;
  --page: #000000;
  --surface: #101010;
  --text: #ffffff;
  --muted: #e0e0e0;
  --line: #ffffff;
  --teal: #66fff0;
  --teal-dark: #80fff4;
  --plum: #ffb8f2;
  --gold: #ffd447;
  --focus: #ffd447;
  --focus-bg: #ffd447;
  --focus-text: #000000;
  --shadow: none;
  --resource-bg: #050505;
  --input-bg: #000000;
  --input-border: #ffffff;
  --button-text: #000000;
  --skip-bg: #ffffff;
  --skip-text: #000000;
  --current-bg: #ffd447;
  --current-text: #000000;
}

:root[data-theme="light-contrast"] {
  color-scheme: light;
  --page: #ffffff;
  --surface: #ffffff;
  --text: #000000;
  --muted: #1f1f1f;
  --line: #000000;
  --teal: #000000;
  --teal-dark: #0000cc;
  --plum: #551a8b;
  --gold: #ffff00;
  --focus: #000000;
  --focus-bg: #ffff00;
  --focus-text: #000000;
  --shadow: none;
  --resource-bg: #ffffff;
  --input-bg: #ffffff;
  --input-border: #000000;
  --button-text: #ffffff;
  --skip-bg: #000000;
  --skip-text: #ffffff;
  --current-bg: #ffff00;
  --current-text: #000000;
}

:root[data-comfort="large"] body {
  font-size: 1.18rem;
  line-height: 1.7;
}

:root[data-comfort="xlarge"] body {
  font-size: 1.35rem;
  line-height: 1.8;
}

:root[data-comfort="large"] .search-panel,
:root[data-comfort="large"] .category-nav,
:root[data-comfort="large"] .category,
:root[data-comfort="large"] .page-notes {
  padding: 1.25rem;
}

:root[data-comfort="xlarge"] .search-panel,
:root[data-comfort="xlarge"] .category-nav,
:root[data-comfort="xlarge"] .category,
:root[data-comfort="xlarge"] .page-notes {
  padding: 1.45rem;
}

:root[data-comfort="large"] .resource-list,
:root[data-comfort="large"] .resource-sections {
  gap: 0.85rem;
}

:root[data-comfort="xlarge"] .resource-list,
:root[data-comfort="xlarge"] .resource-sections {
  gap: 1rem;
}

:root[data-comfort="large"] .resource-item {
  padding: 1rem 1.1rem;
}

:root[data-comfort="xlarge"] .resource-item {
  padding: 1.15rem 1.25rem;
}

* {
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  margin: 0;
  background: var(--page);
  color: var(--text);
  font-family: Arial, Helvetica, sans-serif;
  font-size: 1rem;
  line-height: 1.55;
}

a {
  color: var(--teal-dark);
  text-decoration-thickness: 0.1em;
  text-underline-offset: 0.18em;
}

a:visited {
  color: var(--plum);
}

a:hover {
  color: var(--plum);
}

a:focus-visible,
button:focus-visible,
input:focus-visible,
select:focus-visible,
summary:focus-visible {
  background: var(--focus-bg);
  color: var(--focus-text);
  outline: 4px solid var(--focus);
  outline-offset: 4px;
  text-decoration-color: currentColor;
}

a:focus-visible,
button:focus-visible,
summary:focus-visible {
  box-shadow: 0 0 0 7px var(--focus-bg);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}

.skip-links {
  position: absolute;
  left: 1rem;
  top: 1rem;
  z-index: 10;
  display: grid;
  gap: 0.5rem;
  transform: translateY(calc(-100% - 1.5rem));
}

.skip-links:focus-within {
  transform: translateY(0);
}

.skip-link {
  background: var(--skip-bg);
  color: var(--skip-text);
  padding: 0.75rem 1rem;
  border-radius: 6px;
}

.site-header {
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}

.header-inner,
main,
.site-footer {
  width: min(1120px, calc(100% - 2rem));
  margin: 0 auto;
}

.header-inner {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 1rem;
  align-items: center;
  padding: 2rem 0;
}

.site-mark {
  width: 4rem;
  height: 4rem;
}

.eyebrow {
  margin: 0 0 0.25rem;
  color: var(--plum);
  font-weight: 700;
}

.site-home-nav {
  margin: 0 0 0.6rem;
}

.site-home-nav a {
  display: inline-block;
  font-weight: 700;
}

h1,
h2,
h3,
p {
  overflow-wrap: anywhere;
}

h1 {
  border-left: 0.35rem solid var(--current-bg);
  margin: 0;
  padding-left: 0.75rem;
  font-size: clamp(2.2rem, 2.8rem, 2.8rem);
  line-height: 1.08;
}

.intro {
  max-width: 62rem;
  margin: 0.75rem 0 0;
  color: var(--muted);
  font-size: 1.08rem;
}

.intro-note {
  margin-top: 0.55rem;
}

main {
  padding: 1.5rem 0 2rem;
}

.search-panel,
.category-nav,
.category,
.page-notes,
.community-panel,
.archive-panel,
.archive-page {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
}

.search-panel {
  padding: 1rem;
}

.search-panel h2,
.category-nav h2,
.category h2,
.page-notes h2,
.community-panel h2,
.archive-panel h2,
.archive-page h2,
.subcategory h3 {
  margin-top: 0;
  line-height: 1.2;
}

.search-form label {
  display: block;
  margin-bottom: 0.35rem;
  font-weight: 700;
}

.search-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.75rem;
  align-items: end;
}

.search-actions {
  display: flex;
  gap: 0.5rem;
}

input[type="search"] {
  min-width: 0;
  width: 100%;
  border: 2px solid var(--input-border);
  border-radius: 6px;
  padding: 0.75rem;
  font: inherit;
  background: var(--input-bg);
  color: var(--text);
}

select {
  min-width: 8rem;
  border: 2px solid var(--input-border);
  border-radius: 6px;
  padding: 0.65rem;
  font: inherit;
  background: var(--input-bg);
  color: var(--text);
}

button {
  border: 2px solid var(--teal-dark);
  border-radius: 6px;
  background: var(--teal-dark);
  color: var(--button-text);
  padding: 0.75rem 1rem;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

button:hover {
  background: var(--plum);
  border-color: var(--plum);
}

.vision-menu {
  width: min(1120px, calc(100% - 2rem));
  margin: 0.75rem auto;
  background: var(--surface);
  border: 2px solid var(--text);
  border-radius: 8px;
  color: var(--text);
}

.vision-menu summary {
  cursor: pointer;
  font-weight: 700;
  padding: 0.85rem 1rem;
}

.vision-menu[open] summary {
  border-bottom: 1px solid var(--line);
}

.vision-menu-panel {
  display: grid;
  gap: 0.75rem;
  padding: 1rem;
}

.vision-theme-group {
  display: grid;
  gap: 0.65rem;
  margin: 0;
  padding: 0.85rem;
  border: 1px solid var(--line);
  border-radius: 6px;
}

.vision-theme-group legend {
  font-weight: 700;
  padding: 0 0.25rem;
}

.vision-option {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text);
  font-weight: 700;
  line-height: 1.35;
}

.vision-option-input {
  accent-color: var(--teal-dark);
  flex: 0 0 auto;
  width: 1.3rem;
  height: 1.3rem;
  margin: 0;
}

.vision-state {
  border-left: 1px solid currentColor;
  padding-left: 0.5rem;
}

.status,
.no-results {
  margin: 0.75rem 0 0;
  color: var(--muted);
  font-weight: 700;
}

.filter-panel {
  border: 1px solid var(--line);
  border-radius: 6px;
  margin: 1rem 0 0;
  padding: 0.85rem;
}

.filter-panel legend {
  font-weight: 700;
  padding: 0 0.25rem;
}

.filter-panel label {
  display: inline-flex;
  gap: 0.45rem;
  align-items: flex-start;
  margin: 0;
  font-weight: 400;
}

.filter-panel input[type="checkbox"] {
  width: 1.15rem;
  height: 1.15rem;
  margin-top: 0.15rem;
}

.whole-site-option {
  font-weight: 700 !important;
}

.filter-details {
  margin-top: 0.75rem;
}

.filter-details summary {
  cursor: pointer;
  font-weight: 700;
}

.filter-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(18rem, 1fr));
  gap: 0.45rem 1rem;
  list-style: none;
  margin: 0.85rem 0 0;
  padding: 0;
}

.filter-sublist {
  display: grid;
  gap: 0.35rem;
  list-style: none;
  margin: 0.45rem 0 0.25rem 1.65rem;
  padding: 0;
}

.search-results-panel {
  margin-top: 1rem;
}

.search-results-panel h2 {
  margin-bottom: 0.75rem;
}

.search-results {
  margin-top: 1rem;
}

.pagination-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  align-items: center;
  justify-content: space-between;
  margin: 1rem 0;
  padding: 0.85rem;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
}

.pagination-size {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  align-items: center;
}

.pagination-size label,
.pagination-status {
  font-weight: 700;
}

.pagination-status {
  margin: 0;
  color: var(--muted);
}

.pagination-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.pagination-buttons button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.category-nav {
  margin-top: 1rem;
  padding: 1rem;
}

.category-nav ul {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 16rem), 1fr));
  gap: 0.45rem 0.75rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.category-nav li {
  min-width: 0;
}

.category-grid {
  list-style-position: outside;
}

.category-card a {
  display: block;
  font-weight: 700;
  min-height: 2.75rem;
  padding: 0.65rem 0.75rem;
  border-radius: 6px;
}

.category-card a:hover,
.category-card a:focus-visible {
  background: var(--focus-bg);
  color: var(--focus-text);
}

.breadcrumbs {
  margin-bottom: 1rem;
}

.breadcrumbs ol {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.breadcrumb-separator {
  color: var(--muted);
  margin-left: 0.35rem;
}

.breadcrumbs [aria-current="page"] {
  display: inline-block;
  background: var(--current-bg);
  border: 2px solid var(--text);
  border-radius: 6px;
  color: var(--current-text);
  font-weight: 700;
  padding: 0.1rem 0.45rem;
}

.count {
  color: var(--muted);
  white-space: nowrap;
}

.resource-sections {
  display: grid;
  gap: 1rem;
  margin-top: 1rem;
}

.category {
  padding: 1rem;
}

.page-notes {
  border-left: 4px solid var(--gold);
  margin-top: 1rem;
  padding: 1rem;
}

.page-notes p {
  margin: 0.65rem 0 0;
}

.page-notes p:first-of-type {
  margin-top: 0;
}

.community-panel,
.archive-panel,
.archive-page {
  margin-top: 1rem;
  padding: 1rem;
}

.archive-page {
  display: grid;
  gap: 1rem;
}

.archive-page p {
  margin: 0;
}

.download-link {
  display: inline-block;
  border: 2px solid var(--teal-dark);
  border-radius: 6px;
  background: var(--teal-dark);
  color: var(--button-text);
  font-weight: 700;
  padding: 0.75rem 1rem;
}

.download-link:hover,
.download-link:focus-visible {
  background: var(--plum);
  border-color: var(--plum);
  color: var(--button-text);
}

.instruction-list,
.instruction-list ul {
  display: grid;
  gap: 0.5rem;
}

.instruction-list {
  margin: 0;
  padding-left: 1.5rem;
}

.category-heading {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: baseline;
  border-bottom: 1px solid var(--line);
  padding-bottom: 0.75rem;
  margin-bottom: 0.75rem;
}

.category-heading h2,
.category-heading p {
  margin-bottom: 0;
}

.category-heading p {
  color: var(--muted);
  font-weight: 700;
}

.subcategory {
  margin-top: 1.25rem;
}

.subcategory h3 {
  color: var(--plum);
  font-size: 1.15rem;
}

.resource-list {
  display: grid;
  gap: 0.55rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.resource-item {
  border-left: 4px solid var(--teal);
  background: var(--resource-bg);
  border-radius: 6px;
  min-width: 0;
  padding: 0.75rem 0.85rem;
}

.resource-item:focus-within {
  background: var(--focus-bg);
  border-left-color: var(--focus);
}

.resource-item a {
  font-weight: 700;
  display: block;
  min-height: 2.75rem;
  max-width: 100%;
  overflow: hidden;
  padding: 0.35rem 0;
  text-overflow: ellipsis;
  vertical-align: bottom;
  white-space: nowrap;
}

.resource-item:focus-within a,
.resource-item:focus-within .resource-meta {
  color: var(--focus-text);
}

.resource-meta {
  display: block;
  margin: 0.25rem 0 0;
  color: var(--muted);
  font-size: 0.95rem;
}

.back-to-top {
  margin: 1.5rem 0 0;
}

.back-to-top a {
  display: inline-block;
  background: var(--surface);
  border: 2px solid var(--text);
  border-radius: 6px;
  color: var(--teal-dark);
  font-weight: 700;
  padding: 0.65rem 0.85rem;
}

.site-footer {
  padding: 1.5rem 0 2rem;
  color: var(--muted);
}

[hidden] {
  display: none !important;
}

@media (max-width: 680px) {
  .header-inner {
    grid-template-columns: 1fr;
  }

  .vision-option {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .search-row {
    grid-template-columns: 1fr;
  }

  .search-actions {
    flex-direction: column;
  }

  button {
    width: 100%;
  }

  .pagination-controls,
  .pagination-size,
  .pagination-buttons {
    align-items: stretch;
    flex-direction: column;
  }

  .pagination-buttons {
    width: 100%;
  }

  select {
    width: 100%;
  }

  .category-card a,
  .resource-item a {
    display: block;
    overflow: visible;
    overflow-wrap: anywhere;
    text-overflow: clip;
    white-space: normal;
  }
}

@media (prefers-reduced-motion: reduce) {
  html {
    scroll-behavior: auto;
  }
}

@media (forced-colors: active) {
  .search-panel,
  .category-nav,
  .category,
  .page-notes,
  .pagination-controls,
  .resource-item {
    border: 1px solid CanvasText;
  }

  .resource-item {
    border-left-width: 4px;
  }
}
"""


SITE_JS = r"""(() => {
  const skipLinks = Array.from(document.querySelectorAll(".skip-link"));
  const focusLinks = Array.from(document.querySelectorAll(".skip-link, .back-to-top a"));
  const themeChoices = Array.from(document.querySelectorAll("[data-theme-choice]"));
  const comfortChoices = Array.from(document.querySelectorAll("[data-comfort-choice]"));
  const search = document.querySelector("#resource-search");
  const clearButton = document.querySelector("#clear-search");
  const searchAll = document.querySelector("#search-all");
  const filterDetails = document.querySelector("[data-category-filter-details]");
  const filterBoxes = Array.from(document.querySelectorAll("[data-search-filter]"));
  const resultsSection = document.querySelector("#search-results-section");
  const resultsHeading = document.querySelector("#search-results-heading");
  const status = document.querySelector("#result-count");
  const noResults = document.querySelector("#no-results");
  const resultsList = document.querySelector("#search-results");
  const resources = Array.isArray(window.ROUND_TABLE_RESOURCES) ? window.ROUND_TABLE_RESOURCES : [];
  const pageSizeOptions = [25, 50, 75, 100];
  const pageSizeStorageKey = "roundtable-resources-page-size";
  let paginationControlId = 0;

  function savedTheme() {
    try {
      return localStorage.getItem("roundtable-theme");
    } catch (error) {
      return null;
    }
  }

  function saveTheme(theme) {
    try {
      if (theme === "dark" || theme === "light-contrast") {
        localStorage.setItem("roundtable-theme", theme);
      } else {
        localStorage.removeItem("roundtable-theme");
      }
    } catch (error) {}
  }

  function savedComfort() {
    try {
      return localStorage.getItem("roundtable-comfort");
    } catch (error) {
      return null;
    }
  }

  function saveComfort(value) {
    try {
      if (value === "large" || value === "xlarge") {
        localStorage.setItem("roundtable-comfort", value);
      } else {
        localStorage.removeItem("roundtable-comfort");
      }
    } catch (error) {}
  }

  function applyTheme(theme, persist = false) {
    const selectedTheme = theme === "dark" || theme === "light-contrast" ? theme : "standard";
    if (selectedTheme === "standard") {
      document.documentElement.removeAttribute("data-theme");
    } else {
      document.documentElement.setAttribute("data-theme", selectedTheme);
    }
    themeChoices.forEach((choice) => {
      choice.checked = choice.value === selectedTheme;
    });
    if (persist) {
      saveTheme(selectedTheme);
    }
  }

  function applyComfort(value, persist = false) {
    const selectedComfort = value === "large" || value === "xlarge" ? value : "normal";
    if (selectedComfort === "normal") {
      document.documentElement.removeAttribute("data-comfort");
    } else {
      document.documentElement.setAttribute("data-comfort", selectedComfort);
    }
    comfortChoices.forEach((choice) => {
      choice.checked = choice.value === selectedComfort;
    });
    if (persist) {
      saveComfort(selectedComfort);
    }
  }

  applyTheme(savedTheme());
  applyComfort(savedComfort());
  themeChoices.forEach((choice) => {
    choice.addEventListener("change", () => {
      if (choice.checked) {
        applyTheme(choice.value, true);
      }
    });
  });
  comfortChoices.forEach((choice) => {
    choice.addEventListener("change", () => {
      if (choice.checked) {
        applyComfort(choice.value, true);
      }
    });
  });

  function isTypingOrControl(target) {
    return Boolean(
      target.closest(
        "input, textarea, select, button, summary, [contenteditable='true'], [role='textbox']"
      )
    );
  }

  function sameOriginReferrer() {
    if (!document.referrer) return "";
    try {
      const referrer = new URL(document.referrer);
      if (referrer.origin === window.location.origin && referrer.href !== window.location.href) {
        return referrer.href;
      }
    } catch (error) {}
    return "";
  }

  function fallbackBackHref() {
    const href = document.body.dataset.backHref || "";
    if (!href) return "";
    try {
      const target = new URL(href, window.location.href);
      return target.href !== window.location.href ? target.href : "";
    } catch (error) {
      return "";
    }
  }

  function pageLabel() {
    const heading = document.getElementById("page-title");
    const text = heading && heading.textContent ? heading.textContent.trim() : document.title.trim();
    return text || "this page";
  }

  function isBackForwardNavigation(event) {
    if (event && event.persisted) return true;
    try {
      const entries = performance.getEntriesByType("navigation");
      return entries.length > 0 && entries[0].type === "back_forward";
    } catch (error) {
      return false;
    }
  }

  function requestNavigationAnnouncement() {
    try {
      sessionStorage.setItem("roundtable-announce-navigation", "1");
    } catch (error) {}
  }

  function shouldAnnounceNavigation(event) {
    if (isBackForwardNavigation(event)) return true;
    try {
      if (sessionStorage.getItem("roundtable-announce-navigation") === "1") {
        sessionStorage.removeItem("roundtable-announce-navigation");
        return true;
      }
    } catch (error) {}
    return false;
  }

  function announceHistoryNavigation(event) {
    if (!shouldAnnounceNavigation(event)) return;
    const status = document.getElementById("navigation-status");
    if (!status) return;
    status.textContent = "";
    window.setTimeout(() => {
      status.textContent = `Now on ${pageLabel()}.`;
    }, 100);
  }

  window.addEventListener("pageshow", announceHistoryNavigation);

  document.addEventListener("keydown", (event) => {
    const isBackShortcut = event.key === "ArrowLeft";
    const isForwardShortcut = event.key === "ArrowRight" && event.altKey;
    if (
      (!isBackShortcut && !isForwardShortcut) ||
      event.ctrlKey ||
      event.metaKey ||
      event.shiftKey ||
      event.repeat ||
      isTypingOrControl(event.target)
    ) {
      return;
    }

    if (isForwardShortcut) {
      event.preventDefault();
      requestNavigationAnnouncement();
      window.history.forward();
      return;
    }

    const referrer = sameOriginReferrer();
    const fallback = fallbackBackHref();
    if (referrer && window.history.length > 1) {
      event.preventDefault();
      requestNavigationAnnouncement();
      window.history.back();
    } else if (referrer || fallback) {
      event.preventDefault();
      requestNavigationAnnouncement();
      window.location.href = referrer || fallback;
    } else if (window.history.length > 1) {
      event.preventDefault();
      requestNavigationAnnouncement();
      window.history.back();
    }
  });

  focusLinks.forEach((focusLink) => {
    focusLink.addEventListener("click", () => {
      const href = focusLink.getAttribute("href") || "";
      if (!href.startsWith("#") || href.length < 2) return;
      const target = document.getElementById(href.slice(1));
      if (!target || typeof target.focus !== "function") return;
      window.setTimeout(() => {
        target.focus({ preventScroll: true });
      }, 0);
    });
  });

  function savedPageSize() {
    try {
      const value = Number.parseInt(localStorage.getItem(pageSizeStorageKey) || "", 10);
      if (pageSizeOptions.includes(value)) {
        return value;
      }
    } catch (error) {}
    return pageSizeOptions[0];
  }

  function savePageSize(value) {
    try {
      localStorage.setItem(pageSizeStorageKey, String(value));
    } catch (error) {}
  }

  function pageFromUrl(pageParam) {
    if (!pageParam) return 1;
    try {
      const params = new URLSearchParams(window.location.search);
      const page = Number.parseInt(params.get(pageParam) || "", 10);
      return Number.isFinite(page) && page > 0 ? page : 1;
    } catch (error) {
      return 1;
    }
  }

  function syncPageToUrl(pageParam, currentPage) {
    if (!pageParam || !window.history || typeof window.history.replaceState !== "function") return;
    try {
      const url = new URL(window.location.href);
      const pageValue = currentPage > 1 ? String(currentPage) : "";
      if (pageValue) {
        if (url.searchParams.get(pageParam) === pageValue) return;
        url.searchParams.set(pageParam, pageValue);
      } else {
        if (!url.searchParams.has(pageParam)) return;
        url.searchParams.delete(pageParam);
      }
      window.history.replaceState(null, "", url.href);
    } catch (error) {}
  }

  function createPaginationControls({ label, pageSizeLabel, itemNamePlural, onPrevious, onNext, onPageSizeChange }) {
    paginationControlId += 1;
    const selectId = `pagination-size-${paginationControlId}`;

    const root = document.createElement("nav");
    root.className = "pagination-controls";
    root.setAttribute("aria-label", `${label} pagination`);
    root.hidden = true;

    const sizeWrapper = document.createElement("div");
    sizeWrapper.className = "pagination-size";

    const selectLabel = document.createElement("label");
    selectLabel.htmlFor = selectId;
    selectLabel.textContent = pageSizeLabel;

    const select = document.createElement("select");
    select.id = selectId;
    pageSizeOptions.forEach((optionValue) => {
      const option = document.createElement("option");
      option.value = String(optionValue);
      option.textContent = `${optionValue} ${itemNamePlural}`;
      select.append(option);
    });
    select.addEventListener("change", () => {
      onPageSizeChange(Number.parseInt(select.value, 10));
    });

    sizeWrapper.append(selectLabel, select);

    const statusText = document.createElement("p");
    statusText.className = "pagination-status";
    statusText.setAttribute("aria-live", "polite");
    statusText.setAttribute("aria-atomic", "true");

    const buttonWrapper = document.createElement("div");
    buttonWrapper.className = "pagination-buttons";

    const previousButton = document.createElement("button");
    previousButton.type = "button";
    previousButton.textContent = "Previous";
    previousButton.setAttribute("aria-label", `Previous page of ${label}`);
    previousButton.addEventListener("click", onPrevious);

    const nextButton = document.createElement("button");
    nextButton.type = "button";
    nextButton.textContent = "Next";
    nextButton.setAttribute("aria-label", `Next page of ${label}`);
    nextButton.addEventListener("click", onNext);

    buttonWrapper.append(previousButton, nextButton);
    root.append(sizeWrapper, statusText, buttonWrapper);
    return { root, select, statusText, previousButton, nextButton };
  }

  function createPager({
    containers,
    label,
    pageSizeLabel,
    itemName,
    itemNamePlural,
    total,
    renderRange,
    pageParam = "",
  }) {
    let currentPage = pageFromUrl(pageParam);
    let pageSize = savedPageSize();
    const controls = containers
      .filter(Boolean)
      .map((container) => {
        const control = createPaginationControls({
          label,
          pageSizeLabel,
          itemNamePlural,
          onPrevious: () => {
            currentPage -= 1;
            render();
          },
          onNext: () => {
            currentPage += 1;
            render();
          },
          onPageSizeChange: (value) => {
            if (!pageSizeOptions.includes(value)) return;
            pageSize = value;
            currentPage = 1;
            savePageSize(value);
            render();
          },
        });
        container.replaceChildren(control.root);
        return control;
      });

    function updateControls(totalCount, start, end, pageCount) {
      const showControls = totalCount > pageSizeOptions[0];
      const noun = totalCount === 1 ? itemName : itemNamePlural;
      let statusText = "";
      if (totalCount > 0) {
        statusText =
          totalCount <= pageSize
            ? `Showing all ${totalCount} ${noun}.`
            : `Showing ${start + 1} to ${end} of ${totalCount} ${noun}. Page ${currentPage} of ${pageCount}.`;
      }

      controls.forEach((control) => {
        control.root.hidden = !showControls;
        control.select.value = String(pageSize);
        control.statusText.textContent = statusText;
        control.previousButton.disabled = currentPage <= 1;
        control.nextButton.disabled = currentPage >= pageCount;
      });
    }

    function render() {
      const totalCount = total();
      const pageCount = Math.max(1, Math.ceil(totalCount / pageSize));
      currentPage = Math.min(Math.max(currentPage, 1), pageCount);
      syncPageToUrl(pageParam, currentPage);
      const start = totalCount === 0 ? 0 : (currentPage - 1) * pageSize;
      const end = Math.min(start + pageSize, totalCount);
      renderRange(start, end, totalCount, currentPage, pageCount, pageSize);
      updateControls(totalCount, start, end, pageCount);
    }

    function hide() {
      controls.forEach((control) => {
        control.root.hidden = true;
      });
    }

    return {
      render,
      reset({ restorePage = false } = {}) {
        currentPage = restorePage ? pageFromUrl(pageParam) : 1;
        render();
      },
      hide,
    };
  }

  function initializeResourcePagination() {
    const sections = Array.from(document.querySelectorAll("[data-resource-pagination]"));
    sections.forEach((section) => {
      const items = Array.from(section.querySelectorAll("[data-resource]"));
      if (items.length <= pageSizeOptions[0]) return;

      const heading = section.querySelector("#resources-heading, h2, h3");
      const label = heading && heading.textContent.trim() ? heading.textContent.trim() : "Resources";
      const pager = createPager({
        containers: [
          section.querySelector("[data-pagination-bottom]"),
        ],
        label,
        pageSizeLabel: "Resources per page",
        itemName: "resource",
        itemNamePlural: "resources",
        pageParam: "page",
        total: () => items.length,
        renderRange: (start, end) => {
          items.forEach((item, index) => {
            item.hidden = index < start || index >= end;
          });

          Array.from(section.querySelectorAll("[data-subcategory-section]")).forEach((subsection) => {
            const hasVisibleItems = Array.from(subsection.querySelectorAll("[data-resource]")).some(
              (item) => !item.hidden
            );
            subsection.hidden = !hasVisibleItems;
          });
        },
      });
      pager.render();
    });
  }

  initializeResourcePagination();

  if (!search || !clearButton || !searchAll) return;

  let searchMatches = [];
  let searchPager = null;

  function updateFilterDetailsVisibility() {
    if (!filterDetails) return;
    const hideFilters = searchAll.checked;
    filterDetails.hidden = hideFilters;
    searchAll.setAttribute("aria-expanded", String(!hideFilters));
    if (hideFilters) {
      filterDetails.open = false;
    }
  }

  if (resultsSection && resultsList) {
    searchPager = createPager({
      containers: [
        document.querySelector("[data-search-pagination-bottom]"),
      ],
      label: "Search results",
      pageSizeLabel: "Results per page",
      itemName: "result",
      itemNamePlural: "results",
      pageParam: "page",
      total: () => searchMatches.length,
      renderRange: (start, end, totalCount) => {
        resultsList.replaceChildren(...searchMatches.slice(start, end).map(resultItem));
        resultsSection.hidden = false;
        const hasMatches = totalCount > 0;
        resultsList.hidden = !hasMatches;
        noResults.hidden = hasMatches;
        const noun = totalCount === 1 ? "result" : "results";
        status.textContent = hasMatches
          ? `${totalCount} ${noun} found. Showing ${start + 1} to ${end}.`
          : "0 results found.";
      },
    });
    searchPager.hide();
  }

  function siteRootUrl() {
    const root = document.body.dataset.siteRoot || "./";
    return new URL(root, window.location.href);
  }

  function itemHref(item) {
    if (/^[a-z][a-z0-9+.-]*:/i.test(item.href)) {
      return item.href;
    }
    return new URL(item.href, siteRootUrl()).href;
  }

  function selectedScopes() {
    if (searchAll.checked) return [];
    return filterBoxes.filter((box) => box.checked).map((box) => box.value);
  }

  function matchesScope(item, scopes, wholeSite) {
    if (wholeSite) return true;
    if (scopes.length === 0) return false;
    return scopes.some((scope) => item.scopes.includes(scope));
  }

  function clearResults() {
    if (!resultsSection || !resultsList || !noResults || !status) return;
    searchMatches = [];
    resultsList.replaceChildren();
    resultsList.hidden = true;
    resultsSection.hidden = true;
    noResults.hidden = true;
    status.textContent = "";
    if (searchPager) {
      searchPager.hide();
    }
  }

  function appendTitleText(target, item) {
    const segments = Array.isArray(item.titleSegments) ? item.titleSegments : [];
    if (segments.length === 0) {
      target.textContent = item.title;
      return;
    }

    const onlySegment = segments.length === 1 ? segments[0] : null;
    if (
      onlySegment &&
      typeof onlySegment.lang === "string" &&
      onlySegment.lang &&
      typeof onlySegment.text === "string"
    ) {
      target.lang = onlySegment.lang;
      target.textContent = onlySegment.text;
      return;
    }

    segments.forEach((segment) => {
      if (!segment || typeof segment.text !== "string" || segment.text.length === 0) return;
      if (typeof segment.lang === "string" && segment.lang) {
        const span = document.createElement("span");
        span.lang = segment.lang;
        span.textContent = segment.text;
        target.append(span);
      } else {
        target.append(document.createTextNode(segment.text));
      }
    });
  }

  function resultItem(item) {
    const listItem = document.createElement("li");
    listItem.className = "resource-item";

    const link = document.createElement("a");
    link.href = itemHref(item);
    if (item.downloadable) {
      link.setAttribute("download", item.downloadName || "");
    } else {
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
    appendTitleText(link, item);
    listItem.append(link);

    if (item.fileInfo) {
      const fileInfo = document.createElement("p");
      fileInfo.className = "resource-meta";
      fileInfo.textContent = item.resultType === "resource" ? `File: ${item.fileInfo}` : item.fileInfo;
      listItem.append(fileInfo);
    }

    if (item.category) {
      const category = document.createElement("p");
      category.className = "resource-meta";
      category.textContent = item.category;
      listItem.append(category);
    }

    return listItem;
  }

  function applyUrlSearch() {
    const params = new URLSearchParams(window.location.search);
    const query = params.get("q") || "";
    const scopes = params.getAll("scope");
    const scopeSet = new Set(scopes);

    search.value = query;
    if (scopes.length > 0) {
      searchAll.checked = false;
      filterBoxes.forEach((box) => {
        box.checked = scopeSet.has(box.value);
      });
    } else {
      searchAll.checked = true;
      filterBoxes.forEach((box) => {
        box.checked = false;
      });
    }
    updateFilterDetailsVisibility();

    if (!resultsSection || !resultsList || !noResults || !status) return;

    const normalizedQuery = query.trim().toLocaleLowerCase();
    const wholeSite = scopes.length === 0;
    const hasSearch = normalizedQuery.length > 0;

    if (!hasSearch) {
      clearResults();
      return;
    }

    searchMatches = resources
      .filter((item) => {
        const textMatches = item.searchText.includes(normalizedQuery);
        return textMatches && matchesScope(item, scopes, wholeSite);
      })
      .sort((a, b) => {
        const groupDifference = (a.sortGroup || 3) - (b.sortGroup || 3);
        if (groupDifference !== 0) return groupDifference;
        return a.title.localeCompare(b.title, undefined, { sensitivity: "base" });
      });

    if (searchPager) {
      searchPager.reset({ restorePage: true });
    }
    if (window.location.hash === "#search-results-heading" && resultsHeading) {
      resultsHeading.focus();
    }
  }

  searchAll.addEventListener("change", () => {
    if (searchAll.checked) {
      filterBoxes.forEach((box) => {
        box.checked = false;
      });
    }
    updateFilterDetailsVisibility();
  });
  filterBoxes.forEach((box) => {
    box.addEventListener("change", () => {
      if (box.checked) {
        searchAll.checked = false;
      }
      updateFilterDetailsVisibility();
    });
  });
  clearButton.addEventListener("click", () => {
    search.value = "";
    searchAll.checked = true;
    filterBoxes.forEach((box) => {
      box.checked = false;
    });
    updateFilterDetailsVisibility();
    clearResults();
    search.focus();
    if (resultsSection) {
      history.replaceState(null, "", window.location.pathname);
    }
  });

  if (resultsSection) {
    applyUrlSearch();
  } else {
    updateFilterDetailsVisibility();
  }
})();
"""


SITE_MARK_SVG = r"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="">
  <rect width="64" height="64" rx="8" fill="#006a67"/>
  <circle cx="32" cy="32" r="20" fill="#ffffff"/>
  <circle cx="32" cy="32" r="12" fill="#f2b632"/>
  <path d="M19 32h26M32 19v26" stroke="#171717" stroke-width="4" stroke-linecap="round"/>
  <circle cx="32" cy="32" r="4" fill="#6d275c"/>
</svg>
"""


FAVICON_SVG = r"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="5" fill="#006a67"/>
  <circle cx="16" cy="16" r="10" fill="#ffffff"/>
  <circle cx="16" cy="16" r="5" fill="#f2b632"/>
</svg>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the RoundTable Resources website and publish it to GitHub Pages."
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Build the website files without committing or pushing to GitHub.",
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Git remote to push to after building. Defaults to origin.",
    )
    parser.add_argument(
        "--branch",
        default="main",
        help="Git branch that GitHub Pages publishes from. Defaults to main.",
    )
    parser.add_argument(
        "--message",
        default="Update generated site",
        help="Commit message to use when the generated website changed.",
    )
    return parser.parse_args()


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=SITE_DIR,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        command = "git " + " ".join(args)
        raise RuntimeError(f"{command} failed: {output}")
    return result.stdout.strip()


def ensure_publish_ready(remote: str, branch: str) -> None:
    if run_git(["rev-parse", "--is-inside-work-tree"]) != "true":
        raise RuntimeError(f"{SITE_DIR} is not inside a git repository.")

    run_git(["remote", "get-url", remote])
    current_branch = run_git(["branch", "--show-current"])
    if current_branch != branch:
        raise RuntimeError(
            f"Publishing expects the current branch to be {branch!r}, but it is {current_branch!r}."
        )

    staged_changes = run_git(["diff", "--cached", "--name-only"]).splitlines()
    if staged_changes:
        raise RuntimeError(
            "There are already staged changes. Commit or unstage them before publishing."
        )


def iter_publish_files():
    for publish_path in PUBLISH_PATHS:
        path = SITE_DIR / publish_path
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    yield child


def ensure_publish_files_readable() -> None:
    unreadable: list[str] = []
    for path in iter_publish_files():
        try:
            with path.open("rb") as handle:
                handle.read(1)
        except OSError as error:
            rel = path.relative_to(SITE_DIR).as_posix()
            unreadable.append(f"{rel}: {error}")

    if unreadable:
        details = "\n".join(unreadable[:10])
        if len(unreadable) > 10:
            details += f"\n...and {len(unreadable) - 10} more."
        raise RuntimeError(f"Could not read every generated publish file:\n{details}")


def stage_publish_paths() -> None:
    try:
        run_git(["add", "-A", "--", *PUBLISH_PATHS])
    except RuntimeError as error:
        message = str(error).casefold()
        if not any(marker in message for marker in ("permission denied", "unable to index", "could not open")):
            raise
        print("Git could not read a generated file, so checking the publish files and retrying...", flush=True)
        ensure_publish_files_readable()
        run_git(["add", "-A", "--", *PUBLISH_PATHS])


def publish_site(remote: str, branch: str, message: str) -> None:
    ensure_publish_ready(remote, branch)
    stage_publish_paths()

    staged_changes = run_git(["diff", "--cached", "--name-only"]).splitlines()
    if staged_changes:
        run_git(["commit", "-m", message])
        print(f"Committed {len(staged_changes)} changed website files.")
    else:
        print("No website file changes to commit.")

    print(f"Pushing {branch} to {remote} on GitHub...", flush=True)
    run_git(["push", remote, branch])
    print(f"Successfully pushed {branch} to {remote}. GitHub Pages will update shortly.")


def build_site() -> tuple[int, int]:
    resources = load_resources()
    notes = load_page_notes()
    pages = load_category_pages(resources, notes)
    pages_by_dir = {page.source_dir: page for page in pages}
    write_static_assets(resources, pages, notes)
    (SITE_DIR / "index.html").write_text(render_index(resources, pages, notes), encoding="utf-8")
    (SITE_DIR / ARCHIVE_PAGE_REL).write_text(render_archive_page(), encoding="utf-8")
    (SITE_DIR / "search.html").write_text(render_search_page(pages), encoding="utf-8")
    for page in pages:
        output_path = SITE_DIR / page.page_rel
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_category_page(page, pages, pages_by_dir, resources, notes), encoding="utf-8")
    print(f"Built {len(resources)} resources, {len(notes)} page notes and {len(pages)} category pages into {SITE_DIR}")
    return len(resources), len(pages)


def main() -> None:
    args = parse_args()
    build_site()
    if not args.local_only:
        publish_site(args.remote, args.branch, args.message)


if __name__ == "__main__":
    main()
