# mp3 downloader for server
# Dose not belong in the current achitecture

#Todo: Add .csv file support with argparse 


import shutil
import sys

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

# MP3 conversion needs FFmpeg
if not shutil.which("ffmpeg"):
    sys.exit("FFmpeg not found. Install it first (e.g. 'sudo apt install ffmpeg').")

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

        print("=" * 60)
        print("Title:", info.get("title", "N/A"))
        print("=" * 60)
        print("Creator:", info.get("creator", "N/A"))
        print("=" * 60)
        print("Views:", info.get("view_count", "N/A"))
        print("=" * 60)
        valid_urls.append(video_url)

if not valid_urls:
    sys.exit("No valid URLs to download.")

# Ask user if they want to download
answer = input("Do you want to download the video(s)? (y/n): ").strip().lower()

if answer in ("y", "yes"):
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
        "restrictfilenames": True,   # safe filenames (no spaces/special chars)
        "noplaylist": True,          # only the single video, not the whole playlist
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "320",
        }],
    }

    with YoutubeDL(ydl_opts) as ydl:
        for video_url in valid_urls:
            try:
                ydl.download([video_url])
            except DownloadError as e:
                print(f"Failed to download {video_url}: {e}")

    print("Done. Files are in the 'downloads' folder.")
else:
    print("Download canceled.")