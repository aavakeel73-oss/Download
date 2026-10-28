/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { X, Copy, Check, Terminal, Cloud, Smartphone, Server, Globe } from 'lucide-react';

interface DeploymentGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
  lang: 'hi' | 'en';
}

export const DeploymentGuideModal: React.FC<DeploymentGuideModalProps> = ({
  isOpen,
  onClose,
  lang,
}) => {
  const [activeTab, setActiveTab] = useState<'mobile' | 'cloudrun' | 'render' | 'vps'>('mobile');
  const [copiedSnippet, setCopiedSnippet] = useState<string | null>(null);

  if (!isOpen) return null;

  const copyToClipboard = async (text: string, id: string) => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      }
    } catch {
      // Fallback if clipboard API is blocked in iframe
    }
    setCopiedSnippet(id);
    setTimeout(() => setCopiedSnippet(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-950/85 backdrop-blur-md overflow-y-auto">
      <div className="w-full max-w-3xl glass-panel rounded-2xl border border-cyan-500/30 shadow-2xl my-auto max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-6 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/20 text-cyan-300">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-slate-100">
                {lang === 'hi' ? 'वेबसाइट डिप्लॉयमेंट एवं मोबाइल अपलोड गाइड' : 'Deployment & Mobile Setup Guide'}
              </h2>
              <p className="text-xs text-slate-400">
                {lang === 'hi' ? 'GitHub, Google Cloud Run, Render और VPS पर लाइव करें' : 'Step-by-step deployment on Cloud Run, Render & VPS'}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Bar */}
        <div className="flex items-center gap-1.5 px-4 sm:px-6 pt-3 pb-2 border-b border-slate-800 overflow-x-auto text-xs font-semibold">
          <button
            onClick={() => setActiveTab('mobile')}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg whitespace-nowrap transition-all ${
              activeTab === 'mobile'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Smartphone className="w-4 h-4" />
            <span>Android मोबाइल से GitHub</span>
          </button>

          <button
            onClick={() => setActiveTab('cloudrun')}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg whitespace-nowrap transition-all ${
              activeTab === 'cloudrun'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cloud className="w-4 h-4" />
            <span>Google Cloud Run</span>
          </button>

          <button
            onClick={() => setActiveTab('render')}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg whitespace-nowrap transition-all ${
              activeTab === 'render'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Globe className="w-4 h-4" />
            <span>Render (Free Hosting)</span>
          </button>

          <button
            onClick={() => setActiveTab('vps')}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg whitespace-nowrap transition-all ${
              activeTab === 'vps'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Server className="w-4 h-4" />
            <span>Ubuntu VPS + Nginx</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-4 sm:p-6 overflow-y-auto space-y-4 text-xs sm:text-sm text-slate-300 leading-relaxed font-sans">
          {activeTab === 'mobile' && (
            <div className="space-y-3">
              <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-cyan-400" />
                <span>Android मोबाइल से GitHub पर प्रोजेक्ट अपलोड करने की प्रक्रिया:</span>
              </h3>
              <ol className="list-decimal pl-5 space-y-2 text-slate-300">
                <li>
                  <strong>प्रोजेक्ट ZIP डाउनलोड करें:</strong> ऊपर दिए गए <strong>"Export ZIP"</strong> बटन पर क्लिक करके <code className="text-cyan-300 bg-slate-900 px-1 py-0.5 rounded font-mono">streamrip-complete-project.zip</code> को अपने फोन में सेव करें।
                </li>
                <li>
                  <strong>ZIP फ़ाइल को अनज़िप (Extract) करें:</strong> अपने फोन के 'Files' या 'File Manager' ऐप में जाएं और ZIP को एक्सट्रेक्ट कर लें।
                </li>
                <li>
                  <strong>Chrome में GitHub Desktop मोड खोलें:</strong>
                  अपने Android फोन में Chrome ब्राउज़र खोलें, <strong>github.com</strong> पर जाएं। ऊपर दाईं ओर 3 डॉट्स (⋮) पर क्लिक करें और <strong>"Desktop site"</strong> को चेकमार्क करें।
                </li>
                <li>
                  <strong>New Repository बनाएं:</strong>
                  GitHub पर लॉगिन करके <strong>"+" &gt; "New repository"</strong> पर टैप करें। नाम लिखें: <code className="text-cyan-300 bg-slate-900 px-1 py-0.5 rounded font-mono">streamrip-downloader</code> और <strong>"Create repository"</strong> दबाएं।
                </li>
                <li>
                  <strong>फाइलें अपलोड करें:</strong>
                  अगले पेज पर <strong>"uploading an existing file"</strong> पर टैप करें। फोन से <code className="text-slate-200 font-mono">app.py</code>, <code className="text-slate-200 font-mono">requirements.txt</code>, <code className="text-slate-200 font-mono">Dockerfile</code>, <code className="text-slate-200 font-mono">templates/</code>, और <code className="text-slate-200 font-mono">static/</code> को सेलेक्ट करके अपलोड करें और नीचे <strong>"Commit changes"</strong> दबाएं।
                </li>
              </ol>
              <div className="p-3 bg-cyan-950/30 border border-cyan-500/20 rounded-xl text-cyan-200 text-xs">
                💡 <strong>टिप:</strong> GitHub पर अपलोड होते ही आप सीधे Render या Cloud Run पर GitHub अकाउंट कनेक्ट करके 1-क्लिक में साइट लाइव कर सकते हैं!
              </div>
            </div>
          )}

          {activeTab === 'cloudrun' && (
            <div className="space-y-3">
              <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
                <Cloud className="w-4 h-4 text-cyan-400" />
                <span>Google Cloud Run पर डिप्लॉयमेंट (सर्वरलेस + FFmpeg):</span>
              </h3>
              <p>Google Cloud Run पर FFmpeg कंटेनर में पैक होकर उच्च-गति के साथ लाइव चलता है:</p>

              <div className="relative p-3 bg-slate-900 rounded-xl border border-slate-800 font-mono text-xs text-cyan-300">
                <button
                  onClick={() => copyToClipboard('gcloud run deploy streamrip \\\n  --source . \\\n  --platform managed \\\n  --region asia-south1 \\\n  --allow-unauthenticated \\\n  --memory 1Gi \\\n  --timeout 300', 'cloudrun')}
                  className="absolute top-2.5 right-2.5 p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  {copiedSnippet === 'cloudrun' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
                <pre className="whitespace-pre-wrap">{`gcloud run deploy streamrip \\
  --source . \\
  --platform managed \\
  --region asia-south1 \\
  --allow-unauthenticated \\
  --memory 1Gi \\
  --timeout 300`}</pre>
              </div>

              <ol className="list-decimal pl-5 space-y-1.5 text-slate-300 text-xs">
                <li>Google Cloud SDK से टर्मिनल में लॉगिन करें: <code className="text-slate-200 font-mono">gcloud auth login</code></li>
                <li>प्रोजेक्ट सेट करें: <code className="text-slate-200 font-mono">gcloud config set project [YOUR_PROJECT_ID]</code></li>
                <li>उपरोक्त कमांड चलाएं। 2 मिनट में आपको लाइव HTTPS URL मिल जाएगा।</li>
              </ol>
            </div>
          )}

          {activeTab === 'render' && (
            <div className="space-y-3">
              <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
                <Globe className="w-4 h-4 text-cyan-400" />
                <span>Render (render.com) पर फ्री डिप्लॉयमेंट:</span>
              </h3>
              <ol className="list-decimal pl-5 space-y-2 text-slate-300 text-xs">
                <li><strong>render.com</strong> पर जाएं और अपने GitHub अकाउंट से साइन इन करें।</li>
                <li>डैशबोर्ड पर <strong>"New +"</strong> बटन दबाकर <strong>"Web Service"</strong> चुनें।</li>
                <li>अपनी GitHub रिपॉजिटरी (<code className="text-cyan-300 font-mono">streamrip-downloader</code>) को कनेक्ट करें।</li>
                <li>
                  सेटिंग्स में चुनें:
                  <ul className="list-disc pl-5 mt-1 space-y-1">
                    <li><strong>Runtime / Environment:</strong> <code className="text-emerald-400 font-mono">Docker</code> (यह FFmpeg को ऑटोमैटिक लोड करेगा)</li>
                    <li><strong>Plan:</strong> <code className="text-emerald-400 font-mono">Free</code></li>
                    <li><strong>Region:</strong> Singapore या Frankfurt</li>
                  </ul>
                </li>
                <li><strong>"Deploy Web Service"</strong> पर क्लिक करें। आपका ऐप 3 मिनट में फ्री में लाइव हो जाएगा!</li>
              </ol>
            </div>
          )}

          {activeTab === 'vps' && (
            <div className="space-y-3">
              <h3 className="font-bold text-slate-100 text-sm flex items-center gap-2">
                <Server className="w-4 h-4 text-cyan-400" />
                <span>Ubuntu Linux VPS (Nginx + Gunicorn + FFmpeg):</span>
              </h3>
              <div className="relative p-3 bg-slate-900 rounded-xl border border-slate-800 font-mono text-xs text-cyan-300">
                <button
                  onClick={() => copyToClipboard('sudo apt update && sudo apt install -y python3-pip python3-venv ffmpeg nginx git\ngit clone https://github.com/USER/streamrip-downloader.git\ncd streamrip-downloader\npython3 -m venv venv && source venv/bin/activate\npip install -r requirements.txt\ngunicorn --workers 3 --bind 0.0.0.0:5000 app:app', 'vps')}
                  className="absolute top-2.5 right-2.5 p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                >
                  {copiedSnippet === 'vps' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
                <pre className="whitespace-pre-wrap">{`sudo apt update && sudo apt install -y python3-pip python3-venv ffmpeg nginx git
git clone https://github.com/USER/streamrip-downloader.git
cd streamrip-downloader
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
gunicorn --workers 3 --bind 0.0.0.0:5000 app:app`}</pre>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 flex items-center justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition-colors"
          >
            {lang === 'hi' ? 'समझ गया' : 'Got it'}
          </button>
        </div>
      </div>
    </div>
  );
};
