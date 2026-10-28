/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export type PlatformType = 'youtube' | 'facebook' | 'auto';

export interface VideoFormat {
  formatId: string;
  qualityLabel: '144p' | '240p' | '360p' | '480p' | '720p HD' | '1080p Full HD' | '1440p 2K' | '2160p 4K' | 'Audio MP3' | 'Audio M4A';
  resolution?: string;
  ext: 'mp4' | 'mp3' | 'm4a' | 'webm';
  hasVideo: boolean;
  hasAudio: boolean;
  bitrateKbps: number;
  filesizeBytes: number;
  filesizeFormatted: string;
  fps?: number;
  downloadUrl: string;
  isPopular?: boolean;
}

export interface VideoMetadata {
  id: string;
  title: string;
  description: string;
  thumbnail: string;
  durationSeconds: number;
  durationFormatted: string;
  author: string;
  authorAvatar?: string;
  views: number;
  viewsFormatted: string;
  platform: 'youtube' | 'facebook';
  sourceUrl: string;
  isLive: boolean;
  isPrivate: boolean;
  license?: string;
  formats: VideoFormat[];
}

export interface DownloadJob {
  id: string;
  videoTitle: string;
  format: VideoFormat;
  progressPercent: number;
  bytesDownloaded: number;
  totalBytes: number;
  speedBytesPerSec: number;
  speedFormatted: string;
  etaSeconds: number;
  etaFormatted: string;
  status: 'idle' | 'downloading' | 'processing' | 'completed' | 'cancelled' | 'error';
  errorMessage?: string;
  startedAt: number;
}

export interface SecurityCheckResult {
  isValid: boolean;
  detectedPlatform: 'youtube' | 'facebook' | 'invalid';
  sanitizedUrl?: string;
  errorReason?: string;
}
