import math
import re
import unicodedata

_HANGUL = re.compile(r"[가-힣]")
_WORD = re.compile(r"\w+")
_SPLIT_HANGUL = re.compile(r"[가-힣]+|[^가-힣]+")
_VI_SPECIFIC = set("ăâđêôơưĂÂĐÊÔƠƯ")
# Tilde vowels and Latin Extended Additional. Latin-1 accents, as in "résumé", say nothing about the language.
_VI_RANGE = re.compile("[ĨĩŨũẠ-ỹ]")
MIN_QUOTE_CHARS = 12
MIN_QUOTE_CHARS_KOREAN = 6

K1 = 1.5
B = 0.75

# Tokens that say nothing about a question's topic, so they do not count towards keyword coverage. Ranking keeps them.
_STOP_EN = """
a about all also am an and any are as at be been but by can could did do does for from get got had has have how i if
in into is it its me my no not of on or our shall should so that the their them then there these they this to us was
we were what when where which who whom why will with would you your
""".split()
# Syllables, because tokenise splits Vietnamese on spaces.
_STOP_VI = """
ai anh bao các cho chị có của cũng đã đang để đó được em gì hay hãy khi không là làm lại mà mấy mình một này nào nhiêu
những nếu phải rằng rồi sao sẽ tôi thì thế theo trong và về với vậy
""".split()
# Syllable pairs, because tokenise splits Hangul that way, plus particles that stand alone.
_STOP_KO = """
가 과 는 도 를 에 와 은 을 의 이 입니 니다 니까 습니 합니 됩니 있습 없습 나요 까요 인가 는지 무엇 어떻 떻게 얼마
""".split()
_STOP_WORDS = frozenset(_STOP_EN + _STOP_VI + _STOP_KO)


def normalise_for_match(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text or "").split())


def normalise_title(text: str) -> str:
    return normalise_for_match(text).casefold()


def quote_in(quote: str, source: str) -> bool:
    needle = normalise_for_match(quote)
    if not needle:
        return False
    return needle in normalise_for_match(source)


def verified_quote(quote: str, source: str) -> bool:
    """The anti-fabrication gate: the quote is in its source and long enough to prove something."""
    needle = normalise_for_match(quote)
    minimum = MIN_QUOTE_CHARS_KOREAN if _HANGUL.search(needle) else MIN_QUOTE_CHARS
    return len(needle) >= minimum and quote_in(needle, source)


def tokenise(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKC", text or "").casefold()
    tokens: list[str] = []
    for word in _WORD.findall(folded):
        for run in _SPLIT_HANGUL.findall(word):
            if _HANGUL.match(run):
                if len(run) == 1:
                    tokens.append(run)
                else:
                    tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
            else:
                tokens.append(run)
    return tokens


def content_tokens(tokens: list[str]) -> list[str]:
    return [token for token in tokens if token not in _STOP_WORDS]


def keyword_coverage(query_tokens: list[str], document_tokens: list[str]) -> float:
    """The fraction of the query's distinct non-stop tokens found in the document. 0.0 when it has none."""
    wanted = set(content_tokens(query_tokens))
    if not wanted:
        return 0.0
    return len(wanted & set(document_tokens)) / len(wanted)


def guess_language(text: str) -> str:
    value = unicodedata.normalize("NFC", text or "")
    if _HANGUL.search(value):
        return "ko"
    if any(ch in _VI_SPECIFIC for ch in value) or _VI_RANGE.search(value):
        return "vi"
    return "en"


def keyword_scores(query_tokens: list[str], documents_tokens: list[list[str]]) -> list[float]:
    count = len(documents_tokens)
    if count == 0:
        return []
    lengths = [len(doc) for doc in documents_tokens]
    average = (sum(lengths) / count) or 1.0
    frequencies = [{} for _ in documents_tokens]
    for index, doc in enumerate(documents_tokens):
        for token in doc:
            frequencies[index][token] = frequencies[index].get(token, 0) + 1
    scores = [0.0] * count
    for token in set(query_tokens):
        df = sum(1 for freq in frequencies if token in freq)
        if df == 0:
            continue
        idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
        for index, freq in enumerate(frequencies):
            tf = freq.get(token, 0)
            if tf:
                denominator = tf + K1 * (1 - B + B * lengths[index] / average)
                scores[index] += idf * tf * (K1 + 1) / denominator
    top = max(scores)
    if top <= 0:
        return [0.0] * count
    return [score / top for score in scores]
