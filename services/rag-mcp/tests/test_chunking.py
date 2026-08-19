from __future__ import annotations

import pytest

from app.chunking import chunk_text


def test_empty_text_returns_no_chunks() -> None:
    assert chunk_text("", document_id="doc1") == []
    assert chunk_text("   \n\n  ", document_id="doc1") == []


def test_short_text_returns_single_chunk() -> None:
    chunks = chunk_text("This is a short document. It has two sentences.", document_id="doc1")
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "doc1::chunk-0"
    assert chunks[0].document_id == "doc1"
    assert chunks[0].chunk_index == 0
    assert "short document" in chunks[0].text


def test_long_text_splits_into_multiple_chunks_within_max_chars() -> None:
    sentence = "The payment gateway experienced a timeout under high load. "
    text = sentence * 40  # comfortably longer than max_chars
    chunks = chunk_text(text, document_id="doc1", max_chars=200, overlap_chars=40)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 200 + 1  # small slack for boundary rounding


def test_chunk_indices_are_sequential() -> None:
    sentence = "Service X returned a 500 error during checkout. "
    text = sentence * 30
    chunks = chunk_text(text, document_id="doc9", max_chars=150, overlap_chars=30)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert all(c.chunk_id == f"doc9::chunk-{c.chunk_index}" for c in chunks)


def test_overlap_carries_context_into_next_chunk() -> None:
    sentence = "Root cause was a misconfigured connection pool limit. "
    text = sentence * 30
    chunks = chunk_text(text, document_id="doc1", max_chars=200, overlap_chars=50)

    assert len(chunks) > 1
    # The tail of chunk N should reappear at the start of chunk N+1.
    tail_of_first = chunks[0].text[-30:]
    assert tail_of_first[:15] in chunks[1].text


def test_single_oversized_sentence_is_hard_split() -> None:
    huge_sentence = "word " * 500 + "."  # one giant "sentence", no punctuation breaks
    chunks = chunk_text(huge_sentence, document_id="doc1", max_chars=300, overlap_chars=50)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 300 + 1


def test_paragraph_boundaries_are_respected_as_sentence_sources() -> None:
    text = "First paragraph sentence one. First paragraph sentence two.\n\nSecond paragraph starts here."
    chunks = chunk_text(text, document_id="doc1", max_chars=1000)
    assert len(chunks) == 1
    assert "Second paragraph" in chunks[0].text


@pytest.mark.parametrize(
    "max_chars,overlap_chars",
    [
        (0, 10),
        (-5, 10),
        (100, -1),
        (100, 100),
        (100, 150),
    ],
)
def test_invalid_parameters_raise_value_error(max_chars: int, overlap_chars: int) -> None:
    with pytest.raises(ValueError):
        chunk_text("Some text.", document_id="doc1", max_chars=max_chars, overlap_chars=overlap_chars)
