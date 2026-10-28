/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { X, Download, FileCode, Check, FolderArchive, Terminal, Shield } from 'lucide-react';
import { generateProjectZip } from '../utils/projectZipGenerator';

interface ExportProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  lang: 'hi' | 'en';
}

export const ExportProjectModal: React.FC<ExportProjectModalProps> = ({
  isOpen,
  onClose,
  lang,
}) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [downloadDone, setDownloadDone] = useState(false);

  if (!isOpen) return null;

  const handleDownloadZip = async () => {
    setIsGenerating(true);
    try {
      const blob = await generateProjectZip();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'streamrip-downloader-python-fullstack.zip';
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 1000);
      setDownloadDone(true);
      setTimeout(() => setDownloadDone(false), 4000);
    } catch (e) {
      console.error(e);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-950/85 backdrop-blur-md">
      <div className="w-full max-w-xl glass-panel rounded-2xl border border-cyan-500/30 shadow-2xl p-6 relative">
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/20 text-cyan-300">
              <FolderArchive className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100">
                {lang === 'hi' ? 'पूर्ण प्रोजेक्ट ZIP पैकेज' : 'Export Standalone Project ZIP'}
              </h2>
              <p className="text-xs text-slate-400">
                {lang === 'hi' ? 'Python Flask, yt-dlp, FFmpeg और HTML5 कोड डाउनलोड करें' : 'Download Python Flask, FFmpeg & HTML5 source bundle'}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Included Files Checklist */}
        <div className="space-y-2 mb-5">
          <span className="text-xs font-semibold text-slate-300 block">
            {lang === 'hi' ? 'ZIP में शामिल फाइलें (Turnkey Package):' : 'Package Contents:'}
          </span>
          <div className="grid grid-cols-2 gap-2 text-xs font-mono text-slate-300">
            <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800">
              <FileCode className="w-3.5 h-3.5 text-cyan-400" />
              <span>app.py (Flask API)</span>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800">
              <FileCode className="w-3.5 h-3.5 text-cyan-400" />
              <span>requirements.txt</span>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800">
              <FileCode className="w-3.5 h-3.5 text-cyan-400" />
              <span>Dockerfile (FFmpeg)</span>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800">
              <FileCode className="w-3.5 h-3.5 text-cyan-400" />
              <span>templates/index.html</span>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800">
              <FileCode className="w-3.5 h-3.5 text-cyan-400" />
              <span>static/style.css & js</span>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-slate-900 border border-slate-800">
              <FileCode className="w-3.5 h-3.5 text-cyan-400" />
              <span>README.md (हिंदी गाइड)</span>
            </div>
          </div>
        </div>

        {/* Quick run command preview */}
        <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono text-cyan-300 mb-5">
          <div className="text-[10px] text-slate-500 mb-1 flex items-center gap-1">
            <Terminal className="w-3 h-3" />
            <span>{lang === 'hi' ? 'चलाने का तरीका:' : 'Quick Run:'}</span>
          </div>
          <code>pip install -r requirements.txt && python app.py</code>
        </div>

        {/* Download Button */}
        <button
          onClick={handleDownloadZip}
          disabled={isGenerating}
          className="w-full py-3.5 bg-gradient-to-r from-sky-400 via-cyan-400 to-blue-500 hover:from-sky-300 hover:to-blue-400 text-slate-950 font-bold text-sm rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 active:scale-[0.99] transition-all disabled:opacity-50"
        >
          {downloadDone ? (
            <>
              <Check className="w-4 h-4 stroke-[2.5]" />
              <span>{lang === 'hi' ? 'ZIP डाउनलोड शुरू हो गया!' : 'ZIP Download Started!'}</span>
            </>
          ) : isGenerating ? (
            <span>{lang === 'hi' ? 'ZIP तैयार हो रहा है...' : 'Generating ZIP...'}</span>
          ) : (
            <>
              <Download className="w-4 h-4 stroke-[2.5]" />
              <span>{lang === 'hi' ? 'पूर्ण ZIP प्रोजेक्ट डाउनलोड करें' : 'Download Complete Project (.ZIP)'}</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};
