import os, re, time, json, hmac, hashlib, base64, tempfile, subprocess, secrets, threading, shutil, ipaddress, socket
from urllib.parse import urlparse, urlencode
import requests
from flask import Flask, request, jsonify, send_file, render_template, abort

app = Flask(__name__)
API_HOST='social-media-video-downloader.p.rapidapi.com'
API_KEY=os.getenv('RAPIDAPI_KEY','')
SIGN_KEY=os.getenv('SIGNING_SECRET','')
MAX_BYTES=75*1024*1024
OUT_DIR=tempfile.mkdtemp(prefix='merged_')
JOBS={}
LOCK=threading.Lock()

@app.after_request
def headers(r):
    r.headers['Cache-Control']='no-store'
    r.headers['X-Content-Type-Options']='nosniff'
    return r

def fail(msg, status=400):
    return jsonify(error=msg),status

def safe_public_url(raw, source=False):
    try:
        u=urlparse(raw)
        if u.scheme!='https' or not u.hostname or u.username or u.password: return False
        h=u.hostname.lower().rstrip('.')
        if source:
            return h in ('youtube.com','www.youtube.com','m.youtube.com','music.youtube.com','youtu.be','www.youtu.be','facebook.com','www.facebook.com','m.facebook.com','web.facebook.com','fb.watch','www.fb.watch')
        return any(h==s or h.endswith('.'+s) for s in ('googlevideo.com','fbcdn.net','fbsbx.com','cdninstagram.com','youtube.com','googleusercontent.com','smvd.xyz'))
    except Exception: return False

def youtube_id(u):
    p=urlparse(u)
    if p.hostname in ('youtu.be','www.youtu.be'): v=p.path.strip('/').split('/')[0]
    elif re.match(r'^/(shorts|live|embed)/',p.path): v=p.path.split('/')[2]
    else:
        from urllib.parse import parse_qs
        v=parse_qs(p.query).get('v',[''])[0]
    return v if re.fullmatch(r'[A-Za-z0-9_-]{11}',v) else None

def sign(payload):
    raw=json.dumps(payload,separators=(',',':')).encode()
    sig=hmac.new(SIGN_KEY.encode(),raw,hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw+sig).decode().rstrip('=')

def unsign(token):
    data=base64.urlsafe_b64decode(token+'='*(-len(token)%4))
    raw,sig=data[:-32],data[-32:]
    if not hmac.compare_digest(hmac.new(SIGN_KEY.encode(),raw,hashlib.sha256).digest(),sig): raise ValueError('Bad token')
    value=json.loads(raw)
    if value['exp']<time.time(): raise ValueError('Links expired; search again')
    return value

def clean_items(data, kind):
    out=[]
    for entry in data.get('contents',[]):
        for item in entry.get(kind,[]) or []:
            url=item.get('url')
            if isinstance(url,str) and safe_public_url(url):
                out.append({'url':url,'label':str(item.get('label') or 'Unknown')[:60]})
    return out[:30]

@app.get('/')
def home(): return render_template('index.html')

@app.get('/health')
def health(): return jsonify(status='ok',ffmpeg=bool(shutil.which('ffmpeg')),configured=bool(API_KEY and SIGN_KEY))

@app.post('/api/inspect')
def inspect():
    if not API_KEY or len(SIGN_KEY)<24: return fail('Set RAPIDAPI_KEY and a 24+ character SIGNING_SECRET in Render',503)
    source=(request.get_json(silent=True) or {}).get('url','')
    if not isinstance(source,str) or len(source)>2500 or not safe_public_url(source,True): return fail('Enter a supported YouTube or Facebook HTTPS link')
    p=urlparse(source)
    yt='youtu' in p.hostname
    if yt:
        vid=youtube_id(source)
        if not vid:return fail('Invalid YouTube video ID')
        path='/youtube/v3/video/details'; params={'videoId':vid,'urlAccess':'normal','getTranscript':'false'}
    else:
        path='/facebook/v3/post/details';params={'url':source}
    try:
        r=requests.get('https://'+API_HOST+path,params=params,headers={'x-rapidapi-key':API_KEY,'x-rapidapi-host':API_HOST},timeout=25)
        if not r.ok:return fail('RapidAPI error '+str(r.status_code)+': '+r.text[:180],502)
        data=r.json()
    except (requests.RequestException,ValueError):return fail('RapidAPI connection or response error',502)
    videos=clean_items(data,'videos');audios=clean_items(data,'audios')
    if not videos:return fail('No usable video links returned. API access or media may be restricted',404)
    token=sign({'videos':videos,'audios':audios,'exp':int(time.time())+600})
    return jsonify(videos=[{'label':v['label'],'index':i} for i,v in enumerate(videos)],audios=[{'label':a['label'],'index':i} for i,a in enumerate(audios)],token=token,platform='YouTube' if yt else 'Facebook')

def download_stream(url, path):
    # Do not follow redirects to arbitrary destinations. Only public media CDN hosts allowed.
    for _ in range(3):
        if not safe_public_url(url):raise ValueError('Unsupported media host')
        with requests.get(url,stream=True,timeout=(10,45),allow_redirects=False,headers={'User-Agent':'Mozilla/5.0'}) as r:
            if r.status_code in (301,302,303,307,308):
                url=r.headers.get('Location','')
                from urllib.parse import urljoin
                url=urljoin(r.url,url)
                continue
            r.raise_for_status()
            total=0
            with open(path,'wb') as f:
                for chunk in r.iter_content(256*1024):
                    total+=len(chunk)
                    if total>MAX_BYTES:raise ValueError('Media exceeds 75 MB free-server limit')
                    f.write(chunk)
            if total<100:raise ValueError('Empty media stream')
            return
    raise ValueError('Too many media redirects')

@app.post('/api/merge')
def merge():
    data=request.get_json(silent=True) or {}
    try:
        payload=unsign(str(data.get('token','')))
        vi=int(data.get('video',-1));ai=int(data.get('audio',-1))
        video=payload['videos'][vi]['url']
        if vi<0:raise ValueError('Invalid video index')
        audio=payload['audios'][ai]['url'] if ai>=0 else None
        if ai>=len(payload['audios']):raise ValueError('Invalid audio index')
    except (ValueError,KeyError,IndexError,TypeError):return fail('Invalid or expired selection. Search again')
    with LOCK:
        if len(JOBS)>10:return fail('Server busy, try again later',429)
    job=secrets.token_urlsafe(18)
    directory=tempfile.mkdtemp(prefix='merge_')
    try:
        v=os.path.join(directory,'video.bin');download_stream(video,v)
        output=os.path.join(OUT_DIR,job+'.mp4')
        if audio:
            a=os.path.join(directory,'audio.bin');download_stream(audio,a)
            command=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-i',v,'-i',a,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k','-movflags','+faststart','-t','1800',output]
        else:
            # Keep the original embedded audio, if any. Never claim a silent file has sound.
            command=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-i',v,'-map','0:v:0','-map','0:a:0?','-c:v','copy','-c:a','aac','-b:a','128k','-movflags','+faststart','-t','1800',output]
        run=subprocess.run(command,capture_output=True,text=True,timeout=105)
        if run.returncode!=0:raise ValueError('FFmpeg: '+run.stderr[-300:])
        probe=subprocess.run(['ffprobe','-v','error','-select_streams','a','-show_entries','stream=index','-of','csv=p=0',output],capture_output=True,text=True,timeout=10)
        if not probe.stdout.strip():raise ValueError('No audio track in output. Choose an audio stream and try again')
        with LOCK:JOBS[job]=time.time()+600
        return jsonify(success=True,download='/api/download/'+job)
    except (requests.RequestException,subprocess.TimeoutExpired,ValueError) as e:
        return fail(str(e)[:350],422)
    finally:
        shutil.rmtree(directory,ignore_errors=True)

def cleanup():
    with LOCK:
        for key,exp in list(JOBS.items()):
            if exp<time.time():
                JOBS.pop(key,None)
                try:os.unlink(os.path.join(OUT_DIR,key+'.mp4'))
                except OSError:pass

@app.get('/api/download/<job>')
def download(job):
    cleanup()
    with LOCK:valid=JOBS.get(job,0)>time.time()
    if not valid:abort(404)
    return send_file(os.path.join(OUT_DIR,job+'.mp4'),as_attachment=True,download_name='video_with_audio.mp4',mimetype='video/mp4')

if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','10000')))
