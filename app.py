import os, re, time, secrets, tempfile, threading, subprocess, shutil, ipaddress, socket
from urllib.parse import urlparse
from flask import Flask, request, jsonify, render_template, send_file, abort
import yt_dlp

app = Flask(__name__)
OUT = tempfile.mkdtemp(prefix='video_out_')
JOBS = {}
LOCK = threading.Lock()
MAX_MB = int(os.getenv('MAX_MEDIA_MB', '150'))
MAX_DURATION = int(os.getenv('MAX_DURATION_SECONDS', '1200'))
HOSTS = ('youtube.com','www.youtube.com','m.youtube.com','youtu.be','www.youtu.be','facebook.com','www.facebook.com','m.facebook.com','fb.watch','www.fb.watch','instagram.com','www.instagram.com')

def error(message, status=400):
    return jsonify(error=message), status

def check_url(value):
    if not isinstance(value, str) or len(value)>2048:
        return False
    try:
        u=urlparse(value)
        return u.scheme=='https' and u.hostname in HOSTS and not u.username and not u.password and u.port in (None,443)
    except ValueError:
        return False

def public_dns(value):
    host=urlparse(value).hostname
    try:
        addresses=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
        return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
    except (socket.gaierror, ValueError):
        return False

def ydl_opts(extra=None):
    opts={'quiet':True,'no_warnings':True,'noplaylist':True,'socket_timeout':18,'retries':1,'fragment_retries':1,'extractor_retries':1,'skip_download':True,'cachedir':False,'ignoreerrors':False}
    if extra: opts.update(extra)
    return opts

def prune():
    with LOCK:
        for job,(path,expiry) in list(JOBS.items()):
            if expiry < time.time():
                JOBS.pop(job,None)
                try: os.unlink(path)
                except OSError: pass

@app.after_request
def no_cache(resp):
    resp.headers['Cache-Control']='no-store'
    resp.headers['X-Content-Type-Options']='nosniff'
    return resp

@app.get('/')
def home(): return render_template('index.html')

@app.get('/health')
def health():
    return jsonify(status='ok',backend='yt-dlp',ffmpeg=bool(shutil.which('ffmpeg')),ffprobe=bool(shutil.which('ffprobe')))

@app.post('/api/inspect')
def inspect():
    data=request.get_json(silent=True) or {}
    url=data.get('url','')
    if not check_url(url) or not public_dns(url): return error('सही और समर्थित HTTPS वीडियो लिंक डालें।')
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            info=ydl.extract_info(url,download=False)
        if not isinstance(info,dict): return error('वीडियो की जानकारी नहीं मिली।',404)
        duration=info.get('duration')
        if duration and duration>MAX_DURATION: return error('वीडियो बहुत लंबा है; 20 मिनट तक का वीडियो चुनें।',413)
        formats=[]
        seen=set()
        for f in info.get('formats',[]):
            if f.get('vcodec') in (None,'none') or not f.get('format_id'): continue
            height=f.get('height') or 0
            if height < 144 or height>1080: continue
            fid=str(f['format_id'])
            if fid in seen: continue
            seen.add(fid)
            has_audio=f.get('acodec') not in (None,'none')
            formats.append({'index':len(formats),'label':f"{height}p · {'ऑडियो सहित' if has_audio else 'ऑडियो मर्ज होगा'} · {f.get('ext','video')}", 'format_id':fid,'height':height})
        formats=sorted(formats,key=lambda x:x['height'],reverse=True)[:18]
        # Do not expose raw media URLs to the browser.
        if not formats: return error('इस वीडियो के डाउनलोड फॉर्मेट उपलब्ध नहीं हैं।',404)
        platform=info.get('extractor_key') or 'Video'
        return jsonify(title=str(info.get('title') or 'Video')[:160],thumbnail=info.get('thumbnail',''),platform=platform,videos=[{'index':i,'label':f['label']} for i,f in enumerate(formats)],token=None,formats=[f['format_id'] for f in formats],source=url)
    except Exception as exc:
        app.logger.warning('Inspect error: %s',str(exc)[:250])
        return error('वीडियो जानकारी नहीं मिल सकी। वीडियो निजी, प्रतिबंधित या स्रोत द्वारा ब्लॉक हो सकता है।',422)

@app.post('/api/merge')
def merge():
    if not shutil.which('ffmpeg'): return error('FFmpeg उपलब्ध नहीं है।',503)
    data=request.get_json(silent=True) or {}
    url=data.get('source','')
    fmt=data.get('format_id','')
    if not check_url(url) or not public_dns(url) or not isinstance(fmt,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',fmt): return error('अमान्य चयन।')
    prune()
    with LOCK:
        if len(JOBS)>=3: return error('सर्वर व्यस्त है, थोड़ी देर बाद कोशिश करें।',429)
    job=secrets.token_urlsafe(18)
    folder=tempfile.mkdtemp(prefix='download_')
    try:
        # Re-extract selected format: never trust a user-supplied media URL.
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            info=ydl.extract_info(url,download=False)
        if info.get('duration') and info['duration']>MAX_DURATION: return error('वीडियो बहुत लंबा है।',413)
        valid={str(f.get('format_id')) for f in info.get('formats',[]) if f.get('vcodec') not in (None,'none') and 144 <= (f.get('height') or 0) <= 1080}
        if fmt not in valid: return error('वीडियो क्वालिटी बदल गई है, दोबारा खोजें।')
        path_template=os.path.join(folder,'source.%(ext)s')
        opts=ydl_opts({'skip_download':False,'format':fmt+'+bestaudio/best','outtmpl':path_template,'merge_output_format':'mp4','max_filesize':MAX_MB*1024*1024,'overwrites':True,'nopart':True,'postprocessor_args':{'ffmpeg':['-movflags','+faststart']}})
        with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([url])
        candidates=[os.path.join(folder,n) for n in os.listdir(folder) if os.path.isfile(os.path.join(folder,n)) and not n.endswith(('.part','.ytdl'))]
        if not candidates: raise ValueError('कोई वीडियो फाइल नहीं बनी')
        source=max(candidates,key=os.path.getsize)
        if os.path.getsize(source)>MAX_MB*1024*1024: raise ValueError('वीडियो निर्धारित साइज से बड़ा है')
        dest=os.path.join(OUT,job+'.mp4')
        # Normalize to MP4 with AAC audio, without re-encoding video when compatible.
        result=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-i',source,'-map','0:v:0','-map','0:a:0?','-c:v','copy','-c:a','aac','-movflags','+faststart',dest],capture_output=True,text=True,timeout=120)
        if result.returncode: raise ValueError('MP4 प्रोसेसिंग असफल')
        with LOCK: JOBS[job]=(dest,time.time()+600)
        return jsonify(success=True,download='/api/download/'+job)
    except Exception as exc:
        app.logger.warning('Download error: %s',str(exc)[:300])
        return error('डाउनलोड असफल। स्रोत ने सर्वर अनुरोध रोका हो सकता है, या वीडियो बहुत बड़ा है।',422)
    finally: shutil.rmtree(folder,ignore_errors=True)

@app.get('/api/download/<job>')
def download(job):
    prune()
    with LOCK: item=JOBS.get(job)
    if not item or item[1]<time.time() or not os.path.isfile(item[0]): abort(404)
    return send_file(item[0],as_attachment=True,download_name='video.mp4',mimetype='video/mp4')

if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','10000')))
    
