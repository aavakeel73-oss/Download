import os, time, uuid, json, threading, subprocess, shutil, re
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, request, jsonify, render_template, send_file
import yt_dlp

app = Flask(__name__)
ROOT = Path(os.getenv('TEMP_DOWNLOAD_DIR', '/tmp/streamrip_v2'))
ROOT.mkdir(parents=True, exist_ok=True)
MAX_BYTES = int(os.getenv('MAX_MEDIA_MB', '500')) * 1024 * 1024
jobs = {}
lock = threading.RLock()
sem = threading.BoundedSemaphore(2)

class JobCancelled(Exception): pass

def valid_url(url):
    if not isinstance(url, str) or len(url)>2048: return False
    try:
        p=urlsplit(url.strip()); h=(p.hostname or '').lower().rstrip('.')
        return p.scheme=='https' and not p.username and not p.password and p.port in (None,443) and h in ('facebook.com','www.facebook.com','m.facebook.com','web.facebook.com','fb.watch','www.fb.watch','mbasic.facebook.com')
    except ValueError: return False

def friendly_error(e):
    s=str(e).lower()
    if any(x in s for x in ('sign in','login','private','cookies','not a bot')): return 'इस वीडियो के लिए Facebook की अनुमति या लॉगिन आवश्यक है।'
    if any(x in s for x in ('403','forbidden')): return 'Facebook ने मीडिया एक्सेस अस्वीकार किया (403)।'
    if any(x in s for x in ('404','not found','unavailable')): return 'वीडियो उपलब्ध नहीं है।'
    if 'requested format is not available' in s: return 'यह क्वालिटी अब उपलब्ध नहीं है। फिर से विश्लेषण करें।'
    return 'डाउनलोड या फ़ाइल सत्यापन विफल हुआ। दूसरी उपलब्ध क्वालिटी आज़माएँ।'

def options():
    return {'quiet':True,'no_warnings':True,'noplaylist':True,'socket_timeout':20,'retries':3,'fragment_retries':3,'concurrent_fragment_downloads':4,'ignoreerrors':False}

def probe(path, audio_only=False):
    if not path.is_file() or path.stat().st_size < 1024: raise ValueError('फ़ाइल खाली या अधूरी है।')
    if not shutil.which('ffprobe'): raise RuntimeError('सर्वर पर FFprobe उपलब्ध नहीं है।')
    p=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type:format=duration','-of','json',str(path)],capture_output=True,text=True,timeout=30)
    if p.returncode: raise ValueError('FFprobe फ़ाइल पढ़ नहीं पाया।')
    streams=json.loads(p.stdout).get('streams',[])
    types={s.get('codec_type') for s in streams}
    if 'audio' not in types or (not audio_only and 'video' not in types): raise ValueError('फ़ाइल में आवश्यक ऑडियो/वीडियो स्ट्रीम नहीं मिली।')
    return path.stat().st_size

def update(jid, **fields):
    with lock:
        if jid in jobs: jobs[jid].update(fields)

@app.get('/')
def home(): return render_template('index.html')

@app.post('/api/analyze')
def analyze():
    url=(request.get_json(silent=True) or {}).get('url','')
    if not valid_url(url): return jsonify(success=False,error='केवल मान्य HTTPS Facebook/Reels लिंक डालें।'),400
    try:
        with yt_dlp.YoutubeDL(options()) as y: info=y.extract_info(url,download=False)
        if not info or info.get('_type')=='playlist': raise ValueError('एक वीडियो का लिंक डालें।')
        fmts=[]; seen=set()
        for f in sorted(info.get('formats') or [],key=lambda x:(x.get('height') or 0, x.get('tbr') or 0),reverse=True):
            height=f.get('height')
            if not isinstance(height,int) or height<144 or f.get('vcodec') in (None,'none') or height in seen: continue
            seen.add(height)
            fmts.append({'formatId':str(f.get('format_id')),'qualityLabel':f'{height}p','ext':'mp4','height':height,'filesizeBytes':f.get('filesize') or f.get('filesize_approx') or None})
        if info.get('acodec') not in (None,'none') or any(f.get('acodec') not in (None,'none') for f in info.get('formats') or []):
            fmts.append({'formatId':'bestaudio_mp3','qualityLabel':'Audio MP3','ext':'mp3','filesizeBytes':None})
        return jsonify(success=True,metadata={'title':info.get('title') or 'Facebook वीडियो','author':info.get('uploader') or '', 'thumbnail':info.get('thumbnail'),'durationSeconds':info.get('duration'),'sourceUrl':url,'formats':fmts})
    except Exception as e: return jsonify(success=False,error=friendly_error(e)),422

@app.post('/api/download')
def download():
    data=request.get_json(silent=True) or {}; url=data.get('url',''); fid=str(data.get('formatId',''))
    if not valid_url(url) or not (fid=='bestaudio_mp3' or re.fullmatch(r'[\w.-]{1,80}',fid)):
        return jsonify(success=False,error='अमान्य लिंक या क्वालिटी।'),400
    jid=uuid.uuid4().hex; audio=fid=='bestaudio_mp3'; folder=ROOT/jid; folder.mkdir()
    with lock: jobs[jid]={'id':jid,'status':'queued','progressPercent':0,'bytesDownloaded':0,'totalBytes':0,'speedFormatted':'0 KB/s','fileSizeBytes':None,'error':None,'created':time.time(),'filePath':None,'filename':None}
    def worker():
        if not sem.acquire(timeout=120): update(jid,status='error',error='सर्वर व्यस्त है। दोबारा प्रयास करें।'); return
        try:
            def hook(d):
                if d.get('status')=='downloading':
                    total=d.get('total_bytes') or d.get('total_bytes_estimate') or 0; got=d.get('downloaded_bytes') or 0; speed=d.get('speed') or 0
                    update(jid,status='downloading',progressPercent=min(95,round(got*95/total)) if total else 0,bytesDownloaded=got,totalBytes=total,speedFormatted=f'{speed/1048576:.2f} MB/s' if speed>=1048576 else f'{speed/1024:.1f} KB/s')
                elif d.get('status')=='finished': update(jid,status='processing',progressPercent=96)
            opts=options(); opts.update({'outtmpl':str(folder/'media.%(ext)s'),'progress_hooks':[hook],'max_filesize':MAX_BYTES,'paths':{'home':str(folder)}})
            if audio:
                opts.update({'format':'bestaudio/best','postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}]})
            else:
                opts.update({'format':f'{fid}+bestaudio/{fid}' ,'merge_output_format':'mp4','postprocessors':[{'key':'FFmpegVideoConvertor','preferedformat':'mp4'}]})
            with yt_dlp.YoutubeDL(opts) as y: y.download([url])
            update(jid,status='verifying',progressPercent=98)
            extension='.mp3' if audio else '.mp4'
            candidates=sorted(folder.glob('*'+extension),key=lambda p:p.stat().st_mtime,reverse=True)
            if not candidates: raise ValueError('आउटपुट फ़ाइल नहीं मिली।')
            path=candidates[0]; size=probe(path,audio)
            if size>MAX_BYTES: raise ValueError('फ़ाइल निर्धारित सीमा से बड़ी है।')
            update(jid,status='completed',progressPercent=100,filePath=str(path),filename=f'Facebook_{jid[:8]}{extension}',fileSizeBytes=size,speedFormatted='0 KB/s')
        except Exception as e:
            app.logger.warning('Download job %s failed: %s',jid,type(e).__name__)
            update(jid,status='error',error=friendly_error(e))
        finally: sem.release()
    threading.Thread(target=worker,daemon=True).start()
    return jsonify(success=True,jobId=jid)

@app.get('/api/job/<jid>')
def job(jid):
    with lock:
        j=jobs.get(jid)
        if not j:return jsonify(success=False,error='जॉब नहीं मिला।'),404
        return jsonify(success=True,job={k:v for k,v in j.items() if k not in ('filePath','created')})

@app.get('/api/file/<jid>')
def file(jid):
    with lock: j=jobs.get(jid)
    if not j or j['status']!='completed' or not j['filePath']:return jsonify(error='फ़ाइल तैयार नहीं है।'),404
    p=Path(j['filePath'])
    if not p.is_file():return jsonify(error='फ़ाइल उपलब्ध नहीं है।'),404
    return send_file(p,as_attachment=True,download_name=j['filename'],conditional=True)

def cleanup():
    while True:
        time.sleep(300); now=time.time()
        with lock:
            old=[k for k,v in jobs.items() if now-v['created']>3600 and v['status'] in ('completed','error')]
            for k in old: jobs.pop(k,None)
        for k in old: shutil.rmtree(ROOT/k,ignore_errors=True)
threading.Thread(target=cleanup,daemon=True).start()
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','8080')))
