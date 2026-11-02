"""The company's own learning catalogue. No AI writes here, and only rows from here are ever linked to a candidate."""
import csv
import io
import re
import unicodedata
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.database.sql_models import KbNode, LearningResource
from app.hiring import audit

MAX_ROWS = 1000
MAX_TITLE = 500
MAX_URL = 2000
MAX_PROVIDER = 100
CSV_COLUMNS = ("skill_node_id", "title", "url")
_LANGUAGE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,4})?$")
_URL_BREAKERS = re.compile(r"[\s<>\"\\]")
_TRAILING = ".,;:!?)]}'\"…"
# A link written any way a reader or a mail client would follow it. A bare domain counts only on a common ending,
# because a skill can look like one: Node.js, ASP.NET.
_LINK = re.compile(
    r"\b[a-z][a-z0-9+.-]*://\S+"
    r"|\b(?:javascript|data):\S+"
    r"|(?<![\w.@/-])www\.\S+"
    r"|(?<![\w.@/-])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|edu|gov|vn|kr|info|academy|courses|co)\b(?:/\S*)?",
    re.IGNORECASE,
)


class CatalogueError(ValueError):
    """Row is the 1-based data row, or 0 for the file itself."""

    def __init__(self, row: int, message: str):
        super().__init__(message)
        self.row = row
        self.message = message


def visible_text(text: str) -> str:
    """The text as a reader sees it: compatibility forms folded and invisible characters gone."""
    return "".join(ch for ch in unicodedata.normalize("NFKC", text or "") if unicodedata.category(ch) != "Cf")


def _comparable(url: str) -> str:
    return url.rstrip(_TRAILING)


def links_in(text: str) -> list[str]:
    return [_comparable(found) for found in _LINK.findall(visible_text(text))]


def valid_url(url) -> bool:
    if not isinstance(url, str) or not url or len(url) > MAX_URL or visible_text(url) != url:
        return False
    if _URL_BREAKERS.search(url) or any(unicodedata.category(ch) == "Cc" for ch in url):
        return False
    try:
        parts = urlsplit(url)
        return parts.scheme.lower() in ("http", "https") and bool(parts.hostname)
    except ValueError:
        return False


def _clean_text(value, name: str, limit: int, row: int, required: bool = False) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise CatalogueError(row, f"{name} must be text")
    text = " ".join(value.split())
    if required and not text:
        raise CatalogueError(row, f"{name} is required")
    if len(text) > limit:
        raise CatalogueError(row, f"{name} is longer than {limit} characters")
    if links_in(text):  # only the url column links anywhere, so the guard can compare every link with the catalogue
        raise CatalogueError(row, f"{name} cannot hold a link")
    return text


def _clean_node_id(value, row: int) -> int:
    if isinstance(value, str) and value.strip().isdecimal():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int):
        raise CatalogueError(row, "skill_node_id must be a number")
    return value


def clean(raw, row: int = 1) -> dict:
    if not isinstance(raw, dict):
        raise CatalogueError(row, "Each resource must be an object")
    url = raw.get("url")
    url = url.strip() if isinstance(url, str) else url
    if not valid_url(url):
        raise CatalogueError(row, "url must be a complete http or https link")
    language = raw.get("language")
    language = language.strip() if isinstance(language, str) else language
    language = "en" if language in (None, "") else language
    if not isinstance(language, str) or len(language) > 10 or not _LANGUAGE.match(language):
        raise CatalogueError(row, "language must be a language code such as en or vi")
    return {
        "skill_node_id": _clean_node_id(raw.get("skill_node_id"), row),
        "title": _clean_text(raw.get("title"), "title", MAX_TITLE, row, required=True),
        "url": url,
        "provider": _clean_text(raw.get("provider"), "provider", MAX_PROVIDER, row),
        "language": language,
    }


def parse_csv(data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        columns = [(name or "").strip() for name in (reader.fieldnames or [])]
        if not set(CSV_COLUMNS) <= set(columns):
            raise CatalogueError(0, f"The file needs the columns {', '.join(CSV_COLUMNS)}")
        reader.fieldnames = columns
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CatalogueError(0, "The file is not a readable UTF-8 CSV") from exc
    return rows


def _nodes_in_company(db: Session, company_id: int, node_ids: set[int]) -> set[int]:
    if not node_ids:
        return set()
    rows = db.query(KbNode.id).filter(KbNode.company_id == company_id, KbNode.id.in_(node_ids)).all()
    return {row[0] for row in rows}


def save(db: Session, company_id: int, raw_items: list, user_id: int) -> tuple[int, int, list[LearningResource]]:
    """All or nothing: the caller commits, or rolls back on CatalogueError. The same skill and link updates its row."""
    if len(raw_items) > MAX_ROWS:
        raise CatalogueError(0, f"A file can hold at most {MAX_ROWS} resources")
    items = [clean(raw, index) for index, raw in enumerate(raw_items, 1)]
    known = _nodes_in_company(db, company_id, {item["skill_node_id"] for item in items})
    for index, item in enumerate(items, 1):
        if item["skill_node_id"] not in known:
            raise CatalogueError(index, "skill_node_id is not a node of this company")
    created, updated = 0, 0
    saved = {}
    for item in items:
        key = (item["skill_node_id"], item["url"])
        row = saved.get(key) or (
            db.query(LearningResource)
            .filter_by(company_id=company_id, skill_node_id=item["skill_node_id"], url=item["url"]).first()
        )
        if row is None:
            row = LearningResource(company_id=company_id, created_by=user_id, **item)
            db.add(row)
            created += 1
        else:
            if key not in saved:
                updated += 1
            row.title, row.provider, row.language = item["title"], item["provider"], item["language"]
        saved[key] = row
    db.flush()
    audit.record(db, company_id, user_id, "learning_resources_saved", "company", company_id,
                 payload={"created": created, "updated": updated})
    return created, updated, list(saved.values())


def update(db: Session, row: LearningResource, changes: dict, user_id: int) -> None:
    current = {"skill_node_id": row.skill_node_id, "title": row.title, "url": row.url, "provider": row.provider,
               "language": row.language}
    item = clean({**current, **changes})
    if not _nodes_in_company(db, row.company_id, {item["skill_node_id"]}):
        raise CatalogueError(1, "skill_node_id is not a node of this company")
    for name, value in item.items():
        setattr(row, name, value)
    audit.record(db, row.company_id, user_id, "learning_resource_updated", "learning_resource", row.id)
    db.flush()


def delete(db: Session, row: LearningResource, user_id: int) -> None:
    audit.record(db, row.company_id, user_id, "learning_resource_deleted", "learning_resource", row.id)
    db.delete(row)
    db.flush()


def suggest(db: Session, company_id: int, skill_node_ids) -> list[LearningResource]:
    """Catalogue rows for these skills. A skill with no row adds nothing."""
    ids = set(skill_node_ids or ())
    if not ids:
        return []
    return (
        db.query(LearningResource)
        .filter(LearningResource.company_id == company_id, LearningResource.skill_node_id.in_(ids))
        .order_by(LearningResource.id).all()
    )


def catalogue_urls(db: Session, company_id: int) -> set[str]:
    rows = db.query(LearningResource.url).filter(LearningResource.company_id == company_id).all()
    return {_comparable(visible_text(row[0])) for row in rows}


def linked(db: Session, company_id: int, text: str) -> list[LearningResource]:
    """The catalogue rows this text links to, one per link. A link HR removed from the text is no longer a suggestion."""
    found = set(links_in(text))
    if not found:
        return []
    rows = db.query(LearningResource).filter(LearningResource.company_id == company_id).order_by(LearningResource.id)
    unique = {}
    for row in rows:
        link = _comparable(visible_text(row.url))
        if link in found:
            unique.setdefault(link, row)
    return list(unique.values())


def public_row(row: LearningResource) -> dict:
    return {"id": row.id, "title": row.title, "url": row.url, "provider": row.provider, "language": row.language}
