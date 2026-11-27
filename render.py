"""오늘의 두더지 캐러셀 렌더러 (Windows · macOS · Linux 공통)

render.ps1 과 같은 카드를 만든다. 클라우드 세션이나 GitHub Actions(Linux)에서도 돌아간다.

사용법:
  python render.py posts/sample.json                 # out/sample/01.png ... + caption.txt
  python render.py posts/w1_*.json                   # 여러 원고를 한 번에
  python render.py posts/sample.json --queue 2026-12-01_0700
      # 렌더링 후 queue/2026-12-01_0700_sample/ 에도 복사 (게시 예약, 한국 시간)

필요한 것: Python 3.8+ 와 Chrome/Chromium/Edge 중 하나.
  브라우저가 없으면:  pip install playwright && playwright install chromium
  (또는 Linux: apt-get install -y chromium)

텍스트 서식: [[강조]] -> 노란/빨간 강조,  **굵게** -> 빨간 굵은 글씨,  줄바꿈은 배열로 나눠서 입력
"""
import argparse
import glob
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_HANDLE = "@today_dudeoji"
QUEUE_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}$")


# ---------- 텍스트 서식 ----------

def fmt(s):
    if s is None:
        return ""
    s = html.escape(str(s), quote=True)
    s = re.sub(r"\[\[(.+?)\]\]", r"<em>\1</em>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s


def lines(v):
    if isinstance(v, list):
        return "<br>".join(fmt(x) for x in v)
    return fmt(v)


def head(i, total):
    return (
        '<div class="head">\n  <div class="logo"></div>\n'
        '  <div class="brand">오늘의 <span>두더지</span></div>\n'
        f'  <div class="page">{i} / {total}</div>\n</div>'
    )


# ---------- 카드 HTML ----------

def card_html(c, i, total, handle):
    t = c.get("type")
    if t == "cover":
        return f"""<div class="card cover">
  <div class="art"></div>
  <div class="panel">
    <div class="tag">{fmt(c.get('tag'))}</div>
    <h1>{lines(c.get('title'))}</h1>
    <div class="sub">{lines(c.get('sub'))}</div>
  </div>
  <div class="foot"><span>{fmt(handle)}</span><span class="swipe">넘겨보기 →</span></div>
</div>"""
    if t == "body":
        lst = ""
        if c.get("items"):
            lst = '<div class="items">' + "".join(
                f'<div class="item"><div class="num">{fmt(it.get("num"))}</div><div>'
                f'<div class="t">{lines(it.get("title"))}</div><div class="d">{lines(it.get("desc"))}</div></div></div>'
                for it in c["items"]
            ) + "</div>"
        if c.get("bullets"):
            lst += '<ul class="bullets">' + "".join(f"<li>{fmt(b)}</li>" for b in c["bullets"]) + "</ul>"
        return f"""<div class="card body">
  {head(i, total)}
  <div class="inner">
    <div class="label">{fmt(c.get('label'))}</div>
    <h2>{lines(c.get('heading'))}</h2>
    {lst}
  </div>
  <div class="foot-handle">{fmt(handle)}</div>
</div>"""
    if t == "checklist":
        checks = "".join(f'<li><span class="box"></span><span>{fmt(x)}</span></li>' for x in c.get("items") or [])
        return f"""<div class="card checklist">
  {head(i, total)}
  <div class="inner">
    <div class="label">{fmt(c.get('label'))}</div>
    <h2>{lines(c.get('heading'))}</h2>
    <ul class="checks">{checks}</ul>
    <div class="save-note"><span>{fmt(c.get('note'))}</span></div>
  </div>
  <div class="foot-handle">{fmt(handle)}</div>
</div>"""
    if t == "follow":
        top = fmt(c.get("top") or "[[내 돈·생활 이슈]], 두더지가 캐드려요")
        return f"""<div class="card follow">
  <div class="top">{top}</div>
  <div class="art"></div>
  <div class="bottom">{fmt(handle)}</div>
</div>"""
    raise SystemExit(f"알 수 없는 카드 type: {t}")


def page_html(inner):
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<link rel="stylesheet" href="../../template/style.css">
</head><body>
{inner}
</body></html>
"""


# ---------- 브라우저 찾기 ----------

def find_browser(explicit=""):
    if explicit:
        return explicit
    if os.environ.get("CHROME_PATH"):
        return os.environ["CHROME_PATH"]
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        rf"{pf}\Google\Chrome\Application\chrome.exe",
        rf"{pf86}\Google\Chrome\Application\chrome.exe",
        rf"{local}\Google\Chrome\Application\chrome.exe",
        rf"{pf86}\Microsoft\Edge\Application\msedge.exe",
        rf"{pf}\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]
    for p in candidates:
        if Path(p).is_file():
            return p
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge"):
        p = shutil.which(name)
        if p:
            return p
    # playwright install chromium 으로 받은 브라우저
    home = Path.home()
    for pattern in (
        ".cache/ms-playwright/chromium-*/chrome-linux*/chrome",
        ".cache/ms-playwright/chromium_headless_shell-*/chrome-linux*/headless_shell",
        "Library/Caches/ms-playwright/chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
        "AppData/Local/ms-playwright/chromium-*/chrome-win*/chrome.exe",
    ):
        found = sorted(glob.glob(str(home / pattern)))
        if found:
            return found[-1]
    raise SystemExit(
        "Chrome/Chromium/Edge 를 찾을 수 없습니다.\n"
        "  pip install playwright && playwright install chromium\n"
        "또는 --browser 로 실행 파일 경로를 알려 주세요."
    )


def screenshot(browser, html_file, png):
    args = [
        browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--force-device-scale-factor=1", "--window-size=1080,1350",
        "--virtual-time-budget=8000", "--allow-file-access-from-files",
        "--no-first-run", "--no-default-browser-check",
        f"--screenshot={png}", html_file.as_uri(),
    ]
    if sys.platform.startswith("linux"):
        args.insert(1, "--disable-dev-shm-usage")
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            args.insert(1, "--no-sandbox")  # 컨테이너(root)에서는 샌드박스를 켤 수 없음
    if png.exists():
        png.unlink()
    subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    if not png.exists():
        raise SystemExit(f"렌더링 실패: {png.name} (브라우저: {browser})")


# ---------- 실행 ----------

def render(content_path, browser, queue_time=""):
    content_path = Path(content_path).resolve()
    data = json.loads(content_path.read_text(encoding="utf-8-sig"))
    name = content_path.stem
    out_dir = ROOT / "out" / name
    build_dir = ROOT / "build" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    handle = data.get("handle") or DEFAULT_HANDLE
    cards = data.get("cards") or []
    total = len(cards)
    if not total:
        raise SystemExit(f"{content_path.name}: cards 가 비어 있습니다")

    for old in out_dir.glob("*.png"):
        old.unlink()
    for n, c in enumerate(cards, start=1):
        html_file = build_dir / f"{n:02d}.html"
        html_file.write_text(page_html(card_html(c, n, total, handle)), encoding="utf-8")
        png = out_dir / f"{n:02d}.png"
        screenshot(browser, html_file, png)
        print(f"카드 {n}/{total} -> {png.relative_to(ROOT)}")

    if data.get("caption"):
        (out_dir / "caption.txt").write_text(data["caption"], encoding="utf-8")

    if queue_time:
        q = ROOT / "queue" / f"{queue_time}_{name}"
        q.mkdir(parents=True, exist_ok=True)
        for f in out_dir.iterdir():
            if f.suffix in (".png", ".txt"):
                shutil.copy2(f, q / f.name)
        print(f"게시 예약 -> {q.relative_to(ROOT)}")
    return out_dir


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="오늘의 두더지 카드 렌더러")
    ap.add_argument("content", nargs="+", help="posts/*.json 원고 파일 (여러 개 가능)")
    ap.add_argument("--browser", default="", help="Chrome/Chromium/Edge 실행 파일 경로")
    ap.add_argument("--queue", default="", metavar="YYYY-MM-DD_HHMM",
                    help="렌더링 결과를 queue/<시각>_<원고이름>/ 에 복사 (한국 시간). 원고가 하나일 때만")
    a = ap.parse_args()

    files = []
    for pattern in a.content:
        matched = sorted(glob.glob(pattern))
        files.extend(matched or [pattern])
    if a.queue:
        if not QUEUE_TIME_RE.match(a.queue):
            raise SystemExit("--queue 는 2026-12-01_0700 같은 형식이어야 합니다")
        if len(files) != 1:
            raise SystemExit("--queue 는 원고 하나에만 쓸 수 있습니다")

    browser = find_browser(a.browser)
    for f in files:
        render(f, browser, a.queue)


if __name__ == "__main__":
    main()
