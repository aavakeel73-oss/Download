/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { SecurityCheckResult } from '../types/downloader';

const PRIVATE_IP_PATTERNS = [
  /^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
  /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,
  /^192\.168\.\d{1,3}\.\d{1,3}$/,
  /^172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}$/,
  /^169\.254\.\d{1,3}\.\d{1,3}$/, // AWS / cloud metadata IP
  /^0\.0\.0\.0$/,
  /^localhost$/i,
  /^\[::1\]$/,
];

const YOUTUBE_DOMAINS = [
  'youtube.com',
  'www.youtube.com',
  'm.youtube.com',
  'music.youtube.com',
  'youtu.be',
];

const FACEBOOK_DOMAINS = [
  'facebook.com',
  'www.facebook.com',
  'm.facebook.com',
  'web.facebook.com',
  'fb.watch',
  'fb.com',
];

/**
 * Validates and checks a candidate video URL against SSRF and platform restrictions.
 */
export function validateVideoUrl(rawUrl: string): SecurityCheckResult {
  const trimmed = (rawUrl || '').trim();
  if (!trimmed) {
    return {
      isValid: false,
      detectedPlatform: 'invalid',
      errorReason: 'कृपया एक मान्य वीडियो लिंक (URL) दर्ज करें। (Please enter a valid video link)',
    };
  }

  // Check scheme
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return {
      isValid: false,
      detectedPlatform: 'invalid',
      errorReason: 'अमान्य URL प्रारूप! लिंक https:// या http:// से शुरू होना चाहिए।',
    };
  }

  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return {
      isValid: false,
      detectedPlatform: 'invalid',
      errorReason: 'सुरक्षा नियम: केवल सुरक्षित HTTP/HTTPS प्रोटोकॉल लिंक ही स्वीकार्य हैं।',
    };
  }

  const hostname = parsed.hostname.toLowerCase();

  // SSRF Protection: Check against loopback and private networks
  for (const pattern of PRIVATE_IP_PATTERNS) {
    if (pattern.test(hostname)) {
      return {
        isValid: false,
        detectedPlatform: 'invalid',
        errorReason: 'सुरक्षा अवरोध (SSRF Blocked): आंतरिक या स्थानीय IP पते अनुमत नहीं हैं।',
      };
    }
  }

  // Check if YouTube
  const isYouTube = YOUTUBE_DOMAINS.some(
    (d) => hostname === d || hostname.endsWith('.' + d)
  );

  if (isYouTube) {
    // Validate YouTube path/queries
    if (hostname.includes('youtu.be')) {
      const videoId = parsed.pathname.slice(1);
      if (!videoId) {
        return {
          isValid: false,
          detectedPlatform: 'youtube',
          errorReason: 'YouTu.be लिंक में वीडियो ID मौजूद नहीं है।',
        };
      }
    } else {
      const hasWatch = parsed.pathname.includes('/watch') && parsed.searchParams.has('v');
      const hasShorts = parsed.pathname.includes('/shorts/');
      const hasEmbed = parsed.pathname.includes('/embed/');
      const hasLive = parsed.pathname.includes('/live/');

      if (!hasWatch && !hasShorts && !hasEmbed && !hasLive) {
        return {
          isValid: false,
          detectedPlatform: 'youtube',
          errorReason: 'यह एक वैध YouTube वीडियो या Shorts लिंक नहीं लगता। उदाहरण: https://www.youtube.com/watch?v=... या https://youtu.be/...',
        };
      }
    }

    return {
      isValid: true,
      detectedPlatform: 'youtube',
      sanitizedUrl: parsed.toString(),
    };
  }

  // Check if Facebook
  const isFacebook = FACEBOOK_DOMAINS.some(
    (d) => hostname === d || hostname.endsWith('.' + d)
  );

  if (isFacebook) {
    const p = parsed.pathname;
    const isVideoPath =
      p.includes('/videos/') ||
      p.includes('/reel/') ||
      p.includes('/watch') ||
      p.includes('/story.php') ||
      parsed.searchParams.has('v') ||
      hostname.includes('fb.watch');

    if (!isVideoPath && p.length <= 1) {
      return {
        isValid: false,
        detectedPlatform: 'facebook',
        errorReason: 'Facebook वीडियो या Reel लिंक दर्ज करें (उदा. https://www.facebook.com/watch/?v=... या https://fb.watch/...)',
      };
    }

    return {
      isValid: true,
      detectedPlatform: 'facebook',
      sanitizedUrl: parsed.toString(),
    };
  }

  return {
    isValid: false,
    detectedPlatform: 'invalid',
    errorReason: 'असमर्थित प्लेटफॉर्म! केवल YouTube (Videos/Shorts) और Facebook (Videos/Reels) समर्थित हैं।',
  };
}

/**
 * Extracts YouTube video ID if present
 */
export function extractYouTubeId(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes('youtu.be')) {
      return parsed.pathname.slice(1).split('?')[0];
    }
    if (parsed.pathname.includes('/shorts/')) {
      return parsed.pathname.split('/shorts/')[1].split('/')[0];
    }
    if (parsed.pathname.includes('/embed/')) {
      return parsed.pathname.split('/embed/')[1].split('/')[0];
    }
    return parsed.searchParams.get('v');
  } catch {
    return null;
  }
}
