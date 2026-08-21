from __future__ import annotations

from app.agent.evidence import evidence_summary_text, extract_evidence_items, merge_evidence_items


def _result(entries):
    return {"query": "q", "results": entries}


def test_extract_evidence_items_pulls_well_formed_entries() -> None:
    result = _result(
        [
            {
                "chunk_id": "doc::chunk-0",
                "document_id": "doc",
                "title": "Title",
                "source": "source.md",
                "text": "some text",
                "score": 0.42,
            }
        ]
    )
    items = extract_evidence_items(result)
    assert len(items) == 1
    assert items[0]["chunk_id"] == "doc::chunk-0"
    assert items[0]["score"] == 0.42


def test_extract_evidence_items_skips_malformed_entries() -> None:
    result = _result(
        [
            {"chunk_id": "good::0", "document_id": "d", "title": "t", "source": "s", "text": "x", "score": 0.5},
            {"chunk_id": "bad::0"},  # missing required fields
        ]
    )
    items = extract_evidence_items(result)
    assert len(items) == 1
    assert items[0]["chunk_id"] == "good::0"


def test_extract_evidence_items_handles_empty_results() -> None:
    assert extract_evidence_items(_result([])) == []
    assert extract_evidence_items({}) == []


def _item(chunk_id, score, document_id="d1"):
    return {"chunk_id": chunk_id, "document_id": document_id, "title": "t", "source": "s", "text": "x", "score": score}


def test_merge_evidence_items_deduplicates_by_chunk_id() -> None:
    existing = [_item("c1", 0.5)]
    new = [_item("c1", 0.3)]  # same chunk, lower score
    merged = merge_evidence_items(existing, new)
    assert len(merged) == 1
    assert merged[0]["score"] == 0.5  # higher score kept


def test_merge_evidence_items_updates_when_new_score_is_higher() -> None:
    existing = [_item("c1", 0.3)]
    new = [_item("c1", 0.8)]
    merged = merge_evidence_items(existing, new)
    assert merged[0]["score"] == 0.8


def test_merge_evidence_items_accumulates_distinct_chunks() -> None:
    existing = [_item("c1", 0.5)]
    new = [_item("c2", 0.3)]
    merged = merge_evidence_items(existing, new)
    assert {m["chunk_id"] for m in merged} == {"c1", "c2"}


def test_merge_evidence_items_sorted_by_score_descending() -> None:
    existing = [_item("c1", 0.2)]
    new = [_item("c2", 0.9), _item("c3", 0.5)]
    merged = merge_evidence_items(existing, new)
    assert [m["chunk_id"] for m in merged] == ["c2", "c3", "c1"]


def test_evidence_summary_text_empty() -> None:
    assert "No evidence" in evidence_summary_text([])


def test_evidence_summary_text_counts_distinct_documents() -> None:
    items = [_item("c1", 0.5, document_id="docA"), _item("c2", 0.4, document_id="docA"), _item("c3", 0.3, document_id="docB")]
    text = evidence_summary_text(items)
    assert "2 document(s)" in text
    assert "docA" not in text  # document_id itself isn't printed, title is
    assert "c1" in text and "c2" in text and "c3" in text


def test_evidence_summary_text_truncates_long_snippets() -> None:
    items = [{"chunk_id": "c1", "document_id": "d", "title": "t", "source": "s", "text": "x" * 500, "score": 0.5}]
    text = evidence_summary_text(items, snippet_chars=50)
    assert "x" * 51 not in text
    assert "x" * 50 in text
