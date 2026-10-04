#!/usr/bin/env python3
"""
Lab Member Sync Utility for ONTHAI Lab / BODHI Health Lab
Extracts member data & embedded profile photos from Excel intake templates (*.xlsm / *.xlsx),
crops profile images to 1:1, cleans redundant text, and updates data/th/people.json & data/en/people.json.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROLE_TRANSLATIONS = {
    "นักศึกษาปริญญาตรี": "Undergraduate Student",
    "นักศึกษาปริญญาโท": "Master's Student",
    "นักศึกษาปริญญาเอก": "PhD Candidate",
    "นักวิชาการสาธารณสุข": "Public Health Technical Officer",
    "นักวิจัยหลังปริญญาเอก": "Postdoctoral Researcher",
    "ผู้ช่วยศาสตราจารย์": "Assistant Professor",
    "รองศาสตราจารย์": "Associate Professor",
    "ศาสตราจารย์": "Professor",
    "อาจารย์": "Lecturer",
    "อาจารย์/นักวิจัย": "Lecturer & Researcher",
    "ผู้ประสานงานวิจัย": "Research Coordinator",
    "นักวิเคราะห์ข้อมูล": "Data Analyst",
    "นักวิทยาศาสตร์ข้อมูล": "Data Scientist",
    "บุคลากร/ผู้ร่วมวิจัย": "Research Staff & Collaborator",
}

CATEGORY_TO_GROUP = {
    "นักศึกษาที่ปรึกษา": "current-advisees",
    "ศิษย์เก่า/อดีตทีมงาน": "alumni",
    "ทีมงานปัจจุบัน": "current-team",
    "ผู้ร่วมงาน/ผู้วิจัยร่วม": "current-team",
    "บุคลากร/ผู้ร่วมวิจัย": "current-team",
}

PROGRAM_TRANSLATIONS = {
    "สาธารณสุขศาสตรบัณฑิต สาขาสาธารณสุขชุมชน": "Bachelor of Public Health (Community Public Health)",
    "สาธารณสุขศาสตรบัณฑิต สาขาวิชาสาธารณสุขชุมชน": "Bachelor of Public Health (Community Public Health)",
    "สาธารณสุขศาสตรบัณฑิต": "Bachelor of Public Health",
    "โรงพยาบาลส่งเสริมสุขภาพตำบลบ้านวังดารา": "Ban Wang Dara Sub-district Health Promotion Hospital",
}

TOPIC_TRANSLATIONS = {
    "ความชุกของสารกำจัดศัตรูพืชตกค้างในเลือดเกษตรกร": "Prevalence of Pesticide Residues in Blood Among Farmers",
    "การติดเชื้อพยาธิใบไม้ตับต่อมะเร็งท่อน้ำดี": "Liver Fluke Infection and Cholangiocarcinoma Risk",
}


def find_default_intake_file():
    candidates = glob.glob("*ONTHAI*Intake*.xlsm") + glob.glob("*Member-Intake*.xlsm") + glob.glob("*Intake*.xlsx")
    for c in candidates:
        if not os.path.basename(c).startswith("~$"):
            return c
    return None


def clean_slug(name_en):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name_en.strip().lower()).strip("-")
    first_part = slug.split("-")[0] if slug else "member"
    return first_part


def crop_image_square(src_path):
    """Crop image to 1:1 square centered using macOS sips command."""
    if not os.path.exists(src_path):
        return
    try:
        # Get dimensions with sips
        out = subprocess.check_output(["sips", "-g", "pixelWidth", "-g", "pixelHeight", src_path], text=True)
        w_match = re.search(r"pixelWidth:\s*(\d+)", out)
        h_match = re.search(r"pixelHeight:\s*(\d+)", out)
        if w_match and h_match:
            w, h = int(w_match.group(1)), int(h_match.group(1))
            square_size = min(w, h)
            subprocess.run(["sips", "--cropToHeightWidth", str(square_size), str(square_size), src_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Warning: could not crop image {src_path}: {e}", file=sys.stderr)


def extract_members_from_excel(xl_path):
    if not os.path.exists(xl_path):
        raise FileNotFoundError(f"File not found: {xl_path}")

    with zipfile.ZipFile(xl_path, "r") as z:
        # 1. Read shared strings
        shared_strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for elem in tree.iter():
                if elem.tag.endswith("}si"):
                    text = "".join(t.text for t in elem.iter() if t.tag.endswith("}t") and t.text)
                    shared_strings.append(text)

        # 2. Find worksheet for 'ข้อมูลเผยแพร่'
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheet_rids = {}
        for s in wb.iter():
            if s.tag.endswith("}sheet"):
                sheet_rids[s.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")] = s.attrib.get("name")

        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target_sheet_file = None
        for r in rels.iter():
            if r.tag.endswith("}Relationship"):
                r_id = r.attrib.get("Id")
                name = sheet_rids.get(r_id, "")
                if "ข้อมูลเผยแพร่" in name:
                    target_sheet_file = "xl/" + r.attrib.get("Target").lstrip("xl/")
                    break

        if not target_sheet_file or target_sheet_file not in z.namelist():
            # Fallback to sheet2
            target_sheet_file = "xl/worksheets/sheet2.xml"

        # 3. Find drawing relationship for target sheet
        sheet_rels_file = target_sheet_file.replace("worksheets/", "worksheets/_rels/").replace(".xml", ".xml.rels")
        drawing_target = None
        if sheet_rels_file in z.namelist():
            srels = ET.fromstring(z.read(sheet_rels_file))
            for r in srels.iter():
                if "drawing" in r.attrib.get("Type", ""):
                    drawing_target = "xl/" + r.attrib.get("Target").lstrip("../").lstrip("xl/")
                    break

        # 4. Map row to media file from drawing
        row_to_media = {}
        if drawing_target and drawing_target in z.namelist():
            d_rels_file = drawing_target.replace("drawings/", "drawings/_rels/").replace(".xml", ".xml.rels")
            rid_to_target = {}
            if d_rels_file in z.namelist():
                drels = ET.fromstring(z.read(d_rels_file))
                for r in drels.iter():
                    if r.tag.endswith("}Relationship"):
                        rid_to_target[r.attrib.get("Id")] = r.attrib.get("Target")

            dtree = ET.fromstring(z.read(drawing_target))
            for anchor in dtree:
                from_elem = anchor.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}from")
                row_elem = from_elem.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}row") if from_elem is not None else None
                blip = anchor.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
                if blip is not None and row_elem is not None:
                    embed_id = blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                    target = rid_to_target.get(embed_id, "")
                    media_path = "xl/" + target.lstrip("../").lstrip("xl/")
                    row_idx = int(row_elem.text) + 1  # 1-indexed Excel row
                    row_to_media[row_idx] = media_path

        # 5. Parse cell rows in worksheet
        stree = ET.fromstring(z.read(target_sheet_file))
        members = []
        for row in stree.iter():
            if not row.tag.endswith("}row"):
                continue
            row_num = int(row.attrib.get("r", "0"))
            if row_num <= 6:  # Skip header rows
                continue

            cells = {}
            for c in row.iter():
                if c.tag.endswith("}c"):
                    coord = c.attrib.get("r", "")
                    col = re.sub(r"\d+", "", coord)
                    val = ""
                    v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                    t = c.attrib.get("t")
                    if v is not None and v.text:
                        val = shared_strings[int(v.text)] if t == "s" else v.text
                    cells[col] = val.strip()

            name_th = cells.get("C", "")
            name_en = cells.get("D", "")
            if not name_th and not name_en:
                continue

            category = cells.get("F", "นักศึกษาที่ปรึกษา")
            group_id = CATEGORY_TO_GROUP.get(category, "current-advisees")
            raw_role = cells.get("G", "")
            program_th = cells.get("H", "")
            degree_level = cells.get("I", "")
            topic = cells.get("J", "")
            period_raw = cells.get("K", "")
            status_th = cells.get("L", "")

            # Clean role: avoid repeating degree or program
            cleaned_role_th = raw_role
            if "นักศึกษาปริญญาตรี" in raw_role or ("ปริญญาตรี" in degree_level and "นักศึกษา" in raw_role):
                cleaned_role_th = "นักศึกษาปริญญาตรี"

            # Period formatting
            if status_th == "กำลังศึกษา":
                period_th = "กำลังศึกษา (2569 - ปัจจุบัน)" if not period_raw else f"{status_th} ({period_raw})"
                period_en = "In progress (2026 - Present)"
            elif status_th == "สำเร็จการศึกษา":
                year_match = re.search(r"\b(25\d\d)\b", period_raw)
                th_year = year_match.group(1) if year_match else "2567"
                en_year = str(int(th_year) - 543) if year_match else "2024"
                period_th = f"สำเร็จการศึกษา ({th_year})"
                period_en = f"Graduated ({en_year})"
            else:
                period_th = period_raw or status_th
                period_en = period_raw or status_th

            role_en = ROLE_TRANSLATIONS.get(cleaned_role_th, cleaned_role_th)
            program_en = PROGRAM_TRANSLATIONS.get(program_th, program_th)

            # Extract media if available
            media_path = row_to_media.get(row_num)
            slug = clean_slug(name_en or name_th)
            img_rel_path = ""
            if media_path and media_path in z.namelist():
                ext = ".png" if media_path.endswith(".png") else ".jpg"
                dest_filename = f"{slug}{ext}"
                dest_path = os.path.join("assets", "people", dest_filename)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as f_out:
                    f_out.write(z.read(media_path))
                crop_image_square(dest_path)
                img_rel_path = f"assets/people/{dest_filename}"

            members.append({
                "group_id": group_id,
                "th": {
                    "name": name_th,
                    "role": cleaned_role_th,
                    "program": program_th,
                    "topic": topic,
                    "period": period_th,
                    "profileUrl": cells.get("O", ""),
                    "image": img_rel_path,
                    "visible": True,
                },
                "en": {
                    "name": name_en or name_th,
                    "role": role_en,
                    "program": program_en,
                    "topic": TOPIC_TRANSLATIONS.get(topic, topic),
                    "period": period_en,
                    "profileUrl": cells.get("O", ""),
                    "image": img_rel_path,
                    "visible": True,
                }
            })

    return members


def sync_to_json(members, dry_run=False):
    th_file = "data/th/people.json"
    en_file = "data/en/people.json"

    with open(th_file, "r", encoding="utf-8") as f:
        data_th = json.load(f)
    with open(en_file, "r", encoding="utf-8") as f:
        data_en = json.load(f)

    updated_count = 0
    added_count = 0

    for item in members:
        gid = item["group_id"]
        m_th = item["th"]
        m_en = item["en"]

        for lang_data, m_obj in [(data_th, m_th), (data_en, m_en)]:
            group = next((g for g in lang_data if g["id"] == gid), None)
            if not group:
                continue

            members_list = group.setdefault("members", [])
            # Check existing by name
            existing = next((m for m in members_list if m["name"].strip() == m_obj["name"].strip()), None)
            if existing:
                # Update fields, preserve image if new one is empty
                if not m_obj["image"] and existing.get("image"):
                    m_obj["image"] = existing["image"]
                existing.update(m_obj)
                if lang_data is data_th:
                    updated_count += 1
            else:
                members_list.append(m_obj)
                if lang_data is data_th:
                    added_count += 1

    if not dry_run:
        with open(th_file, "w", encoding="utf-8") as f:
            json.dump(data_th, f, ensure_ascii=False, indent=2)
        with open(en_file, "w", encoding="utf-8") as f:
            json.dump(data_en, f, ensure_ascii=False, indent=2)
        print(f"Success! Updated {updated_count} members, added {added_count} members to {th_file} and {en_file}")
    else:
        print(f"[Dry Run] Would update {updated_count} members and add {added_count} members.")


def main():
    parser = argparse.ArgumentParser(description="Sync members from ONTHAI Lab Excel template to people.json.")
    parser.add_argument("--file", "-f", help="Path to Excel intake template (*.xlsm / *.xlsx)")
    parser.add_argument("--dry-run", action="store_true", help="Preview sync results without writing changes")
    args = parser.parse_args()

    excel_file = args.file or find_default_intake_file()
    if not excel_file:
        print("Error: No intake Excel template found. Specify one with --file <path>", file=sys.stderr)
        sys.exit(1)

    print(f"Reading member intake from: {excel_file}")
    members = extract_members_from_excel(excel_file)
    print(f"Found {len(members)} member(s) in sheet 'ข้อมูลเผยแพร่':")
    for m in members:
        print(f" - [{m['group_id']}] {m['th']['name']} ({m['en']['name']}) | Image: {m['th']['image'] or 'None'}")

    sync_to_json(members, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
