---
name: chloe-threads-daily
description: >
  매일 AI 트렌드 뉴스를 수집하여 Threads에 게시합니다.
  HEARTBEAT에서 자동 호출됩니다. 수동 실행 시 "chloe-threads-daily 스킬 실행해줘"
version: 1.0.0
metadata:
  openclaw:
    requires:
      env:
        - THREADS_ACCESS_TOKEN
        - THREADS_USER_ID
      bins:
        - python3
    primaryEnv: THREADS_ACCESS_TOKEN
---

# Chloe Threads Daily Post Skill

매일 AI 트렌드 뉴스를 Threads에 게시하는 자율 스킬입니다.

## 실행 단계

### 1. state.json 확인

`~/.openclaw/workspace/my-skills/chloe-threads-daily/scripts/state.json`이 존재하면 읽는다.
없으면 미게시로 간주하고 3단계로 진행.

파일이 있으면:
- `last_posted`가 오늘 날짜(KST)이고 `skipped`가 false이면 → 종료 (오늘 이미 포스팅 완료)
- 그 외(skipped: true 또는 날짜 다름) → 3단계로 진행

### 2. 뉴스 수집

다음 명령어로 뉴스 후보 배열을 가져온다:

    python3 ~/.openclaw/workspace/my-skills/chloe-threads-daily/scripts/fetch_news.py

결과가 빈 배열 `[]`이면, 다음 Python 코드로 state.json에 skipped 기록 후 종료:

    import json, os, pytz
    from datetime import datetime
    state_path = os.path.expanduser("~/.openclaw/workspace/my-skills/chloe-threads-daily/scripts/state.json")
    try:
        with open(state_path) as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {}
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.now(kst).strftime("%Y-%m-%d")
    state.update({"last_posted": today, "post_id": None, "skipped": True,
                  "posted_urls": state.get("posted_urls", [])})
    with open(state_path, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

### 3. 포스팅 후보 선택

fetch_news.py 결과 배열에서 state.json의 `posted_urls`에 없는 첫 번째 항목을 선택한다.
없으면 2단계 실패와 동일하게 skipped: true 기록 후 종료.

### 4. 포스팅 텍스트 생성 (인라인)

선택된 뉴스의 title, url을 사용해 직접 아래 포맷으로 텍스트를 작성한다:

    [한국어 한줄 요약, 트렌디하고 Gen-Z 말투] ✨

    [영어 원제목]
    🔗 [선택된 뉴스의 url]

    #AI #AITrends #인공지능 #테크뉴스

엄수 사항:
- 전체 텍스트 500자 이하 (한국어 요약은 80자 이내 권장)
- 500자 초과 시 한국어 요약을 줄여 재생성 (URL/해시태그는 고정)
- Chloe 페르소나 반영: 트렌디, 재치있음, 참여 유도

### 5. Threads 게시

4단계에서 생성한 텍스트를 변수 `post_text`에 담아 다음 Python 코드로 게시한다:

    import subprocess, os, re
    result = subprocess.run(
        ["python3", os.path.expanduser("~/.openclaw/workspace/my-skills/threads-post/scripts/post.py")],
        input=post_text,
        capture_output=True, text=True,
        env={**os.environ}
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        if "코드 190" in result.stderr or "code 190" in result.stderr.lower():
            raise SystemExit("Threads 토큰 만료. Discord #office에 갱신 요청 메시지 전송 필요.")
        raise SystemExit("Threads 게시 실패. 다음 heartbeat에 재시도.")

    # stdout에서 Post ID 추출 (예: "   Post ID: 18047234567890123")
    match = re.search(r"Post ID:\s*(\d+)", result.stdout)
    post_id = match.group(1) if match else None

게시 실패(코드 190 외) 시 → state.json 업데이트 없이 종료 (다음 heartbeat 재시도).

### 6. state.json 업데이트

선택한 뉴스의 url을 `selected_url`, 5단계에서 추출한 post_id를 `post_id` 변수에 담아
다음 Python 코드로 state.json을 업데이트한다:

    import json, os, pytz
    from datetime import datetime
    state_path = os.path.expanduser("~/.openclaw/workspace/my-skills/chloe-threads-daily/scripts/state.json")
    try:
        with open(state_path) as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {}
    posted_urls = state.get("posted_urls", [])
    posted_urls.append(selected_url)
    if len(posted_urls) > 30:
        posted_urls = posted_urls[-30:]
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.now(kst).strftime("%Y-%m-%d")
    state.update({
        "last_posted": today,
        "post_id": post_id,
        "skipped": False,
        "posted_urls": posted_urls,
    })
    with open(state_path, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

## 오류 참고

| 오류 | 처리 |
|------|------|
| fetch_news.py 빈 배열 | skipped: true 기록 후 종료 |
| Threads API 코드 190 | Discord #office 알림 후 종료 |
| 기타 Threads 오류 | state.json 미업데이트, 다음 heartbeat 재시도 |
