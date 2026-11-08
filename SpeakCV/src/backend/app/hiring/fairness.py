"""The identity-swap check: swap name and gender in a CV, mask again, and report honestly whether anything changed.

It reads the application and writes only an audit row. `screening.assess` is never called, because it replaces the
application's results; the result is compared through the cache that makes two identical blind texts share one.
"""
import re
import unicodedata
from dataclasses import dataclass

from app.ai.config import get_config
from app.database.sql_models import Application
from app.hiring import audit, identity, screening

_FOUND_BY_AI = re.compile(r"\[(NAME|GENDER|AGE|ADDRESS)\]")
_ANY_TOKEN = re.compile(r"\[[A-Z]+\]")
_GENDER_LABEL = re.compile(
    r"(?<!\w)(?:Gender|Sex|Giới tính|성별)[ \t]*[:：][ \t]*(.*?)(?=[ \t]{2,}|\t|$)", re.IGNORECASE | re.MULTILINE,
)
_MEN_TO_WOMEN = {
    "he": "she", "him": "her", "his": "her", "himself": "herself", "mr": "ms", "mr.": "ms.", "male": "female",
    "man": "woman", "nam": "nữ", "anh": "chị", "ông": "bà", "남성": "여성", "남자": "여자", "그": "그녀",
}
_WOMEN_TO_MEN = {
    **{woman: man for man, woman in _MEN_TO_WOMEN.items()},
    "her": "him", "hers": "his", "ms.": "mr.", "ms": "mr", "mrs.": "mr.", "mrs": "mr", "miss": "mr",
}


class FairnessUnavailable(Exception):
    """This application cannot be checked. The message is fixed text, safe to show."""


class ApplicationDeleted(FairnessUnavailable):
    """This application's personal data has been deleted, so to HR there is nothing here to check."""


@dataclass(frozen=True)
class SwapIdentity:
    name: str
    pronoun: str


WOMAN = SwapIdentity(name="Trần Thị Mai", pronoun="she")
MAN = SwapIdentity(name="Nguyễn Văn Minh", pronoun="he")


@dataclass(frozen=True)
class FairnessResult:
    identical_blind_text: bool
    identical_result: bool
    original_blind_text: str
    swapped_blind_text: str


def found_terms(raw_text: str, blind_text: str) -> dict[str, list[str]]:
    """Read what masking replaced by lining the blind text up with the CV, so no new AI call sees the raw CV."""
    source = "\n".join(" ".join(line.split()) for line in identity.regex_mask(raw_text).splitlines()).strip()
    parts = _FOUND_BY_AI.split(blind_text)
    literals, tokens = parts[0::2], parts[1::2]
    if not source.startswith(literals[0]):
        raise FairnessUnavailable("The stored blind text does not line up with this CV")
    found = {"NAME": [], "GENDER": []}
    position = len(literals[0])
    for index, token in enumerate(tokens):
        literal = literals[index + 1]
        if index == len(tokens) - 1:
            end = len(source) - len(literal) if source.endswith(literal) else -1
        else:
            end = source.find(literal, position + 1)
        if end < position:
            raise FairnessUnavailable("The stored blind text does not line up with this CV")
        term = source[position:end]
        if token in found and term not in found[token] and not _ANY_TOKEN.fullmatch(term):
            found[token].append(term)
        position = end + len(literal)
    if not tokens and source != blind_text:
        raise FairnessUnavailable("The stored blind text does not line up with this CV")
    return {"names": found["NAME"], "gender_terms": found["GENDER"]}


def _other_identity(gender_terms: list[str]) -> SwapIdentity:
    words = [term.casefold() for term in gender_terms]
    women = sum(word in _WOMEN_TO_MEN for word in words)
    men = sum(word in _MEN_TO_WOMEN for word in words)
    return MAN if women > men else WOMAN


def _flipped(term: str, other: SwapIdentity) -> str:
    table = _MEN_TO_WOMEN if other is WOMAN else _WOMEN_TO_MEN
    word = table.get(term.casefold(), other.pronoun)
    return word.capitalize() if term[:1].isupper() else word


def swap_identity(raw_text: str, terms: dict[str, list[str]]) -> str:
    """The CV with its names and gender terms replaced by a fixed identity of the other gender.

    Contact details are masked first, because a name inside an email address would otherwise be replaced there, and
    the broken address would no longer mask. A gender label's value is masked by then too, so it only guides the choice.
    """
    labels = [match[1].strip() for match in _GENDER_LABEL.finditer(unicodedata.normalize("NFC", raw_text))]
    other = _other_identity([*terms["gender_terms"], *labels])
    replacements: dict[str, list[str]] = {other.name: list(terms["names"])}
    for term in terms["gender_terms"]:
        replacements.setdefault(_flipped(term, other), []).append(term)
    return identity.apply_terms(identity.regex_mask(raw_text), replacements)


def _same_result(db, application, original_hash: str, swapped_hash: str) -> bool:
    """Identical hashes share one cache row by construction. Different ones count only if both rows exist and agree."""
    if original_hash == swapped_hash:
        return True
    key = {
        "job_id": application.job_id, "job_version": application.job_version,
        "prompt_version": screening.PROMPT_VERSION, "model": get_config().slot("bulk").model,
    }
    original = screening._cached(db, {**key, "blind_hash": original_hash})
    swapped = screening._cached(db, {**key, "blind_hash": swapped_hash})
    return original is not None and original == swapped


def check(db, application, *, actor_user_id=None) -> FairnessResult:
    """Commits. It holds no transaction during the masking call, and rereads the application after it."""
    if application.anonymized_at is not None:
        raise ApplicationDeleted("This application's personal data has been deleted")
    raw_text, original_blind, original_hash = application.cv_text_raw, application.cv_text_blind, application.cv_blind_hash
    if not raw_text or not original_blind:
        raise FairnessUnavailable("This application's CV has not been read")
    swapped_text = swap_identity(raw_text, found_terms(raw_text, original_blind))
    if swapped_text == identity.regex_mask(raw_text):
        raise FairnessUnavailable("No name or gender term was found in this CV, so there is nothing to swap")
    application_id, company_id = application.id, application.company_id
    db.commit()

    masked = identity.mask_with_ai(swapped_text, company_id=company_id)

    application = (
        db.query(Application).filter(Application.id == application_id)
        .populate_existing().with_for_update().first()
    )
    if application is None or application.anonymized_at is not None:
        db.rollback()
        raise ApplicationDeleted("This application's personal data has been deleted")
    identical_text = masked.blind_text == original_blind
    identical_result = _same_result(db, application, original_hash, masked.blind_hash)
    slot = get_config().slot("bulk")
    audit.record(
        db, company_id, actor_user_id, "fairness_check", "application", application.id,
        payload={"identical_blind_text": identical_text, "identical_result": identical_result},
        ai_provider=slot.provider, ai_model=slot.model,
    )
    db.commit()
    return FairnessResult(
        identical_blind_text=identical_text, identical_result=identical_result,
        original_blind_text=original_blind, swapped_blind_text=masked.blind_text,
    )
