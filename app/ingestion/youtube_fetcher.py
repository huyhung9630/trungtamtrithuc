from __future__ import annotations

import json
import re
import subprocess


def _parse_youtube_id(url_or_id: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url_or_id):
        return url_or_id
    for pattern in [r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})"]:
        m = re.search(pattern, url_or_id)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot parse YouTube video id from: {url_or_id}")


def _fetch_title_oembed(url: str) -> str:
    import requests  # type: ignore

    try:
        resp = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=10,
        )
        if resp.ok:
            return resp.json().get("title", "")
    except Exception:
        pass
    return ""


def _fetch_title_ytdlp(video_id: str) -> str:
    try:
        result = subprocess.run(
            ["yt-dlp", "--skip-download", "--print", "title",
             f"https://www.youtube.com/watch?v={video_id}"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def fetch_playlist_video_ids(playlist_url: str) -> list[dict]:
    """Extract all video IDs and titles from a YouTube playlist using yt-dlp."""
    result = subprocess.run(
        [
            "yt-dlp", "--flat-playlist", "--print", "%(id)s\t%(title)s",
            "--no-warnings", playlist_url,
        ],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp playlist error: {result.stderr[:500]}")

    videos = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        video_id = parts[0].strip()
        title = parts[1].strip() if len(parts) > 1 else video_id
        if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            videos.append({"video_id": video_id, "title": title})
    return videos


def fetch_youtube_transcript(
    url_or_id: str,
    langs: list[str] | None = None,
) -> dict:
    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore

    langs = langs or ["vi", "en"]
    video_id = _parse_youtube_id(url_or_id)
    source_url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=langs)
        raw = fetched.to_raw_data()
    except AttributeError:
        raw = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)

    segments = []
    for item in raw:
        start = float(item["start"])
        duration = float(item.get("duration", 0.0))
        segments.append({
            "start": round(start, 3),
            "end": round(start + duration, 3),
            "text": item["text"].strip(),
        })

    title = _fetch_title_oembed(source_url) or _fetch_title_ytdlp(video_id) or video_id

    return {
        "video_id": video_id,
        "title": title,
        "segments": segments,
        "source_url": source_url,
    }
