#!/usr/bin/env python3
"""
Sync Student Portfolios for GE25301 (AI and Life in the Digital Age)
Fetches Google Sheet CSV, scrapes each student's GitHub Pages portfolio,
and writes structured data to data/ge25301_students.json.
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: 'beautifulsoup4' is required. Please run: pip3 install beautifulsoup4", file=sys.stderr)
    sys.exit(1)

DEFAULT_SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTgkooBMdaE8SThKHLZwr58PDqIYl7tdftKNy0VIa0I3fpTZNGFTDgWFFL8TNswqxH3JxsJEdgj6z1D"
    "/pub?output=csv"
)
OUTPUT_JSON_PATH = "data/ge25301_students.json"

STOP_WORDS = {
    "สวัสดี", "หนูชื่อ", "ยินดีต้อนรับ", "เกี่ยวกับ", "ประวัติ", "แฟ้มสะสม",
    "ผลงาน", "นักศึกษา", "การศึกษา", "ทักษะ", "ความสามารถ", "งานอดิเรก",
    "ช่องทางติดต่อ", "คติประจำใจ", "ข้อมูลส่วนตัว", "portfolio", "resume",
    "personal", "academic", "about", "contact", "home"
}


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def parse_name(title: str, h1: str, text: str) -> str:
    """Extract full Thai name from title, h1, or page text."""
    # 1. First check H1 and Title for prefix + name
    for src in [h1, title]:
        m = re.search(r"(นาย|นางสาว|น\.ส\.)\s*([ก-๙]{2,})\s+([ก-๙]{2,})", src)
        if m and m.group(2) not in STOP_WORDS and m.group(3) not in STOP_WORDS:
            return f"{m.group(1)} {m.group(2)} {m.group(3)}".strip()

    # 2. Check Title for two Thai words e.g. "กนกอร อ่อนสิน (Kanokon Onsin)"
    m = re.search(r"\b([ก-๙]{2,})\s+([ก-๙]{2,})\b", title)
    if m and m.group(1) not in STOP_WORDS and m.group(2) not in STOP_WORDS:
        return f"{m.group(1)} {m.group(2)}".strip()

    # 3. Check H1 for two Thai words e.g. "กนกอร อ่อนสิน"
    m = re.search(r"\b([ก-๙]{2,})\s+([ก-๙]{2,})\b", h1)
    if m and m.group(1) not in STOP_WORDS and m.group(2) not in STOP_WORDS:
        return f"{m.group(1)} {m.group(2)}".strip()

    # 4. Check text for prefix + name
    for m in re.finditer(r"(นาย|นางสาว|น\.ส\.)\s*([ก-๙]{2,})\s+([ก-๙]{2,})", text[:1000]):
        if m.group(2) not in STOP_WORDS and m.group(3) not in STOP_WORDS:
            return f"{m.group(1)} {m.group(2)} {m.group(3)}".strip()

    # 5. Fallback search in page text
    for m in re.finditer(r"\b([ก-๙]{2,})\s+([ก-๙]{2,})\b", text[:800]):
        if m.group(1) not in STOP_WORDS and m.group(2) not in STOP_WORDS:
            return f"{m.group(1)} {m.group(2)}".strip()

    return h1 or title or "นักศึกษา"


def parse_nickname(title: str, h1: str, text: str) -> str:
    """Extract nickname e.g. ชื่อเล่น: นาเดียร์ or (มิ้ล)."""
    # Pattern: ชื่อเล่น: XXX
    m = re.search(r"ชื่อเล่น[:\s]*([ก-๙a-zA-Z]+)", text)
    if m and m.group(1) not in STOP_WORDS:
        return m.group(1).strip()

    # Parentheses in title or h1 or start of text e.g. (กิ๊ฟ), (มิ้ล), (นาเดียร์)
    for src in [title, h1, text[:500]]:
        m = re.search(r"\(([ก-๙]{2,10})\)", src)
        if m and m.group(1) not in STOP_WORDS:
            return m.group(1).strip()

    return ""


def parse_name_en(title: str, text: str) -> str:
    """Extract English name from title or early text."""
    for src in [title, text[:500]]:
        m = re.search(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b", src)
        if m:
            w1, w2 = m.group(1), m.group(2)
            if w1 not in {"Personal", "About", "Academic", "Portfolio", "Resume", "Hello", "Welcome"}:
                return f"{w1} {w2}"
    return ""


def parse_student_id(url: str, text: str) -> str:
    """Extract 11-digit or 10-digit student ID starting with 6x."""
    # Often in subdomain e.g. 69202302002-arch.github.io
    m = re.search(r"\b(6[5-9]\d{9,11})\b", url) or re.search(r"\b(6[5-9]\d{8,10})\b", url)
    if m:
        return m.group(1)

    # In text / email e.g. 69202302004@scphkk.ac.th
    m = re.search(r"\b(6[5-9]\d{9,11})\b", text) or re.search(r"\b(6[5-9]\d{8,10})\b", text)
    if m:
        return m.group(1)

    return ""


def parse_avatar(soup: BeautifulSoup, base_url: str) -> str:
    """Find student profile image, avoiding logos/icons/placeholders."""
    candidates = []
    for img in soup.find_all("img"):
        src = img.get("src", "").strip()
        if not src:
            continue
        lower_src = src.lower()
        if any(skip in lower_src for skip in [".svg", "logo", "icon", "placeholder", "placehold.co", "badge", "favicon"]):
            continue
        full_url = urllib.parse.urljoin(base_url, src)
        candidates.append(full_url)

    if candidates:
        return candidates[0]
    return ""


def parse_bio(soup: BeautifulSoup, text: str) -> str:
    """Extract short bio or program snippet."""
    keywords = ["สาขาวิชา", "วิทยาลัยการสาธารณสุข", "สาธารณสุข", "นักศึกษาชั้นปีที่"]
    for p in soup.find_all(["p", "span", "div"]):
        content = clean_text(p.get_text())
        if 15 <= len(content) <= 180 and any(kw in content for kw in keywords):
            return content

    # Default fallback
    return "นักศึกษา รายวิชา GE25301 AI กับชีวิตยุคดิจิทัล · วิทยาลัยการสาธารณสุขสิรินธร จังหวัดขอนแก่น"


def scrape_portfolio(no: int, url: str) -> dict:
    url = url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[{no}] Error fetching {url}: {e}", file=sys.stderr)
        return {
            "no": no,
            "url": url,
            "name": f"นักศึกษา ลำดับที่ {no}",
            "name_en": "",
            "nickname": "",
            "student_id": "",
            "avatar": "",
            "bio": "พอร์ตโฟลิโอออนไลน์ รายวิชา GE25301",
            "school": "วิทยาลัยการสาธารณสุขสิรินธร จังหวัดขอนแก่น",
            "status": "active",
            "error": str(e)
        }

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    h1 = soup.find("h1")
    h1_text = clean_text(h1.get_text()) if h1 else ""
    text = clean_text(soup.get_text(" "))

    name = parse_name(title, h1_text, text)
    nickname = parse_nickname(title, h1_text, text)
    name_en = parse_name_en(title, text)
    student_id = parse_student_id(url, text)
    avatar = parse_avatar(soup, url)
    bio = parse_bio(soup, text)

    return {
        "no": no,
        "url": url,
        "name": name,
        "name_en": name_en,
        "nickname": nickname,
        "student_id": student_id,
        "avatar": avatar,
        "bio": bio,
        "school": "วิทยาลัยการสาธารณสุขสิรินธร จังหวัดขอนแก่น",
        "status": "active"
    }


def fetch_sheet_csv(csv_url_or_path: str) -> list:
    if csv_url_or_path.startswith("http://") or csv_url_or_path.startswith("https://"):
        headers = {"User-Agent": "Mozilla/5.0"}
        req = urllib.request.Request(csv_url_or_path, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as res:
            content = res.read().decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(content))
    else:
        with open(csv_url_or_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)

    rows = []
    for r in reader:
        if not r or len(r) < 2:
            continue
        col_no, col_url = r[0].strip(), r[1].strip()
        if col_no.lower() == "no" or col_url.lower() == "url":
            continue
        if col_url and ("github.io" in col_url or col_url.startswith("http")):
            try:
                num = int(col_no)
            except ValueError:
                num = len(rows) + 1
            rows.append((num, col_url))

    return rows


def main():
    parser = argparse.ArgumentParser(description="Sync GE25301 Student Portfolios from Google Sheet to JSON")
    parser.add_argument("--url", default=DEFAULT_SHEET_CSV_URL, help="Google Sheet CSV URL or local CSV path")
    parser.add_argument("--out", default=OUTPUT_JSON_PATH, help="Output JSON path")
    args = parser.parse_args()

    print(f"Fetching student list from: {args.url}")
    sheet_rows = fetch_sheet_csv(args.url)
    print(f"Found {len(sheet_rows)} student portfolio URL(s) to process.\n")

    students = []
    for no, url in sheet_rows:
        print(f"Processing #{no}: {url} ...")
        info = scrape_portfolio(no, url)
        students.append(info)
        print(f"  -> Name: {info['name']}" + (f" ({info['nickname']})" if info['nickname'] else "") +
              (f" [ID: {info['student_id']}]" if info['student_id'] else "") +
              f" | Avatar: {'Yes' if info['avatar'] else 'None'}")

    payload = {
        "course_code": "GE25301",
        "course_title_th": "AI กับชีวิตยุคดิจิทัล",
        "course_title_en": "AI and Life in the Digital Age",
        "institution_th": "วิทยาลัยการสาธารณสุขสิรินธร จังหวัดขอนแก่น",
        "institution_en": "Sirindhorn College of Public Health Khon Kaen",
        "total_students": len(students),
        "last_synced": datetime.now(timezone.utc).isoformat(),
        "students": students
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\nSuccessfully wrote {len(students)} student records to: {args.out}")


if __name__ == "__main__":
    main()
