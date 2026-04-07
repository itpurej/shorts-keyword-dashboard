"""
YouTube Shorts 생활용품 카테고리 키워드 Top 100 수집기
매일 GitHub Actions에서 실행됨
"""

import os
import json
import requests
from datetime import datetime, timezone
from collections import defaultdict

API_KEY = os.environ["YT_API_KEY"]
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# 생활용품 시드 키워드 (자동완성으로 확장)
SEED_KEYWORDS = [
    "생활용품", "주방용품", "청소용품", "욕실용품", "수납용품",
    "주방도구", "청소도구", "세탁용품", "정리함", "다이소",
    "홈리빙", "인테리어소품", "주방수납", "욕실정리", "청소꿀템",
    "주방꿀템", "생활꿀템", "정리정돈", "주방살림", "살림템",
    "수납박스", "청소기", "밀대청소기", "수세미", "주방세제",
    "분리수거함", "휴지통", "빨래건조대", "옷걸이", "행거",
]

def get_autocomplete_keywords(seed: str) -> list[str]:
    """YouTube 검색 자동완성으로 키워드 확장"""
    url = "https://suggestqueries.google.com/complete/search"
    params = {
        "client": "youtube",
        "ds": "yt",
        "q": seed,
        "hl": "ko",
    }
    try:
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        suggestions = [item[0] for item in data[1]]
        return suggestions[:10]
    except Exception:
        return []


def search_shorts(keyword: str) -> dict:
    """YouTube Data API로 해당 키워드 쇼츠 검색 결과 가져오기"""
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key": API_KEY,
        "q": keyword + " #shorts",
        "part": "snippet",
        "type": "video",
        "videoDuration": "short",
        "maxResults": 10,
        "order": "relevance",
        "relevanceLanguage": "ko",
        "regionCode": "KR",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        items = data.get("items", [])
        video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
        return {"video_ids": video_ids, "result_count": len(video_ids)}
    except Exception:
        return {"video_ids": [], "result_count": 0}


def get_video_stats(video_ids: list[str]) -> dict:
    """영상 ID 목록으로 조회수 합계 가져오기"""
    if not video_ids:
        return {"total_views": 0, "avg_views": 0}
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "key": API_KEY,
        "id": ",".join(video_ids),
        "part": "statistics",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        views = []
        for item in data.get("items", []):
            v = int(item.get("statistics", {}).get("viewCount", 0))
            views.append(v)
        total = sum(views)
        avg = total // len(views) if views else 0
        return {"total_views": total, "avg_views": avg}
    except Exception:
        return {"total_views": 0, "avg_views": 0}


def score(result_count: int, total_views: int, avg_views: int) -> float:
    """인기도 점수 계산 (영상 수 + 조회수 가중 합산)"""
    return result_count * 1000 + total_views * 0.001 + avg_views * 0.01


def main():
    print(f"[{TODAY}] 키워드 수집 시작")

    # 1) 자동완성으로 키워드 확장
    all_keywords = set(SEED_KEYWORDS)
    for seed in SEED_KEYWORDS:
        expanded = get_autocomplete_keywords(seed)
        all_keywords.update(expanded)
        print(f"  자동완성 '{seed}' → {len(expanded)}개 추가")

    all_keywords = list(all_keywords)
    print(f"총 확장 키워드: {len(all_keywords)}개")

    # 2) 각 키워드 점수 계산
    results = []
    for i, kw in enumerate(all_keywords):
        sr = search_shorts(kw)
        stats = get_video_stats(sr["video_ids"])
        s = score(sr["result_count"], stats["total_views"], stats["avg_views"])
        results.append({
            "rank": 0,
            "keyword": kw,
            "score": round(s, 1),
            "video_count": sr["result_count"],
            "total_views": stats["total_views"],
            "avg_views": stats["avg_views"],
        })
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(all_keywords)} 처리 완료")

    # 3) 점수 기준 정렬 → Top 100
    results.sort(key=lambda x: x["score"], reverse=True)
    top100 = results[:100]
    for i, item in enumerate(top100):
        item["rank"] = i + 1

    # 4) 저장
    output = {
        "date": TODAY,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "keywords": top100,
    }

    os.makedirs("docs/data", exist_ok=True)

    with open(f"docs/data/{TODAY}.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    with open("docs/data/latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: docs/data/{TODAY}.json")
    print(f"Top 3: {[x['keyword'] for x in top100[:3]]}")


if __name__ == "__main__":
    main()
