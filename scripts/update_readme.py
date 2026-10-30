#!/usr/bin/env python3
"""Update the README index using local video metadata and YouTube's public RSS feed."""
from pathlib import Path
from datetime import date
import re
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
START, END = "<!-- AUTO:START -->", "<!-- AUTO:END -->"
SHORTS_START, SHORTS_END = "<!-- SHORTS:START -->", "<!-- SHORTS:END -->"
CHANNEL_HANDLE = "lytexbio"


def field(content, key):
    match = re.search(rf'^{re.escape(key)}:\s*["\']?([^\n"\']+)', content, re.M)
    return match.group(1).strip() if match else ""


def sources():
    entries = []
    for path in (ROOT / "videos").rglob("*.md"):
        content = path.read_text(encoding="utf-8")
        title, published, video_id = (field(content, key) for key in ("title", "published", "youtube_id"))
        try:
            date.fromisoformat(published)
        except ValueError:
            continue
        if not title or not video_id or video_id == "YOUTUBE_ID":
            continue
        entries.append((published, title, video_id, path.relative_to(ROOT).as_posix()))
    return sorted(entries, reverse=True)


def shorts():
    entries = []
    for path in (ROOT / "shorts").rglob("*.md"):
        content = path.read_text(encoding="utf-8")
        title, published, tiktok, instagram = (
            field(content, key) for key in ("title", "published", "tiktok_url", "instagram_url")
        )
        try:
            date.fromisoformat(published)
        except ValueError:
            continue
        if not title or not (tiktok or instagram):
            continue
        entries.append((published, title, tiktok, instagram, path.relative_to(ROOT).as_posix()))
    return sorted(entries, reverse=True)


def latest_youtube():
    try:
        req = urllib.request.Request(f"https://www.youtube.com/@{CHANNEL_HANDLE}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8", errors="replace")
        match = re.search(r'"channelId":"(UC[\w-]{22})"', html) or re.search(r'channel_id=(UC[\w-]{22})', html)
        if not match:
            return []
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={match.group(1)}"
        req = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as response:
            root = ET.fromstring(response.read())
        ns = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
        result = []
        for entry in root.findall("atom:entry", ns):
            video_id = entry.findtext("yt:videoId", default="", namespaces=ns)
            title = entry.findtext("atom:title", default="", namespaces=ns)
            link = entry.find("atom:link", ns)
            # Shorts are linked as /shorts/<id> in the feed; only list long-form videos.
            if link is not None and "/shorts/" in link.get("href", ""):
                continue
            if video_id and title:
                result.append((video_id, title))
        return result[:5]
    except (OSError, ET.ParseError):
        return []


def main():
    entries = sources()
    lookup = {e[2]: e for e in entries}
    lines = ["### Aktuelle Quellenlisten", ""]
    if entries:
        for published, title, video_id, path in entries[:10]:
            lines.append(f"- **{published}** — [{title}]({path}) · [YouTube](https://www.youtube.com/watch?v={video_id})")
    else:
        lines.append("Noch keine veröffentlichten Quelldateien vorhanden.")
    videos = latest_youtube()
    if videos:
        lines.extend(["", "### Neueste YouTube-Videos", ""])
        for video_id, title in videos:
            if video_id in lookup:
                lines.append(f"- [{title}](https://www.youtube.com/watch?v={video_id}) · [Quellen]({lookup[video_id][3]})")
            else:
                lines.append(f"- [{title}](https://www.youtube.com/watch?v={video_id}) · Quellenliste noch nicht hinterlegt")
    short_lines = []
    short_entries = shorts()
    if short_entries:
        for published, title, tiktok, instagram, path in short_entries[:10]:
            links = [f"[TikTok]({tiktok})"] if tiktok else []
            if instagram:
                links.append(f"[Instagram]({instagram})")
            short_lines.append(f"- **{published}** — [{title}]({path}) · " + " · ".join(links))
    else:
        short_lines.append("Noch keine Quellenlisten zu Shorts vorhanden.")
    text = replace_block(README.read_text(encoding="utf-8"), START, END, lines)
    text = replace_block(text, SHORTS_START, SHORTS_END, short_lines)
    README.write_text(text, encoding="utf-8")


def replace_block(text, start, end, lines):
    if start not in text or end not in text:
        raise RuntimeError(f"README markers missing: {start} / {end}")
    before, tail = text.split(start, 1)
    _, after = tail.split(end, 1)
    return before + start + "\n" + "\n".join(lines) + "\n" + end + after


if __name__ == "__main__":
    main()
