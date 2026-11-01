import unicodedata

from app.brain.text import guess_language, keyword_scores, normalise_for_match, normalise_title, quote_in, tokenise


def test_quote_matches_across_unicode_forms_and_whitespace():
    source = "Nhân viên được nghỉ\n  12 ngày phép mỗi năm."
    assert quote_in("được nghỉ 12 ngày phép", source)
    assert quote_in(unicodedata.normalize("NFD", "được nghỉ 12 ngày phép"), source)


def test_a_fabricated_quote_is_not_found():
    assert not quote_in("được nghỉ 20 ngày phép", "Nhân viên được nghỉ 12 ngày phép mỗi năm.")


def test_empty_quote_is_never_found():
    assert not quote_in("   ", "anything")


def test_title_normalisation_casefolds():
    assert normalise_title("  Annual   LEAVE ") == "annual leave"
    assert normalise_for_match("  Annual   LEAVE ") == "Annual LEAVE"


def test_tokenise_keeps_vietnamese_words():
    assert tokenise("Nghỉ phép năm") == ["nghỉ", "phép", "năm"]


def test_tokenise_makes_hangul_bigrams():
    assert tokenise("연차 휴가") == ["연차", "휴가"]
    assert tokenise("연차휴가") == ["연차", "차휴", "휴가"]
    assert tokenise("휴") == ["휴"]


def test_guess_language():
    assert guess_language("연차 휴가는 며칠입니까") == "ko"
    assert guess_language("Tôi được nghỉ bao nhiêu ngày?") == "vi"
    assert guess_language("How many days of leave?") == "en"


def test_keyword_scores_are_normalised_and_rank_matches_first():
    docs = [tokenise("annual leave policy"), tokenise("kubernetes cluster"), tokenise("leave")]
    scores = keyword_scores(tokenise("annual leave"), docs)
    assert max(scores) == 1.0
    assert scores[1] == 0.0
    assert scores[0] > scores[2] > 0


def test_keyword_scores_with_no_match_are_all_zero():
    assert keyword_scores(tokenise("zzz"), [tokenise("abc")]) == [0.0]


def test_vectors_roundtrip_and_cosine():
    import numpy as np

    from app.brain.vectors import cosine_matrix, decode, encode

    v = decode(encode([1.0, 0.0]))
    assert v.dtype == np.dtype("<f4")
    m = np.array([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]], dtype="<f4")
    assert np.allclose(cosine_matrix(v, m), [1.0, 0.0, 0.0])
    assert cosine_matrix(v, np.zeros((0, 2), dtype="<f4")).size == 0
