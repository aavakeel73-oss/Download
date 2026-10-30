#!/usr/bin/env python3
"""StreamRip Flask API. Existing routes and response fields retained."""
import ipaddress
import json
import os
import re
import shutil
import socket
import tempfile
import threading
import time
import uuid
from urllib.parse import urlsplit
from flask import Flask, request, jsonify, render_template, send_file, abort
from flask_cors import CORS
import yt_dlp
from video_processor import analyze_video as analyze_youtube, error_result, run_ffprobe_validation, safe_log

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)
TEMP_DOWNLOAD_DIR = os.environ.get('TEMP_DOWNLOAD_DIR', '/tmp/streamrip_downloads')
MAX_FILE_SIZE_BYTES = int(os.environ.get('MAX_MEDIA_MB', '500')) * 1024 * 1024
FILE_EXPIRY_SECONDS = 3600
MAX_JOBS = 20
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
download_jobs = {}
jobs_lock = threading.Lock()
YOUTUBE_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'www.youtu.be'}
FACEBOOK_HOSTS = {'facebook.com', 'www.facebook.com', 'm.facebook.com', 'web.facebook.com', 'fb.watch'}


def validate_url_security(url):
    if not isinstance(url, str) or not url or len(url) > 2048:
        return False, 'मान्य URL दें।'
    try:
        parsed = urlsplit(url.strip())
        host = (parsed.hostname or '').lower().rstrip('.')
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
            return False, 'केवल मान्य HTTPS लिंक स्वीकार हैं।'
        if host not in YOUTUBE_HOSTS | FACEBOOK_HOSTS:
            return False, 'केवल YouTube और Facebook लिंक स्वीकार हैं।'
        # Resolve the approved host to reject local/private destination addresses.
        for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
            ip = ipaddress.ip_address(item[4][0])
            if not ip.is_global:
                return False, 'असुरक्षित नेटवर्क पता मिला।'
        return True, parsed.geturl()
    except (ValueError, OSError, TypeError):
        return False, 'लिंक या नेटवर्क पता मान्य नहीं है।'


def cleanup_expired_files():
    while True:
        try:
            now = time.time()
            with jobs_lock:
                for job_id, job in list(download_jobs.items()):
                    if now - job['createdAt'] > FILE_EXPIRY_SECONDS:
                        if job['status'] not in ('starting', 'downloading', 'processing'):
                            download_jobs.pop(job_id, None)
            for filename in os.listdir(TEMP_DOWNLOAD_DIR):
                path = os.path.join(TEMP_DOWNLOAD_DIR, filename)
                if os.path.isfile(path) and now - os.path.getmtime(path) > FILE_EXPIRY_SECONDS:
                    os.remove(path)
        except Exception as exc:
            safe_log('WARN', 'Cleanup failed', {'exception_type': type(exc).__name__})
        time.sleep(300)


threading.Thread(target=cleanup_expired_files, daemon=True).start()


def build_formats(info):
    formats = []
    heights = set()
    candidates = sorted((f for f in (info.get('formats') or []) if isinstance(f, dict)),
                        key=lambda f: (f.get('height') or 0, f.get('tbr') or 0), reverse=True)
    for f in candidates:
        height = f.get('height')
        if not isinstance(height, int) or height <= 0 or height in heights or f.get('vcodec') in (None, 'none'):
            continue
        heights.add(height)
        label = f'{height}p'
        if height == 2160:
            label = '2160p 4K'
        elif height == 1440:
            label = '1440p 2K'
        elif height == 1080:
            label = '1080p Full HD'
        elif height == 720:
            label = '720p HD'
        formats.append({'formatId': str(f.get('format_id') or 'best'), 'qualityLabel': label,
                        'resolution': f"{f.get('width') or 0}x{height}", 'ext': 'mp4',
                        'hasVideo': True, 'hasAudio': f.get('acodec') not in (None, 'none'),
                        'filesizeBytes': f.get('filesize') or f.get('filesize_approx') or 0,
                        'fps': f.get('fps')})
    if any(f.get('acodec') not in (None, 'none') for f in (info.get('formats') or []) if isinstance(f, dict)):
        formats.append({'formatId': 'bestaudio_mp3', 'qualityLabel': 'Audio MP3',
                        'resolution': 'N/A', 'ext': 'mp3', 'hasVideo': False, 'hasAudio': True,
                        'filesizeBytes': int((info.get('duration') or 0) * 192000 / 8), 'fps': None})
    return formats


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze_route():
    data = request.get_json(silent=True) or {}
    valid, result = validate_url_security(data.get('url'))
    if not valid:
        return jsonify({'success': False, 'error': result}), 400
    host = urlsplit(result).hostname
    try:
        if host in YOUTUBE_HOSTS:
            analysis = analyze_youtube(result)
            if not analysis['success']:
                return jsonify({k: v for k, v in analysis.items() if k != 'statusCode'}), analysis.get('statusCode', 502)
            info = analysis['info']
            platform = 'youtube'
        else:
            # Facebook's established yt-dlp extraction path remains unchanged.
            with yt_dlp.YoutubeDL({'skip_download': True, 'quiet': True, 'no_warnings': True,
                                   'extract_flat': False, 'socket_timeout': 15}) as ydl:
                info = ydl.extract_info(result, download=False)
            platform = 'facebook'
        if not isinstance(info, dict):
            return jsonify({'success': False, 'error': 'वीडियो जानकारी नहीं मिली।'}), 404
        return jsonify({'success': True, 'metadata': {
            'id': info.get('id'), 'title': info.get('title'),
            'description': (info.get('description') or '')[:300],
            'thumbnail': info.get('thumbnail'), 'durationSeconds': info.get('duration') or 0,
            'author': info.get('uploader') or info.get('channel') or 'Creator',
            'views': info.get('view_count') or 0, 'platform': platform,
            'sourceUrl': result, 'formats': build_formats(info)}})
    except yt_dlp.utils.DownloadError as exc:
        error = error_result(exc)
        return jsonify({'success': False, 'error': error['error'], 'errorCode': error['errorCode']}), error['statusCode']
    except Exception as exc:
        safe_log('ERROR', 'Analysis exception', {'exception_type': type(exc).__name__})
        return jsonify({'success': False, 'error': 'सर्वर पर विश्लेषण विफल हुआ।'}), 502


def update_job(job_id, **fields):
    with jobs_lock:
        if job_id in download_jobs:
            download_jobs[job_id].update(fields)


@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.get_json(silent=True) or {}
    valid, result = validate_url_security(data.get('url'))
    if not valid:
        return jsonify({'success': False, 'error': result}), 400
    format_id = str(data.get('formatId') or 'best')
    if len(format_id) > 80 or not re.fullmatch(r'[A-Za-z0-9_.+-]+', format_id):
        return jsonify({'success': False, 'error': 'अमान्य क्वालिटी विकल्प।'}), 400
    is_audio = data.get('isAudio') is True or format_id == 'bestaudio_mp3'
    with jobs_lock:
        active = sum(j['status'] in ('starting', 'downloading', 'processing') for j in download_jobs.values())
        if active >= MAX_JOBS:
            return jsonify({'success': False, 'error': 'सर्वर व्यस्त है। बाद में प्रयास करें।'}), 429
        job_id = str(uuid.uuid4())
        filename = f'{job_id}.{"mp3" if is_audio else "mp4"}'
        download_jobs[job_id] = {'id': job_id, 'progressPercent': 0, 'bytesDownloaded': 0,
                                 'totalBytes': 0, 'speedFormatted': '0 KB/s', 'status': 'starting',
                                 'filePath': os.path.join(TEMP_DOWNLOAD_DIR, filename),
                                 'filename': filename, 'error': None, 'createdAt': time.time()}

    def hook(event):
        if event.get('status') == 'downloading':
            total = event.get('total_bytes') or event.get('total_bytes_estimate') or 0
            current = event.get('downloaded_bytes') or 0
            speed = event.get('speed') or 0
            update_job(job_id, progressPercent=min(99, int(current / total * 100)) if total else 0,
                       bytesDownloaded=current, totalBytes=total,
                       speedFormatted=f'{speed / 1048576:.1f} MB/s' if speed >= 1048576 else f'{speed / 1024:.1f} KB/s',
                       status='downloading')
        elif event.get('status') == 'finished':
            update_job(job_id, progressPercent=99, status='processing')

    def worker():
        base = os.path.join(TEMP_DOWNLOAD_DIR, job_id)
        output = base + ('.mp3' if is_audio else '.mp4')
        options = {'outtmpl': base + '.%(ext)s', 'progress_hooks': [hook], 'max_filesize': MAX_FILE_SIZE_BYTES,
                   'quiet': True, 'no_warnings': True, 'noplaylist': True, 'socket_timeout': 20,
                   'merge_output_format': 'mp4'}
        if is_audio:
            options.update({'format': 'bestaudio/best', 'postprocessors': [
                {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]})
        else:
            options['format'] = ('bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
                                 if format_id == 'best' else f'{format_id}+bestaudio/{format_id}')
            # Recode only when necessary, to preserve working Facebook audio and MP4 compatibility.
            options['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([result])
            ok, details = run_ffprobe_validation(output)
            if not ok:
                raise ValueError(str(details))
            if is_audio and not details['has_audio']:
                raise ValueError('ऑडियो स्ट्रीम गायब है।')
            if not is_audio and not (details['has_video'] and details['has_audio']):
                raise ValueError('वीडियो या ऑडियो स्ट्रीम गायब है।')
            if os.path.getsize(output) > MAX_FILE_SIZE_BYTES:
                raise ValueError('फ़ाइल आकार सीमा से अधिक है।')
            update_job(job_id, status='completed', progressPercent=100, filePath=output)
        except Exception as exc:
            message = error_result(exc)['error'] if 'bot' in str(exc).lower() or 'sign in' in str(exc).lower() else 'डाउनलोड या फ़ाइल सत्यापन विफल हुआ।'
            safe_log('WARN', 'Download job failed', {'exception_type': type(exc).__name__})
            update_job(job_id, status='error', error=message)
            for name in os.listdir(TEMP_DOWNLOAD_DIR):
                if name.startswith(job_id):
                    try:
                        os.remove(os.path.join(TEMP_DOWNLOAD_DIR, name))
                    except OSError:
                        pass

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({'success': True, 'jobId': job_id})


@app.route('/api/job/<job_id>')
def get_job_status(job_id):
    with jobs_lock:
        job = download_jobs.get(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'कार्य नहीं मिला।'}), 404
        public_job = {k: v for k, v in job.items() if k not in ('filePath', 'createdAt')}
    return jsonify({'success': True, 'job': public_job})


@app.route('/api/file/<job_id>')
def download_file(job_id):
    with jobs_lock:
        job = download_jobs.get(job_id)
        if not job or job['status'] != 'completed':
            abort(404, description='फ़ाइल तैयार नहीं है।')
        path, filename = job['filePath'], job['filename']
    if not os.path.isfile(path):
        abort(404, description='फ़ाइल नहीं मिली।')
    return send_file(path, as_attachment=True, download_name=filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '10000')), debug=False)
    
