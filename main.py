# mp3 downloader for server
# Does not belong in the current architecture
#
# Output is organized for Jellyfin:
#
#   downloads/
#   └── Artist/
#       └── Album/            (Singles when the video has no album)
#           └── Title.mp3
#
# Todo: Add .csv file support with argparse

import re
import shutil
import sys

from yt_dlp import YoutubeDL
from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import DownloadError

OUT_DIR = "downloads"
ARCHIVE_FILE = "downloaded.txt"   # remembers finished videos, skips them on re-run
UNKNOWN_ARTIST = "Unknown Artist"
SINGLES_ALBUM = "Singles"

# MP3 conversion needs FFmpeg
if not shutil.which("ffmpeg"):
    sys.exit("FFmpeg not found. Install it first (e.g. 'sudo apt install ffmpeg').")


def clean_artist(name):
    """Strip YouTube auto-channel suffixes like ' - Topic' and 'VEVO'."""
    if not name:
        return None
    name = re.sub(r"\s*-\s*Topic$", "", name, flags=re.I)
    name = re.sub(r"VEVO$", "", name, flags=re.I).strip()
    return name or None


def first_artist(name):
    """Jellyfin groups best under a single artist folder, so use the first."""
    return re.split(r",|\s+&\s+|\s+feat\.?\s+|\s+ft\.?\s+", name,
                    maxsplit=1, flags=re.I)[0].strip()


def enrich(info):
    """Work out artist / album / title and add the fields the template uses."""
    title = info.get("track") or info.get("title") or "Untitled"
    artist = info.get("artist") or info.get("creator")

    # No artist tag? Try to parse "Artist - Title" from the video title
    if not artist:
        m = re.match(r"^(.+?)\s+-\s+(.+)$", title)
        if m:
            artist, title = m.group(1).strip(), m.group(2).strip()

    if not artist:
        artist = clean_artist(info.get("uploader") or info.get("channel"))

    artist = artist or UNKNOWN_ARTIST
    album = info.get("album") or SINGLES_ALBUM

    # Tags written into the MP3 (FFmpegMetadata reads these)
    info["title"] = title
    info["artist"] = artist
    info["album"] = album
    info["album_artist"] = first_artist(artist)

    # Fields used by outtmpl (yt-dlp sanitizes path separators in these)
    info["dir_artist"] = info["album_artist"]
    info["dir_album"] = album
    return info


class EnrichPP(PostProcessor):
    """
    Runs enrich() on the FRESH info yt-dlp extracts at download time, so the
    download itself stays a plain ydl.download() call (re-extracting gives
    new, valid stream URLs instead of possibly expired ones -> no 403).
    """

    def run(self, info):
        enrich(info)
        return [], info


# Get the video URLs
raw = input("You can download multiple separated by spaces. Enter the video URL(s): ")
urls = raw.split()

if not urls:
    sys.exit("No URL entered.")

# Show info for each URL (skip ones that fail instead of crashing)
info_opts = {"quiet": True, "no_warnings": True, "noplaylist": True}
valid_urls = []

with YoutubeDL(info_opts) as ydl:
    for video_url in urls:
        try:
            info = ydl.extract_info(video_url, download=False)
        except DownloadError as e:
            print(f"\nSkipping {video_url}: {e}\n")
            continue

        if info is None:
            continue

        info = enrich(info)   # preview only; not reused for the download

        print("=" * 60)
        print("Title:  ", info["title"])
        print("Artist: ", info["artist"])
        print("Album:  ", info["album"])
        print("Views:  ", info.get("view_count", "N/A"))
        print("Saves to:", f"{OUT_DIR}/{info['dir_artist']}/{info['dir_album']}/")
        print("=" * 60)
        valid_urls.append(video_url)

if not valid_urls:
    sys.exit("No valid URLs to download.")

# Ask user if they want to download
answer = input("Do you want to download the video(s)? (y/n): ").strip().lower()

if answer in ("y", "yes"):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{OUT_DIR}/%(dir_artist)s/%(dir_album)s/%(title)s.%(ext)s",
        # Keeps accents/non-ASCII, only strips characters illegal on Windows
        "windowsfilenames": True,
        "noplaylist": True,          # only the single video, not the whole playlist
        "download_archive": ARCHIVE_FILE,
        "writethumbnail": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            },
            # Convert webp -> jpg so it can be embedded
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail"},
        ],
        # Center-crop the 16:9 thumbnail to a square cover
        "postprocessor_args": {
            "thumbnailsconvertor+ffmpeg_o": [
                "-c:v", "mjpeg",
                "-vf", "crop='if(gt(ih,iw),iw,ih)':'if(gt(iw,ih),ih,iw)'",
            ],
        },
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.add_post_processor(EnrichPP(ydl), when="pre_process")
        for video_url in valid_urls:
            try:
                ydl.download([video_url])   # original core download call
            except DownloadError as e:
                print(f"Failed to download {video_url}: {e}")

    print(f"Done. Files are in the '{OUT_DIR}' folder.")
else:
    print("Download canceled.")