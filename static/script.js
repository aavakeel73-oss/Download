document.addEventListener('DOMContentLoaded', () => {
    const videoUrlInput = document.getElementById('videoUrl');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const pasteBtn = document.getElementById('pasteBtn');
    const clearBtn = document.getElementById('clearBtn');
    const statusMessage = document.getElementById('statusMessage');
    const previewCard = document.getElementById('previewCard');
    const videoThumb = document.getElementById('videoThumb');
    const videoTitle = document.getElementById('videoTitle');
    const videoAuthor = document.getElementById('videoAuthor');
    const videoDuration = document.getElementById('videoDuration');
    const formatList = document.getElementById('formatList');
    const progressModal = document.getElementById('progressModal');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const progressSpeed = document.getElementById('progressSpeed');
    const cancelDlBtn = document.getElementById('cancelDlBtn');
    const themeToggle = document.getElementById('themeToggle');

    let currentJobId = null;
    let pollInterval = null;

    // Theme toggle
    themeToggle.addEventListener('click', () => {
        document.body.classList.toggle('light-mode');
    });

    // Paste handler
    pasteBtn.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            videoUrlInput.value = text;
            clearBtn.classList.remove('hidden');
        } catch {
            alert('क्लिपबोर्ड एक्सेस की अनुमति दें।');
        }
    });

    // Clear handler
    clearBtn.addEventListener('click', () => {
        videoUrlInput.value = '';
        clearBtn.classList.add('hidden');
        previewCard.classList.add('hidden');
        statusMessage.textContent = '';
    });

    videoUrlInput.addEventListener('input', () => {
        if (videoUrlInput.value.trim()) {
            clearBtn.classList.remove('hidden');
        } else {
            clearBtn.classList.add('hidden');
        }
    });

    // Analyze video
    analyzeBtn.addEventListener('click', async () => {
        const url = videoUrlInput.value.trim();
        if (!url) {
            statusMessage.className = 'status-msg error';
            statusMessage.textContent = 'कृपया एक मान्य YouTube या Facebook लिंक दर्ज करें।';
            return;
        }

        statusMessage.className = 'status-msg';
        statusMessage.textContent = 'वीडियो का विश्लेषण हो रहा है, कृपया प्रतीक्षा करें...';
        analyzeBtn.disabled = true;

        try {
            const res = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const data = await res.json();
            if (!res.ok || !data.success) {
                throw new Error(data.error || 'वीडियो डेटा लोड करने में त्रुटि।');
            }

            const meta = data.metadata;
            videoThumb.src = meta.thumbnail || '';
            videoTitle.textContent = meta.title || 'शीर्षक अनुपलब्ध';
            videoAuthor.textContent = meta.author || 'चैनल';
            videoDuration.textContent = formatSec(meta.durationSeconds);

            // Render formats
            formatList.innerHTML = '';
            (meta.formats || []).forEach(f => {
                const btn = document.createElement('button');
                btn.className = 'format-btn';
                const sizeStr = f.filesizeBytes ? `${(f.filesizeBytes / (1024 * 1024)).toFixed(1)} MB` : 'उपलब्ध';
                btn.innerHTML = `<strong>${f.qualityLabel}</strong><span class="size">${sizeStr} · ${f.ext.toUpperCase()}</span>`;
                btn.addEventListener('click', () => initiateDownload(meta.sourceUrl, f.formatId, f.ext === 'mp3'));
                formatList.appendChild(btn);
            });

            previewCard.classList.remove('hidden');
            statusMessage.textContent = 'विश्लेषण पूर्ण! अपनी पसंदीदा क्वालिटी चुनें।';
        } catch (err) {
            statusMessage.className = 'status-msg error';
            statusMessage.textContent = err.message;
        } finally {
            analyzeBtn.disabled = false;
        }
    });

    function initiateDownload(url, formatId, isAudio) {
        progressModal.classList.remove('hidden');
        progressBar.style.width = '0%';
        progressPercent.textContent = '0%';
        progressSpeed.textContent = 'प्रारंभ हो रहा है...';

        fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, formatId, isAudio })
        })
        .then(res => res.json())
        .then(data => {
            if (!data.success) throw new Error(data.error);
            currentJobId = data.jobId;
            startPolling(currentJobId);
        })
        .catch(err => {
            alert('डाउनलोड प्रारंभ करने में त्रुटि: ' + err.message);
            progressModal.classList.add('hidden');
        });
    }

    function startPolling(jobId) {
        if (pollInterval) clearInterval(pollInterval);

        pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/job/${jobId}`);
                const data = await res.json();
                if (!res.ok || !data.success) return;

                const job = data.job;
                progressBar.style.width = `${job.progressPercent}%`;
                progressPercent.textContent = `${job.progressPercent}%`;
                progressSpeed.textContent = job.speedFormatted || 'प्रसंस्करण चालू है...';

                if (job.status === 'completed') {
                    clearInterval(pollInterval);
                    progressModal.classList.add('hidden');
                    // Trigger download
                    window.location.href = `/api/file/${jobId}`;
                } else if (job.status === 'error') {
                    clearInterval(pollInterval);
                    alert('डाउनलोड असफल: ' + (job.error || 'अज्ञात त्रुटि'));
                    progressModal.classList.add('hidden');
                }
            } catch (e) {
                console.error(e);
            }
        }, 1000);
    }

    cancelDlBtn.addEventListener('click', () => {
        if (pollInterval) clearInterval(pollInterval);
        progressModal.classList.add('hidden');
    });

    function formatSec(seconds) {
        if (!seconds) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
});
