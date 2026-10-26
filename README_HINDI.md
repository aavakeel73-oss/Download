# मुफ्त Backend — मोबाइल से सेटअप

यह एक परीक्षण-योग्य Flask + FFmpeg Backend है। YouTube/Facebook के लिए RapidAPI से मिले अलग वीडियो/ऑडियो URL को सर्वर पर डाउनलोड कर MP4 में जोड़ता है। 100% वीडियो सफलता की गारंटी नहीं: स्रोत के signed URLs, access restrictions, API plan, free-tier limits लागू होते हैं।

## Android मोबाइल पर GitHub + Render
1. GitHub.com पर नया repository `social-downloader-backend` बनाएँ।
2. ZIP extract करें। `app.py`, `Dockerfile`, `requirements.txt` और पूरा `templates/index.html` फोल्डर repository की root में अपलोड करें (ZIP को सीधे repository में रखने से Render उसे स्वतः extract नहीं करता)।
3. https://dashboard.render.com/ खोलें, **New > Web Service > Connect GitHub repository** चुनें।
4. Runtime: Docker (Dockerfile auto-detected); Instance type **Free** चुनें।
5. Environment में `RAPIDAPI_KEY` = आपकी RapidAPI secret key और `SIGNING_SECRET` = 32+ random characters का secret रखें। इन दोनों को GitHub में न डालें।
6. Deploy पूरा होने पर Render का `https://....onrender.com` लिंक खोलें। वेबसाइट उसी लिंक पर मिलेगी। `/health` में `configured:true` और `ffmpeg:true` जाँचें।
7. शेयर लिंक डालें, वीडियो/ऑडियो चुनें और MP4 बनाएँ।

## सीमाएँ
- 75 MB प्रति stream, 105 सेकंड FFmpeg timeout; बड़े 4K वीडियो फ्री सर्वर पर नहीं चलेंगे।
- 10 मिनट बाद डाउनलोड फ़ाइल expire; Render restart पर फ़ाइल खो सकती है।
- कुछ API media URLs सर्वर से 403 देते हैं; उस स्थिति में API या होस्टिंग बदलनी होगी।
- RapidAPI key Render में ही रखें, HTML/JS में कभी नहीं।
- सार्वजनिक उपयोग से पहले authentication, rate limiting और resource quotas जोड़ें।
