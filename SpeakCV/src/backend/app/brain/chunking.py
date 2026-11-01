from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    position: int
    page: int | None
    text: str


def _is_heading(paragraph: str) -> bool:
    if "\n" in paragraph:
        return False
    return paragraph.startswith("#") or (len(paragraph) <= 60 and paragraph.isupper())


def chunk_pages(pages, target: int = 1200, overlap: int = 150) -> list[Chunk]:
    chunks: list[Chunk] = []

    for page, text in pages:
        paragraphs = [p.strip() for p in (text or "").replace("\r\n", "\n").split("\n\n")]
        paragraphs = [p for p in paragraphs if p]
        buf = ""  # overlap prefix plus fresh content
        fresh = 0  # characters added since the last flush, separators included

        def emit(body: str) -> None:
            chunks.append(Chunk(position=len(chunks), page=page, text=body))

        def flush() -> None:
            nonlocal buf, fresh
            if fresh <= 0:
                return
            emit(buf)
            buf = buf[-overlap:] if overlap else ""
            fresh = 0

        for paragraph in paragraphs:
            if _is_heading(paragraph) and fresh > target / 2:
                flush()
            if len(paragraph) > target:
                full = (buf + "\n\n" + paragraph) if buf else paragraph
                buf, fresh = "", 0
                step = target
                windows = []
                start = 0
                while True:
                    windows.append(full[start:start + target + overlap])
                    start += step
                    if start + overlap >= len(full):
                        break
                for window in windows[:-1]:
                    emit(window)
                buf = windows[-1]
                fresh = len(buf)
                continue
            separator = 2 if buf else 0
            if fresh > 0 and fresh + separator + len(paragraph) > target:
                flush()
                separator = 2 if buf else 0
            buf = buf + "\n\n" + paragraph if buf else paragraph
            fresh += separator + len(paragraph)
        flush()
    return chunks
