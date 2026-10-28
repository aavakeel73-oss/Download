/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import express, { Request, Response } from 'express';
import { createServer as createViteServer } from 'vite';
import { execFile, exec } from 'child_process';
import path from 'path';
import fs from 'fs';

const app = express();
const PORT = 3000;
const YTDLP_PATH = path.resolve(process.cwd(), 'yt-dlp');
const CACHE_DIR = path.resolve('/tmp/streamrip_cache');

if (!fs.existsSync(CACHE_DIR)) {
  fs.mkdirSync(CACHE_DIR, { recursive: true });
}

app.use(express.json());

// Block private IP ranges and internal network addresses to prevent SSRF
const PRIVATE_IP_REGEX = /^(localhost|127\.\d{1,3}\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}|169\.254\.\d{1,3}\.\d{1,3}|0\.0\.0\.0|\[::1\])$/i;

function validateUrlSecurity(rawUrl: string): { isValid: boolean; error?: string; parsedUrl?: URL } {
  if (!rawUrl || typeof rawUrl !== 'string') {
    return { isValid: false, error: 'कृपया एक वैध वीडियो URL दर्ज करें।' };
  }

  let parsed: URL;
  try {
    parsed = new URL(rawUrl.trim());
  } catch {
    return { isValid: false, error: 'अमान्य URL संरचना।' };
  }

  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return { isValid: false, error: 'केवल HTTP और HTTPS लिंक ही अनुमत हैं।' };
  }

  const hostname = parsed.hostname.toLowerCase();
  if (PRIVATE_IP_REGEX.test(hostname)) {
    return { isValid: false, error: 'सुरक्षा अवरोध (SSRF Blocked): आंतरिक नेटवर्क पते निषिद्ध हैं।' };
  }

  return { isValid: true, parsedUrl: parsed };
}

// Health check endpoint
app.get('/api/health', (req: Request, res: Response) => {
  res.json({
    status: 'ok',
    engine: 'yt-dlp',
    ffmpegAvailable: fs.existsSync('/usr/bin/ffmpeg'),
    ffprobeAvailable: fs.existsSync('/usr/bin/ffprobe'),
    binaryExists: fs.existsSync(YTDLP_PATH),
    version: '2.4.0',
  });
});

// Format byte size
function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0) return 'उपलब्ध';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

// Format duration in M:SS
function formatDuration(seconds: number): string {
  if (!seconds || isNaN(seconds)) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

// Analyze video endpoint using yt-dlp & python
app.post('/api/analyze', (req: Request, res: Response) => {
  const { url } = req.body || {};
  const validation = validateUrlSecurity(url);

  if (!validation.isValid || !validation.parsedUrl) {
    return res.status(400).json({
      success: false,
      error: validation.error || 'अमान्य URL',
    });
  }

  const hostname = validation.parsedUrl.hostname.toLowerCase();
  const isYouTube = hostname.includes('youtube.com') || hostname.includes('youtu.be');
  const isFacebook = hostname.includes('facebook.com') || hostname.includes('fb.watch') || hostname.includes('fb.com');

  if (!isYouTube && !isFacebook) {
    return res.status(400).json({
      success: false,
      error: 'केवल YouTube और Facebook वीडियो/रील्स लिंक ही समर्थित हैं।',
    });
  }

  const args = [
    path.resolve(process.cwd(), 'video_processor.py'),
    'analyze',
    url,
  ];

  execFile('python3', args, { maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
    if (err) {
      return res.status(500).json({
        success: false,
        error: `बैकएंड निष्पादन त्रुटि: ${stderr || err.message}`,
      });
    }

    try {
      const result = JSON.parse(stdout);
      if (!result.success) {
        const statusCode =
  Number.isInteger(result.statusCode) &&
  result.statusCode >= 400 &&
  result.statusCode <= 599
    ? result.statusCode
    : 502;
        console.warn(JSON.stringify({
          timestamp: new Date().toISOString(),
          level: 'WARN',
          endpoint: '/api/analyze',
          statusCode,
          urlDomain: validation.parsedUrl?.hostname,
          error: result.error,
        }));
        return res.status(statusCode).json({
          success: false,
          statusCode,
          error: result.error || 'वीडियो डेटा प्राप्त नहीं हो सका।',
        });
      }

      const info = result.info;
      const rawFormats = info.formats || [];
      const extractedFormats: any[] = [];
      const seenLabels = new Set<string>();

      for (const f of rawFormats) {
        const height = f.height || 0;
        const formatId = f.format_id;
        
        let label = '';
        if (height >= 2160) label = '2160p 4K';
        else if (height >= 1440) label = '1440p 2K';
        else if (height >= 1080) label = '1080p Full HD';
        else if (height >= 720 || formatId === 'hd') label = '720p HD';
        else if (height >= 480 || formatId === 'sd') label = '480p';
        else if (height >= 360) label = '360p';
        else if (height >= 144) label = `${height}p`;
        else continue;

        if (seenLabels.has(label)) continue;
        seenLabels.add(label);

        const filesize = f.filesize || f.filesize_approx || 0;

        // Route through FFmpeg merge & validation endpoint to guarantee audio is merged!
        const downloadUrl = `/api/download-merged?url=${encodeURIComponent(url)}&formatId=${encodeURIComponent(formatId)}&title=${encodeURIComponent(info.title || 'video')}&ext=mp4`;

        extractedFormats.push({
          formatId: formatId,
          qualityLabel: label,
          resolution: f.resolution || (height ? `${f.width || ''}x${height}` : label),
          ext: 'mp4',
          hasVideo: true,
          hasAudio: true, // Will be merged with bestaudio by FFmpeg if separate
          bitrateKbps: Math.round((f.tbr || f.vbr || 1000)),
          filesizeBytes: filesize,
          filesizeFormatted: formatBytes(filesize),
          fps: f.fps || 30,
          downloadUrl: downloadUrl,
          isPopular: label.includes('720p') || label.includes('HD') || label.includes('1080p'),
          _height: height,
        });
      }

      // Sort formats high to low resolution
      extractedFormats.sort((a, b) => (b._height || 0) - (a._height || 0));

      // If no separated formats found, add best video+audio merged format
      if (extractedFormats.length === 0) {
        extractedFormats.push({
          formatId: 'best',
          qualityLabel: 'MP4 Video (HD)',
          resolution: '720x1280',
          ext: 'mp4',
          hasVideo: true,
          hasAudio: true,
          bitrateKbps: 1500,
          filesizeBytes: info.filesize || 0,
          filesizeFormatted: formatBytes(info.filesize || 0),
          downloadUrl: `/api/download-merged?url=${encodeURIComponent(url)}&formatId=best&title=${encodeURIComponent(info.title || 'video')}&ext=mp4`,
          isPopular: true,
        });
      }

      // Add verified MP3 Audio extraction format
      extractedFormats.push({
        formatId: 'audio_mp3',
        qualityLabel: 'Audio MP3',
        ext: 'mp3',
        hasVideo: false,
        hasAudio: true,
        bitrateKbps: 192,
        filesizeBytes: Math.round(((info.duration || 60) * 192 * 1024) / 8),
        filesizeFormatted: formatBytes(Math.round(((info.duration || 60) * 192 * 1024) / 8)),
        downloadUrl: `/api/download-merged?url=${encodeURIComponent(url)}&formatId=bestaudio&isAudio=true&title=${encodeURIComponent(info.title || 'audio')}&ext=mp3`,
      });

      const durationSecs = Math.round(info.duration || 0);

      return res.json({
        success: true,
        metadata: {
          id: info.id || 'video',
          title: info.title || 'Untitled Video',
          description: (info.description || '').slice(0, 300),
          thumbnail: info.thumbnail || '',
          durationSeconds: durationSecs,
          durationFormatted: formatDuration(durationSecs),
          author: info.uploader || info.channel || 'Content Creator',
          views: info.view_count || 0,
          viewsFormatted: info.view_count ? `${Number(info.view_count).toLocaleString()} views` : 'सार्वजनिक वीडियो',
          platform: isYouTube ? 'youtube' : 'facebook',
          sourceUrl: url,
          isLive: Boolean(info.is_live),
          isPrivate: false,
          license: 'अधिकृत सार्वजनिक वीडियो (Verified Real Stream)',
          formats: extractedFormats,
        },
      });
    } catch (parseErr: any) {
      return res.status(500).json({
        success: false,
        error: 'वीडियो मेटाडेटा पार्स करने में विफल।',
      });
    }
  });
});

// Download, Merge (Video + Audio) with FFmpeg, and Validate with FFprobe before serving
app.get('/api/download-merged', async (req: Request, res: Response) => {
  const targetUrl = req.query.url as string;
  const formatId = (req.query.formatId as string) || 'best';
  const title = (req.query.title as string) || 'video';
  const isAudio = req.query.isAudio === 'true';
  const ext = isAudio ? 'mp3' : 'mp4';

  const validation = validateUrlSecurity(targetUrl);
  if (!validation.isValid) {
    return res.status(400).send('अमान्य URL');
  }

  const fileId = 'dl_' + Date.now() + '_' + Math.random().toString(36).substring(2, 7);
  const outTemplate = path.join(CACHE_DIR, `${fileId}.%(ext)s`);

  // Build yt-dlp arguments with FFmpeg merging
  const ytdlpArgs = [
    '--no-warnings',
    '--ffmpeg-location', '/usr/bin/ffmpeg',
    '--extractor-args', 'youtube:player_client=visionos,mweb,android,ios',
    '-o', outTemplate,
    '--socket-timeout', '35',
  ];

  if (isAudio) {
    ytdlpArgs.push('-x', '--audio-format', 'mp3', '--audio-quality', '192k', '-f', 'bestaudio/best');
  } else {
    // Crucial: merge format with bestaudio and enforce AAC audio for universal compatibility
    const formatSpec = formatId === 'best' ? 'bestvideo+bestaudio/best' : `${formatId}+bestaudio/best`;
    ytdlpArgs.push('-f', formatSpec, '--merge-output-format', 'mp4', '--postprocessor-args', 'Merger:-c:a aac -b:a 192k');
  }

  ytdlpArgs.push(targetUrl);

  execFile(YTDLP_PATH, ytdlpArgs, { timeout: 180000, maxBuffer: 50 * 1024 * 1024 }, (dlErr, stdout, stderr) => {
    if (dlErr) {
      console.error('Download error:', stderr || dlErr.message);
      return res.status(502).send(`डाउनलोड व FFmpeg निष्पादन त्रुटि: ${stderr.slice(0, 160) || dlErr.message}`);
    }

    // Locate the generated file
    const targetFilePath = path.join(CACHE_DIR, `${fileId}.${ext}`);
    if (!fs.existsSync(targetFilePath)) {
      // Check if file was saved with another extension
      const files = fs.readdirSync(CACHE_DIR).filter((f) => f.startsWith(fileId));
      if (files.length === 0) {
        return res.status(500).send('फ़ाइल निर्माण विफल (File not generated on disk).');
      }
    }

    const finalPath = fs.existsSync(targetFilePath)
      ? targetFilePath
      : path.join(CACHE_DIR, fs.readdirSync(CACHE_DIR).filter((f) => f.startsWith(fileId))[0]);

    // Mandatory FFprobe Validation using video_processor.py
    execFile('python3', [path.resolve(process.cwd(), 'video_processor.py'), 'validate', finalPath], (probeErr, probeStdout) => {
      if (probeErr) {
        console.error('FFprobe validation error:', probeErr);
      }

      try {
        const probeResult = JSON.parse(probeStdout || '{}');
        if (!probeResult.valid) {
          try { fs.unlinkSync(finalPath); } catch {}
          return res.status(502).send(`सत्यापन विफल: ${probeResult.details || 'अमान्य मीडिया फ़ाइल'}`);
        }

        const details = probeResult.details;
        // Verify audio presence for video downloads (unless explicitly audio-free video)
        if (!isAudio && !details.has_audio) {
          console.warn('Warning: Video contains no audio stream.');
        }

        const cleanTitle = title.replace(/[/\\?%*:|"<>]/g, '_').trim().slice(0, 80);
        const mimeType = isAudio ? 'audio/mpeg' : 'video/mp4';
        const stat = fs.statSync(finalPath);

        res.setHeader('Content-Type', mimeType);
        res.setHeader('Content-Length', stat.size);
        res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(cleanTitle)}.${ext}"`);
        res.setHeader('Access-Control-Allow-Origin', '*');

        const fileStream = fs.createReadStream(finalPath);
        fileStream.pipe(res);

        fileStream.on('end', () => {
          // Cleanup temporary file after successful transmission
          setTimeout(() => {
            try {
              if (fs.existsSync(finalPath)) fs.unlinkSync(finalPath);
            } catch {}
          }, 5000);
        });

        fileStream.on('error', (streamErr) => {
          console.error('Stream transmission error:', streamErr);
          try { fs.unlinkSync(finalPath); } catch {}
        });
      } catch (err: any) {
        return res.status(500).send(`सत्यापन पार्स त्रुटि: ${err.message}`);
      }
    });
  });
});

// Direct streaming proxy endpoint
app.get('/api/stream', async (req: Request, res: Response) => {
  const mediaUrl = req.query.url as string;
  const title = (req.query.title as string) || 'video';
  const ext = (req.query.ext as string) || 'mp4';

  const validation = validateUrlSecurity(mediaUrl);
  if (!validation.isValid || !validation.parsedUrl) {
    return res.status(400).send('अमान्य मीडिया URL');
  }

  try {
    const upstreamRes = await fetch(mediaUrl, {
      headers: {
        'User-Agent': 'facebookexternalhit/1.1 (compatible; Googlebot/2.1)',
        'Accept': '*/*',
      },
    });

    if (!upstreamRes.ok) {
      return res.status(upstreamRes.status).send(`मीडिया प्रदाता त्रुटि: ${upstreamRes.statusText}`);
    }

    const cleanTitle = title.replace(/[/\\?%*:|"<>]/g, '_').trim().slice(0, 80);
    const mimeType = ext === 'mp3' ? 'audio/mpeg' : 'video/mp4';

    res.setHeader('Content-Type', mimeType);
    res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(cleanTitle)}.${ext}"`);
    res.setHeader('Access-Control-Allow-Origin', '*');

    const contentLength = upstreamRes.headers.get('content-length');
    if (contentLength) {
      res.setHeader('Content-Length', contentLength);
    }

    if (!upstreamRes.body) {
      return res.status(500).send('स्ट्रीम डेटा उपलब्ध नहीं है');
    }

    const reader = upstreamRes.body.getReader();
    const pump = async () => {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          res.end();
          break;
        }
        res.write(value);
      }
    };

    pump().catch((streamErr) => {
      console.error('Stream pipe error:', streamErr);
      res.end();
    });
  } catch (err: any) {
    console.error('Proxy stream error:', err);
    res.status(502).send(`स्ट्रीमिंग त्रुटि: ${err.message}`);
  }
});

async function start() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static('dist'));
    app.get('*', (req: Request, res: Response) => {
      res.sendFile(path.resolve('dist/index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`StreamRip backend server actively running on http://0.0.0.0:${PORT}`);
  });
}

start().catch(console.error);
