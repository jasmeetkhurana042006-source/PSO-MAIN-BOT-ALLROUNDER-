import os
import re
import sys
import json
import shutil
import subprocess
from pathlib import Path
from pyrogram import Client

# 🔥 TELEGRAM CONFIG
API_ID = 7684469
API_HASH = "7289a31b2b539f5c92f39fa1a3c3ad6c"
SESSION = "my_session"
CHANNEL = "@PSODATABASECHANNEL"

BASE = Path("/storage/emulated/0/Download/TermuxVideoTool")
TEMP = BASE / "temp"
DOWN = BASE / "downloads"

TEMP.mkdir(parents=True, exist_ok=True)
DOWN.mkdir(parents=True, exist_ok=True)

VIDEO_EXTS = [
    ".mp4", ".mkv", ".avi", ".mov", ".webm",
    ".flv", ".wmv", ".mpg", ".mpeg", ".3gp"
]

ARCHIVES = [".zip", ".rar", ".7z"]


def pick_all_videos(folder):
    videos = []

    for root, _, files in os.walk(folder):
        for f in files:
            if any(f.lower().endswith(ext) for ext in VIDEO_EXTS):
                videos.append(Path(root) / f)

    if not videos:
        print("❌ No video found")
        sys.exit(1)

    print(f"\n🎬 Total videos found: {len(videos)}\n")
    return videos


def clean(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)[:150]


def get_name(url):
    return clean(url.split("/")[-1].split("?")[0])


# ⚡ DOWNLOAD
def download(url):
    name = get_name(url)
    path = DOWN / name

    print("\n🚀 Downloading...\n")

    subprocess.run([
        "aria2c",
        "-x", "16", "-s", "16",
        "--summary-interval=1",
        "--dir", str(DOWN),
        "--out", name,
        url
    ])

    return path


# 📦 EXTRACT
def extract(file):
    print("\n📦 Extracting...\n")

    out = TEMP / file.stem
    out.mkdir(exist_ok=True)

    subprocess.run(["7z", "x", str(file), f"-o{out}", "-y"])

    return out


# 🎧 AUDIO TRACKS WITH NAMES
def get_audio_tracks(file):
    data = subprocess.getoutput(
        f'ffprobe -v quiet -print_format json -show_streams "{file}"'
    )
    data = json.loads(data)

    tracks = []

    for s in data["streams"]:
        if s["codec_type"] == "audio":
            tracks.append({
                "index": s["index"],
                "lang": s.get("tags", {}).get("language", "unknown"),
                "title": s.get("tags", {}).get("title", ""),
                "codec": s.get("codec_name", ""),
                "channels": s.get("channels", "")
            })

    return tracks


def select_audio(tracks):
    print("\n🎧 Audio Tracks:\n")

    for i, t in enumerate(tracks):
        print(f"{i} → {t['lang']} | {t['codec']} | {t['channels']}ch | {t['title']}")

    return tracks[int(input("\nSelect audio: "))]["index"]


# ⏱️ DURATION
def get_duration(file):
    out = subprocess.getoutput(
        f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file}"'
    )
    return float(out.strip())


# ⚡ CONVERT (iOS SAFE + HIGH QUALITY + BUG FIXED)
def convert(input_file, audio_index):
    output = TEMP / "final.mp4"

    duration = get_duration(input_file)

    print("\n⚡ Converting (100% iOS Compatible + High Quality)...\n")

    cmd = [
        "ffmpeg", "-y",
        "-threads", "0",
        "-i", str(input_file),

        "-map", "0:v:0",
        "-map", f"0:{audio_index}",

        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",

        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-level", "4.1",

        "-movflags", "+faststart",

        "-c:a", "aac",
        "-b:a", "160k",
        "-ac", "2",

        "-progress", "pipe:1",
        "-nostats",

        str(output)
    ]

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)

    # 🔥 FIXED PROGRESS BAR
    for line in p.stdout:
        if "out_time_ms" in line:
            try:
                value = line.split("=")[1].strip()
                t = int(value) / 1000000
                percent = (t / duration) * 100
                print(f"📊 {percent:.2f}% ", end="\r")
            except:
                pass

    p.wait()

    print("\n✅ DONE (iOS Guaranteed + High Quality)")
    return output


# 📤 TELEGRAM UPLOAD
def upload(file):
    print("\n📤 Uploading...\n")

    app = Client(SESSION, api_id=API_ID, api_hash=API_HASH)
    app.start()

    def prog(c, t):
        print(f"📤 {(c/t)*100:.2f}% ", end="\r")

    app.send_video(
        CHANNEL,
        video=str(file),
        caption="🔥 Uploaded via FINAL TOOL",
        supports_streaming=True,
        progress=prog
    )

    app.stop()


def main():
    url = input("🔗 Enter link: ")

    file = download(url)

    # 📦 ZIP MODE
    if any(file.name.endswith(ext) for ext in ARCHIVES):
        folder = extract(file)

        videos = pick_all_videos(folder)

        print("\n🎧 Select audio (will apply to ALL videos)\n")

        tracks = get_audio_tracks(videos[0])

        if not tracks:
            print("❌ No audio found")
            sys.exit(1)

        for i, t in enumerate(tracks):
            print(f"{i} → {t['lang']} | {t['codec']} | {t['channels']}ch | {t['title']}")

        audio_index = tracks[int(input("\nSelect audio: "))]["index"]

        print("\n🚀 Processing all videos...\n")

        for i, video in enumerate(videos, start=1):
            print(f"\n🔥 ({i}/{len(videos)}) {video.name}\n")

            try:
                final = convert(video, audio_index)
                upload(final)
            except Exception as e:
                print(f"❌ Error: {e}")

    else:
        video = file

        tracks = get_audio_tracks(video)

        if not tracks:
            print("❌ No audio found")
            sys.exit(1)

        audio = select_audio(tracks)

        final = convert(video, audio)

        upload(final)

    shutil.rmtree(TEMP, ignore_errors=True)

    print("\n✅ HURRAY !! SUCCESSFULLY DONE 🎉")


if __name__ == "__main__":
    main()
