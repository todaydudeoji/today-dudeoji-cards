"""오늘의 두더지 - 인스타그램 캐러셀 자동 게시

queue/ 아래 폴더 하나 = 게시물 하나.
  폴더 이름: YYYY-MM-DD_HHMM_제목  (한국 시간, 이 시각 이후 첫 실행 때 게시)
  안에 들어갈 것: 01.png ~ 10.png (순서대로), caption.txt

게시가 끝나면 폴더를 published/ 로 옮기고 결과(permalink)를 result.json 에 남긴다.

환경 변수: IG_TOKEN, IG_USER_ID, GITHUB_REPOSITORY, GITHUB_SHA
사용: python publish.py            # 시간이 된 게시물 중 가장 오래된 것 1개 게시
      python publish.py --folder 폴더이름   # 시간과 상관없이 해당 폴더 게시
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

GRAPH = "https://graph.facebook.com/v23.0"
ROOT = Path(__file__).resolve().parent
QUEUE = ROOT / "queue"
PUBLISHED = ROOT / "published"
KST = dt.timezone(dt.timedelta(hours=9))
NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(\d{4})_")


def api(method, path, **params):
    params["access_token"] = os.environ["IG_TOKEN"]
    data = urllib.parse.urlencode(params).encode()
    url = f"{GRAPH}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise SystemExit(f"Graph API 오류 ({path}): {body}")


def wait_finished(container_id, label):
    for _ in range(30):
        status = api("GET", container_id, fields="status_code,status").get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise SystemExit(f"{label} 처리 실패: {status}")
        time.sleep(5)
    raise SystemExit(f"{label} 처리 시간 초과")


def due_time(folder):
    m = NAME_RE.match(folder.name)
    if not m:
        return None
    return dt.datetime.strptime(m.group(1) + m.group(2), "%Y-%m-%d%H%M").replace(tzinfo=KST)


def pick_folder(name):
    if name:
        f = QUEUE / name
        if not f.is_dir():
            raise SystemExit(f"queue/{name} 폴더가 없습니다")
        return f
    now = dt.datetime.now(KST)
    due = sorted((due_time(f), f) for f in QUEUE.iterdir() if f.is_dir() and due_time(f) and due_time(f) <= now)
    return due[0][1] if due else None


def publish(folder):
    images = sorted(p for p in folder.glob("*.png"))
    if not 2 <= len(images) <= 10:
        raise SystemExit(f"이미지는 2~10장이어야 합니다 (현재 {len(images)}장)")
    caption = (folder / "caption.txt").read_text(encoding="utf-8-sig").strip()
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ.get("IMAGE_SHA") or os.environ["GITHUB_SHA"]
    rel = folder.relative_to(ROOT).as_posix()
    ig = os.environ["IG_USER_ID"]

    children = []
    for img in images:
        url = f"https://raw.githubusercontent.com/{repo}/{sha}/{urllib.parse.quote(rel)}/{img.name}"
        cid = api("POST", f"{ig}/media", image_url=url, is_carousel_item="true")["id"]
        wait_finished(cid, img.name)
        children.append(cid)
        print(f"  이미지 준비: {img.name}")

    carousel = api("POST", f"{ig}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
    wait_finished(carousel, "캐러셀")
    media_id = api("POST", f"{ig}/media_publish", creation_id=carousel)["id"]
    permalink = api("GET", media_id, fields="permalink").get("permalink")
    print(f"게시 완료: {permalink}")

    PUBLISHED.mkdir(exist_ok=True)
    dest = PUBLISHED / folder.name
    shutil.move(str(folder), str(dest))
    (dest / "result.json").write_text(
        json.dumps({"media_id": media_id, "permalink": permalink,
                    "published_at": dt.datetime.now(KST).isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return permalink


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="")
    args = ap.parse_args()
    QUEUE.mkdir(exist_ok=True)
    folder = pick_folder(args.folder.strip())
    if not folder:
        print("게시할 차례인 게시물이 없습니다.")
        return
    print(f"게시 시작: {folder.name}")
    publish(folder)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
