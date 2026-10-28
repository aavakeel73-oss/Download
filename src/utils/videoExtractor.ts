/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { VideoMetadata, VideoFormat } from '../types/downloader';
import { validateVideoUrl, extractYouTubeId } from './security';
import { PRESET_SAMPLE_VIDEOS } from './mockSamples';

/**
 * Format bytes to readable string (KB, MB, GB)
 */
export function formatBytes(bytes: number, decimals = 1): string {
  if (!bytes || bytes <= 0) return 'उपलब्ध';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

/**
 * Format seconds to M:SS or H:MM:SS
 */
export function formatDuration(seconds: number): string {
  if (!seconds || isNaN(seconds)) return '0:00';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hrs > 0) {
    return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Analyzes and extracts real video details from YouTube or Facebook.
 * Strictly queries the real backend engine and NEVER substitutes unrelated sample videos.
 */
export async function analyzeVideoUrl(url: string): Promise<VideoMetadata> {
  const securityCheck = validateVideoUrl(url);
  if (!securityCheck.isValid) {
    throw new Error(securityCheck.errorReason || 'अमान्य वीडियो लिंक');
  }

  const validUrl = securityCheck.sanitizedUrl || url;

  // 1. Check if user clicked an explicit preset sample video button
  const matchedSample = PRESET_SAMPLE_VIDEOS.find(
    (s) => s.sourceUrl.toLowerCase() === validUrl.toLowerCase() ||
           (extractYouTubeId(validUrl) && extractYouTubeId(validUrl) === extractYouTubeId(s.sourceUrl))
  );
  if (matchedSample) {
    return matchedSample;
  }

  // 2. Query our real backend /api/analyze endpoint
  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url: validUrl }),
    });

    const data = await res.json().catch(() => null);

    if (!res.ok || !data?.success) {
      const errorMsg = data?.error || `सर्वर त्रुटि: HTTP ${res.status} (${res.statusText})`;
      throw new Error(errorMsg);
    }

    if (!data.metadata || !Array.isArray(data.metadata.formats) || data.metadata.formats.length === 0) {
      throw new Error('इस वीडियो के लिए कोई डाउनलोड करने योग्य प्रारूप (formats) नहीं मिले।');
    }

    return data.metadata as VideoMetadata;
  } catch (err: unknown) {
    const error = err as Error;
    // Strictly preserve error message. NEVER fall back to fake or demo sample videos!
    throw new Error(error.message || 'वीडियो का विश्लेषण करने में असमर्थ। कृपया जांचें कि वीडियो सार्वजनिक और उपलब्ध है।');
  }
}
