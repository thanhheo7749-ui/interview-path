from app.brain.chunking import chunk_pages

TARGET, OVERLAP = 1200, 150


def _paras(n, size=300, tag="p"):
    return [f"{tag}{i} " + ("x" * size) for i in range(n)]


def test_positions_sequential_and_pages_kept():
    pages = [(1, "\n\n".join(_paras(6, tag="a"))), (2, "\n\n".join(_paras(6, tag="b")))]
    chunks = chunk_pages(pages)
    assert [c.position for c in chunks] == list(range(len(chunks)))
    assert {c.page for c in chunks} == {1, 2}
    assert chunks[0].page == 1


def test_no_chunk_exceeds_limit():
    chunks = chunk_pages([(1, "\n\n".join(_paras(30)))])
    assert len(chunks) > 1
    assert all(len(c.text) <= TARGET + OVERLAP for c in chunks)


def test_oversized_paragraph_is_split_by_characters():
    chunks = chunk_pages([(1, "y" * 5000)])
    assert len(chunks) >= 4
    assert all(len(c.text) <= TARGET + OVERLAP for c in chunks)
    assert "".join(c.text for c in chunks).count("y") >= 5000


def test_heading_starts_new_chunk_when_buffer_over_half():
    text = "\n\n".join(_paras(3, 300) + ["# Heading", "after heading body"])
    chunks = chunk_pages([(1, text)])
    assert len(chunks) == 2
    assert "# Heading" in chunks[1].text
    assert "# Heading" not in chunks[0].text


def test_heading_does_not_flush_small_buffer():
    chunks = chunk_pages([(1, "intro\n\n# Heading\n\nbody")])
    assert len(chunks) == 1


def test_consecutive_chunks_overlap():
    chunks = chunk_pages([(1, "\n\n".join(_paras(12)))])
    assert len(chunks) > 1
    for a, b in zip(chunks, chunks[1:]):
        assert b.text.startswith(a.text[-OVERLAP:])


def test_empty_pages_yield_nothing():
    assert chunk_pages([(1, ""), (2, "  \n\n ")]) == []


def test_every_paragraph_is_covered():
    paras = _paras(25)
    chunks = chunk_pages([(1, "\n\n".join(paras))])
    joined = "\n".join(c.text for c in chunks)
    assert all(p in joined for p in paras)
