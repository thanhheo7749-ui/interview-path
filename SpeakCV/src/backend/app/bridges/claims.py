"""What a job description line may claim, given the nodes it cites: every number with its unit, and every salary or
benefit it names. The check is on words, so a line that fails is not false: it goes to HR, who may confirm it."""
import re

from app.brain import contradiction
from app.brain.text import normalise_title

# Each set means one thing in English, Vietnamese and Korean, so a Korean line can rest on an English node.
_TERMS = {
    "salary": ("salary", "salaries", "pay", "wage", "wages", "compensation", "remuneration", "stipend",
               "lương", "luong", "thu nhập", "thù lao",
               "연봉", "월급", "급여", "임금", "처우"),
    "bonus": ("bonus", "bonuses", "incentive", "incentives", "commission", "13th month", "thirteenth month",
              "thưởng", "hoa hồng", "tháng 13",
              "보너스", "상여", "성과급", "인센티브"),
    "allowance or benefit": ("allowance", "allowances", "perk", "perks", "benefit", "benefits",
                             "phụ cấp", "trợ cấp", "phúc lợi",
                             "수당", "복지", "복리후생", "혜택"),
    "housing": ("housing", "accommodation", "dormitory", "rent",
                "nhà ở", "chỗ ở", "ký túc",
                "주택", "기숙사", "사택", "숙소"),
    "transport": ("company car", "car", "shuttle", "commute", "commuting",
                  "xe công ty", "đưa đón",
                  "회사 차", "법인차", "법인 차", "셔틀", "통근"),
    "insurance": ("insurance",
                  "bảo hiểm",
                  "보험"),
    "leave": ("leave", "vacation", "pto", "holiday", "holidays",
              "nghỉ phép", "phép năm", "ngày phép",
              "연차", "휴가"),
    "meals": ("lunch", "meal", "meals", "catering",
              "bữa trưa", "ăn trưa", "bữa ăn",
              "식대", "점심", "식사"),
    "equity": ("equity", "stock option", "stock options", "shares", "rsu", "rsus",
               "cổ phần", "cổ phiếu",
               "스톡옵션", "주식"),
}


def _is_hangul(term: str) -> bool:
    return any("가" <= char <= "힣" for char in term)


def _pattern(terms: tuple[str, ...]) -> re.Pattern:
    """Korean attaches particles to a word, so its terms match anywhere. The rest match as whole words."""
    parts = [re.escape(normalise_title(term)) if _is_hangul(term)
             else rf"(?<!\w){re.escape(normalise_title(term))}(?!\w)" for term in terms]
    return re.compile("|".join(parts))


_TERM_PATTERNS = {name: _pattern(terms) for name, terms in _TERMS.items()}


def terms_in(text: str) -> set[str]:
    folded = normalise_title(text or "")
    return {name for name, pattern in _TERM_PATTERNS.items() if pattern.search(folded)}


def _source_of(line: dict, node_texts: dict[int, str]) -> str:
    return "\n".join(node_texts.get(node_id, "") for node_id in line.get("source_node_ids") or [])


def unsupported_line_numbers(line: dict, node_texts: dict[int, str]) -> list[str]:
    """The numbers in this line, in any language, that the nodes it cites do not state with that unit."""
    source = _source_of(line, node_texts)
    texts = [text for text in (line.get("text") or {}).values() if text]
    return list(dict.fromkeys(number for text in texts for number in contradiction.unsupported_numbers(text, source)))


def unsupported_claims(line: dict, node_texts: dict[int, str]) -> str | None:
    """Why the nodes this line cites do not support it, or None when they do."""
    source = _source_of(line, node_texts)
    texts = [text for text in (line.get("text") or {}).values() if text]
    numbers = unsupported_line_numbers(line, node_texts)
    terms = sorted(set().union(*(terms_in(text) for text in texts)) - terms_in(source)) if texts else []
    reasons = []
    if numbers:
        reasons.append(f"The line states numbers that its sources do not contain: {', '.join(numbers)}.")
    if terms:
        reasons.append(f"The line mentions what its sources do not: {', '.join(terms)}.")
    return " ".join(reasons) or None
