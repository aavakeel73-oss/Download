/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { UrlInputCard } from './components/UrlInputCard';
import { VideoPreviewCard } from './components/VideoPreviewCard';
import { DownloadProgressModal } from './components/DownloadProgressModal';
import { DeploymentGuideModal } from './components/DeploymentGuideModal';
import { ExportProjectModal } from './components/ExportProjectModal';
import { SecurityComplianceCard } from './components/SecurityComplianceCard';
import { PlatformType, VideoMetadata, VideoFormat, DownloadJob } from './types/downloader';
import { analyzeVideoUrl } from './utils/videoExtractor';
import { downloadManager } from './utils/downloadManager';
import { Sparkles, Shield, Zap, CheckCircle2, ArrowDownCircle } from 'lucide-react';

export default function App() {
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [lang, setLang] = useState<'hi' | 'en'>('hi');
  const [selectedPlatform, setSelectedPlatform] = useState<PlatformType>('youtube');
  const [url, setUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [videoMetadata, setVideoMetadata] = useState<VideoMetadata | null>(null);
  const [activeDownloadJob, setActiveDownloadJob] = useState<DownloadJob | null>(null);
  const [showProgressModal, setShowProgressModal] = useState(false);
  const [showGuideModal, setShowGuideModal] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);

  // Sync theme with html class
  useEffect(() => {
    const root = document.documentElement;
    if (isDarkMode) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [isDarkMode]);

  // Handle video analysis
  const handleAnalyze = async (customUrl?: string) => {
    const targetUrl = customUrl || url;
    if (!targetUrl.trim()) {
      setErrorMessage(
        lang === 'hi'
          ? 'कृपया एक वैध YouTube या Facebook वीडियो लिंक दर्ज करें।'
          : 'Please enter a valid YouTube or Facebook video link.'
      );
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const meta = await analyzeVideoUrl(targetUrl);
      setVideoMetadata(meta);
      setSelectedPlatform(meta.platform);
    } catch (err: unknown) {
      const error = err as Error;
      setErrorMessage(error.message || 'वीडियो डेटा लोड करने में असमर्थ');
      setVideoMetadata(null);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle format selection and start real chunked streaming download
  const handleSelectFormat = async (format: VideoFormat) => {
    if (!videoMetadata) return;

    setShowProgressModal(true);

    try {
      await downloadManager.startDownload(
        videoMetadata.title,
        format,
        (updatedJob) => {
          setActiveDownloadJob(updatedJob);
        }
      );
    } catch (err) {
      console.warn('Download flow status:', err);
    }
  };

  const handleCancelDownload = (jobId: string) => {
    downloadManager.cancelDownload(jobId);
  };

  return (
    <div className={`min-h-screen flex flex-col ${isDarkMode ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'} transition-colors duration-200`}>
      {/* Background ambient lighting */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[360px] bg-gradient-to-b from-cyan-500/10 via-sky-500/5 to-transparent blur-[120px]" />
      </div>

      {/* Top Bar Contract (3 zones) */}
      <Header
        isDarkMode={isDarkMode}
        onToggleTheme={() => setIsDarkMode(!isDarkMode)}
        lang={lang}
        onToggleLang={() => setLang(lang === 'hi' ? 'en' : 'hi')}
        onOpenGuide={() => setShowGuideModal(true)}
        onOpenExport={() => setShowExportModal(true)}
      />

      {/* Main Container */}
      <main className="relative z-10 flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-12 flex flex-col gap-8">
        {/* Hero Section */}
        <div className="text-center space-y-3 max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/40 border border-cyan-500/30 text-cyan-300 text-xs font-mono font-medium">
            <Sparkles className="w-3.5 h-3.5" />
            <span>{lang === 'hi' ? 'उच्च गति 4K / 1080p MP4 एवं MP3 डाउनलोडर' : 'High-Speed 4K / 1080p MP4 & MP3 Downloader'}</span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight leading-tight">
            <span className="bg-gradient-to-r from-sky-400 via-cyan-300 to-blue-500 bg-clip-text text-transparent">
              YouTube & Facebook
            </span>{' '}
            <span className={isDarkMode ? 'text-white' : 'text-slate-900'}>
              {lang === 'hi' ? 'वीडियो डाउनलोडर' : 'Video Downloader'}
            </span>
          </h1>

          <p className="text-sm sm:text-base text-slate-400 max-w-xl mx-auto leading-relaxed">
            {lang === 'hi'
              ? 'बिना वॉटरमार्क, 100% सुरक्षित और तेज़। केवल सार्वजनिक और अधिकृत वीडियो डाउनलोड के लिए पूर्ण अनुपालन।'
              : 'Zero watermarks, 100% secure, and high-speed. Fully compliant for public & authorized media.'}
          </p>
        </div>

        {/* Input Card */}
        <UrlInputCard
          url={url}
          setUrl={setUrl}
          selectedPlatform={selectedPlatform}
          setSelectedPlatform={setSelectedPlatform}
          onAnalyze={handleAnalyze}
          isLoading={isLoading}
          errorMessage={errorMessage}
          lang={lang}
        />

        {/* Video Preview & Format Selection */}
        {videoMetadata && (
          <div className="animate-fadeIn">
            <VideoPreviewCard
              metadata={videoMetadata}
              onSelectFormat={handleSelectFormat}
              lang={lang}
            />
          </div>
        )}

        {/* Feature Highlights Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4">
          <div className="p-4 rounded-xl glass-panel border border-slate-800 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-sky-500/15 text-sky-400 shrink-0">
              <Zap className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-200 mb-1">
                {lang === 'hi' ? 'बिजली जैसी तेज़ गति' : 'Lightning Fast Speed'}
              </h4>
              <p className="text-[11px] text-slate-400 leading-normal">
                {lang === 'hi'
                  ? 'चंक-आधारित डायरेक्ट मीडिया स्ट्रीमिंग जिससे अधिकतम बैंडविड्थ प्राप्त होती है।'
                  : 'Direct chunked streaming for maximum connection throughput.'}
              </p>
            </div>
          </div>

          <div className="p-4 rounded-xl glass-panel border border-slate-800 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/15 text-emerald-400 shrink-0">
              <Shield className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-200 mb-1">
                {lang === 'hi' ? 'पूर्ण SSRF सुरक्षा' : 'Robust SSRF Security'}
              </h4>
              <p className="text-[11px] text-slate-400 leading-normal">
                {lang === 'hi'
                  ? 'आंतरिक IP व अनाधिकृत पतों को स्वतः ब्लॉक करने वाला साइबर सुरक्षा कवच।'
                  : 'Automated RFC1918 and cloud metadata address sanitization.'}
              </p>
            </div>
          </div>

          <div className="p-4 rounded-xl glass-panel border border-slate-800 flex items-start gap-3">
            <div className="p-2 rounded-lg bg-cyan-500/15 text-cyan-400 shrink-0">
              <ArrowDownCircle className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-slate-200 mb-1">
                {lang === 'hi' ? 'मोबाइल ब्राउज़र संगत' : 'Mobile Browser Ready'}
              </h4>
              <p className="text-[11px] text-slate-400 leading-normal">
                {lang === 'hi'
                  ? 'Android Chrome व iPhone Safari पर बिना किसी अतिरिक्त ऐप के सीधे डाउनलोड।'
                  : 'Direct native file saving across Android Chrome and iOS Safari.'}
              </p>
            </div>
          </div>
        </div>

        {/* Security & Legal Compliance Card */}
        <SecurityComplianceCard lang={lang} />
      </main>

      {/* Footer */}
      <footer className="w-full border-t border-slate-900 bg-slate-950/80 py-6 text-center text-xs text-slate-500 relative z-10">
        <div className="max-w-5xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p>
            © {new Date().getFullYear()} StreamRip · {lang === 'hi' ? 'केवल अधिकृत एवं सार्वजनिक वीडियो डाउनलोड के लिए' : 'Authorized & Public Video Downloader'}
          </p>
          <div className="flex items-center gap-4 text-[11px] text-slate-400 font-mono">
            <span>yt-dlp Engine</span>
            <span aria-hidden="true">·</span>
            <span>FFmpeg Media Merger</span>
            <span aria-hidden="true">·</span>
            <span>Python Flask API</span>
          </div>
        </div>
      </footer>

      {/* Progress & Speed Modal */}
      <DownloadProgressModal
        job={activeDownloadJob}
        onCancel={handleCancelDownload}
        onClose={() => setShowProgressModal(false)}
        lang={lang}
      />

      {/* Deployment & Mobile Guide Modal */}
      <DeploymentGuideModal
        isOpen={showGuideModal}
        onClose={() => setShowGuideModal(false)}
        lang={lang}
      />

      {/* Standalone Project Export Modal */}
      <ExportProjectModal
        isOpen={showExportModal}
        onClose={() => setShowExportModal(false)}
        lang={lang}
      />
    </div>
  );
}
