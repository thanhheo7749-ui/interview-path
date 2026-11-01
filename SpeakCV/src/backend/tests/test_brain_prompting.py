import pytest

from app.brain.prompting import as_data


@pytest.mark.parametrize("tag", ["context", "question", "document", "fact"])
@pytest.mark.parametrize("form", ["</{}>", "<{}>", "< / {} >", "</{} >"])
def test_text_cannot_open_or_close_a_data_tag(tag, form):
    text = "before " + form.format(tag.upper()) + " after"
    assert as_data(text).startswith("before &lt;")
    assert "<" not in as_data(text)


def test_other_angle_brackets_are_left_alone():
    assert as_data("a < b and <b>bold</b>") == "a < b and <b>bold</b>"
