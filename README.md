# 말과 글 수첩 — 국어 5-2

초등 5학년 2학기 국어 차시별 복습 사이트. 사회 '역사 탐정 수첩'과 같은 구조.

## 배포 (GitHub Pages)

1. GitHub에서 새 저장소를 만든다 (Public).
2. 이 폴더의 파일을 전부 업로드한다. (폴더 구조 그대로)
3. 저장소 → Settings → Pages → Source를 `Deploy from a branch`, 브랜치 `main` / `/ (root)` 로 설정.
4. 1~2분 뒤 `https://<계정명>.github.io/<저장소명>/` 에서 열린다.

## 구조

```
index.html        홈 (진행률, 이어서 하기)
unit1.html        1단원 차시 목록
teacher.html      선생님용 안내
lesson/1.html     1차시 인상적인 부분이란
lesson/2-3.html   2~3차시 말에도 색깔이 있지
assets/style.css  공통 디자인
assets/app.js     진도 저장, 퀴즈 동작
```

## 차시 추가하기

1. `lesson/`에 파일을 넣는다 (기존 파일을 복사해 내용만 교체).
2. `unit1.html`의 잠긴 항목(`<div class="item" style="opacity:.45">`)을
   `<a class="item" data-slug="4-6" href="lesson/4-6.html">`로 바꾼다.
3. `index.html`의 `SEQ` 배열에 한 줄 추가한다. (진행률 계산용)
4. 페이지 맨 아래 `initQuiz("슬러그", 문항수)`의 문항 수를 맞춘다.

## 저장 방식

`localStorage` 키 `gugeo52-v1`에 `{done, wrong, last}` 저장.
서버 전송 없음. 개인정보 수집 없음. 사회 사이트(`sahoe52-v1`)와 키가 달라 서로 간섭하지 않는다.
