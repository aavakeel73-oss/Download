/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { DownloadJob, VideoFormat } from '../types/downloader';
import { formatBytes } from './videoExtractor';

export type ProgressCallback = (job: DownloadJob) => void;

class DownloadManager {
  private activeJobs = new Map<string, { abortController: AbortController; job: DownloadJob }>();

  /**
   * Starts a real streaming download with progress, speed, ETA, and mobile browser file save.
   */
  async startDownload(
    videoTitle: string,
    format: VideoFormat,
    onProgress: ProgressCallback
  ): Promise<string> {
    const jobId = 'dl_' + Date.now() + '_' + Math.random().toString(36).substring(2, 6);
    const abortController = new AbortController();

    const initialJob: DownloadJob = {
      id: jobId,
      videoTitle,
      format,
      progressPercent: 0,
      bytesDownloaded: 0,
      totalBytes: format.filesizeBytes || 15 * 1024 * 1024,
      speedBytesPerSec: 0,
      speedFormatted: '0 KB/s',
      etaSeconds: 0,
      etaFormatted: '--:--',
      status: 'downloading',
      startedAt: Date.now(),
    };

    this.activeJobs.set(jobId, { abortController, job: initialJob });
    onProgress(initialJob);

    try {
      // Fetch stream from target URL
      let response: Response;
      try {
        response = await fetch(format.downloadUrl, {
          signal: abortController.signal,
          headers: {
            // Standard stream header
            Accept: '*/*',
          },
        });
      } catch (err: unknown) {
        if ((err as Error)?.name === 'AbortError') {
          const cancelledJob: DownloadJob = {
            ...initialJob,
            status: 'cancelled',
            errorMessage: 'डाउनलोड रद्द कर दिया गया (Download Cancelled).',
          };
          this.activeJobs.delete(jobId);
          onProgress(cancelledJob);
          throw new Error('Download was cancelled by user');
        }
        // Fallback or retry
        throw err;
      }

      if (!response.ok) {
        const errorText = await response.text().catch(() => '');
        throw new Error(errorText || `डाउनलोड त्रुटि: HTTP ${response.status} ${response.statusText}`);
      }

      const contentLength = response.headers.get('content-length');
      const totalBytes = contentLength ? parseInt(contentLength, 10) : format.filesizeBytes;
      initialJob.totalBytes = totalBytes;

      const reader = response.body?.getReader();
      if (!reader) {
        // Direct blob fallback if reader not available
        const blob = await response.blob();
        this.saveBlobToDevice(blob, videoTitle, format.ext);
        const completedJob: DownloadJob = {
          ...initialJob,
          progressPercent: 100,
          bytesDownloaded: totalBytes,
          status: 'completed',
        };
        this.activeJobs.delete(jobId);
        onProgress(completedJob);
        return jobId;
      }

      const chunks: Uint8Array[] = [];
      let receivedBytes = 0;
      let lastReportTime = Date.now();
      let lastReportBytes = 0;

      while (true) {
        if (abortController.signal.aborted) {
          throw new Error('Download was cancelled by user');
        }

        const { done, value } = await reader.read();
        if (done) break;

        chunks.push(value);
        receivedBytes += value.length;

        const now = Date.now();
        const timeDiff = (now - lastReportTime) / 1000;

        if (timeDiff >= 0.2 || receivedBytes >= totalBytes) {
          const bytesDiff = receivedBytes - lastReportBytes;
          const currentSpeed = timeDiff > 0 ? bytesDiff / timeDiff : 0;
          const remainingBytes = Math.max(0, totalBytes - receivedBytes);
          const etaSecs = currentSpeed > 0 ? Math.round(remainingBytes / currentSpeed) : 0;

          const progressPercent = Math.min(
            99,
            Math.round((receivedBytes / (totalBytes || 1)) * 100)
          );

          const updatedJob: DownloadJob = {
            ...initialJob,
            progressPercent,
            bytesDownloaded: receivedBytes,
            totalBytes,
            speedBytesPerSec: currentSpeed,
            speedFormatted: `${formatBytes(currentSpeed)}/s`,
            etaSeconds: etaSecs,
            etaFormatted: `${Math.floor(etaSecs / 60)}m ${etaSecs % 60}s`,
            status: 'downloading',
          };

          this.activeJobs.set(jobId, { abortController, job: updatedJob });
          onProgress(updatedJob);

          lastReportTime = now;
          lastReportBytes = receivedBytes;
        }
      }

      // Processing & Final Assembly
      const processingJob: DownloadJob = {
        ...initialJob,
        progressPercent: 100,
        bytesDownloaded: receivedBytes,
        speedFormatted: 'पूर्ण हो रहा है...',
        status: 'processing',
      };
      onProgress(processingJob);

      // Concatenate all chunks into final Blob
      const mimeType = format.ext === 'mp3' ? 'audio/mpeg' : format.ext === 'm4a' ? 'audio/mp4' : 'video/mp4';
      const finalBlob = new Blob(chunks as unknown as BlobPart[], { type: mimeType });

      // Save to client's device (Mobile & Desktop compatible)
      this.saveBlobToDevice(finalBlob, videoTitle, format.ext);

      const completedJob: DownloadJob = {
        ...processingJob,
        status: 'completed',
        speedFormatted: 'सफलतापूर्वक सहेजा गया',
      };
      this.activeJobs.delete(jobId);
      onProgress(completedJob);

      return jobId;
    } catch (error: unknown) {
      const err = error as Error;
      if (err.name === 'AbortError' || err.message.includes('cancelled')) {
        const cancelledJob: DownloadJob = {
          ...initialJob,
          status: 'cancelled',
          errorMessage: 'डाउनलोड उपयोगकर्ता द्वारा रद्द किया गया।',
        };
        this.activeJobs.delete(jobId);
        onProgress(cancelledJob);
        return jobId;
      }

      const errorJob: DownloadJob = {
        ...initialJob,
        status: 'error',
        errorMessage: err.message || 'डाउनलोड के दौरान अज्ञात त्रुटि उत्पन्न हुई।',
      };
      this.activeJobs.delete(jobId);
      onProgress(errorJob);
      throw error;
    }
  }

  /**
   * Cancels an ongoing download job
   */
  cancelDownload(jobId: string): boolean {
    const active = this.activeJobs.get(jobId);
    if (active) {
      active.abortController.abort();
      this.activeJobs.delete(jobId);
      return true;
    }
    return false;
  }

  /**
   * Saves a Blob directly to the client device in Android/iOS/Desktop browsers
   */
  private saveBlobToDevice(blob: Blob, rawTitle: string, ext: string) {
    // Sanitize title for filename
    const cleanTitle = (rawTitle || 'video')
      .replace(/[/\\?%*:|"<>]/g, '_')
      .trim()
      .substring(0, 80);

    const filename = `${cleanTitle}.${ext}`;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.style.display = 'none';
    document.body.appendChild(anchor);
    anchor.click();

    setTimeout(() => {
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
    }, 1500);
  }
}

export const downloadManager = new DownloadManager();
