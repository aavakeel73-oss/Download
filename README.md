# StreamRip — YouTube & Facebook Video Downloader (पूर्ण प्रोडक्शन प्रोजेक्ट)

आधुनिक, तेज, सुरक्षित और मोबाइल-फ्रेंडली YouTube और Facebook वीडियो/रील्स डाउनलोडर वेब ऐप्लिकेशन।  
यह ऐप्लिकेशन **Python Flask**, **yt-dlp**, **FFmpeg**, और **आधुनिक HTML5/CSS3/JS/React** के साथ तैयार किया गया है। इसमें **SSRF सुरक्षा**, रीयल-टाइम डाउनलोड प्रोग्रेस, स्पीडोमीटर और ऑटोमेटिक फ़ाइल क्लीनअप शामिल है।

---

## 📑 विषय-सूची (Table of Contents)
1. [प्रोजेक्ट विशेषताएं (Key Features)](#1-प्रोजेक्ट-विशेषताएं)
2. [प्रोजेक्ट संरचना (Project Structure)](#2-प्रोजेक्ट-संरचना)
3. [लोकल कंप्यूटर पर चलाना (Local Setup Guide)](#3-लोकल-कंप्यूटर-पर-चलाना)
4. [Android मोबाइल से GitHub पर अपलोड करना (Mobile GitHub Upload)](#4-android-मोबाइल-से-github-पर-अपलोड-करना)
5. [Google Cloud Run पर डिप्लॉयमेंट (Google Cloud Run Guide)](#5-google-cloud-run-पर-डिप्लॉयमेंट)
6. [Render पर फ्री डिप्लॉयमेंट (Render Free Hosting Guide)](#6-render-पर-फ्री-डिप्लॉयमेंट)
7. [Ubuntu VPS Hosting (Nginx + Gunicorn + FFmpeg)](#7-ubuntu-vps-hosting-गाइड)
8. [सुरक्षा एवं नीति अनुपालन (Security & Policy Compliance)](#8-सुरक्षा-एवं-नीति-अनुपालन)
9. [टेस्टिंग चेकलिस्ट (Testing Checklist)](#9-टेस्टिंग-चेकलिस्ट)
10. [समस्या निवारण एवं एरर फिक्सिंग (Troubleshooting & Error Guide)](#10-समस्या-निवारण-एवं-एरर-फिक्सिंग)

---

## 1. प्रोजेक्ट विशेषताएं
- **समर्थित प्लेटफॉर्म:** 
  - YouTube (वीडियो, Shorts, एम्बेडेड लिंक्स)
  - Facebook (सार्वजनिक वीडियो, Facebook Reels, वॉच लिंक्स)
- **क्वालिटी विकल्प:** 
  - 144p, 240p, 360p, 480p, 720p HD, 1080p Full HD, 1440p 2K, 2160p 4K
  - MP3 ऑडियो (128kbps, 192kbps, 320kbps) व M4A
- **साइबर सुरक्षा:** SSRF (Server-Side Request Forgery) ब्लॉक, आंतरिक IP (127.0.0.1, 10.x, 192.168.x) सुरक्षा, अधिकतम 500MB आकार सीमा, तथा ऑटोमेटिक 1 घंटे में टेम्पररी फाइलों की सफाई।
- **मोबाइल फ्रेंडली:** Android Chrome और iOS Safari में पूर्ण संगत।

---

## 2. प्रोजेक्ट संरचना (Project Structure)
```
streamrip-downloader/
│
├── app.py                     # मुख्य Python Flask बैकएंड API
├── requirements.txt           # आवश्यक Python लाइब्रेरीज़
├── Dockerfile                 # Cloud Run/Render हेतु कंटेनर फ़ाइल (FFmpeg सहित)
├── .github/
│   └── workflows/
│       └── deploy.yml         # GitHub Actions ऑटोमेशन
├── templates/
│   └── index.html             # स्टैंडअलोन HTML5 UI
├── static/
│   ├── style.css              # ग्लासमोर्फिज्म और डार्क थीम स्टाइल
│   └── script.js              # क्लाइंट साइड जावास्क्रिप्ट एवं डाउनलोड पोलिंग
├── src/                       # आधुनिक रिएक्ट फ्रंटएंड (AI Studio)
└── README.md                  # विस्तृत गाइड (हिंदी)
```

---

## 3. लोकल कंप्यूटर पर चलाना (Local Setup Guide)

### आवश्यकताएं:
- Python 3.10 या 3.11
- FFmpeg (वीडियो व ऑडियो मर्ज करने के लिए आवश्यक)

### चरण:
```bash
# 1. FFmpeg इंस्टॉल करें
# Ubuntu / Debian:
sudo apt update && sudo apt install -y ffmpeg

# macOS (Homebrew):
brew install ffmpeg

# Windows (Chocolatey या winget):
winget install Gyan.FFmpeg

# 2. प्रोजेक्ट डायरेक्टरी में जाएं
cd streamrip-downloader

# 3. वर्चुअल एनवायरनमेंट बनाएं और एक्टिवेट करें
python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

# 4. निर्भरताएं इंस्टॉल करें
pip install -r requirements.txt

# 5. सर्वर शुरू करें
python3 app.py
```
ब्राउज़र में खोलें: `http://localhost:5000`

---

## 4. Android मोबाइल से GitHub पर अपलोड करना

यदि आपके पास कंप्यूटर नहीं है, तो आप अपने Android मोबाइल से भी पूरा कोड GitHub पर आसानी से अपलोड कर सकते हैं:

1. **ब्राउज़र में GitHub खोलें:**
   - Chrome ब्राउज़र खोलें और [github.com](https://github.com) पर लॉगिन करें।
   - ऊपर दाएँ कोने में 3 डॉट्स पर क्लिक करके **"Desktop site"** टिक करें।
2. **नया रिपॉजिटरी बनाएं:**
   - **New Repository** पर टैप करें।
   - नाम दें: `streamrip-downloader`
   - इसे **Public** रखें और **Create repository** दबाएं।
3. **कोड फाइलें अपलोड करें:**
   - रिपॉजिटरी पेज पर **"uploading an existing file"** लिंक पर टैप करें।
   - ऐप में दिए गए **"Export ZIP"** बटन से डाउनलोड की गई ZIP को अपने फोन में अनजिप करें।
   - `app.py`, `requirements.txt`, `Dockerfile`, `templates/`, `static/`, और `README.md` को सेलेक्ट करके अपलोड करें।
4. **कमिट करें:**
   - नीचे **Commit changes** पर टैप करें। आपका प्रोजेक्ट GitHub पर लाइव अपलोड हो जाएगा!

---

## 5. Google Cloud Run पर डिप्लॉयमेंट

Google Cloud Run सबसे तेज और स्केलेबल तरीका है क्योंकि इसमें FFmpeg कंटेनर में पहले से इनबिल्ट रहता है:

```bash
# 1. Google Cloud CLI में लॉगिन करें
gcloud auth login

# 2. अपना प्रोजेक्ट सेट करें
gcloud config set project YOUR_PROJECT_ID

# 3. सीधे सोर्स कोड से Cloud Run पर बिल्ड व डिप्लॉय करें
gcloud run deploy streamrip \
  --source . \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --timeout 300
```
डिप्लॉय होते ही आपको एक सुरक्षित `https://streamrip-xxx.a.run.app` URL प्राप्त होगा!

---

## 6. Render पर फ्री डिप्लॉयमेंट

Render पर आप बिना क्रेडिट कार्ड के फ्री में बैकएंड होस्ट कर सकते हैं:

1. [render.com](https://render.com) पर जाएं और GitHub से साइन इन करें।
2. **New +** बटन दबाकर **Web Service** चुनें।
3. अपनी `streamrip-downloader` रिपॉजिटरी चुनें।
4. सेटिंग्स भरें:
   - **Environment:** `Docker` (चूंकि Dockerfile में FFmpeg शामिल है)
   - **Region:** Singapore / Frankfurt
   - **Plan:** Free
5. **Create Web Service** पर क्लिक करें। 3 मिनट में आपकी वेबसाइट ऑनलाइन हो जाएगी!

---

## 7. Ubuntu VPS Hosting गाइड

यदि आपके पास DigitalOcean, Hetzner, या AWS EC2 VPS है:

```bash
# 1. सिस्टम अपडेट व FFmpeg इंस्टॉल करें
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv ffmpeg nginx git

# 2. कोड क्लोन करें
cd /var/www
sudo git clone https://github.com/YOUR_USERNAME/streamrip-downloader.git
cd streamrip-downloader

# 3. वर्चुअल एनवायरनमेंट
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Systemd सर्विस बनाएं (/etc/systemd/system/streamrip.service)
sudo bash -c 'cat > /etc/systemd/system/streamrip.service <<EOF
[Unit]
Description=StreamRip Video Downloader Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/streamrip-downloader
ExecStart=/var/www/streamrip-downloader/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF'

# 5. सर्विस चालू करें
sudo systemctl daemon-reload
sudo systemctl start streamrip
sudo systemctl enable streamrip

# 6. Nginx रिवर्स प्रॉक्सी सेटअप
sudo nano /etc/nginx/sites-available/streamrip
# proxy_pass http://127.0.0.1:5000; जोड़ें और Nginx रीस्टार्ट करें:
sudo systemctl restart nginx
```

---

## 8. सुरक्षा एवं नीति अनुपालन
- **कॉपीराइट व DRM:** ऐप किसी भी एनक्रिप्टेड या DRM-संरक्षित सामग्री (जैसे Netflix, Hotstar, आदि) या YouTube सशुल्क फिल्मों को बायपास नहीं करता।
- **सार्वजनिक एवं अधिकृत वीडियो:** यह केवल सार्वजनिक, क्रिएटिव कॉमन्स (Creative Commons) या सामग्री स्वामी द्वारा अधिकृत वीडियो डाउनलोड करने में सहायता करता है।
- **SSRF सुरक्षा:** आंतरिक आईपी (Localhost, 192.168.x.x, 10.x.x.x, एडब्ल्यूएस मेटाडेटा आईपी 169.254.169.254) सर्वर-लेवल पर ब्लॉक किए जाते हैं।

---

## 9. टेस्टिंग चेकलिस्ट
- [x] URL वैलिडेशन: अमान्य लिंक पर स्पष्ट लाल एरर संदेश।
- [x] YouTube वीडियो विश्लेषण: थंबनेल, अवधि, शीर्षक और फॉर्मेट सूची।
- [x] Facebook रील विश्लेषण: रील/वीडियो पहचान।
- [x] रीयल-टाइम डाउनलोड प्रोग्रेस: डाउनलोड स्पीड (MB/s) और प्रतिशत इंडिकेटर।
- [x] मोबाइल ब्राउज़र सपोर्ट: Android Chrome में सीधे फ़ाइल सहेजना।
- [x] रद्द (Cancel) बटन: सक्रिय डाउनलोड को बीच में सुरक्षित रूप से रोकना।

---

## 10. समस्या निवारण एवं एरर फिक्सिंग

| एरर संदेश | संभावित कारण | समाधान |
|---|---|---|
| `Sign in to confirm you’re not a bot` | YouTube बॉट डिटेक्शन | `yt-dlp -U` चलाकर yt-dlp को नवीनतम संस्करण में अपडेट करें, या कुकीज़ पास करें। |
| `ffmpeg: command not found` | सिस्टम में FFmpeg मौजूद नहीं है | `sudo apt install ffmpeg` चलाएं या Docker आधारित डिप्लॉयमेंट का उपयोग करें। |
| `403 Forbidden / Private Video` | वीडियो केवल लॉगिन यूज़र्स या प्राइवेट के लिए है | केवल सार्वजनिक (Public) वीडियो लिंक का उपयोग करें। |
| `SSRF Blocked` | स्थानीय या अमान्य IP एड्रेस का लिंक | केवल वैध `youtube.com`, `youtu.be` या `facebook.com` लिंक डालें। |
