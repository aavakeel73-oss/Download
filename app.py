import os, re, time, uuid, json, threading, subprocess, shutil, logging
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, request, jsonify, render_template, send_file
import yt_dlp

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024
logging.basicConfig(level=logging.INFO)
BASE = Path(os.getenv('TEMP_DOWNLOAD_DIR', '/tmp/streamrip')).resolve()
BASE.mkdir(parents=True, exist_ok=True)
MAX_BYTES = int(os.getenv('MAX_MEDIA_MB', '350')) * 1024 * 1024
EXPIRY = 3600
JOBS = {}
LOCK = threading.RLock()
ALLOWED = {'facebook.com', 'www.facebook.com', 'm.facebook.com', 'web.facebook.com', 'mbasic.facebook.com', 'fb.watch', 'www.fb.watch'}
MAX_JOBS = 4

def valid_url(url):
    if not isinstance(url, str) or len(url) > 2048:
        return False
    try:
        p = urlsplit(url.strip())
        return p.scheme == 'https' and p.hostname in ALLOWED and not p.username and not p.password and (p.port in (None,443))
    except ValueError:
        return False

def error_message(exc):
    msg = str(exc).lower()
    if 'confirm you' in msg or 'login' in msg or 'cookies' in msg or 'private' in msg:
        return 'Facebook ने इस वीडियो के लिए लॉगिन या अतिरिक्त अनुमति माँगी है। केवल अधिकृत सार्वजनिक वीडियो उपलब्ध हैं।'
    if 'unsupported url' in msg or 'not available' in msg:
        return 'यह Facebook वीडियो उपलब्ध नहीं है या लिंक समर्थित नहीं है।'
    if 'file is larger' in msg or 'max-filesize' in msg:
        return 'फ़ाइल सर्वर की निर्धारित साइज सीमा से बड़ी है।'
    return 'वीडियो प्रोसेस नहीं हो सका। Render Logs में वास्तविक त्रुटि देखें।'

def options():
    return {'quiet': True, 'no_warnings': True, 'noplaylist': True, 'socket_timeout': 20,
            'retries': 2, 'fragment_retries': 2, 'extractor_retries': 2,
            'concurrent_fragment_downloads': 3, 'max_filesize': MAX_BYTES}

def quality_label(height):
    return f'{height}p' + (' 4K' if height == 2160 else ' 2K' if height == 1440 else '')

def inspect_media(path, audio_only):
    cmd = ['ffprobe','-v','error','-show_entries','stream=codec_type,codec_name,width,height:format=duration', '-of','json',str(path)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if p.returncode: raise RuntimeError('FFprobe फ़ाइल नहीं पढ़ पाया।')
    streams = json.loads(p.stdout).get('streams') or []
    video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    if not audio or (not audio_only and not video):
        raise RuntimeError('फ़ाइल में वीडियो या आवाज़ उपलब्ध नहीं है।')
    return video, audio

def update(jid, **changes):
    with LOCK:
        if jid in JOBS: JOBS[jid].update(changes)

def worker(jid, url, height, audio_only):
    folder = BASE / jid
    folder.mkdir(exist_ok=True)
    try:
        opts = options()
        opts['outtmpl'] = str(folder / 'media.%(ext)s')
        if audio_only:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'] = [{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}]
        else:
            # Never upscale. Prefer MP4/H264 + M4A; allow other codecs then normalize if needed.
            opts['format'] = (f'bestvideo[height<={height}][vcodec^=avc1]+bestaudio[ext=m4a]/'
                              f'bestvideo[height<={height}]+bestaudio/'
                              f'best[height<={height}][ext=mp4]/best[height<={height}]')
            opts['merge_output_format'] = 'mp4'
        def progress(d):
            if d.get('status') == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                done = d.get('downloaded_bytes') or 0
                pct = min(95, int(done * 95 / total)) if total else 0
                update(jid, status='downloading', progressPercent=pct, bytesDownloaded=done,
                       totalBytes=total, speedBytesPerSecond=d.get('speed') or 0)
            elif d.get('status') == 'finished':
                update(jid, status='processing', progressPercent=96, speedBytesPerSecond=0)
        opts['progress_hooks'] = [progress]
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        suffix = '.mp3' if audio_only else '.mp4'
        candidates = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == suffix]
        if not candidates: raise RuntimeError('अंतिम फ़ाइल नहीं बनी।')
        source = max(candidates, key=lambda p:p.stat().st_size)
        update(jid, status='verifying', progressPercent=97)
        video, audio = inspect_media(source, audio_only)
        if not audio_only and (video.get('codec_name') != 'h264' or audio.get('codec_name') != 'aac'):
            update(jid, status='converting', progressPercent=98)
            converted = folder / 'compatible.mp4'
            cmd = ['ffmpeg','-nostdin','-y','-i',str(source),'-map','0:v:0','-map','0:a:0',
                   '-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p',
                   '-c:a','aac','-b:a','160k','-movflags','+faststart',str(converted)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if proc.returncode: raise RuntimeError('MP4 कन्वर्ज़न विफल हुआ। Render Logs देखें।')
            source = converted
            inspect_media(source, False)
        size = source.stat().st_size
        if size < 1024 or size > MAX_BYTES: raise RuntimeError('फ़ाइल खाली या साइज सीमा से बड़ी है।')
        update(jid, status='completed', progressPercent=100, fileSizeBytes=size,
               filename=('Facebook_Audio_' if audio_only else 'Facebook_Video_')+jid[:8]+suffix,
               filePath=str(source), speedBytesPerSecond=0)
    except Exception as exc:
        app.logger.exception('Job %s failed', jid)
        update(jid, status='error', error=error_message(exc), progressPercent=0, speedBytesPerSecond=0)

def cleanup():
    while True:
        time.sleep(300)
        now = time.time()
        with LOCK:
            expired = [jid for jid, j in JOBS.items() if now-j['createdAt'] > EXPIRY and j['status'] not in ('starting','downloading','processing','verifying','converting')]
            for jid in expired: JOBS.pop(jid,None)
        for jid in expired: shutil.rmtree(BASE/jid, ignore_errors=True)
threading.Thread(target=cleanup, daemon=True).start()

@app.errorhandler(Exception)
def api_error(exc):
    from werkzeug.exceptions import HTTPException
    if isinstance(exc, HTTPException):
        status = exc.code
        message = exc.description if status < 500 else 'सर्वर त्रुटि।'
    else:
        app.logger.exception('Unhandled request error')
        status, message = 500, 'सर्वर में समस्या आई। Render Logs देखें।'
    if request.path.startswith('/api/'):
        return jsonify(success=False, error=message), status
    return message, status

@app.get('/')
def home(): return render_template('index.html')

@app.get('/api/health')
def health(): return jsonify(success=True, status='ok')

@app.post('/api/analyze')
def analyze():
    url = (request.get_json(silent=True) or {}).get('url','')
    if not valid_url(url): return jsonify(success=False,error='केवल मान्य HTTPS Facebook वीडियो/Reel लिंक डालें।'),400
    try:
        with yt_dlp.YoutubeDL(options()) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info or info.get('_type') == 'playlist':
            return jsonify(success=False,error='एक वीडियो का लिंक डालें।'),400
        heights = sorted({int(f['height']) for f in info.get('formats',[]) if f.get('height') and f.get('vcodec','none')!='none'},reverse=True)
        formats = [{'formatId':str(h),'qualityLabel':quality_label(h),'ext':'mp4','height':h} for h in heights]
        if any(f.get('acodec','none')!='none' for f in info.get('formats',[])):
            formats.append({'formatId':'audio','qualityLabel':'Audio MP3','ext':'mp3'})
        return jsonify(success=True, metadata={'title':info.get('title') or 'Facebook वीडियो',
           'thumbnail':info.get('thumbnail'), 'author':info.get('uploader') or '',
           'durationSeconds':info.get('duration') or 0,'formats':formats})
    except Exception as exc:
        app.logger.exception('Analyze failed')
        return jsonify(success=False,error=error_message(exc)),502

@app.post('/api/download')
def start():
    data = request.get_json(silent=True) or {}
    url, fid = data.get('url',''),str(data.get('formatId',''))
    if not valid_url(url): return jsonify(success=False,error='मान्य Facebook लिंक डालें।'),400
    if fid != 'audio' and (not fid.isdecimal() or not 1 <= int(fid) <= 4320):
        return jsonify(success=False,error='मान्य क्वालिटी चुनें।'),400
    with LOCK:
        active = sum(j['status'] in ('starting','downloading','processing','verifying','converting') for j in JOBS.values())
        if active >= MAX_JOBS: return jsonify(success=False,error='सर्वर व्यस्त है। थोड़ी देर बाद प्रयास करें।'),429
        jid = uuid.uuid4().hex
        JOBS[jid] = {'id':jid,'createdAt':time.time(),'status':'starting','progressPercent':0,
                     'bytesDownloaded':0,'totalBytes':0,'speedBytesPerSecond':0,'fileSizeBytes':0,'error':None}
    threading.Thread(target=worker,args=(jid,url,0 if fid=='audio' else int(fid),fid=='audio'),daemon=True).start()
    return jsonify(success=True,jobId=jid)

@app.get('/api/job/<jid>')
def status(jid):
    with LOCK:
        job = JOBS.get(jid)
        if not job: return jsonify(success=False,error='जॉब नहीं मिला या समाप्त हो गया।'),404
        public = {k:v for k,v in job.items() if k not in ('filePath','createdAt')}
    return jsonify(success=True,job=public)

@app.get('/api/file/<jid>')
def file(jid):
    with LOCK:
        job = JOBS.get(jid)
        if not job or job['status']!='completed': return jsonify(success=False,error='फ़ाइल अभी तैयार नहीं है।'),404
        path, name = job['filePath'],job['filename']
    if not os.path.isfile(path): return jsonify(success=False,error='फ़ाइल समाप्त हो गई।'),404
    response = send_file(path,as_attachment=True,download_name=name,
                         mimetype='audio/mpeg' if name.endswith('.mp3') else 'video/mp4',conditional=True)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=int(os.getenv('PORT','10000')))
