/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { DownloadJob } from '../types/downloader';
import { formatBytes } from '../utils/videoExtractor';
import { Download, XCircle, CheckCircle, AlertTriangle, Loader2, Gauge, Clock } from 'lucide-react';

interface DownloadProgressModalProps {
  job: DownloadJob | null;
  onCancel: (jobId: string) => void;
  onClose: () => void;
  lang: 'hi' | 'en';
}

export const DownloadProgressModal: React.FC<DownloadProgressModalProps> = ({
  job,
  onCancel,
  onClose,
  lang,
}) => {
  if (!job) return null;

  const isDownloading = job.status === 'downloading';
  const isProcessing = job.status === 'processing';
  const isCompleted = job.status === 'completed';
  const isCancelled = job.status === 'cancelled';
  const isError = job.status === 'error';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fadeIn">
      <div className="w-full max-w-md glass-panel rounded-2xl p-6 border border-cyan-500/30 shadow-2xl relative">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className={`p-2 rounded-xl ${
              isCompleted ? 'bg-emerald-500/20 text-emerald-400' :
              isError ? 'bg-rose-500/20 text-rose-400' :
              isCancelled ? 'bg-amber-500/20 text-amber-400' :
              'bg-cyan-500/20 text-cyan-400 animate-pulse'
            }`}>
              {isCompleted ? <CheckCircle className="w-5 h-5" /> :
               isError ? <AlertTriangle className="w-5 h-5" /> :
               isCancelled ? <XCircle className="w-5 h-5" /> :
               <Download className="w-5 h-5" />}
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-100">
                {isCompleted ? (lang === 'hi' ? 'डाउनलोड पूर्ण हुआ!' : 'Download Complete!') :
                 isError ? (lang === 'hi' ? 'डाउनलोड त्रुटि' : 'Download Error') :
                 isCancelled ? (lang === 'hi' ? 'रद्द किया गया' : 'Cancelled') :
                 isProcessing ? (lang === 'hi' ? 'फ़ाइल संसाधित हो रही है...' : 'Processing File...') :
                 (lang === 'hi' ? 'डाउनलोडिंग चालू है...' : 'Downloading Media...')}
              </h3>
              <p className="text-[11px] text-slate-400 font-mono">
                {job.format.qualityLabel} · {job.format.ext.toUpperCase()}
              </p>
            </div>
          </div>

          {(isCompleted || isCancelled || isError) && (
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 text-xs px-2 py-1 rounded bg-slate-900 border border-slate-800"
            >
              {lang === 'hi' ? 'बंद करें' : 'Close'}
            </button>
          )}
        </div>

        {/* Video Title */}
        <p className="text-xs text-slate-300 font-medium line-clamp-1 mb-4">
          {job.videoTitle}
        </p>

        {/* Progress Bar */}
        <div className="w-full bg-slate-900 h-3 rounded-full overflow-hidden border border-slate-800 mb-3 relative">
          <div
            className={`h-full transition-all duration-300 rounded-full ${
              isCompleted ? 'bg-gradient-to-r from-emerald-500 to-teal-400' :
              isError ? 'bg-rose-500' :
              isCancelled ? 'bg-amber-500' :
              'bg-gradient-to-r from-sky-500 via-cyan-400 to-blue-500'
            }`}
            style={{ width: `${job.progressPercent}%` }}
          />
        </div>

        {/* Numeric Telemetry */}
        <div className="grid grid-cols-3 gap-2 py-2 px-3 rounded-xl bg-slate-900/60 border border-slate-800/80 text-xs font-mono mb-4">
          <div>
            <div className="text-[10px] text-slate-500">{lang === 'hi' ? 'प्रगति' : 'Progress'}</div>
            <div className="font-bold text-cyan-300 tabular-nums">{job.progressPercent}%</div>
          </div>
          <div>
            <div className="text-[10px] text-slate-500 flex items-center gap-1">
              <Gauge className="w-2.5 h-2.5" />
              <span>{lang === 'hi' ? 'गति' : 'Speed'}</span>
            </div>
            <div className="font-semibold text-slate-200 tabular-nums truncate">
              {job.speedFormatted || '0 KB/s'}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-slate-500 flex items-center justify-end gap-1">
              <Clock className="w-2.5 h-2.5" />
              <span>{lang === 'hi' ? 'शेष समय' : 'ETA'}</span>
            </div>
            <div className="font-semibold text-slate-200 tabular-nums">
              {isCompleted ? '0s' : job.etaFormatted || '--:--'}
            </div>
          </div>
        </div>

        {/* Transfer Bytes */}
        <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono mb-5">
          <span>{formatBytes(job.bytesDownloaded)} / {formatBytes(job.totalBytes)}</span>
          <span className="text-slate-500">
            {isDownloading && (lang === 'hi' ? 'स्ट्रीमिंग डेटा...' : 'Streaming chunk data...')}
          </span>
        </div>

        {/* Error or cancellation details */}
        {isError && (
          <div className="p-3 mb-4 rounded-xl bg-rose-950/40 border border-rose-500/30 text-rose-200 text-xs">
            {job.errorMessage || 'अज्ञात त्रुटि उत्पन्न हुई।'}
          </div>
        )}

        {/* Bottom Actions */}
        <div className="flex items-center justify-end gap-2">
          {isDownloading && (
            <button
              onClick={() => onCancel(job.id)}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 transition-all"
            >
              {lang === 'hi' ? 'डाउनलोड रद्द करें' : 'Cancel Download'}
            </button>
          )}

          {isCompleted && (
            <button
              onClick={onClose}
              className="px-5 py-2 text-xs font-bold rounded-lg bg-gradient-to-r from-emerald-500 to-teal-400 text-slate-950 shadow-md transition-all hover:opacity-95"
            >
              {lang === 'hi' ? 'फ़ाइल सहेज ली गई ✓' : 'File Saved ✓'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
