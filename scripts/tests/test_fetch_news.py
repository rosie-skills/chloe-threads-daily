import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import pytest
from fetch_news import fetch_rss


def make_entry(title, url, published_offset_hours=1):
    """published_offset_hours: 현재로부터 몇 시간 전인지"""
    entry = MagicMock()
    entry.title = title
    entry.link = url
    entry.summary = "Test summary"
    pub_time = datetime.now(timezone.utc) - timedelta(hours=published_offset_hours)
    entry.published_parsed = pub_time.timetuple()
    return entry


def test_fetch_rss_returns_recent_items():
    """24시간 이내 기사를 반환한다"""
    feed = MagicMock()
    feed.entries = [
        make_entry("AI News Today", "https://example.com/ai-news", published_offset_hours=2),
    ]
    with patch("feedparser.parse", return_value=feed):
        result = fetch_rss("https://example.com/feed")
    assert len(result) == 1
    assert result[0]["title"] == "AI News Today"
    assert result[0]["url"] == "https://example.com/ai-news"
    assert "summary" in result[0]


def test_fetch_rss_excludes_old_items():
    """25시간 이상 된 기사는 제외한다"""
    feed = MagicMock()
    feed.entries = [
        make_entry("Old News", "https://example.com/old", published_offset_hours=25),
    ]
    with patch("feedparser.parse", return_value=feed):
        result = fetch_rss("https://example.com/feed")
    assert result == []


def test_fetch_rss_returns_empty_on_network_error():
    """네트워크 오류 시 빈 리스트 반환 (예외 전파 안 함)"""
    with patch("feedparser.parse", side_effect=Exception("network error")):
        result = fetch_rss("https://example.com/feed")
    assert result == []


import requests
from fetch_news import fetch_hn

def test_fetch_hn_returns_ai_items():
    """AI 관련 기사만 필터링해 반환한다"""
    top_ids = [1, 2, 3]
    stories = {
        1: {"id": 1, "title": "OpenAI releases new model", "url": "https://news.ycombinator.com/1", "type": "story"},
        2: {"id": 2, "title": "Python tips for beginners", "url": "https://example.com/python", "type": "story"},
        3: {"id": 3, "title": "LLM benchmark results 2025", "url": "https://example.com/llm", "type": "story"},
    }

    def mock_get(url, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if "topstories" in url:
            resp.json.return_value = top_ids
        else:
            item_id = int(url.split("/")[-1].replace(".json", ""))
            resp.json.return_value = stories[item_id]
        return resp

    with patch("requests.get", side_effect=mock_get):
        result = fetch_hn()

    titles = [r["title"] for r in result]
    assert "OpenAI releases new model" in titles
    assert "LLM benchmark results 2025" in titles
    assert "Python tips for beginners" not in titles


def test_fetch_hn_returns_empty_on_error():
    """HN API 오류 시 빈 리스트 반환"""
    with patch("requests.get", side_effect=requests.RequestException("timeout")):
        result = fetch_hn()
    assert result == []


from fetch_news import fetch_news

RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "https://venturebeat.com/category/ai/feed/",
]


def test_fetch_news_uses_rss_first():
    """RSS에 결과가 있으면 HN을 호출하지 않는다"""
    rss_items = [{"title": "RSS AI News", "url": "https://rss.com/1", "summary": "s"}]
    with patch("fetch_news.fetch_rss", return_value=rss_items) as mock_rss, \
         patch("fetch_news.fetch_hn") as mock_hn:
        result = fetch_news(posted_urls=[])
    assert mock_rss.called
    assert not mock_hn.called
    assert result == rss_items


def test_fetch_news_falls_back_to_hn_when_rss_empty():
    """모든 RSS 피드가 빈 결과면 HN을 시도한다"""
    hn_items = [{"title": "HN AI News", "url": "https://hn.com/1", "summary": "s"}]
    with patch("fetch_news.fetch_rss", return_value=[]), \
         patch("fetch_news.fetch_hn", return_value=hn_items):
        result = fetch_news(posted_urls=[])
    assert result == hn_items


def test_fetch_news_returns_empty_when_all_fail():
    """RSS와 HN 모두 빈 결과면 빈 배열 반환"""
    with patch("fetch_news.fetch_rss", return_value=[]), \
         patch("fetch_news.fetch_hn", return_value=[]):
        result = fetch_news(posted_urls=[])
    assert result == []


def test_fetch_news_excludes_posted_urls():
    """이미 posted_urls에 있는 URL은 결과에서 제외된다"""
    rss_items = [
        {"title": "Old News", "url": "https://example.com/old", "summary": "s"},
        {"title": "New News", "url": "https://example.com/new", "summary": "s"},
    ]
    with patch("fetch_news.fetch_rss", return_value=rss_items), \
         patch("fetch_news.fetch_hn", return_value=[]):
        result = fetch_news(posted_urls=["https://example.com/old"])
    urls = [r["url"] for r in result]
    assert "https://example.com/old" not in urls
    assert "https://example.com/new" in urls
