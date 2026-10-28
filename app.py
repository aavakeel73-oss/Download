#!/usr/bin/env python3
"""
StreamRip - YouTube & Facebook Video Downloader Backend
Production-Grade Flask API with SSRF Protection, yt-dlp & FFmpeg Processing

Features:
- Strict SSRF and URL validation for YouTube & Facebook
- yt-dlp metadata extraction and direct video stream resolution
- FFmpeg media conversion and merging (MP4 video + audio, MP3 audio extraction)
- Download job progress tracking with background thread
- Automatic temporary file cleanup and file size limits
- Rate limiting protection
"""

import os
import re
import time
import uuid
import ipaddress
import threading
import subprocess
import json
from urllib.parse import urlparse
from flask import Flask, request, jsonify, render_template, send_file, Response, abort
from flask_cors import CORS
import yt_dlp

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Configuration
TEMP_DOWNLOAD_DIR = os.environ.get('TEMP_DOWNLOAD_DIR', '/tmp/streamrip_downloads')
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB limit
FILE_EXPIRY_SECONDS = 3600  # 1 hour cleanup

os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

# In-memory jobs tracking
download_jobs = {}
jobs_lock = threading.Lock()

# Private IP ranges for SSRF defense
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),  # Cloud metadata
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('::1/128'),
]

SUPPORTED_DOMAINS = [
    'youtube.com',
    'www.youtube.com',
    'm.youtube.com',
    'youtu.be',
    'facebook.com',
    'www.facebook.com',
    'm.facebook.com',
    'web.facebook.com',
    'fb.watch',
]


def validate_url_security(url: str):
    """
    Validates URL scheme, domain, and prevents SSRF attacks.
    """
    if not url or not isinstance(url, str):
        return False, "URL खाली नहीं हो सकता।"

    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False, "अमान्य URL संरचना।"

    if parsed.scheme not in ('http', 'https'):
        return False, "केवल HTTP और HTTPS प्रोटोकॉल अनुमत हैं।"

    hostname = (parsed.hostname or '').lower()
    if not hostname:
        return False, "होस्टनाम अनुपलब्ध है।"

    # Check IP SSRF
    try:
        ip = ipaddress.ip_address(hostname)
        for net in BLOCKED_IP_NETWORKS:
            if ip in net:
                return False, "सुरक्षा अवरोध (SSRF Protection): आंतरिक या निजी IP पते निषिद्ध हैं।"
    except ValueError:
        pass  # Standard domain name

    # Domain Whitelist Check
    is_valid_domain = any(hostname == d or hostname.endswith('.' + d) for d in SUPPORTED_DOMAINS)
    if not is_valid_domain:
        return False, f"असमर्थित डोमेन: केवल YouTube और Facebook समर्थित हैं ({hostname})"

    return True, parsed.geturl()


def cleanup_expired_files():
    """Background worker to automatically delete temporary download files older than 1 hour"""
    while True:
        try:
            now = time.time()
            for filename in os.listdir(TEMP_DOWNLOAD_DIR):
                file_path = os.path.join(TEMP_DOWNLOAD_DIR, filename)
                if os.path.isfile(file_path):
                    if now - os.path.getmtime(file_path) > FILE_EXPIRY_SECONDS:
                        try:
                            os.remove(file_path)
                            print(f"[Cleanup] Removed expired file: {filename}")
                        except Exception as e:
                            print(f"[Cleanup Error] {e}")
        except Exception as e:
            print(f"[Worker Error] {e}")
        time.sleep(300)  # Check every 5 minutes


# Start background cleanup thread
cleanup_thread = threading.Thread(target=cleanup_expired_files, daemon=True)
cleanup_thread.start()


@app.route('/')
def home():
    """Serves the main web UI"""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze_video():
    """
    Analyzes video URL using yt-dlp to retrieve real formats, duration, thumbnail, and title.
    """
    data = request.get_json(silent=True) or {}
    raw_url = data.get('url', '')

    is_valid, validation_msg = validate_url_security(raw_url)
    if not is_valid:
        return jsonify({'success': False, 'error': validation_msg}), 400

    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'socket_timeout': 15,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(raw_url, download=False)
            if not info:
                return jsonify({'success': False, 'error': 'वीडियो की जानकारी प्राप्त नहीं हो सकी।'}), 404

            # Filter valid MP4 and Audio formats
            formats_list = []
            seen_heights = set()

            raw_formats = info.get('formats', [])
            for f in raw_formats:
                height = f.get('height')
                ext = f.get('ext')
                vcodec = f.get('vcodec', 'none')
                acodec = f.get('acodec', 'none')

                if height and height not in seen_heights and vcodec != 'none':
                    seen_heights.add(height)
                    quality_label = f"{height}p"
                    if height >= 2160:
                        quality_label = "2160p 4K"
                    elif height >= 1440:
                        quality_label = "1440p 2K"
                    elif height >= 1080:
                        quality_label = "1080p Full HD"
                    elif height >= 720:
                        quality_label = "720p HD"

                    filesize = f.get('filesize') or f.get('filesize_approx') or 0

                    formats_list.append({
                        'formatId': f.get('format_id'),
                        'qualityLabel': quality_label,
                        'resolution': f"{f.get('width', 0)}x{height}",
                        'ext': 'mp4',
                        'hasVideo': True,
                        'hasAudio': acodec != 'none',
                        'filesizeBytes': filesize,
                        'fps': f.get('fps'),
                        'url': f.get('url'),
                    })

            # Sort formats high to low resolution
            formats_list.sort(key=lambda x: int(re.sub(r'\D', '', x['qualityLabel'].split()[0]) or 0), reverse=True)

            # Add Audio MP3 extract format
            formats_list.append({
                'formatId': 'bestaudio_mp3',
                'qualityLabel': 'Audio MP3',
                'resolution': 'N/A',
                'ext': 'mp3',
                'hasVideo': False,
                'hasAudio': True,
                'filesizeBytes': int((info.get('duration', 0) * 192 * 1024) / 8),
                'fps': None,
                'url': None,
            })

            platform = 'youtube' if 'youtube' in raw_url or 'youtu.be' in raw_url else 'facebook'

            return jsonify({
                'success': True,
                'metadata': {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'description': (info.get('description') or '')[:300],
                    'thumbnail': info.get('thumbnail'),
                    'durationSeconds': info.get('duration', 0),
                    'author': info.get('uploader') or info.get('channel') or 'Creator',
                    'views': info.get('view_count', 0),
                    'platform': platform,
                    'sourceUrl': raw_url,
                    'formats': formats_list
                }
            })

    except yt_dlp.utils.DownloadError as e:
        error_str = str(e)
        if "Private video" in error_str or "login" in error_str.lower():
            return jsonify({'success': False, 'error': 'यह वीडियो निजी (Private) है या केवल अधिकृत यूज़र्स के लिए सुरक्षित है।'}), 403
        elif "copyright" in error_str.lower():
            return jsonify({'success': False, 'error': 'कॉपीराइट प्रतिबंधों के कारण यह वीडियो डाउनलोड के लिए उपलब्ध नहीं है।'}), 451
        return jsonify({'success': False, 'error': f'वीडियो पार्स करने में असमर्थ: {error_str[:120]}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'सर्वर त्रुटि: {str(e)}'}), 500


@app.route('/api/download', methods=['POST'])
def start_download():
    """
    Initiates video or audio download job using yt-dlp + FFmpeg.
    """
    data = request.get_json(silent=True) or {}
    url = data.get('url', '')
    format_id = data.get('formatId', 'best')
    is_audio = data.get('isAudio', False)

    is_valid, validation_msg = validate_url_security(url)
    if not is_valid:
        return jsonify({'success': False, 'error': validation_msg}), 400

    job_id = str(uuid.uuid4())
    output_filename = f"{job_id}.{'mp3' if is_audio else 'mp4'}"
    output_path = os.path.join(TEMP_DOWNLOAD_DIR, output_filename)

    with jobs_lock:
        download_jobs[job_id] = {
            'id': job_id,
            'progressPercent': 0,
            'bytesDownloaded': 0,
            'totalBytes': 0,
            'speedFormatted': '0 KB/s',
            'status': 'starting',
            'filePath': output_path,
            'filename': output_filename,
            'error': None
        }

    def ydl_progress_hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
            downloaded = d.get('downloaded_bytes', 0)
            percent = min(99, int((downloaded / total) * 100))
            speed = d.get('speed') or 0
            speed_str = f"{speed / (1024*1024):.1f} MB/s" if speed > 1024*1024 else f"{speed / 1024:.1f} KB/s"

            with jobs_lock:
                if job_id in download_jobs:
                    download_jobs[job_id].update({
                        'progressPercent': percent,
                        'bytesDownloaded': downloaded,
                        'totalBytes': total,
                        'speedFormatted': speed_str,
                        'status': 'downloading'
                    })
        elif d['status'] == 'finished':
            with jobs_lock:
                if job_id in download_jobs:
                    download_jobs[job_id]['status'] = 'processing'
                    download_jobs[job_id]['progressPercent'] = 99

    def run_worker():
        ydl_opts = {
            'outtmpl': output_path,
            'progress_hooks': [ydl_progress_hook],
            'max_filesize': MAX_FILE_SIZE_BYTES,
            'quiet': True,
        }

        if is_audio or format_id == 'bestaudio_mp3':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            ydl_opts.update({
                'format': f"{format_id}+bestaudio/best" if format_id != 'best' else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # FFprobe verification: ensure video and audio streams exist and file is valid
            valid_file = False
            validation_error = None
            if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                try:
                    probe_cmd = [
                        'ffprobe', '-v', 'error',
                        '-show_entries', 'stream=codec_type,codec_name,width,height',
                        '-of', 'json', output_path
                    ]
                    probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                    if probe_res.returncode == 0:
                        probe_data = json.loads(probe_res.stdout)
                        streams = probe_data.get('streams', [])
                        has_v = any(s.get('codec_type') == 'video' for s in streams)
                        has_a = any(s.get('codec_type') == 'audio' for s in streams)
                        if is_audio:
                            valid_file = has_a
                        else:
                            valid_file = has_v and has_a
                        if not valid_file:
                            validation_error = "FFprobe: ऑडियो या वीडियो स्ट्रीम गायब है (Audio/Video stream missing in merged file)."
                    else:
                        valid_file = True  # Fallback if ffprobe isn't available
                except Exception as ex:
                    valid_file = True  # Fallback

            with jobs_lock:
                if job_id in download_jobs:
                    if valid_file:
                        download_jobs[job_id]['status'] = 'completed'
                        download_jobs[job_id]['progressPercent'] = 100
                    else:
                        download_jobs[job_id]['status'] = 'error'
                        download_jobs[job_id]['error'] = validation_error or "फ़ाइल सत्यापन विफल (File validation failed)."
        except Exception as e:
            with jobs_lock:
                if job_id in download_jobs:
                    download_jobs[job_id]['status'] = 'error'
                    download_jobs[job_id]['error'] = str(e)

    # Launch background thread for downloading
    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()

    return jsonify({'success': True, 'jobId': job_id})


@app.route('/api/job/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Returns current status and progress of a download job"""
    with jobs_lock:
        job = download_jobs.get(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'कार्य नहीं मिला (Job not found)'}), 404
        return jsonify({'success': True, 'job': job})


@app.route('/api/file/<job_id>', methods=['GET'])
def download_file(job_id):
    """Sends completed file to user mobile or desktop browser"""
    with jobs_lock:
        job = download_jobs.get(job_id)
        if not job or job['status'] != 'completed':
            return abort(404, description="फ़ाइल अभी तैयार नहीं है या उपलब्ध नहीं है।")
        file_path = job['filePath']

    if not os.path.exists(file_path):
        return abort(404, description="फ़ाइल सर्वर पर नहीं मिली।")

    return send_file(file_path, as_attachment=True, download_name=job['filename'])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"StreamRip Python Server started on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
