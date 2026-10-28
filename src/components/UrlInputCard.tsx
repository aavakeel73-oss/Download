/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { Search, Clipboard, X, Sparkles, Youtube, Facebook, AlertCircle, Loader2 } from 'lucide-react';
import { PlatformType } from '../types/downloader';
import { PRESET_SAMPLE_VIDEOS } from '../utils/mockSamples';

interface UrlInputCardProps {
  url: string;
  setUrl: (val: string) => void;
  selectedPlatform: PlatformType;
  setSelectedPlatform: (p: PlatformType) => void;
  onAnalyze: (customUrl?: string) => void;
  isLoading: boolean;
  errorMessage: string | null;
  lang: 'hi' | 'en';
}

export const UrlInputCard: React.FC<UrlInputCardProps> = ({
  url,
  setUrl,
  selectedPlatform,
  setSelectedPlatform,
  onAnalyze,
  isLoading,
  errorMessage,
  lang,
}) => {
  const [pasteFeedback, setPasteFeedback] = useState<string | null>(null);

  const handlePaste = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text) {
          setUrl(text);
          setPasteFeedback(lang === 'hi' ? 'पेस्ट हो गया!' : 'Pasted!');
          setTimeout(() => setPasteFeedback(null), 1500);
        }
      } else {
        setPasteFeedback(lang === 'hi' ? 'मैन्युअल पेस्ट करें (Ctrl+V)' : 'Paste manually (Ctrl+V)');
        setTimeout(() => setPasteFeedback(null), 2000);
      }
    } catch {
      setPasteFeedback(lang === 'hi' ? 'क्लिपबोर्ड अनुमति दें' : 'Allow clipboard permission');
      setTimeout(() => setPasteFeedback(null), 2000);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !isLoading) {
      onAnalyze();
    }
  };

  return (
    <div className="w-full glass-panel rounded-2xl p-4 sm:p-6 shadow-2xl relative overflow-hidden transition-all border border-cyan-500/20">
      {/* Subtle background glow */}
      <div className="absolute -top-24 -right-24 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

      {/* Platform Selector Tabs */}
      <div className="flex items-center justify-between flex-wrap gap-2 mb-4 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-1.5 p-1 bg-slate-900/90 rounded-xl border border-slate-800">
          <button
            onClick={() => setSelectedPlatform('youtube')}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all ${
              selectedPlatform === 'youtube'
                ? 'bg-gradient-to-r from-red-600 to-rose-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Youtube className="w-4 h-4" />
            <span>YouTube Video & Shorts</span>
          </button>

          <button
            onClick={() => setSelectedPlatform('facebook')}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded-lg transition-all ${
              selectedPlatform === 'facebook'
                ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Facebook className="w-4 h-4" />
            <span>Facebook & Reels</span>
          </button>
        </div>

        <div className="text-xs text-slate-400 font-mono hidden sm:flex items-center gap-2">
          <span>SSRF Protected</span>
          <span aria-hidden="true">·</span>
          <span>Fast MP4/MP3</span>
        </div>
      </div>

      {/* Input Group */}
      <div className="relative flex flex-col sm:flex-row items-stretch gap-2.5">
        <div className="relative flex-1">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              selectedPlatform === 'youtube'
                ? (lang === 'hi' ? 'YouTube वीडियो या Shorts लिंक यहाँ पेस्ट करें...' : 'Paste YouTube Video or Shorts link here...')
                : (lang === 'hi' ? 'Facebook वीडियो या Reel लिंक यहाँ पेस्ट करें...' : 'Paste Facebook Video or Reel link here...')
            }
            className="w-full pl-10 pr-24 py-3.5 bg-slate-900/90 border border-slate-700/80 rounded-xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 transition-all font-mono"
          />

          <div className="absolute inset-y-0 right-0 pr-2 flex items-center gap-1">
            {url && (
              <button
                onClick={() => setUrl('')}
                className="p-1.5 text-slate-400 hover:text-slate-200 rounded-md hover:bg-slate-800 transition-colors"
                title="Clear"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            <button
              onClick={handlePaste}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-cyan-300 hover:text-cyan-200 bg-cyan-950/40 border border-cyan-800/40 rounded-lg hover:bg-cyan-900/40 transition-colors"
              title="Paste from clipboard"
            >
              <Clipboard className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{pasteFeedback || (lang === 'hi' ? 'पेस्ट' : 'Paste')}</span>
            </button>
          </div>
        </div>

        <button
          onClick={() => onAnalyze()}
          disabled={isLoading || !url.trim()}
          className="flex items-center justify-center gap-2 px-6 py-3.5 bg-gradient-to-r from-sky-500 via-cyan-500 to-blue-500 hover:from-sky-400 hover:to-blue-400 text-slate-950 font-bold text-sm rounded-xl shadow-lg shadow-cyan-500/25 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all shrink-0"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-slate-950" />
              <span>{lang === 'hi' ? 'विश्लेषण चालू है...' : 'Analyzing...'}</span>
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4 fill-current" />
              <span>{lang === 'hi' ? 'वीडियो विश्लेषण करें' : 'Analyze Video'}</span>
            </>
          )}
        </button>
      </div>

      {/* Error Display */}
      {errorMessage && (
        <div className="mt-3.5 p-3 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-200 text-xs flex items-start gap-2.5 animate-fadeIn">
          <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1 font-medium leading-relaxed">{errorMessage}</div>
        </div>
      )}

      {/* Quick Verified Test Presets */}
      <div className="mt-4 pt-3.5 border-t border-slate-800/80 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-slate-400 font-medium">
          {lang === 'hi' ? 'त्वरित टेस्ट वीडियो (1-क्लिक):' : 'Instant Test Samples (1-Click):'}
        </span>
        {PRESET_SAMPLE_VIDEOS.map((sample) => (
          <button
            key={sample.id}
            onClick={() => {
              setUrl(sample.sourceUrl);
              setSelectedPlatform(sample.platform);
              onAnalyze(sample.sourceUrl);
            }}
            className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-cyan-300 hover:border-cyan-500/40 transition-all font-mono text-[11px]"
          >
            {sample.platform === 'youtube' ? '▶ YouTube' : '✦ FB Reel'} · {sample.title.substring(0, 24)}...
          </button>
        ))}
      </div>
    </div>
  );
};
