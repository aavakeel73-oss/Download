/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import JSZip from 'jszip';

export async function generateProjectZip(): Promise<Blob> {
  const zip = new JSZip();

  // Python Flask backend
  const appPyContent = `#!/usr/bin/env python3
"""
StreamRip - YouTube & Facebook Video Downloader Backend
Production Flask API with SSRF Protection, yt-dlp & FFmpeg
"""
import os
import re
import time
import uuid
import ipaddress
import threading
from urllib.parse import urlparse
from flask import Flask, request, jsonify, render_template, send_file, abort
from flask_cors import CORS
import yt_dlp

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

TEMP_DOWNLOAD_DIR = os.environ.get('TEMP_DOWNLOAD_DIR', '/tmp/streamrip_downloads')
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024
os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)

download_jobs = {}
jobs_lock = threading.Lock()

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('::1/128'),
]

SUPPORTED_DOMAINS = [
    'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
    'facebook.com', 'www.facebook.com', 'm.facebook.com', 'fb.watch'
]

def validate_url_security(url: str):
    if not url:
        return False, "URL खाली नहीं हो सकता।"
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False, "अमान्य URL संरचना।"
    if parsed.scheme not in ('http', 'https'):
        return False, "केवल HTTP और HTTPS प्रोटोकॉल अनुमत हैं।"
    hostname = (parsed.hostname or '').lower()
    try:
        ip = ipaddress.ip_address(hostname)
        for net in BLOCKED_IP_NETWORKS:
            if ip in net:
                return False, "सुरक्षा अवरोध (SSRF Protection): आंतरिक IP निषिद्ध हैं।"
    except ValueError:
        pass
    is_valid_domain = any(hostname == d or hostname.endswith('.' + d) for d in SUPPORTED_DOMAINS)
    if not is_valid_domain:
        return False, f"असमर्थित डोमेन: केवल YouTube व Facebook अनुमत हैं ({hostname})"
    return True, parsed.geturl()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze_video():
    data = request.get_json(silent=True) or {}
    raw_url = data.get('url', '')
    is_valid, msg = validate_url_security(raw_url)
    if not is_valid:
        return jsonify({'success': False, 'error': msg}), 400

    ydl_opts = {'skip_download': True, 'quiet': True, 'no_warnings': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(raw_url, download=False)
            formats_list = []
            seen = set()
            for f in info.get('formats', []):
                h = f.get('height')
                if h and h not in seen and f.get('vcodec') != 'none':
                    seen.add(h)
                    formats_list.append({
                        'formatId': f.get('format_id'),
                        'qualityLabel': f"{h}p" if h < 720 else ("720p HD" if h == 720 else ("1080p Full HD" if h == 1080 else f"{h}p")),
                        'resolution': f"{f.get('width', 0)}x{h}",
                        'ext': 'mp4',
                        'filesizeBytes': f.get('filesize') or f.get('filesize_approx') or 0,
                    })
            formats_list.sort(key=lambda x: int(re.sub(r'\\D', '', x['qualityLabel'].split()[0]) or 0), reverse=True)
            return jsonify({
                'success': True,
                'metadata': {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'thumbnail': info.get('thumbnail'),
                    'durationSeconds': info.get('duration', 0),
                    'author': info.get('uploader') or 'Creator',
                    'formats': formats_list
                }
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '')
    format_id = data.get('formatId', 'best')
    is_audio = data.get('isAudio', False)
    is_valid, msg = validate_url_security(url)
    if not is_valid:
        return jsonify({'success': False, 'error': msg}), 400

    job_id = str(uuid.uuid4())
    output_filename = f"{job_id}.{'mp3' if is_audio else 'mp4'}"
    output_path = os.path.join(TEMP_DOWNLOAD_DIR, output_filename)

    with jobs_lock:
        download_jobs[job_id] = {
            'progressPercent': 0, 'speedFormatted': 'प्रारंभ...',
            'status': 'downloading', 'filePath': output_path, 'filename': output_filename
        }

    def worker():
        ydl_opts = {'outtmpl': output_path, 'quiet': True}
        if is_audio:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        else:
            ydl_opts['format'] = f"{format_id}+bestaudio/best" if format_id != 'best' else 'best'
            ydl_opts['merge_output_format'] = 'mp4'
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            with jobs_lock:
                if job_id in download_jobs:
                    download_jobs[job_id]['status'] = 'completed'
                    download_jobs[job_id]['progressPercent'] = 100
        except Exception as e:
            with jobs_lock:
                if job_id in download_jobs:
                    download_jobs[job_id]['status'] = 'error'
                    download_jobs[job_id]['error'] = str(e)

    threading.Thread(target=worker, daemon=True).start()
    return jsonify({'success': True, 'jobId': job_id})

@app.route('/api/job/<job_id>', methods=['GET'])
def get_job(job_id):
    with jobs_lock:
        job = download_jobs.get(job_id)
        if not job: return abort(404)
        return jsonify({'success': True, 'job': job})

@app.route('/api/file/<job_id>', methods=['GET'])
def send_file_stream(job_id):
    with jobs_lock:
        job = download_jobs.get(job_id)
        if not job or job['status'] != 'completed': return abort(404)
        path = job['filePath']
    return send_file(path, as_attachment=True, download_name=job['filename'])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
`;

  const requirementsTxt = `flask>=3.0.0\nflask-cors>=4.0.0\nyt-dlp>=2024.10.22\ngunicorn>=22.0.0\nrequests>=2.31.0\n`;
  const dockerfile = `FROM python:3.11-slim\nRUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl && rm -rf /var/lib/apt/lists/*\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nENV PORT=5000\nCMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "app:app"]\n`;

  const indexHtml = `<!DOCTYPE html>
<html lang="hi">
<head>
  <meta charset="UTF-8">
  <title>StreamRip Video Downloader</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <h1>StreamRip Downloader</h1>
  <p>Run via python app.py or docker build</p>
</body>
</html>`;

  const readmeMd = `# StreamRip - Python Video Downloader
पूर्ण उत्पादन प्रोजेक्ट - YouTube & Facebook Video Downloader
1. pip install -r requirements.txt
2. python app.py
ब्राउज़र में खोलें: http://localhost:5000`;

  zip.file('app.py', appPyContent);
  zip.file('requirements.txt', requirementsTxt);
  zip.file('Dockerfile', dockerfile);
  zip.file('README.md', readmeMd);
  zip.file('.gitignore', '__pycache__/\n*.pyc\nvenv/\n/tmp/\n.env\n');

  const templatesFolder = zip.folder('templates');
  templatesFolder?.file('index.html', indexHtml);

  const staticFolder = zip.folder('static');
  staticFolder?.file('style.css', `body { background: #030712; color: #fff; font-family: sans-serif; }`);
  staticFolder?.file('script.js', `console.log("StreamRip initialized");`);

  const workflowFolder = zip.folder('.github')?.folder('workflows');
  workflowFolder?.file('deploy.yml', `name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: python -m py_compile app.py\n`);

  return await zip.generateAsync({ type: 'blob' });
}
