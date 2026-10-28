/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { ShieldCheck, Lock, CheckCircle2, AlertOctagon, Cpu, Database } from 'lucide-react';

interface SecurityComplianceCardProps {
  lang: 'hi' | 'en';
}

export const SecurityComplianceCard: React.FC<SecurityComplianceCardProps> = ({ lang }) => {
  return (
    <div id="compliance" className="w-full glass-panel rounded-2xl p-5 sm:p-7 border border-slate-800/80 shadow-xl space-y-5">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-xl bg-emerald-500/15 text-emerald-400">
          <ShieldCheck className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-sm sm:text-base font-bold text-slate-100">
            {lang === 'hi' ? 'सुरक्षा, नीति एवं कानूनी अनुपालन' : 'Security & Policy Compliance'}
          </h3>
          <p className="text-xs text-slate-400">
            {lang === 'hi' ? 'केवल सार्वजनिक एवं अधिकृत वीडियो के लिए सुरक्षित डाउनलोड' : 'Authorized downloads for public & Creative Commons media'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
          <div className="flex items-center gap-2 text-cyan-400 font-semibold">
            <Lock className="w-4 h-4" />
            <span>{lang === 'hi' ? 'SSRF साइबर सुरक्षा' : 'SSRF Cyber Defense'}</span>
          </div>
          <p className="text-slate-400 leading-relaxed">
            {lang === 'hi'
              ? 'आंतरिक नेटवर्क (127.0.0.1, 10.x, 192.168.x, एडब्ल्यूएस मेटाडेटा 169.254.169.254) पूरी तरह ब्लॉक हैं ताकि सर्वर हैक न हो सके।'
              : 'Strict SSRF mitigation filters localhost, private RFC1918 subnets, and cloud instance metadata.'}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
          <div className="flex items-center gap-2 text-emerald-400 font-semibold">
            <CheckCircle2 className="w-4 h-4" />
            <span>{lang === 'hi' ? 'अधिकृत एवं सार्वजनिक मीडिया' : 'Authorized Media'}</span>
          </div>
          <p className="text-slate-400 leading-relaxed">
            {lang === 'hi'
              ? 'केवल सार्वजनिक, क्रिएटिव कॉमन्स (Creative Commons) या सामग्री स्वामी द्वारा डाउनलोड की अनुमति वाले वीडियो समर्थित हैं।'
              : 'Strict adherence to platform terms; processes publicly accessible educational and Creative Commons streams.'}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
          <div className="flex items-center gap-2 text-amber-400 font-semibold">
            <AlertOctagon className="w-4 h-4" />
            <span>{lang === 'hi' ? 'DRM व प्राइवेट सुरक्षा' : 'DRM & Access Control'}</span>
          </div>
          <p className="text-slate-400 leading-relaxed">
            {lang === 'hi'
              ? 'प्रतिबंधित वीडियो, DRM सुरक्षा, या पासवर्ड-युक्त निजी सामग्री को बायपास नहीं किया जाता। नियमों का पूर्ण आदर किया जाता है।'
              : 'Never attempts to circumvent encrypted DRM or private restricted paywalled media.'}
          </p>
        </div>
      </div>

      {/* Architecture Highlights */}
      <div className="pt-3 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3 text-[11px] text-slate-500 font-mono">
        <span className="flex items-center gap-1.5">
          <Cpu className="w-3.5 h-3.5 text-cyan-400" />
          <span>FFmpeg Native Stream Processing</span>
        </span>
        <span className="flex items-center gap-1.5">
          <Database className="w-3.5 h-3.5 text-sky-400" />
          <span>Auto Temporary File Garbage Collection (60m)</span>
        </span>
        <span>Max File Size Guard: 500 MB</span>
      </div>
    </div>
  );
};
