/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { DownloadCloud, Moon, Sun, BookOpen, ShieldCheck, Film } from 'lucide-react';

interface HeaderProps {
  isDarkMode: boolean;
  onToggleTheme: () => void;
  lang: 'hi' | 'en';
  onToggleLang: () => void;
  onOpenGuide: () => void;
  onOpenExport: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  isDarkMode,
  onToggleTheme,
  lang,
  onToggleLang,
  onOpenGuide,
  onOpenExport,
}) => {
  return (
    <header className="w-full border-b border-cyan-500/10 bg-slate-950/80 backdrop-blur-xl sticky top-0 z-40 transition-colors">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        {/* Zone 1: Single text element wordmark */}
        <div className="flex items-center gap-2.5 shrink-0">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-500 to-cyan-400 flex items-center justify-center text-slate-950 shadow-md shadow-cyan-500/20">
            <Film className="w-5 h-5 stroke-[2.2]" />
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-lg font-bold tracking-tight bg-gradient-to-r from-sky-400 via-cyan-300 to-blue-400 bg-clip-text text-transparent whitespace-nowrap">
              StreamRip
            </span>
            <span className="text-[10px] font-semibold text-cyan-400/80 uppercase tracking-wider font-mono">
              v2.4
            </span>
          </div>
        </div>

        {/* Zone 2: Clean single-line nav actions & quick guides */}
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-400">
          <button
            onClick={onOpenGuide}
            className="flex items-center gap-1.5 hover:text-cyan-300 transition-colors whitespace-nowrap"
          >
            <BookOpen className="w-4 h-4 text-cyan-400" />
            <span>{lang === 'hi' ? 'डिप्लॉयमेंट गाइड (हिंदी)' : 'Deployment Guide'}</span>
          </button>
          <a
            href="#compliance"
            className="flex items-center gap-1.5 hover:text-cyan-300 transition-colors whitespace-nowrap"
          >
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>{lang === 'hi' ? 'सुरक्षा एवं नियम' : 'Terms & Safety'}</span>
          </a>
        </nav>

        {/* Zone 3: Primary action + Utilities */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <button
            onClick={onToggleLang}
            className="px-2.5 py-1 text-xs font-semibold rounded-lg border border-slate-800 bg-slate-900/60 text-slate-300 hover:text-white hover:border-cyan-500/30 transition-all whitespace-nowrap"
            title="भाषा बदलें / Toggle Language"
          >
            {lang === 'hi' ? 'EN' : 'हिन्दी'}
          </button>

          <button
            onClick={onToggleTheme}
            className="p-2 rounded-lg border border-slate-800 bg-slate-900/60 text-slate-400 hover:text-cyan-300 hover:border-cyan-500/30 transition-all"
            aria-label="Toggle dark/light mode"
          >
            {isDarkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>

          <button
            onClick={onOpenExport}
            className="flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-slate-950 bg-gradient-to-r from-sky-400 to-cyan-400 rounded-lg hover:from-sky-300 hover:to-cyan-300 active:scale-[0.98] transition-all shadow-md shadow-cyan-500/20 whitespace-nowrap"
          >
            <DownloadCloud className="w-4 h-4 stroke-[2.2]" />
            <span className="hidden sm:inline">{lang === 'hi' ? 'प्रोजेक्ट ZIP' : 'Export ZIP'}</span>
          </button>
        </div>
      </div>
    </header>
  );
};
