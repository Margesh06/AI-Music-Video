import os
import requests
from flask import Flask, request, jsonify, send_from_directory, render_template
from moviepy.editor import VideoFileClip, AudioFileClip
import json
from dotenv import load_dotenv
import random

load_dotenv()
app = Flask(__name__)

# Paths
VIDEOS_PATH = "videos"
MUSIC_PATH = "music"
os.makedirs(VIDEOS_PATH, exist_ok=True)
os.makedirs(MUSIC_PATH, exist_ok=True)

# Pexels API Details
PEXELS_API_URL = "https://api.pexels.com/videos/search"
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

# Soundstripe API Details
SOUNDSTRIPE_API_URL = "https://api.soundstripe.com/v1/songs"
SOUNDSTRIPE_API_KEY = os.getenv("SOUNDSTRIPE_API_KEY")


def download_video_from_pexels(query, download_path):
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 3}  

    try:
        response = requests.get(PEXELS_API_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        if not data["videos"]:
            print(f"No videos found for query: {query}")
            return None

        video = random.choice(data["videos"])
        video_url = video["video_files"][0]["link"]
        video_file_path = os.path.join(download_path, f"{query}_video.mp4")

        video_data = requests.get(video_url).content
        with open(video_file_path, "wb") as video_file:
            video_file.write(video_data)

        re_encoded_video = re_encode_video(video_file_path)
        return re_encoded_video
    except requests.exceptions.RequestException as e:
        print(f"Error fetching video: {e}")
        return None


def re_encode_video(video_file_path):
    try:
        clip = VideoFileClip(video_file_path)
        output_path = video_file_path.replace(".mp4", "_encoded.mp4")

        clip.write_videofile(output_path, codec="libx264", audio_codec="aac", threads=4)
        return output_path
    except Exception as e:
        print(f"Error re-encoding video: {e}")
        return None


@app.route("/")
def index():
    return render_template("index.html")


def fetch_music_from_soundstripe(query: str) -> str:
    headers = {
        "accept": "application/json",
        "Content-Type": "application/vnd.api+json",
        "Authorization": f"Token {SOUNDSTRIPE_API_KEY}",
    }
    params = {"search": query, "limit": 3}  

    try:
        response = requests.get(SOUNDSTRIPE_API_URL, headers=headers, params=params)
        response.raise_for_status()

        response_json = response.json()
        with open("soundstripe_response.json", "w") as json_file:
            json.dump(response_json, json_file, indent=4)

        # Randomly select one track
        tracks = [
            item for item in response_json["included"]
            if item["type"] == "audio_files" and "versions" in item["attributes"]
        ]
        if not tracks:
            print("No valid audio files found.")
            return None

        track = random.choice(tracks)
        mp3_url = track["attributes"]["versions"]["mp3"]

        music_file_path = os.path.join(MUSIC_PATH, f"{query}_music.mp3")
        download_response = requests.get(mp3_url, stream=True)

        if download_response.status_code == 200:
            with open(music_file_path, "wb") as file:
                for chunk in download_response.iter_content(chunk_size=1024):
                    if chunk:
                        file.write(chunk)
            print(f"Music downloaded successfully: {music_file_path}")
            return music_file_path
        else:
            print(f"Failed to download MP3: {download_response.status_code}")
            return None
    except (requests.exceptions.RequestException, KeyError, StopIteration) as e:
        print(f"Error fetching music: {e}")
        return None


def create_video_with_music(video_file, music_file):
    try:
        video_clip = VideoFileClip(video_file)
        audio_clip = AudioFileClip(music_file)

        # Set audio duration to match video duration
        final_audio = audio_clip.set_duration(video_clip.duration)
        final_video = video_clip.set_audio(final_audio)

        final_video_path = video_file.replace(".mp4", "_final.mp4")
        final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac", threads=4)

        print(f"Final video created: {final_video_path}")
        return final_video_path
    except Exception as e:
        print(f"Error creating final video: {e}")
        return None


@app.route("/generate", methods=["POST"])
def generate():
    query = request.form.get("query")

    video_file = download_video_from_pexels(query, VIDEOS_PATH)
    if not video_file:
        return jsonify({"error": "Failed to fetch video. Please try again."}), 500

    music_file = fetch_music_from_soundstripe(query)
    if not music_file:
        return jsonify({"error": "Failed to fetch music. Please try again."}), 500

    # Combine video and music to create the final video
    final_video = create_video_with_music(video_file, music_file)
    if not final_video:
        return jsonify({"error": "Failed to create final video."}), 500

    video_filename = os.path.basename(final_video)
    video_url = f"/download/{video_filename}"

    return render_template("index.html", video_url=video_url)


@app.route("/download/<filename>")
def download(filename):
    return send_from_directory(VIDEOS_PATH, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
    # app.run(debug=True)
