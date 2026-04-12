"""
YouTube Shorts 생활용품 카테고리 키워드 Top 100 수집기
+ 네이버 데이터랩 검색 트렌드 연동
매일 GitHub Actions에서 실행됨
"""

import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta

API_KEY = os.environ["YT_API_KEY"]
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# 생활용품 시드 키워드 (자동완성으로 확장)
SEED_KEYWORDS = [
    # 기본 카테고리
    "생활용품", "주방용품", "청소용품", "욕실용품", "수납용품",
    "주방도구", "청소도구", "세탁용품", "정리함", "다이소",
    "홈리빙", "인테리어소품", "주방수납", "욕실정리", "청소꿀템",
    "주방꿀템", "생활꿀템", "정리정돈", "주방살림", "살림템",
    "수납박스", "청소기", "밀대청소기", "수세미", "주방세제",
    "분리수거함", "휴지통", "빨래건조대", "옷걸이", "행거",
    # 트렌드 키워드
    "다이소신상", "다이소추천", "살림꿀팁", "주방정리", "냉장고정리",
    "싱크대정리", "욕실소품", "세면대정리", "화장실청소", "주방청소",
    "집청소", "대청소", "청소방법", "청소꿀팁", "정리수납",
    "옷정리", "신발정리", "현관정리", "베란다정리", "다용도실정리",
    "주방인테리어", "욕실인테리어", "수납인테리어", "홈인테리어", "미니멀라이프",
    "살림노하우", "주부꿀팁", "집꾸미기", "소품샵", "생활소품",
    # 제품 카테고리
    "주방가전", "소형가전", "청소기추천", "공기청정기", "제습기",
    "식기세척기", "음식물처리기", "쓰레기통", "세탁기", "건조기",
    "냄비추천", "프라이팬추천", "칼추천", "도마추천", "그릇추천",
]


# ── YouTube ──────────────────────────────────────────────

def get_autocomplete_keywords(seed: str) -> list[str]:
    """YouTube 검색 자동완성으로 키워드 확장"""
    url = "https://suggestqueries.google.com/complete/search"
    params = {"client": "youtube", "ds": "yt", "q": seed, "hl": "ko"}
    try:
        resp = requests.get(url, params=params, timeout=8)
        text = resp.text
        if text.startswith("window.google"):
            import re
            text = re.search(r'\((.+)\)', text).group(1)
        data = json.loads(text)
        return [item[0] for item in data[1] if isinstance(item, list)][:10]
    except Exception:
        return []


def search_shorts(keyword: str) -> dict:
    """YouTube Data API로 해당 키워드 쇼츠 검색"""
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
    """영상 ID 목록으로 조회수 가져오기"""
    if not video_ids:
        return {"total_views": 0, "avg_views": 0}
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"key": API_KEY, "id": ",".join(video_ids), "part": "statistics"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        views = [int(item.get("statistics", {}).get("viewCount", 0)) for item in data.get("items", [])]
        total = sum(views)
        avg = total // len(views) if views else 0
        return {"total_views": total, "avg_views": avg}
    except Exception:
        return {"total_views": 0, "avg_views": 0}


# ── 네이버 데이터랩 ──────────────────────────────────────

def get_naver_trends(keywords: list[str]) -> dict[str, float]:
    """네이버 검색 트렌드 점수 가져오기 (0~100)"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return {}

    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%d")

    scores = {}
    # 한 번에 최대 5개 키워드 그룹
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i+5]
        keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in batch]
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "timeUnit": "month",
            "keywordGroups": keyword_groups,
        }
        try:
            resp = requests.post(
                "https://openapi.naver.com/v1/datalab/search",
                headers={
                    "X-Naver-Client-Id": NAVER_CLIENT_ID,
                    "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=10,
            )
            data = resp.json()
            for result in data.get("results", []):
                kw_name = result["title"]
                data_points = result.get("data", [])
                if data_points:
                    avg = sum(d["ratio"] for d in data_points) / len(data_points)
                    scores[kw_name] = round(avg, 1)
        except Exception as e:
            print(f"  네이버 API 오류 (배치 {i//5+1}): {e}")
        time.sleep(0.3)

    return scores


# ── 점수 계산 ──────────────────────────────────────────

def yt_score(result_count: int, total_views: int, avg_views: int) -> float:
    """YouTube 인기도 점수"""
    return result_count * 1000 + total_views * 0.001 + avg_views * 0.01


def blue_ocean_score(video_count: int, avg_views: int) -> float:
    """블루오션 지수: 영상 수 적고 평균 조회수 높을수록 높음"""
    if video_count == 0:
        return 0.0
    return round(avg_views / video_count, 1)


# ── 메인 ──────────────────────────────────────────────

def main():
    print(f"[{TODAY}] 키워드 수집 시작")

    # 1) 자동완성으로 키워드 확장 (YouTube API 하루 한도: 100번)
    # search.list 100 units × 80개 = 8,000 units (한도 10,000 이내)
    all_keywords = set(SEED_KEYWORDS)
    for seed in SEED_KEYWORDS[:20]:  # 시드 20개만 자동완성 확장
        expanded = get_autocomplete_keywords(seed)
        all_keywords.update(expanded)
    all_keywords = list(all_keywords)[:80]  # 최대 80개로 제한
    print(f"총 확장 키워드: {len(all_keywords)}개")

    # 2) YouTube 점수 계산
    results = []
    for i, kw in enumerate(all_keywords):
        sr = search_shorts(kw)
        stats = get_video_stats(sr["video_ids"])
        results.append({
            "keyword": kw,
            "yt_score": round(yt_score(sr["result_count"], stats["total_views"], stats["avg_views"]), 1),
            "video_count": sr["result_count"],
            "total_views": stats["total_views"],
            "avg_views": stats["avg_views"],
            "blue_ocean": blue_ocean_score(sr["result_count"], stats["avg_views"]),
            "naver_trend": 0.0,
        })
        if (i + 1) % 10 == 0:
            print(f"  YouTube {i+1}/{len(all_keywords)} 처리")

    # 3) 네이버 데이터랩 트렌드 추가
    if NAVER_CLIENT_ID:
        print("네이버 데이터랩 수집 중...")
        naver_scores = get_naver_trends([r["keyword"] for r in results])
        for r in results:
            r["naver_trend"] = naver_scores.get(r["keyword"], 0.0)
        print(f"  네이버 트렌드 {len(naver_scores)}개 수집 완료")
    else:
        print("  NAVER_CLIENT_ID 없음 → 네이버 트렌드 스킵")

    # 4) 종합 점수로 정렬 → Top 100
    for r in results:
        r["total_score"] = round(r["yt_score"] + r["naver_trend"] * 500, 1)

    results.sort(key=lambda x: x["total_score"], reverse=True)
    top100 = results[:100]
    for i, item in enumerate(top100):
        item["rank"] = i + 1

    # 5) 저장
    output = {
        "date": TODAY,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "has_naver": bool(NAVER_CLIENT_ID),
        "keywords": top100,
    }

    os.makedirs("docs/data", exist_ok=True)
    with open(f"docs/data/{TODAY}.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    with open("docs/data/latest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"저장 완료! Top 3: {[x['keyword'] for x in top100[:3]]}")


if __name__ == "__main__":
    main()
