# -*- coding: utf-8 -*-
"""말과 글 수첩 — 차시 JSON을 정적 HTML로 빌드한다.

    python build_gugeo.py            lessons/ -> site/
    python build_gugeo.py --check    화면 텍스트에 '지도서'가 남았는지 검사

표준 라이브러리만 쓴다. 설치할 것이 없다.
스키마는 schema.md 참고.
"""

import html
import json
import pathlib
import re
import sys

# 윈도우 명령 프롬프트는 기본이 cp949라 한글 출력에서 죽는다. 먼저 막아 둔다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent
LESSONS = ROOT / "lessons"

# 빌드 결과를 어디에 쓸지. "." 이면 이 폴더에 바로 쓴다.
# GitHub Pages 저장소를 그대로 작업 폴더로 쓰기 때문에 기본값이 "." 이다.
OUTPUT = "."

SITE = (ROOT / OUTPUT).resolve()

# 학생 화면에 절대 나가면 안 되는 낱말.
# 아이는 지도서를 볼 수 없으므로 "지도서 91쪽"이 떠도 무의미하다.
FORBIDDEN = ["지도서"]

# 검사에서 빼는 파일. 선생님 안내는 독자가 교사라 지도서를 언급해도 된다.
NOT_STUDENT_FACING = {"teacher.html"}


# --------------------------------------------------------------------------
# 차시 코드 — '01', '04-06', '1-2' 를 모두 받는다
# --------------------------------------------------------------------------

def code_numbers(code):
    """'04-06' -> [4, 5, 6] / '01' -> [1] / '1-2' -> [1, 2]"""
    parts = [int(p) for p in str(code).split("-")]
    if len(parts) == 1:
        return parts
    if len(parts) != 2:
        raise ValueError("차시 코드 형식이 아닙니다: %r" % code)
    lo, hi = parts
    if hi < lo:
        raise ValueError("차시 범위가 거꾸로입니다: %r" % code)
    return list(range(lo, hi + 1))


def code_label(code):
    """'04-06' -> '4~6차시' / '01' -> '1차시'"""
    ns = code_numbers(code)
    return "%d차시" % ns[0] if len(ns) == 1 else "%d~%d차시" % (ns[0], ns[-1])


def code_sort_key(code):
    return code_numbers(code)[0]


def code_normalize(code):
    """'1-2' -> '01-02'. 파일 이름 정렬과 차시 정렬을 일치시킨다."""
    return "-".join("%02d" % int(p) for p in str(code).split("-"))


# --------------------------------------------------------------------------
# 인라인 서식 — **굵게** 하나만 허용, 나머지는 전부 이스케이프
# --------------------------------------------------------------------------

_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)


def inline(text):
    return _BOLD.sub(r"<strong>\1</strong>", html.escape(str(text)))


def lines(text):
    """줄바꿈 문자를 <br>로. 제목·안내문용."""
    return "<br>".join(inline(t) for t in str(text).split("\n"))


def comment(text):
    """HTML 주석. 교사 대조용 근거는 여기에만 남는다."""
    return "<!-- %s -->" % str(text).replace("--", "—")


# --------------------------------------------------------------------------
# 블록 렌더러 — 타입은 닫힌 집합이다
# --------------------------------------------------------------------------

CIRCLED = "①②③④⑤⑥⑦⑧⑨"


def _text(b):
    return "<p>%s</p>" % inline(b["text"])


def _list(b):
    return "<ul>%s</ul>" % "".join("<li>%s</li>" % inline(x) for x in b["items"])


def _word(b):
    out = ['<div class="word">']
    out.append('<p class="term">%s</p>' % inline(b["term"]))
    out.append('<ol class="senses">%s</ol>'
               % "".join("<li>%s</li>" % inline(s) for s in b["senses"]))
    used = b.get("used")
    if used:
        out.append('<p class="used">여기에서는 <strong>%s</strong>의 뜻으로 쓰였어요.</p>'
                   % CIRCLED[int(used) - 1])
    if b.get("note"):
        out.append("<p>%s</p>" % inline(b["note"]))
    out.append("</div>")
    return "".join(out)


def _shape(b):
    inner = "<em>＋</em>".join("<span>%s</span>" % inline(p) for p in b["parts"])
    return '<div class="shape">%s</div>' % inner


def _example(b):
    out = ['<div class="ex">']
    if b.get("tag"):
        out.append('<span class="tag">%s</span>' % inline(b["tag"]))
    out.append('<p class="q">%s</p>' % inline(b["quote"]))
    if b.get("why"):
        out.append('<p class="why">%s</p>' % inline(b["why"]))
    out.append("</div>")
    return "".join(out)


def _note(b):
    return '<p class="note">%s</p>' % inline(b["text"])


BLOCKS = {
    "text": _text,
    "list": _list,
    "word": _word,
    "shape": _shape,
    "example": _example,
    "note": _note,
}


def render_blocks(blocks, where):
    out = []
    for i, b in enumerate(blocks, 1):
        fn = BLOCKS.get(b.get("type"))
        if fn is None:
            raise SystemExit("%s 블록 %d: 알 수 없는 타입 %r (쓸 수 있는 것: %s)"
                             % (where, i, b.get("type"), ", ".join(sorted(BLOCKS))))
        try:
            out.append(fn(b))
        except KeyError as e:
            raise SystemExit("%s 블록 %d(%s): 필수 필드 %s 가 없습니다"
                             % (where, i, b.get("type"), e))
    return "\n          ".join(out)


# --------------------------------------------------------------------------
# 과제 — 전 차시 고정. 데이터가 아니라 템플릿이다.
# --------------------------------------------------------------------------

TASK = """<div class="task">
        <h3>오늘 과제</h3>
        <ol>
          <li><b>오늘 배운 것</b>을 한 줄로 써 보세요.</li>
          <li><b>친구에게 물어보고 싶은 질문</b>을 하나 만들어 보세요.
            <div class="hint">
              이런 것을 물어볼 수 있어요.
              <span>나는 이렇게 생각했는데 너는 어때?</span>
              <span>여기는 왜 이렇게 했을까?</span>
              <span>만약에 ○○였다면 어떻게 됐을까?</span>
            </div>
          </li>
          <li>그 질문에 <b>나라면 어떻게 답할지</b> 써 보세요.</li>%s
        </ol>
      </div>"""


def render_task(extra):
    return TASK % ("\n          <li>%s</li>" % inline(extra) if extra else "")


# --------------------------------------------------------------------------
# 목차
# --------------------------------------------------------------------------

def unit_nav_title(unit):
    """label이 숫자면 '1. 제목', 아니면 제목만. 독서·매체 대응."""
    label = str(unit["label"])
    return "%s. %s" % (label, unit["title"]) if label.isdigit() else unit["title"]


def unit_crumb(unit):
    label = str(unit["label"])
    return "%s단원 · %s" % (label, unit["title"]) if label.isdigit() else unit["title"]


def render_nav(site, units, built, cur_unit, cur_code):
    out = ['<nav class="nav" id="nav">',
           '    <div class="brand">',
           "      <h1>%s</h1>" % inline(site["title"])]
    if site.get("subtitle"):
        out.append("      <p>%s</p>" % inline(site["subtitle"]))
    out.append("    </div>")

    for unit in sorted(units, key=lambda u: u["order"]):
        is_cur = unit["id"] == cur_unit
        out.append('    <div class="unit%s">' % (" open" if is_cur else ""))
        out.append('      <button><span class="caret">▶</span>%s</button>'
                   % inline(unit_nav_title(unit)))
        out.append('      <div class="lessons">')
        for lesson in sorted(unit["lessons"], key=lambda l: code_sort_key(l["code"])):
            code = code_normalize(lesson["code"])
            label = "%s · %s" % (code_label(code), lesson["title"])
            if (unit["id"], code) not in built:
                # JSON이 아직 없는 차시 — 링크를 걸지 않는다
                out.append('        <span class="soon">%s</span>' % inline(label))
            else:
                on = ' class="on"' if (is_cur and code == cur_code) else ""
                out.append('        <a href="../%s/%s.html"%s>%s</a>'
                           % (unit["id"], code, on, inline(label)))
        out.append("      </div>")
        out.append("    </div>")

    if site.get("nav_foot"):
        out.append('    <p class="navfoot">%s</p>' % lines(site["nav_foot"]))
    if site.get("teacher_page"):
        out.append('    <p class="navfoot"><a class="teach" href="../teacher.html">'
                   '선생님께 드리는 안내</a></p>')
    out.append("  </nav>")
    return "\n".join(out)


# --------------------------------------------------------------------------
# 페이지
# --------------------------------------------------------------------------

PAGE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&display=swap" rel="stylesheet">
<style>
{style}</style>
</head>
<body>

<div class="bar">
  <button id="open">☰</button>
  <span>{site_title}</span>
</div>
<div class="scrim" id="scrim"></div>

<div class="wrap">
  {nav}

  <main class="main">
    <div class="col">
      {source_comment}
      <p class="crumb">{crumb}</p>
      <h2 class="title">{title}</h2>
{goal}      <p class="meta">{meta}</p>

      <div class="progress">
        <span>오늘 볼 것</span>
        <span class="dots">{dots}</span>
        <span>{open_count} / {total}</span>
      </div>

{items}

      {task}
    </div>
  </main>
</div>

<script>
{script}</script>
</body>
</html>
"""

ITEM = """      <div class="item{open}">{source_comment}
        <button><span class="num">{n}</span><span class="h">{title}</span>{pg}<span class="sign">＋</span></button>
        <div class="body">
          {blocks}
        </div>
      </div>"""


def render_page(lesson, unit, site, units, built):
    code = code_normalize(lesson["code"])
    where = "%s/%s" % (unit["id"], code)

    items_html = []
    open_count = 0
    for i, item in enumerate(lesson["items"], 1):
        is_open = bool(item.get("open"))
        open_count += is_open
        items_html.append(ITEM.format(
            open=" open" if is_open else "",
            source_comment=("\n        " + comment("근거: 지도서 %s쪽" % item["guide_page"])
                            if item.get("guide_page") else ""),
            n=i,
            title=inline(item["title"]),
            pg=('<span class="pg">%s쪽</span>' % inline(item["pages"])
                if item.get("pages") else ""),
            blocks=render_blocks(item["blocks"], "%s %d번 항목" % (where, i)),
        ))

    total = len(lesson["items"])
    dots = "".join('<i class="done"></i>' if i < open_count else "<i></i>"
                   for i in range(total))

    nav_title = next((l["title"] for l in unit["lessons"]
                      if code_normalize(l["code"]) == code), lesson["title"])

    return PAGE.format(
        style=STYLE,
        script=SCRIPT,
        page_title=inline("%s · %s · %s" % (nav_title, code_label(code), site["title"])),
        site_title=inline(site["title"]),
        nav=render_nav(site, units, built, unit["id"], code),
        source_comment=(comment("근거: 지도서 %s쪽" % lesson["guide_pages"])
                        if lesson.get("guide_pages") else ""),
        crumb=inline(unit_crumb(unit)),
        title=lines(lesson["title"]),
        goal=('      <p class="goal">%s</p>\n' % inline(lesson["goal"])
              if lesson.get("goal") else ""),
        meta=inline("%s · 교과서 %s쪽" % (code_label(code), lesson["textbook_pages"])),
        dots=dots,
        open_count=open_count,
        total=total,
        items="\n\n".join(items_html),
        task=render_task(lesson.get("extra_task")),
    )


# --------------------------------------------------------------------------
# 검증
# --------------------------------------------------------------------------

def validate(lesson, unit, code, path):
    def bad(msg):
        raise SystemExit("[%s] %s" % (path, msg))

    if lesson.get("schema") != "lesson/1":
        bad("schema 가 'lesson/1' 이 아닙니다: %r" % lesson.get("schema"))
    if code_normalize(lesson.get("code", "0")) != code:
        bad("code(%r)가 파일 이름(%s)과 다릅니다" % (lesson.get("code"), code))
    if lesson.get("unit") != unit["id"]:
        bad("unit(%r)이 폴더(%s)와 다릅니다" % (lesson.get("unit"), unit["id"]))
    for f in ("title", "textbook_pages", "items"):
        if not lesson.get(f):
            bad("필수 필드 %s 가 없습니다" % f)
    roster = {code_normalize(l["code"]) for l in unit["lessons"]}
    if code not in roster:
        bad("units.json의 %s 차시 목록에 %s 가 없습니다" % (unit["id"], code))
    for i, item in enumerate(lesson["items"], 1):
        if not item.get("title"):
            bad("%d번 항목에 title 이 없습니다" % i)
        if not item.get("blocks"):
            bad("%d번 항목(%s)에 blocks 가 없습니다" % (i, item.get("title")))


def strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def check_forbidden(paths):
    """주석을 걷어낸 뒤, 화면 텍스트에 금지어가 남았는지 본다."""
    hits = []
    for p in paths:
        if p.name in NOT_STUDENT_FACING:
            continue
        visible = strip_comments(p.read_text(encoding="utf-8"))
        for line_no, line in enumerate(visible.splitlines(), 1):
            for word in FORBIDDEN:
                if word in line:
                    hits.append((p, line_no, word, line.strip()[:90]))
    return hits


# --------------------------------------------------------------------------
# 빌드
# --------------------------------------------------------------------------

def build(site_id="gugeo-5-2"):
    base = LESSONS / site_id
    index = json.loads((base / "units.json").read_text(encoding="utf-8"))
    site, units = index["site"], index["units"]
    by_id = {u["id"]: u for u in units}

    found = []
    for unit in units:
        d = base / unit["id"]
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                found.append((unit, code_normalize(f.stem), f))
    found.sort(key=lambda t: (t[0]["order"], code_sort_key(t[1])))
    built = {(u["id"], c) for u, c, _ in found}

    out_dir = SITE
    written = []
    for unit, code, f in found:
        lesson = json.loads(f.read_text(encoding="utf-8"))
        validate(lesson, unit, code, f)
        target = out_dir / unit["id"] / ("%s.html" % code)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            render_page(lesson, by_id[lesson["unit"]], site, units, built),
            encoding="utf-8")
        written.append(target)

    about = base / "about.json"
    if about.is_file():
        target = out_dir / "teacher.html"
        target.write_text(
            render_about(json.loads(about.read_text(encoding="utf-8")), site),
            encoding="utf-8")
        written.append(target)

    if found:
        home = "%s/%s.html" % (found[0][0]["id"], found[0][1])
        title = html.escape(site["title"])
        (out_dir / "index.html").write_text(
            '<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">'
            '<meta http-equiv="refresh" content="0; url=%s">'
            '<title>%s</title></head><body><a href="%s">%s</a></body></html>\n'
            % (home, title, home, title), encoding="utf-8")

    return written, len(units), sum(len(u["lessons"]) for u in units)


STYLE = """/* 말과 글 수첩 — build_gugeo.py 안의 STYLE/SCRIPT 에서 나온다. HTML을 직접 고치지 말 것. */
:root{
  --paper:#FBFAF8;
  --panel:#F3F2ED;
  --ink:#20242A;
  --ink-soft:#5C636D;
  --ink-faint:#8E959E;
  --rule:#E2E0D9;
  --grid:#CBDCCF;
  --accent:#2E6B4F;
  --accent-soft:#EAF2EC;
  --sans:"Pretendard","Apple SD Gothic Neo",sans-serif;
  --serif:"Gowun Batang",serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{
  background:var(--paper);color:var(--ink);
  font-family:var(--sans);font-size:16px;line-height:1.75;
  letter-spacing:-.01em;
}
.wrap{display:flex;min-height:100vh}

/* ---------- 왼쪽 목차 ---------- */
.nav{
  width:264px;flex:0 0 264px;background:var(--panel);
  border-right:1px solid var(--rule);
  position:sticky;top:0;height:100vh;overflow-y:auto;
  padding:26px 0 40px;
}
.brand{padding:0 22px 20px;border-bottom:1px solid var(--rule);margin-bottom:14px}
.brand h1{font-family:var(--serif);font-size:21px;font-weight:700;letter-spacing:.01em}
.brand p{font-size:12.5px;color:var(--ink-faint);margin-top:3px;letter-spacing:.02em}

.unit{border-bottom:1px solid rgba(0,0,0,.045)}
.unit>button{
  width:100%;background:none;border:0;cursor:pointer;font:inherit;color:var(--ink-soft);
  display:flex;align-items:center;gap:9px;
  padding:11px 22px;text-align:left;font-size:14.5px;
}
.unit>button:hover{color:var(--ink)}
.unit>button .caret{
  font-size:9px;color:var(--ink-faint);transition:transform .18s;flex:0 0 9px;
}
.unit.open>button{color:var(--ink);font-weight:600}
.unit.open>button .caret{transform:rotate(90deg)}
.lessons{display:none;padding:2px 0 10px}
.unit.open .lessons{display:block}
.lessons a,.lessons .soon{
  display:block;padding:7px 22px 7px 40px;font-size:14px;
  color:var(--ink-soft);text-decoration:none;position:relative;
}
.lessons a:hover{color:var(--accent);background:rgba(0,0,0,.02)}
.lessons .soon{color:var(--ink-faint);opacity:.5}
.lessons a.on{color:var(--accent);font-weight:600;background:var(--accent-soft)}
.lessons a.on::before{
  content:"";position:absolute;left:22px;top:50%;transform:translateY(-50%);
  width:7px;height:7px;border:1.5px solid var(--accent);
}
.navfoot a.teach{color:var(--ink-faint);text-decoration:underline;text-underline-offset:3px}
.navfoot a.teach:hover{color:var(--accent)}
.navfoot{padding:16px 22px 0;font-size:12px;color:var(--ink-faint);line-height:1.6}

/* ---------- 본문 ---------- */
.main{flex:1;min-width:0;display:flex;justify-content:center;padding:44px 32px 90px}
.col{width:100%;max-width:680px}

.crumb{font-size:13px;color:var(--ink-faint);letter-spacing:.02em}
.title{font-family:var(--serif);font-size:32px;font-weight:700;line-height:1.35;margin:8px 0 14px;letter-spacing:-.01em}
.goal{
  border-left:2px solid var(--accent);padding:2px 0 2px 14px;
  font-size:15px;color:var(--ink-soft);margin-bottom:10px;
}
.meta{font-size:12.5px;color:var(--ink-faint);letter-spacing:.02em}

.progress{
  display:flex;align-items:center;gap:10px;margin:26px 0 6px;
  font-size:12.5px;color:var(--ink-faint);
}
.dots{display:flex;gap:5px}
.dots i{width:7px;height:7px;border:1.5px solid var(--grid);display:block}
.dots i.done{background:var(--accent);border-color:var(--accent)}

/* 항목 */
.item{border-bottom:1px solid var(--rule)}
.item:first-of-type{border-top:1px solid var(--rule)}
.item>button{
  width:100%;background:none;border:0;cursor:pointer;font:inherit;color:var(--ink);
  display:flex;align-items:baseline;gap:14px;padding:17px 2px;text-align:left;
}
.item>button:hover .h{color:var(--accent)}
.num{
  font-family:var(--serif);font-size:14px;color:var(--accent);
  flex:0 0 20px;font-weight:700;
}
.h{font-size:17px;font-weight:600;flex:1;letter-spacing:-.01em}
.pg{font-size:11.5px;color:var(--ink-faint);flex:0 0 auto;letter-spacing:.02em}
.sign{flex:0 0 12px;color:var(--ink-faint);font-size:13px;transition:transform .18s}
.item.open .sign{transform:rotate(45deg)}
.body{display:none;padding:0 2px 26px 34px}
.item.open .body{display:block}
.body p{margin-bottom:11px;color:var(--ink-soft)}
.body p strong{color:var(--ink);font-weight:600}
.body ul{margin:0 0 12px;padding-left:17px;color:var(--ink-soft)}
.body li{margin-bottom:5px}
.body .ex+p{margin-top:15px}

/* 낱말 */
.word{
  border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);
  padding:13px 0;margin:2px 0 14px;
}
.word .term{font-family:var(--serif);font-size:18px;font-weight:700;color:var(--ink);margin-bottom:6px}
.word .senses{margin:0 0 8px;padding-left:20px;color:var(--ink-soft)}
.word .senses li{margin-bottom:3px}
.word p:last-child{margin-bottom:0}

/* 예시 카드 — 이 사이트의 시그니처 */
.ex{
  background:#fff;
  border:1px solid var(--rule);
  border-left:3px solid var(--accent);
  padding:15px 18px;margin:6px 0 12px;
}
.ex .q{
  font-family:var(--serif);font-size:16.5px;line-height:1.7;
  margin-bottom:7px;color:var(--ink);
}
.ex .q:last-child{margin-bottom:0}
.ex .why{font-size:14.5px;color:var(--ink-soft);line-height:1.7;margin-bottom:0}
.ex .tag{
  display:block;font-size:11px;letter-spacing:.06em;color:var(--accent);
  font-weight:600;margin-bottom:8px;
}
.shape{
  display:flex;gap:8px;align-items:center;flex-wrap:wrap;
  font-size:14px;color:var(--ink);margin:4px 0 16px;
}
.shape span{background:var(--accent-soft);border:1px solid #CFE0D4;padding:4px 11px}
.shape em{color:var(--ink-faint);font-style:normal}

.note{
  font-size:13.5px;color:var(--ink-faint);border-top:1px dotted var(--rule);
  padding-top:9px;margin-top:14px;line-height:1.65;
}

/* 과제 */
.task{margin-top:38px;border:1px solid var(--rule);background:#fff;padding:22px 24px}
.task h3{font-family:var(--serif);font-size:18px;margin-bottom:4px}
.task .sub{font-size:12.5px;color:var(--ink-faint);margin-bottom:14px}
.task ol{padding-left:19px;color:var(--ink-soft);font-size:15px}
.task li{margin-bottom:7px}
.task li b{color:var(--ink);font-weight:600}
.hint{
  margin:7px 0 4px;padding:10px 13px;background:var(--accent-soft);
  font-size:13.5px;color:var(--ink-soft);line-height:1.6;
}
.hint span{display:block;padding-left:11px;position:relative;margin-top:3px;color:var(--ink)}
.hint span::before{content:"·";position:absolute;left:0;color:var(--accent)}

/* 모바일 */
.bar{display:none}
@media(max-width:820px){
  .bar{
    display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:30;
    background:var(--paper);border-bottom:1px solid var(--rule);padding:11px 16px;
  }
  .bar button{background:none;border:0;font-size:20px;cursor:pointer;color:var(--ink);line-height:1}
  .bar span{font-family:var(--serif);font-size:16px;font-weight:700}
  .wrap{flex-direction:column}
  .nav{
    position:fixed;top:0;left:0;height:100vh;z-index:40;
    transform:translateX(-100%);transition:transform .22s ease;
  }
  .nav.show{transform:translateX(0)}
  .scrim{
    display:none;position:fixed;inset:0;background:rgba(20,24,28,.35);z-index:35;
  }
  .scrim.show{display:block}
  .main{padding:26px 18px 70px}
  .title{font-size:26px}
}
"""

SCRIPT = """/* 말과 글 수첩 — build_gugeo.py 안의 STYLE/SCRIPT 에서 나온다. HTML을 직접 고치지 말 것. */
document.querySelectorAll('.unit>button').forEach(function(b){
  b.onclick=function(){b.parentElement.classList.toggle('open')};
});
var dots=document.querySelectorAll('.dots i');
var count=document.querySelector('.progress span:last-child');
document.querySelectorAll('.item>button').forEach(function(b){
  b.onclick=function(){
    b.parentElement.classList.toggle('open');
    var total=document.querySelectorAll('.item').length;
    var open=document.querySelectorAll('.item.open').length;
    dots.forEach(function(d,i){d.classList.toggle('done',i<open)});
    if(count) count.textContent=open+' / '+total;
  };
});
var nav=document.getElementById('nav'),scrim=document.getElementById('scrim'),
    opener=document.getElementById('open');
if(opener) opener.onclick=function(){nav.classList.add('show');scrim.classList.add('show')};
if(scrim) scrim.onclick=function(){nav.classList.remove('show');scrim.classList.remove('show')};
"""


ABOUT_PAGE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{page_title}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&display=swap" rel="stylesheet">
<style>
{style}
.about{{max-width:680px;margin:0 auto;padding:46px 22px 90px}}
.about .back{{font-size:13px;color:var(--ink-faint);text-decoration:none}}
.about .back:hover{{color:var(--accent)}}
.about h1{{font-family:var(--serif);font-size:30px;font-weight:700;line-height:1.35;margin:10px 0 6px}}
.about .sub{{font-size:14px;color:var(--ink-faint);margin-bottom:32px}}
.about h2{{font-family:var(--serif);font-size:19px;margin:34px 0 10px;padding-top:18px;border-top:1px solid var(--rule)}}
.about p{{color:var(--ink-soft);margin-bottom:11px}}
.about p strong{{color:var(--ink);font-weight:600}}
.about ul{{margin:0 0 12px;padding-left:18px;color:var(--ink-soft)}}
.about li{{margin-bottom:5px}}
.about .foot{{margin-top:44px;font-size:12.5px;color:var(--ink-faint)}}
</style>
</head>
<body>
<div class="about">
  <a class="back" href="index.html">← {site_title}</a>
  <h1>{title}</h1>
  <p class="sub">{subtitle}</p>
{sections}
  <p class="foot">{foot}</p>
</div>
</body>
</html>
"""


SECTION_SEP = "\n"


def render_about(about, site):
    """선생님 안내 페이지. 차시 데이터와 같은 CSS를 쓴다."""
    out = []
    for sec in about.get("sections", []):
        if sec.get("heading"):
            out.append("  <h2>%s</h2>" % inline(sec["heading"]))
        for b in sec.get("blocks", []):
            if b.get("type") == "list":
                out.append("  <ul>%s</ul>"
                           % "".join("<li>%s</li>" % inline(x) for x in b["items"]))
            else:
                out.append("  <p>%s</p>" % inline(b["text"]))
    return ABOUT_PAGE.format(
        page_title=inline("%s · %s" % (about["title"], site["title"])),
        site_title=inline(site["title"]),
        style=STYLE,
        title=lines(about["title"]),
        subtitle=inline(about.get("subtitle", "")),
        sections=SECTION_SEP.join(out),
        foot=inline(about.get("foot", "")),
    )


def main():
    written, n_units, n_lessons = build()
    for p in written:
        print("  %s" % p.relative_to(ROOT))
    pages = [q for q in written if q.parent != SITE]
    print("단원 %d · 차시 %d 중 %d개 빌드" % (n_units, n_lessons, len(pages)))

    hits = check_forbidden(written)
    if hits:
        print("\n화면 텍스트에 금지어가 남아 있습니다:")
        for p, ln, w, s in hits:
            print("  %s:%d  [%s]  %s" % (p.relative_to(ROOT), ln, w, s))
        return 1
    print("금지어 검사 통과 — 학생 화면에 '%s' 없음" % "/".join(FORBIDDEN))
    return 0


if __name__ == "__main__":
    if "--check" in sys.argv:
        files = sorted(SITE.rglob("*.html"))
        if not files:
            print("빌드된 HTML이 없습니다. 먼저 python build_gugeo.py 를 실행하세요.")
            sys.exit(1)
        found = check_forbidden(files)
        for p, ln, w, s in found:
            print("%s:%d  [%s]  %s" % (p.relative_to(ROOT), ln, w, s))
        print("%d개 파일 검사 · 위반 %d건" % (len(files), len(found)))
        sys.exit(1 if found else 0)
    sys.exit(main())
