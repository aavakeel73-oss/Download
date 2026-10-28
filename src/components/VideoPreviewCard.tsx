/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { VideoMetadata, VideoFormat } from '../types/downloader';
import { Play, Download, Music, Video, Clock, Eye, CheckCircle2, ShieldAlert } from 'lucide-react';

interface VideoPreviewCardProps {
  metadata: VideoMetadata;
  onSelectFormat: (format: VideoFormat) => void;
  lang: 'hi' | 'en';
}

export const VideoPreviewCard: React.FC<VideoPreviewCardProps> = ({
  metadata,
  onSelectFormat,
  lang,
}) => {
  const [activeTab, setActiveTab] = useState<'video' | 'audio'>('video');
  const [imgError, setImgError] = useState(false);

  const videoFormats = metadata.formats.filter((f) => f.hasVideo);
  const audioFormats = metadata.formats.filter((f) => !f.hasVideo && f.hasAudio);

  return (
    <div className="w-full glass-panel rounded-2xl p-5 sm:p-7 shadow-2xl border border-cyan-500/20 transition-all">
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Left: Thumbnail container */}
        <div className="relative w-full lg:w-80 h-48 sm:h-52 rounded-xl overflow-hidden shrink-0 border border-slate-800 bg-slate-900 group">
          {!imgError && metadata.thumbnail ? (
            <img
              src={metadata.thumbnail}
              alt={metadata.title}
              onError={() => setImgError(true)}
              referrerPolicy="no-referrer"
              className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 text-slate-400">
              <Play className="w-10 h-10 text-cyan-400/80 mb-2" />
              <span className="text-xs font-mono">{metadata.platform.toUpperCase()} Video</span>
            </div>
          )}

          {/* Duration Badge */}
          <div className="absolute bottom-2.5 right-2.5 px-2 py-0.5 rounded bg-black/85 backdrop-blur-md text-white font-mono text-xs font-semibold flex items-center gap-1 shadow-md">
            <Clock className="w-3 h-3 text-cyan-400" />
            <span>{metadata.durationFormatted}</span>
          </div>

          {/* Platform Tag */}
          <div className="absolute top-2.5 left-2.5 px-2 py-0.5 rounded bg-black/80 backdrop-blur-md text-white text-[11px] font-semibold flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${metadata.platform === 'youtube' ? 'bg-red-500' : 'bg-blue-500'}`} />
            <span className="capitalize">{metadata.platform}</span>
          </div>
        </div>

        {/* Right: Info and Download Formats */}
        <div className="flex-1 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs text-slate-400 mb-1.5 font-medium">
              <span>{metadata.author}</span>
              <span aria-hidden="true">·</span>
              <span className="flex items-center gap-1">
                <Eye className="w-3 h-3 text-slate-500" />
                <span className="tabular-nums font-mono">{metadata.viewsFormatted}</span>
              </span>
              <span aria-hidden="true">·</span>
              <span className="text-emerald-400 flex items-center gap-1 font-mono text-[11px]">
                <CheckCircle2 className="w-3 h-3" />
                {lang === 'hi' ? 'सत्यापित' : 'Verified'}
              </span>
            </div>

            <h2 className="text-lg sm:text-xl font-bold text-slate-100 leading-snug mb-2 line-clamp-2">
              {metadata.title}
            </h2>

            {metadata.description && (
              <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed mb-4">
                {metadata.description}
              </p>
            )}

            {metadata.license && (
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-950/30 border border-emerald-500/20 text-emerald-300 text-[11px] font-mono mb-4">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                <span>{metadata.license}</span>
              </div>
            )}
          </div>

          {/* Format Tabs (Video vs Audio) */}
          <div className="mt-2 pt-4 border-t border-slate-800">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-1 p-1 bg-slate-900 rounded-lg border border-slate-800">
                <button
                  onClick={() => setActiveTab('video')}
                  className={`flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                    activeTab === 'video'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Video className="w-3.5 h-3.5" />
                  <span>{lang === 'hi' ? 'वीडियो (MP4)' : 'Video (MP4)'}</span>
                </button>
                <button
                  onClick={() => setActiveTab('audio')}
                  className={`flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                    activeTab === 'audio'
                      ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Music className="w-3.5 h-3.5" />
                  <span>{lang === 'hi' ? 'ऑडियो (MP3 / M4A)' : 'Audio (MP3)'}</span>
                </button>
              </div>

              <span className="text-[11px] text-slate-400 font-mono hidden sm:inline">
                {lang === 'hi' ? 'क्वालिटी चुनें:' : 'Select Quality:'}
              </span>
            </div>

            {/* Quality Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2.5">
              {(activeTab === 'video' ? videoFormats : audioFormats).map((fmt) => (
                <button
                  key={fmt.formatId}
                  onClick={() => onSelectFormat(fmt)}
                  className="group flex flex-col items-start p-3 rounded-xl bg-slate-900/80 hover:bg-slate-800 border border-slate-800 hover:border-cyan-400/50 transition-all text-left relative overflow-hidden"
                >
                  {fmt.isPopular && (
                    <span className="absolute top-1.5 right-1.5 px-1.5 py-0.2 bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 text-[9px] font-mono rounded">
                      BEST
                    </span>
                  )}
                  <div className="flex items-center gap-1.5 text-xs font-bold text-slate-100 group-hover:text-cyan-300 transition-colors">
                    <Download className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                    <span>{fmt.qualityLabel}</span>
                  </div>
                  <div className="flex items-center justify-between w-full mt-1.5 text-[11px] text-slate-400 font-mono">
                    <span>{fmt.ext.toUpperCase()}</span>
                    <span className="text-slate-300 font-semibold">{fmt.filesizeFormatted}</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
