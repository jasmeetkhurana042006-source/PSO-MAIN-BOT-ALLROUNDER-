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

# ✅ AUTO PATH (Termux + VS Code both support)
BASE = Path("./TermuxVideoTool")
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
    return clean(url.split("/")[-1].split("?")[0]) or "video"


# ⚡ DOWNLOAD
def download(url):
    name = get_name(url)
    path = DOWN / name

    print("\n🚀 Downloading...\n")

    result = subprocess.run([
        "aria2c",
        "-x", "16", "-s", "16",
        "--dir", str(DOWN),
        "--out", name,
        url
    ])

    if result.returncode != 0 or not path.exists():
        print("❌ Download failed")
        sys.exit(1)

    return path


# 📦 EXTRACT
def extract(file):
    print("\n📦 Extracting...\n")

    out = TEMP / file.stem
    out.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(["7z", "x", str(file), f"-o{out}", "-y"])

    if result.returncode != 0:
        print("❌ Extraction failed")
        sys.exit(1)

    return out


# 🎧 FIXED AUDIO TRACKS
def get_audio_tracks(file):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_streams",
        str(file)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0 or not result.stdout.strip():
        print("❌ FFprobe failed")
        return []

    try:
        data = json.loads(result.stdout)
    except:
        print("❌ JSON parse error")
        return []

    tracks = []

    for s in data.get("streams", []):
        if s.get("codec_type") == "audio":
            tracks.append({
                "index": s.get("index"),
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

    while True:
        choice = input("\nSelect audio: ")
        if choice.isdigit() and 0 <= int(choice) < len(tracks):
            return tracks[int(choice)]["index"]
        print("❌ Invalid choice")


# ⏱️ DURATION SAFE
def get_duration(file):
    try:
        out = subprocess.getoutput(
            f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{file}"'
        )
        return float(out.strip())
    except:
        return 1.0


# ⚡ CONVERT (FINAL STABLE)
def convert(input_file, audio_index):
    output = TEMP / "final.mp4"

    duration = get_duration(input_file)

    print("\n⚡ Converting (iOS Compatible + Stable)...\n")

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

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)

    for line in p.stdout:
        if "out_time_ms" in line:
            try:
                val = line.split("=")[1].strip()
                if val.isdigit():
                    t = int(val) / 1000000
                    percent = (t / duration) * 100
                    print(f"📊 {percent:.2f}% ", end="\r")
            except:
                pass

    p.wait()

    if not output.exists():
        print("❌ Conversion failed")
        sys.exit(1)

    print("\n✅ DONE")
    return output


# 📤 TELEGRAM UPLOAD
def upload(file):
    print("\n📤 Uploading...\n")

    app = Client(SESSION, api_id=API_ID, api_hash=API_HASH)
    app.start()

    def prog(c, t):
        try:
            print(f"📤 {(c/t)*100:.2f}% ", end="\r")
        except:
            pass

    app.send_video(
        CHANNEL,
        video=str(file),
        caption="🔥 Uploaded via FINAL TOOL",
        supports_streaming=True,
        progress=prog
    )

    app.stop()


def main():
    url = input("🔗 Enter link: ").strip()

    file = download(url)

    if any(file.name.lower().endswith(ext) for ext in ARCHIVES):
        folder = extract(file)
        videos = pick_all_videos(folder)

        tracks = get_audio_tracks(videos[0])
        if not tracks:
            print("❌ No audio")
            sys.exit(1)

        audio_index = select_audio(tracks)

        for video in videos:
            final = convert(video, audio_index)
            upload(final)

    else:
        video = file
        tracks = get_audio_tracks(video)

        if not tracks:
            print("❌ No audio")
            sys.exit(1)

        audio = select_audio(tracks)
        final = convert(video, audio)
        upload(final)

    shutil.rmtree(TEMP, ignore_errors=True)

    print("\n✅ DONE 🎉")


if __name__ == "__main__":
    main()
