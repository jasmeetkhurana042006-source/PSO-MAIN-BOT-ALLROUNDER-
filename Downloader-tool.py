import os
import re
import sys
import json
import shutil
import subprocess
import time
from pathlib import Path
from pyrogram import Client
from concurrent.futures import ThreadPoolExecutor

API_ID = 7684469
API_HASH = "7289a31b2b539f5c92f39fa1a3c3ad6c"
SESSION = "my_session"
CHANNEL = "@PSODATABASECHANNEL"

BASE = Path("./TermuxVideoTool")
TEMP = BASE / "temp"
DOWN = BASE / "downloads"

TEMP.mkdir(parents=True, exist_ok=True)
DOWN.mkdir(parents=True, exist_ok=True)

VIDEO_EXTS = [".mp4",".mkv",".avi",".mov",".webm",".flv",".wmv",".mpg",".mpeg",".3gp"]
ARCHIVES = [".zip",".rar",".7z"]

MAX_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

# ---------------------

def clean(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)[:150]

def get_name(url):
    return clean(url.split("/")[-1].split("?")[0]) or "video"

# ---------------------

def download(url):
    name = get_name(url)
    path = DOWN / name

    print("\n🚀 Downloading...\n")

    subprocess.run([
        "aria2c",
        "-x","16","-s","16",
        "--summary-interval=1",
        "--dir",str(DOWN),
        "--out",name,
        url
    ])

    return path

# ---------------------

def extract(file):
    print("\n📦 Extracting...\n")
    out = TEMP / file.stem
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run(["7z","x",str(file),f"-o{out}","-y"])
    return out

# ---------------------

def pick_all_videos(folder):
    videos=[]
    for root,_,files in os.walk(folder):
        for f in files:
            if any(f.lower().endswith(ext) for ext in VIDEO_EXTS):
                videos.append(Path(root)/f)

    if not videos:
        print("❌ No video found")
        sys.exit(1)

    return videos

# ---------------------

def get_audio_tracks(file):
    result = subprocess.run(
        ["ffprobe","-v","error","-print_format","json","-show_streams",str(file)],
        capture_output=True,text=True
    )

    if result.returncode != 0:
        return []

    data = json.loads(result.stdout)

    tracks=[]
    for s in data.get("streams",[]):
        if s.get("codec_type")=="audio":
            tracks.append({
                "index": s["index"],
                "lang": s.get("tags",{}).get("language","audio"),
            })
    return tracks

# ---------------------

def ffmpeg_progress(process, duration):
    while True:
        line = process.stderr.readline().decode("utf-8", errors="ignore")
        if not line:
            break

        if "time=" in line:
            try:
                t = line.split("time=")[1].split(" ")[0]
                h, m, s = t.split(":")
                current = int(h)*3600 + int(m)*60 + float(s)

                percent = (current / duration) * 100
                bar = "█" * int(percent//5) + "░"*(20-int(percent//5))

                print(f"\r🎬 FFmpeg: {percent:.2f}% {bar}", end="")
            except:
                pass

# ---------------------

def get_duration(file):
    result = subprocess.run(
        ["ffprobe","-v","error",
         "-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1",
         str(file)],
        capture_output=True,text=True
    )
    return float(result.stdout.strip())

# ---------------------

def process_audio(input_file, track, duration):
    audio_index = track["index"]
    lang = track["lang"]

    output = TEMP / f"{input_file.stem}_{lang}.mp4"

    print(f"\n⚙️ Processing: {lang}\n")

    cmd = [
        "ffmpeg","-y",
        "-i",str(input_file),
        "-map","0:v:0",
        "-map",f"0:{audio_index}",
        "-c:v","copy",
        "-c:a","aac","-b:a","128k",
        "-movflags","+faststart",
        str(output)
    ]

    process = subprocess.Popen(cmd, stderr=subprocess.PIPE)

    ffmpeg_progress(process, duration)

    process.wait()

    print("\n✅ Done:", lang)

    return output, lang

# ---------------------

def split_video(file):
    print("\n📦 Splitting if needed...\n")

    if os.path.getsize(file) <= MAX_SIZE:
        return [file]

    parts = []
    part_num = 1

    cmd = [
        "ffmpeg","-i",str(file),
        "-c","copy",
        "-map","0",
        "-segment_time","1800",
        "-f","segment",
        str(file.with_name(file.stem + "_part_%03d.mp4"))
    ]

    subprocess.run(cmd)

    for f in file.parent.glob(file.stem + "_part_*.mp4"):
        parts.append(f)

    return sorted(parts)

# ---------------------

def progress(current, total, start, action):
    now = time.time()
    diff = now - start

    if diff < 1:
        return

    speed = current / diff
    percentage = current * 100 / total

    bar = "█"*int(percentage//5)+"░"*(20-int(percentage//5))

    print(f"\r📤 {percentage:.2f}% {bar} {speed/1024/1024:.2f} MB/s", end="")

# ---------------------

def upload(file, caption):
    app = Client(SESSION,api_id=API_ID,api_hash=API_HASH)
    app.start()

    start = time.time()

    print("\n📤 Uploading...\n")

    app.send_video(
        CHANNEL,
        video=str(file),
        caption=caption,
        supports_streaming=True,
        progress=progress,
        progress_args=(start,"UPLOAD")
    )

    print("\n✅ Uploaded\n")

    app.stop()

# ---------------------

def main():
    url = input("🔗 Enter link: ").strip()
    file = download(url)

    if any(file.name.endswith(ext) for ext in ARCHIVES):
        folder = extract(file)
        videos = pick_all_videos(folder)
    else:
        videos = [file]

    for video in videos:
        tracks = get_audio_tracks(video)
        duration = get_duration(video)

        print(f"\n🎧 Total Audios: {len(tracks)}\n")

        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(
                lambda t: process_audio(video, t, duration),
                tracks
            ))

        for out, lang in results:
            parts = split_video(out)

            for i, part in enumerate(parts,1):
                caption = f"""🎬 {video.name}

🎧 Audio: {lang.upper()}
📦 Part {i}/{len(parts)}

⚡ Powered by Tool"""

                upload(part, caption)

    shutil.rmtree(TEMP,ignore_errors=True)

    print("\n🔥 ALL DONE 🔥")

# ---------------------

if __name__ == "__main__":
    main()