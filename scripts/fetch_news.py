#!/usr/bin/env python3
"""
AI 트렌드 뉴스 수집 스크립트
RSS 피드 → HN API 순서로 수집 후 JSON 배열 출력
"""

import feedparser
from datetime import datetime, timezone, timedelta
import calendar
import requests


def fetch_rss(feed_url: str) -> list[dict]:
    """
    RSS 피드에서 최근 24시간 이내 기사를 수집한다.
    Returns: [{"title": str, "url": str, "summary": str}, ...]
    """
    try:
        feed = feedparser.parse(feed_url)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        results = []
        for entry in feed.entries:
            if not hasattr(entry, 'published_parsed') or entry.published_parsed is None:
                continue
            pub_dt = datetime.fromtimestamp(
                calendar.timegm(entry.published_parsed), tz=timezone.utc
            )
            if pub_dt < cutoff:
                continue
            results.append({
                "title": entry.title,
                "url": entry.link,
                "summary": getattr(entry, 'summary', entry.title),
            })
        return results
    except Exception:
        return []


HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
HN_FETCH_COUNT = 30

AI_KEYWORDS = [
    "ai", "llm", "gpt", "openai", "anthropic", "gemini",
    "machine learning", "deep learning", "neural", "transformer",
    "diffusion", "claude", "mistral", "artificial intelligence",
]


def fetch_hn() -> list[dict]:
    """
    Hacker News Top Stories에서 AI 관련 기사를 수집한다.
    Returns: [{"title": str, "url": str, "summary": str}, ...]
    """
    try:
        resp = requests.get(HN_TOP_URL, timeout=10)
        resp.raise_for_status()
        top_ids = resp.json()[:HN_FETCH_COUNT]

        results = []
        for item_id in top_ids:
            try:
                item_resp = requests.get(HN_ITEM_URL.format(item_id), timeout=10)
                item_resp.raise_for_status()
                item = item_resp.json()
                if item.get("type") != "story":
                    continue
                title = item.get("title", "")
                url = item.get("url", f"https://news.ycombinator.com/item?id={item_id}")
                if any(kw in title.lower() for kw in AI_KEYWORDS):
                    results.append({
                        "title": title,
                        "url": url,
                        "summary": title,
                    })
            except Exception:
                continue
        return results
    except requests.RequestException:
        return []


RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "https://venturebeat.com/category/ai/feed/",
]


def fetch_news(posted_urls: list[str] = None) -> list[dict]:
    """
    AI 뉴스 후보 배열을 반환한다. RSS 우선, 실패 시 HN fallback.
    posted_urls에 있는 URL은 제외된다.
    Returns: [{"title": str, "url": str, "summary": str}, ...]
    """
    if posted_urls is None:
        posted_urls = []

    # 1순위: RSS 피드 (하나라도 결과 있으면 사용)
    for feed_url in RSS_FEEDS:
        items = fetch_rss(feed_url)
        if items:
            return [i for i in items if i["url"] not in posted_urls]

    # 2순위: HN fallback
    items = fetch_hn()
    return [i for i in items if i["url"] not in posted_urls]


if __name__ == "__main__":
    import json as _json
    import sys as _sys

    posted = _sys.argv[1:]  # optional: posted URLs as args
    results = fetch_news(posted_urls=posted)
    print(_json.dumps(results, ensure_ascii=False, indent=2))
