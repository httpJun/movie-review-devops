import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import labels


@pytest.fixture
def clusters():
    return [
        {"topic": "연기", "sentiment": "positive", "phrases": ["연기가 좋아요"]},
        {"topic": "스토리", "sentiment": "negative", "phrases": ["지루해요"]},
    ]


@pytest.fixture(autouse=True)
def no_live_client(monkeypatch):
    # Fail closed: tests must never use a developer's API key or the network.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(labels, "_client", None)
    monkeypatch.setattr(labels, "_client_init_failed", False)
    monkeypatch.setattr(labels, "OpenAI", Mock(side_effect=AssertionError("Live API forbidden")))


def fake_client(monkeypatch, content=None, error=None):
    create = Mock(side_effect=error) if error else Mock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    ))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(labels, "_get_client", lambda: client)
    return create


def test_empty_clusters_do_not_call_api(monkeypatch):
    get_client = Mock(side_effect=AssertionError("No API needed"))
    monkeypatch.setattr(labels, "_get_client", get_client)
    assert labels.generate_top_opinion_labels([], {"results": []}) == []
    get_client.assert_not_called()


def test_missing_api_key_uses_fallback(clusters, caplog):
    assert labels.generate_top_opinion_labels(clusters, {"results": []}) == [
        "연기가 좋아요", "스토리가 아쉬워요",
    ]
    assert "폴백" in caplog.text


def test_labels_are_returned_in_cluster_order(monkeypatch, clusters):
    create = fake_client(monkeypatch, json.dumps({"labels": [
        {"index": 1, "label": "  후반부가 지루해요  "},
        {"index": 0, "label": "배우의 표정 연기가 좋아요"},
    ]}))
    assert labels.generate_top_opinion_labels(clusters, {"results": []}) == [
        "배우의 표정 연기가 좋아요", "후반부가 지루해요",
    ]
    create.assert_called_once()


@pytest.mark.parametrize("content", ["invalid-json", '{"labels": null}', '{"labels": [{"index": "oops"}]}'])
def test_malformed_response_falls_back(monkeypatch, clusters, content):
    fake_client(monkeypatch, content)
    assert labels.generate_top_opinion_labels(clusters, {"results": []}) == [
        "연기가 좋아요", "스토리가 아쉬워요",
    ]


def test_api_failure_falls_back(monkeypatch, clusters):
    fake_client(monkeypatch, error=TimeoutError("API timeout"))
    assert labels.generate_top_opinion_labels(clusters, {"results": []}) == [
        "연기가 좋아요", "스토리가 아쉬워요",
    ]


@pytest.mark.parametrize("rows", [[], [{"index": 1, "label": " "}], [{"index": 99, "label": "unknown"}]])
def test_missing_or_blank_label_falls_back_per_item(monkeypatch, clusters, rows):
    fake_client(monkeypatch, json.dumps({"labels": [{"index": 0, "label": "자연스러운 연기"}] + rows}))
    assert labels.generate_top_opinion_labels(clusters, {"results": []}) == [
        "자연스러운 연기", "스토리가 아쉬워요",
    ]


def test_representative_phrases_rank_by_frequency_and_exclude_other_clusters():
    cluster = {"phrases": ["rare", "frequent", "unseen"]}
    result = {"results": [{"phrases": [{"text": t} for t in
        ["other", "rare", "frequent", "frequent"]]}]}
    assert labels._representative_phrases(cluster, result, 2) == ["frequent", "rare"]
    assert labels._representative_phrases(cluster, result, 3) == ["frequent", "rare", "unseen"]


def test_unknown_topic_preserved_in_fallback():
    assert labels.make_label("새로운 주제", "positive") == "새로운 주제 (positive)"
