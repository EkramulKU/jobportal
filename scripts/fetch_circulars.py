import requests
import json
import re
import time
import os
from datetime import datetime, timezone

DATA_FILE = "data/circulars.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ─── LOAD / SAVE ──────────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_updated": "", "biddabari": [], "safollo": [], "bcsconfidence": []}

def save_data(data):
    os.makedirs("data", exist_ok=True)
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved to {DATA_FILE}")

def existing_ids(items):
    return {item["id"] for item in items}

# ─── DEADLINE STATUS ──────────────────────────────────────────────────────────
def deadline_status(dl_str):
    if not dl_str or dl_str == "—":
        return "none"
    try:
        for fmt in ["%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"]:
            try:
                dl_date = datetime.strptime(dl_str, fmt)
                diff = (dl_date - datetime.now()).days
                if diff < 0:   return "expired"
                if diff <= 7:  return "urgent"
                return "active"
            except ValueError:
                continue
    except Exception:
        pass
    return "active"

# ─── SAFOLLO ──────────────────────────────────────────────────────────────────
def fetch_safollo(existing):
    print("\n🔵 Fetching Safollo...")
    new_items = []
    try:
        r = requests.get(
            "https://api.safollo.ac/api/job-circular?per_page=100",
            headers=HEADERS, timeout=25
        )
        r.raise_for_status()
        items = r.json().get("data", [])
        print(f"   Found {len(items)} circulars on Safollo")

        for item in items:
            slug = item.get("slug", "")
            if not slug or slug in existing:
                continue

            deadline = item.get("deadline") or "—"
            new_items.append({
                "id":              slug,
                "org":             item.get("title", ""),
                "posts":           str(item.get("total_post", "") or "—"),
                "deadline":        deadline,
                "deadline_status": deadline_status(deadline),
                "detail_url":      f"https://www.safollo.ac/job-circular/{slug}",
                "pdf_url":         item.get("file") or "",
                "apply_url":       item.get("apply_link") or "",
                "date_added":      datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })

        print(f"   ✨ {len(new_items)} new circulars from Safollo")
    except Exception as e:
        print(f"   ❌ Safollo error: {e}")
    return new_items

# ─── BCS CONFIDENCE ───────────────────────────────────────────────────────────
def fetch_bcsconfidence(existing):
    print("\n🟣 Fetching BCS Confidence...")
    new_items = []
    try:
        # Step 1: get Inertia version
        r = requests.get("https://www.bcsconfidence.online/job-news", headers=HEADERS, timeout=25)
        vm = re.search(r'"version":"([^"]+)"', r.text)
        version = vm.group(1) if vm else "1"

        # Step 2: fetch via Inertia API (JSON mode)
        inertia_headers = {
            **HEADERS,
            "X-Inertia": "true",
            "X-Inertia-Version": version,
            "Accept": "application/json",
        }
        r2 = requests.get(
            "https://www.bcsconfidence.online/job-news",
            headers=inertia_headers, timeout=25
        )
        r2.raise_for_status()
        data = r2.json()
        items = data.get("props", {}).get("job_news", {}).get("data", [])
        print(f"   Found {len(items)} items on BCS Confidence")

        for item in items:
            slug = item.get("slug", "")
            if not slug or slug in existing:
                continue

            created = item.get("created_at", "")[:10]
            new_items.append({
                "id":         slug,
                "title":      item.get("title", ""),
                "date":       created,
                "detail_url": f"https://www.bcsconfidence.online/job-news/{slug}",
                "date_added": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })

        print(f"   ✨ {len(new_items)} new items from BCS Confidence")
    except Exception as e:
        print(f"   ❌ BCS Confidence error: {e}")
    return new_items

# ─── BIDDABARI ────────────────────────────────────────────────────────────────
def fetch_biddabari(existing):
    print("\n🔷 Fetching Biddabari...")
    new_items = []
    seen_slugs = set()

    for page in range(1, 5):   # check 4 pages
        try:
            url = f"https://biddabari.com/job-circular?page={page}" if page > 1 else "https://biddabari.com/job-circular"
            r = requests.get(url, headers=HEADERS, timeout=25)
            r.raise_for_status()
            html = r.text

            # Extract all detail page links
            links = re.findall(r'href="(https://biddabari\.com/job-circular-details/[^"]+)"', html)
            links = list(dict.fromkeys(links))   # deduplicate order-preserving

            print(f"   Page {page}: {len(links)} links")
            new_count = 0

            for link in links:
                slug = link.rstrip("/").split("/")[-1]
                if slug in existing or slug in seen_slugs:
                    continue
                seen_slugs.add(slug)

                # Fetch detail page
                try:
                    time.sleep(0.4)
                    dr = requests.get(link, headers=HEADERS, timeout=20)
                    dhtml = dr.text

                    # Extract org/title
                    title_match = re.search(r'<title[^>]*>([^<|]+)', dhtml)
                    org = title_match.group(1).strip() if title_match else slug.replace("-", " ").title()

                    # Extract PDF link
                    pdf_match = re.search(
                        r'href="(https://storage\.biddabari\.online/[^"]+\.pdf)"',
                        dhtml
                    )
                    pdf_url = pdf_match.group(1) if pdf_match else ""

                    # Extract deadline
                    dl_match = re.search(
                        r'(?:deadline|last.?date|শেষ.?তারিখ)[^:]*:?\s*([0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+20\d\d)',
                        dhtml, re.IGNORECASE
                    )
                    deadline = dl_match.group(1).strip() if dl_match else "—"

                    new_items.append({
                        "id":              slug,
                        "org":             org,
                        "posts":           "—",
                        "deadline":        deadline,
                        "deadline_status": deadline_status(deadline),
                        "detail_url":      link,
                        "pdf_url":         pdf_url,
                        "date_added":      datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    })
                    new_count += 1

                except Exception as inner_e:
                    print(f"      ⚠ Detail page error for {slug}: {inner_e}")

            print(f"   Page {page}: {new_count} new circulars added")

            # If no new circulars on this page, stop early
            if new_count == 0 and page > 1:
                print(f"   No new items on page {page}, stopping.")
                break

            time.sleep(1)

        except Exception as e:
            print(f"   ❌ Biddabari page {page} error: {e}")

    print(f"   ✨ {len(new_items)} total new from Biddabari")
    return new_items

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("🚀 Job Circular Fetcher")
    print(f"   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    data = load_data()

    # --- Safollo
    s_existing = existing_ids(data.get("safollo", []))
    new_safollo = fetch_safollo(s_existing)
    data.setdefault("safollo", [])
    data["safollo"] = new_safollo + data["safollo"]   # newest first

    # --- BCS Confidence
    b_existing = existing_ids(data.get("bcsconfidence", []))
    new_bcs = fetch_bcsconfidence(b_existing)
    data.setdefault("bcsconfidence", [])
    data["bcsconfidence"] = new_bcs + data["bcsconfidence"]

    # --- Biddabari
    bd_existing = existing_ids(data.get("biddabari", []))
    new_bd = fetch_biddabari(bd_existing)
    data.setdefault("biddabari", [])
    data["biddabari"] = new_bd + data["biddabari"]

    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Summary:")
    print(f"   Biddabari:       {len(data['biddabari'])} total  (+{len(new_bd)} new)")
    print(f"   Safollo:         {len(data['safollo'])} total  (+{len(new_safollo)} new)")
    print(f"   BCS Confidence:  {len(data['bcsconfidence'])} total  (+{len(new_bcs)} new)")
    total = len(data['biddabari']) + len(data['safollo']) + len(data['bcsconfidence'])
    print(f"   TOTAL:           {total}")
    print("=" * 50)

    save_data(data)
    print("\n✅ Done!")

if __name__ == "__main__":
    main()
