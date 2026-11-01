import os
import re
import json
import time
import uuid
import asyncio
import logging
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import quote_plus

import requests
import imageio_ffmpeg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, filters)
from shazamio import Shazam

TOKEN = os.environ["BOT_TOKEN"]
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ytmusicbot")



INVIDIOUS = ["https://yt.chocolatemoo53.com"]
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
# ---------- languages ----------
LANGS = [("hi", "हिंदी"), ("en", "English"), ("bn", "বাংলা"), ("te", "తెలుగు"),
         ("mr", "मराठी"), ("ta", "தமிழ்"), ("gu", "ગુજરાતી"), ("kn", "ಕನ್ನಡ"),
         ("ml", "മലയാളം"), ("pa", "ਪੰਜਾਬੀ"), ("ur", "اردو"), ("es", "Español")]

STRINGS = {
"en": {
 "welcome": "Hello! 🎵\n\nI find songs and send MP3s, and I download videos from links. Send me:\n\n📝 Song name, singer, or a lyrics line\n🎤 Voice note with a song playing\n🎬 Audio or video with a song in it\n🔗 YouTube, Instagram or TikTok link (I'll download the video)\n\nEvery song comes with Lyrics, Video and Info (links to all music apps) buttons. Enjoy!",
 "pick_lang": "🌐 Choose your language:",
 "lang_set": "✅ Language set to English. Send a song name to begin!",
 "btn_lang": "🌐 Language",
 "searching": "🔍 Searching...",
 "choose": "Pick a song:",
 "no_result": "Nothing found for that name. Try a different spelling (add the singer's name).",
 "no_more": "No more results.",
 "btn_more": "➕ More tracks",
 "btn_cancel": "❌ Cancel",
 "too_long": "That track is too long (over 15 min), I can't send it. Pick a shorter version.",
 "dl_wait": "⬇️ Downloading, please wait (can take 1-2 min)...",
 "dl_fail": "Sorry, couldn't download this right now. Try again later or pick another version.",
 "fallback_audio": "🎧 Couldn't get the video, recognizing the song from its audio...",
 "link_fail": "Couldn't pull audio/video from this link. Try another link or a voice note.",
 "send_fail": "Couldn't send the file. Please try again.",
 "btn_lyrics": "🔤 Lyrics",
 "btn_video": "🎬 Video",
 "btn_recog": "🎵 Recognize song",
 "recog_fail": "Couldn't recognize the song. Send clearer audio or type the song name.",
 "listening": "🎧 Listening, recognizing the song...",
 "tg_dl_fail": "Couldn't download this file. Send a file under 20 MB.",
 "convert_fail": "Couldn't read this audio. Try another file.",
 "old_search": "That search expired, send the name again.",
 "old_audio": "This audio expired, send the link again.",
 "lyrics_search": "🔍 Finding lyrics...",
 "lyrics_none": "Lyrics not found for this track.",
},
"hi": {
 "welcome": "नमस्ते! 🎵\n\nमैं गाने ढूँढकर MP3 भेजता हूँ और लिंक से वीडियो डाउनलोड करता हूँ। मुझे भेजें:\n\n📝 गाने का नाम, सिंगर या लिरिक्स की लाइन\n🎤 वॉइस नोट जिसमें गाना बज रहा हो\n🎬 ऑडियो या वीडियो जिसमें गाना हो\n🔗 YouTube, Instagram या TikTok लिंक (वीडियो डाउनलोड हो जाएगा)\n\nहर गाने के नीचे Lyrics, Video और Info (सारे म्यूज़िक ऐप के लिंक) बटन मिलते हैं।",
 "pick_lang": "🌐 अपनी भाषा चुनें:",
 "lang_set": "✅ भाषा हिंदी चुनी गई। शुरू करने के लिए गाने का नाम भेजें!",
 "btn_lang": "🌐 भाषा",
 "searching": "🔍 ढूँढ रहा हूँ...",
 "choose": "गाना चुनें:",
 "no_result": "इस नाम से कुछ नहीं मिला। नाम थोड़ा बदलकर भेजें (सिंगर का नाम जोड़ें)।",
 "no_more": "और नतीजे नहीं मिले।",
 "btn_more": "➕ और गाने",
 "btn_cancel": "❌ रद्द करें",
 "too_long": "यह ट्रैक बहुत लंबा है (15 मिनट से ज़्यादा), इसे नहीं भेज सकता। छोटा वर्ज़न चुनें।",
 "dl_wait": "⬇️ डाउनलोड हो रहा है, थोड़ा इंतज़ार करें (1-2 मिनट लग सकते हैं)...",
 "dl_fail": "माफ़ करें, अभी यह डाउनलोड नहीं हो पाया। थोड़ी देर बाद या कोई और वर्ज़न आज़माएँ।",
 "fallback_audio": "🎧 वीडियो नहीं निकल पाया, ऑडियो से गाना पहचान रहा हूँ...",
 "link_fail": "इस लिंक से ऑडियो/वीडियो नहीं निकल पाया। दूसरा लिंक या वॉइस नोट आज़माएँ।",
 "send_fail": "फ़ाइल भेजने में दिक्कत आई। दोबारा कोशिश करें।",
 "btn_lyrics": "🔤 लिरिक्स",
 "btn_video": "🎬 वीडियो",
 "btn_recog": "🎵 गाना पहचानो",
 "recog_fail": "गाना पहचान नहीं पाया। साफ़ ऑडियो या गाने का नाम लिखकर भेजें।",
 "listening": "🎧 सुन रहा हूँ, गाना पहचान रहा हूँ...",
 "tg_dl_fail": "यह फ़ाइल डाउनलोड नहीं हो पाई। 20 MB से छोटी फ़ाइल भेजें।",
 "convert_fail": "इस ऑडियो को समझ नहीं पाया। दूसरी फ़ाइल आज़माएँ।",
 "old_search": "पुरानी सर्च है, नाम दोबारा भेजें।",
 "old_audio": "यह ऑडियो पुराना हो गया, लिंक दोबारा भेजें।",
 "lyrics_search": "🔍 लिरिक्स ढूँढ रहा हूँ...",
 "lyrics_none": "इस ट्रैक की लिरिक्स नहीं मिली।",
},
"bn": {
 "welcome": "নমস্কার! 🎵\n\nআমি গান খুঁজে MP3 পাঠাই এবং লিংক থেকে ভিডিও ডাউনলোড করি। পাঠান:\n\n📝 গানের নাম, শিল্পী বা লিরিক্সের লাইন\n🎤 গান বাজানো ভয়েস নোট\n🎬 গান থাকা অডিও বা ভিডিও\n🔗 YouTube, Instagram বা TikTok লিংক (ভিডিও ডাউনলোড হয়ে যাবে)\n\nপ্রতিটি গানের নিচে Lyrics, Video ও Info বাটন পাবেন।",
 "pick_lang": "🌐 আপনার ভাষা বেছে নিন:",
 "lang_set": "✅ ভাষা বাংলা নির্বাচিত। শুরু করতে গানের নাম পাঠান!",
 "btn_lang": "🌐 ভাষা",
 "searching": "🔍 খুঁজছি...",
 "choose": "গান বেছে নিন:",
 "no_result": "এই নামে কিছু পাওয়া যায়নি। নাম বদলে পাঠান (শিল্পীর নাম যোগ করুন)।",
 "no_more": "আর ফলাফল নেই।",
 "btn_more": "➕ আরও গান",
 "btn_cancel": "❌ বাতিল",
 "too_long": "এই ট্র্যাকটি বেশি লম্বা (১৫ মিনিটের বেশি), পাঠাতে পারব না। ছোট সংস্করণ বেছে নিন।",
 "dl_wait": "⬇️ ডাউনলোড হচ্ছে, একটু অপেক্ষা করুন (১-২ মিনিট লাগতে পারে)...",
 "dl_fail": "দুঃখিত, এখন ডাউনলোড করা গেল না। কিছুক্ষণ পর বা অন্য সংস্করণ চেষ্টা করুন।",
 "fallback_audio": "🎧 ভিডিও পাওয়া গেল না, অডিও থেকে গান চিনছি...",
 "link_fail": "এই লিংক থেকে অডিও/ভিডিও বের করা গেল না। অন্য লিংক বা ভয়েস নোট চেষ্টা করুন।",
 "send_fail": "ফাইল পাঠাতে সমস্যা হলো। আবার চেষ্টা করুন।",
 "btn_lyrics": "🔤 লিরিক্স",
 "btn_video": "🎬 ভিডিও",
 "btn_recog": "🎵 গান চিনুন",
 "recog_fail": "গান চিনতে পারলাম না। পরিষ্কার অডিও বা গানের নাম লিখে পাঠান।",
 "listening": "🎧 শুনছি, গান চিনছি...",
 "tg_dl_fail": "এই ফাইল ডাউনলোড করা গেল না। ২০ MB-এর ছোট ফাইল পাঠান।",
 "convert_fail": "এই অডিও বুঝতে পারলাম না। অন্য ফাইল চেষ্টা করুন।",
 "old_search": "পুরনো সার্চ, নাম আবার পাঠান।",
 "old_audio": "এই অডিও পুরনো হয়ে গেছে, লিংক আবার পাঠান।",
 "lyrics_search": "🔍 লিরিক্স খুঁজছি...",
 "lyrics_none": "এই ট্র্যাকের লিরিক্স পাওয়া যায়নি।",
},
"te": {
 "welcome": "నమస్తే! 🎵\n\nనేను పాటలు వెతికి MP3 పంపుతాను, లింకుల నుండి వీడియోలు డౌన్‌లోడ్ చేస్తాను. పంపండి:\n\n📝 పాట పేరు, సింగర్ లేదా లిరిక్స్ లైన్\n🎤 పాట వాయిస్తున్న వాయిస్ నోట్\n🎬 పాట ఉన్న ఆడియో లేదా వీడియో\n🔗 YouTube, Instagram లేదా TikTok లింక్ (వీడియో డౌన్‌లోడ్ అవుతుంది)\n\nప్రతి పాట కింద Lyrics, Video మరియు Info బటన్లు ఉంటాయి।",
 "pick_lang": "🌐 మీ భాషను ఎంచుకోండి:",
 "lang_set": "✅ భాష తెలుగు ఎంచుకున్నారు. మొదలుపెట్టడానికి పాట పేరు పంపండి!",
 "btn_lang": "🌐 భాష",
 "searching": "🔍 వెతుకుతున్నాను...",
 "choose": "పాటను ఎంచుకోండి:",
 "no_result": "ఈ పేరుతో ఏమీ దొరకలేదు. పేరు మార్చి పంపండి (సింగర్ పేరు చేర్చండి).",
 "no_more": "ఇంకా ఫలితాలు లేవు.",
 "btn_more": "➕ మరిన్ని పాటలు",
 "btn_cancel": "❌ రద్దు",
 "too_long": "ఈ ట్రాక్ చాలా పొడవుగా ఉంది (15 నిమిషాల కంటే ఎక్కువ), పంపలేను. చిన్న వెర్షన్ ఎంచుకోండి.",
 "dl_wait": "⬇️ డౌన్‌లోడ్ అవుతోంది, కొంచెం వేచి ఉండండి (1-2 నిమిషాలు పట్టవచ్చు)...",
 "dl_fail": "క్షమించండి, ఇప్పుడు డౌన్‌లోడ్ కాలేదు. కొద్దిసేపటి తర్వాత లేదా మరో వెర్షన్ ప్రయత్నించండి.",
 "fallback_audio": "🎧 వీడియో రాలేదు, ఆడియో నుండి పాటను గుర్తిస్తున్నాను...",
 "link_fail": "ఈ లింక్ నుండి ఆడియో/వీడియో రాలేదు. మరో లింక్ లేదా వాయిస్ నోట్ ప్రయత్నించండి.",
 "send_fail": "ఫైల్ పంపడంలో ఇబ్బంది వచ్చింది. మళ్లీ ప్రయత్నించండి.",
 "btn_lyrics": "🔤 లిరిక్స్",
 "btn_video": "🎬 వీడియో",
 "btn_recog": "🎵 పాట గుర్తించండి",
 "recog_fail": "పాట గుర్తించలేకపోయాను. స్పష్టమైన ఆడియో లేదా పాట పేరు టైప్ చేసి పంపండి.",
 "listening": "🎧 వింటున్నాను, పాట గుర్తిస్తున్నాను...",
 "tg_dl_fail": "ఈ ఫైల్ డౌన్‌లోడ్ కాలేదు. 20 MB కంటే చిన్న ఫైల్ పంపండి.",
 "convert_fail": "ఈ ఆడియో అర్థం కాలేదు. మరో ఫైల్ ప్రయత్నించండి.",
 "old_search": "పాత సెర్చ్, పేరు మళ్లీ పంపండి.",
 "old_audio": "ఈ ఆడియో పాతదైపోయింది, లింక్ మళ్లీ పంపండి.",
 "lyrics_search": "🔍 లిరిక్స్ వెతుకుతున్నాను...",
 "lyrics_none": "ఈ ట్రాక్‌కు లిరిక్స్ దొరకలేదు.",
},
"mr": {
 "welcome": "नमस्कार! 🎵\n\nमी गाणी शोधून MP3 पाठवतो आणि लिंकवरून व्हिडिओ डाउनलोड करतो. पाठवा:\n\n📝 गाण्याचे नाव, गायक किंवा लिरिक्सची ओळ\n🎤 गाणे वाजत असलेला व्हॉइस नोट\n🎬 गाणे असलेले ऑडिओ किंवा व्हिडिओ\n🔗 YouTube, Instagram किंवा TikTok लिंक (व्हिडिओ डाउनलोड होईल)\n\nप्रत्येक गाण्याखाली Lyrics, Video आणि Info बटणे मिळतात.",
 "pick_lang": "🌐 तुमची भाषा निवडा:",
 "lang_set": "✅ भाषा मराठी निवडली. सुरू करण्यासाठी गाण्याचे नाव पाठवा!",
 "btn_lang": "🌐 भाषा",
 "searching": "🔍 शोधत आहे...",
 "choose": "गाणे निवडा:",
 "no_result": "या नावाने काही सापडले नाही. नाव थोडे बदलून पाठवा (गायकाचे नाव जोडा).",
 "no_more": "आणखी निकाल नाहीत.",
 "btn_more": "➕ आणखी गाणी",
 "btn_cancel": "❌ रद्द करा",
 "too_long": "हा ट्रॅक खूप लांब आहे (१५ मिनिटांपेक्षा जास्त), पाठवू शकत नाही. छोटा व्हर्जन निवडा.",
 "dl_wait": "⬇️ डाउनलोड होत आहे, थोडे थांबा (१-२ मिनिटे लागू शकतात)...",
 "dl_fail": "माफ करा, आत्ता डाउनलोड झाले नाही. थोड्या वेळाने किंवा दुसरा व्हर्जन वापरून पाहा.",
 "fallback_audio": "🎧 व्हिडिओ मिळाला नाही, ऑडिओवरून गाणे ओळखत आहे...",
 "link_fail": "या लिंकवरून ऑडिओ/व्हिडिओ मिळाला नाही. दुसरी लिंक किंवा व्हॉइस नोट वापरून पाहा.",
 "send_fail": "फाइल पाठवताना अडचण आली. पुन्हा प्रयत्न करा.",
 "btn_lyrics": "🔤 लिरिक्स",
 "btn_video": "🎬 व्हिडिओ",
 "btn_recog": "🎵 गाणे ओळखा",
 "recog_fail": "गाणे ओळखता आले नाही. स्पष्ट ऑडिओ किंवा गाण्याचे नाव लिहून पाठवा.",
 "listening": "🎧 ऐकत आहे, गाणे ओळखत आहे...",
 "tg_dl_fail": "ही फाइल डाउनलोड झाली नाही. २० MB पेक्षा छोटी फाइल पाठवा.",
 "convert_fail": "हे ऑडिओ समजले नाही. दुसरी फाइल वापरून पाहा.",
 "old_search": "जुनी सर्च आहे, नाव पुन्हा पाठवा.",
 "old_audio": "हे ऑडिओ जुने झाले, लिंक पुन्हा पाठवा.",
 "lyrics_search": "🔍 लिरिक्स शोधत आहे...",
 "lyrics_none": "या ट्रॅकचे लिरिक्स सापडले नाही.",
},
"ta": {
 "welcome": "வணக்கம்! 🎵\n\nநான் பாடல்களைத் தேடி MP3 அனுப்புகிறேன், லிங்குகளிலிருந்து வீடியோ டவுன்லோட் செய்கிறேன். அனுப்புங்கள்:\n\n📝 பாடல் பெயர், பாடகர் அல்லது லிரிக்ஸ் வரி\n🎤 பாடல் ஒலிக்கும் வாய்ஸ் நோட்\n🎬 பாடல் உள்ள ஆடியோ அல்லது வீடியோ\n🔗 YouTube, Instagram அல்லது TikTok லிங்க் (வீடியோ டவுன்லோட் ஆகும்)\n\nஒவ்வொரு பாடலின் கீழும் Lyrics, Video மற்றும் Info பட்டன்கள் இருக்கும்.",
 "pick_lang": "🌐 உங்கள் மொழியைத் தேர்ந்தெடுங்கள்:",
 "lang_set": "✅ மொழி தமிழ் தேர்ந்தெடுக்கப்பட்டது. தொடங்க பாடல் பெயரை அனுப்புங்கள்!",
 "btn_lang": "🌐 மொழி",
 "searching": "🔍 தேடுகிறேன்...",
 "choose": "பாடலைத் தேர்ந்தெடுங்கள்:",
 "no_result": "இந்தப் பெயரில் எதுவும் கிடைக்கவில்லை. பெயரை மாற்றி அனுப்புங்கள் (பாடகர் பெயரைச் சேர்க்கவும்).",
 "no_more": "மேலும் முடிவுகள் இல்லை.",
 "btn_more": "➕ மேலும் பாடல்கள்",
 "btn_cancel": "❌ ரத்து",
 "too_long": "இந்த டிராக் மிக நீளம் (15 நிமிடத்துக்கு மேல்), அனுப்ப முடியாது. சிறிய பதிப்பைத் தேர்ந்தெடுங்கள்.",
 "dl_wait": "⬇️ டவுன்லோட் ஆகிறது, கொஞ்சம் காத்திருங்கள் (1-2 நிமிடம் ஆகலாம்)...",
 "dl_fail": "மன்னிக்கவும், இப்போது டவுன்லோட் ஆகவில்லை. சிறிது நேரம் கழித்து அல்லது வேறு பதிப்பை முயற்சிக்கவும்.",
 "fallback_audio": "🎧 வீடியோ கிடைக்கவில்லை, ஆடியோவிலிருந்து பாடலை அடையாளம் காண்கிறேன்...",
 "link_fail": "இந்த லிங்கிலிருந்து ஆடியோ/வீடியோ கிடைக்கவில்லை. வேறு லிங்க் அல்லது வாய்ஸ் நோட் முயற்சிக்கவும்.",
 "send_fail": "ஃபைல் அனுப்புவதில் சிக்கல். மீண்டும் முயற்சிக்கவும்.",
 "btn_lyrics": "🔤 லிரிக்ஸ்",
 "btn_video": "🎬 வீடியோ",
 "btn_recog": "🎵 பாடலை அடையாளம் காண்க",
 "recog_fail": "பாடலை அடையாளம் காண முடியவில்லை. தெளிவான ஆடியோ அல்லது பாடல் பெயரை எழுதி அனுப்புங்கள்.",
 "listening": "🎧 கேட்கிறேன், பாடலை அடையாளம் காண்கிறேன்...",
 "tg_dl_fail": "இந்த ஃபைலை டவுன்லோட் செய்ய முடியவில்லை. 20 MBக்குக் குறைந்த ஃபைல் அனுப்புங்கள்.",
 "convert_fail": "இந்த ஆடியோ புரியவில்லை. வேறு ஃபைல் முயற்சிக்கவும்.",
 "old_search": "பழைய தேடல், பெயரை மீண்டும் அனுப்புங்கள்.",
 "old_audio": "இந்த ஆடியோ பழையது, லிங்கை மீண்டும் அனுப்புங்கள்.",
 "lyrics_search": "🔍 லிரிக்ஸ் தேடுகிறேன்...",
 "lyrics_none": "இந்த டிராக்கின் லிரிக்ஸ் கிடைக்கவில்லை.",
},
}
STRINGS.update({
"gu": {
 "welcome": "નમસ્તે! 🎵\n\nહું ગીતો શોધીને MP3 મોકલું છું અને લિંક પરથી વીડિયો ડાઉનલોડ કરું છું. મને મોકલો:\n\n📝 ગીતનું નામ, સિંગર કે લિરિક્સની લાઈન\n🎤 ગીત વાગતું હોય એવી વોઈસ નોટ\n🎬 ગીત ધરાવતું ઓડિયો કે વીડિયો\n🔗 YouTube, Instagram કે TikTok લિંક (વીડિયો ડાઉનલોડ થઈ જશે)\n\nદરેક ગીત નીચે Lyrics, Video અને Info બટન મળે છે.",
 "pick_lang": "🌐 તમારી ભાષા પસંદ કરો:",
 "lang_set": "✅ ભાષા ગુજરાતી પસંદ થઈ. શરૂ કરવા ગીતનું નામ મોકલો!",
 "btn_lang": "🌐 ભાષા",
 "searching": "🔍 શોધું છું...",
 "choose": "ગીત પસંદ કરો:",
 "no_result": "આ નામથી કંઈ મળ્યું નહીં. નામ થોડું બદલીને મોકલો (સિંગરનું નામ ઉમેરો).",
 "no_more": "વધુ પરિણામો નથી.",
 "btn_more": "➕ વધુ ગીતો",
 "btn_cancel": "❌ રદ કરો",
 "too_long": "આ ટ્રેક બહુ લાંબો છે (૧૫ મિનિટથી વધુ), મોકલી શકાતો નથી. નાનું વર્ઝન પસંદ કરો.",
 "dl_wait": "⬇️ ડાઉનલોડ થઈ રહ્યું છે, થોડી રાહ જુઓ (૧-૨ મિનિટ લાગી શકે)...",
 "dl_fail": "માફ કરશો, અત્યારે ડાઉનલોડ થઈ શક્યું નથી. થોડી વાર પછી કે બીજું વર્ઝન અજમાવો.",
 "fallback_audio": "🎧 વીડિયો મળ્યો નથી, ઓડિયો પરથી ગીત ઓળખું છું...",
 "link_fail": "આ લિંક પરથી ઓડિયો/વીડિયો મળ્યો નથી. બીજી લિંક કે વોઈસ નોટ અજમાવો.",
 "send_fail": "ફાઈલ મોકલવામાં મુશ્કેલી આવી. ફરી પ્રયાસ કરો.",
 "btn_lyrics": "🔤 લિરિક્સ",
 "btn_video": "🎬 વીડિયો",
 "btn_recog": "🎵 ગીત ઓળખો",
 "recog_fail": "ગીત ઓળખી શક્યો નહીં. સ્પષ્ટ ઓડિયો કે ગીતનું નામ લખીને મોકલો.",
 "listening": "🎧 સાંભળું છું, ગીત ઓળખું છું...",
 "tg_dl_fail": "આ ફાઈલ ડાઉનલોડ થઈ શકી નથી. ૨૦ MB થી નાની ફાઈલ મોકલો.",
 "convert_fail": "આ ઓડિયો સમજાયું નથી. બીજી ફાઈલ અજમાવો.",
 "old_search": "જૂની સર્ચ છે, નામ ફરી મોકલો.",
 "old_audio": "આ ઓડિયો જૂનું થઈ ગયું, લિંક ફરી મોકલો.",
 "lyrics_search": "🔍 લિરિક્સ શોધું છું...",
 "lyrics_none": "આ ટ્રેકના લિરિક્સ મળ્યા નથી.",
},
"kn": {
 "welcome": "ನಮಸ್ತे! 🎵\n\nನಾನು ಹಾಡುಗಳನ್ನು ಹುಡುಕಿ MP3 ಕಳುಹಿಸುತ್ತೇನೆ ಮತ್ತು ಲಿಂಕ್‌ಗಳಿಂದ ವೀಡಿಯೊ ಡೌನ್‌ಲೋಡ್ ಮಾಡುತ್ತೇನೆ. ಕಳುಹಿಸಿ:\n\n📝 ಹಾಡಿನ ಹೆಸರು, ಸಿಂಗರ್ ಅಥವಾ ಲಿರಿಕ್ಸ್ ಲೈನ್\n🎤 ಹಾಡು ಪ್ಲೇ ಆಗುತ್ತಿರುವ ವಾಯ್ಸ್ ನೋಟ್\n🎬 ಹಾಡಿರುವ ಆಡಿಯೋ ಅಥವಾ ವೀಡಿಯೊ\n🔗 YouTube, Instagram ಅಥವಾ TikTok ಲಿಂಕ್ (ವೀಡಿಯೊ ಡೌನ್‌ಲೋಡ್ ಆಗುತ್ತದೆ)\n\nಪ್ರತಿ ಹಾಡಿನ ಕೆಳಗೆ Lyrics, Video ಮತ್ತು Info ಬಟನ್‌ಗಳು ಸಿಗುತ್ತವೆ.",
 "pick_lang": "🌐 ನಿಮ್ಮ ಭಾಷೆಯನ್ನು ಆಯ್ಕೆಮಾಡಿ:",
 "lang_set": "✅ ಭಾಷೆ ಕನ್ನಡ ಆಯ್ಕೆಯಾಯಿತು. ಪ್ರಾರಂಭಿಸಲು ಹಾಡಿನ ಹೆಸರು ಕಳುಹಿಸಿ!",
 "btn_lang": "🌐 ಭಾಷೆ",
 "searching": "🔍 ಹುಡುಕುತ್ತಿದ್ದೇನೆ...",
 "choose": "ಹಾಡನ್ನು ಆಯ್ಕೆಮಾಡಿ:",
 "no_result": "ಈ ಹೆಸರಿನಿಂದ ಏನೂ ಸಿಗಲಿಲ್ಲ. ಹೆಸರು ಸ್ವಲ್ಪ ಬದಲಿಸಿ ಕಳುಹಿಸಿ (ಸಿಂಗರ್ ಹೆಸರು ಸೇರಿಸಿ).",
 "no_more": "ಇನ್ನು ಫಲಿತಾಂಶಗಳಿಲ್ಲ.",
 "btn_more": "➕ ಇನ್ನಷ್ಟು ಹಾಡುಗಳು",
 "btn_cancel": "❌ ರದ್ದುಮಾಡಿ",
 "too_long": "ಈ ಟ್ರ್ಯಾಕ್ ತುಂಬಾ ಉದ್ದ (15 ನಿಮಿಷಕ್ಕಿಂತ ಹೆಚ್ಚು), ಕಳುಹಿಸಲಾಗುವುದಿಲ್ಲ. ಚಿಕ್ಕ ವರ್ಷನ್ ಆಯ್ಕೆಮಾಡಿ.",
 "dl_wait": "⬇️ ಡೌನ್‌ಲೋಡ್ ಆಗುತ್ತಿದೆ, ಸ್ವಲ್ಪ ನಿರೀಕ್ಷಿಸಿ (1-2 ನಿಮಿಷ ಬೇಕಾಗಬಹುದು)...",
 "dl_fail": "ಕ್ಷಮಿಸಿ, ಈಗ ಡೌನ್‌ಲೋಡ್ ಆಗಲಿಲ್ಲ. ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಅಥವಾ ಬೇರೆ ವರ್ಷನ್ ಪ್ರಯತ್ನಿಸಿ.",
 "fallback_audio": "🎧 ವೀಡಿಯೊ ಸಿಗಲಿಲ್ಲ, ಆಡಿಯೋದಿಂದ ಹಾಡನ್ನು ಗುರುತಿಸುತ್ತಿದ್ದೇನೆ...",
 "link_fail": "ಈ ಲಿಂಕ್‌ನಿಂದ ಆಡಿಯೋ/ವೀಡಿಯೊ ಸಿಗಲಿಲ್ಲ. ಬೇರೆ ಲಿಂಕ್ ಅಥವಾ ವಾಯ್ಸ್ ನೋಟ್ ಪ್ರಯತ್ನಿಸಿ.",
 "send_fail": "ಫೈಲ್ ಕಳುಹಿಸುವಲ್ಲಿ ತೊಂದರೆಯಾಯಿತು. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
 "btn_lyrics": "🔤 ಲಿರిక్స್",
 "btn_video": "🎬 ವೀಡಿಯೊ",
 "btn_recog": "🎵 ಹಾಡು ಗುರುತಿಸಿ",
 "recog_fail": "ಹಾಡು ಗುರುತಿಸಲಾಗಲಿಲ್ಲ. ಸ್ಪಷ್ಟ ಆಡಿಯೋ ಅಥವಾ ಹಾಡಿನ ಹೆಸರು ಬರೆದು ಕಳುಹಿಸಿ.",
 "listening": "🎧 ಕೇಳುತ್ತಿದ್ದೇನೆ, ಹಾಡು ಗುರುತಿಸುತ್ತಿದ್ದೇನೆ...",
 "tg_dl_fail": "ಈ ಫೈಲ್ ಡೌನ್‌ಲೋಡ್ ಆಗಲಿಲ್ಲ. 20 MBಗಿಂತ ಚಿಕ್ಕ ಫೈಲ್ ಕಳುಹಿಸಿ.",
 "convert_fail": "ಈ ಆಡಿಯೋ ಅರ್ಥವಾಗಲಿಲ್ಲ. ಬೇರೆ ಫೈಲ್ ಪ್ರಯತ್ನಿಸಿ.",
 "old_search": "ಹಳೆಯ ಸರ್ಚ್, ಹೆಸರು ಮತ್ತೆ ಕಳುಹಿಸಿ.",
 "old_audio": "ಈ ಆಡಿಯೋ ಹಳೆಯದಾಗಿದೆ, ಲಿಂಕ್ ಮತ್ತೆ ಕಳುಹಿಸಿ.",
 "lyrics_search": "🔍 ಲಿರಿಕ್ಸ್ ಹುಡುಕುತ್ತಿದ್ದೇನೆ...",
 "lyrics_none": "ಈ ಟ್ರ್ಯಾಕ್‌ನ ಲಿರಿಕ್ಸ್ ಸಿಗಲಿಲ್ಲ.",
},
"ml": {
 "welcome": "നമസ്കാരം! 🎵\n\nഞാൻ പാട്ടുകൾ കണ്ടെത്തി MP3 അയക്കുകയും ലിങ്കുകളിൽ നിന്ന് വീഡിയോ ഡൗൺലോഡ് ചെയ്യുകയും ചെയ്യും. അയക്കുക:\n\n📝 പാട്ടിന്റെ പേര്, സിംഗർ അല്ലെങ്കിൽ ലിറിക്സ് ലൈൻ\n🎤 പാട്ട് കേൾക്കുന്ന വോയ്സ് നോട്ട്\n🎬 പാട്ടുള്ള ഓഡിയോ അല്ലെങ്കിൽ വീഡിയോ\n🔗 YouTube, Instagram അല്ലെങ്കിൽ TikTok ലിങ്ക് (വീഡിയോ ഡൗൺലോഡ് ആകും)\n\nഓരോ പാട്ടിനും താഴെ Lyrics, Video, Info ബട്ടണുകൾ ലഭിക്കും.",
 "pick_lang": "🌐 നിങ്ങളുടെ ഭാഷ തിരഞ്ഞെടുക്കുക:",
 "lang_set": "✅ ഭാഷ മലയാളം തിരഞ്ഞെടുത്തു. തുടങ്ങാൻ പാട്ടിന്റെ പേര് അയക്കുക!",
 "btn_lang": "🌐 ഭാഷ",
 "searching": "🔍 തിരയുന്നു...",
 "choose": "പാട്ട് തിരഞ്ഞെടുക്കുക:",
 "no_result": "ഈ പേരിൽ ഒന്നും കിട്ടിയില്ല. പേര് അൽപ്പം മാറ്റി അയക്കുക (സിംഗറുടെ പേര് ചേർക്കുക).",
 "no_more": "കൂടുതൽ ഫലങ്ങളില്ല.",
 "btn_more": "➕ കൂടുതൽ പാട്ടുകൾ",
 "btn_cancel": "❌ റദ്ദാക്കുക",
 "too_long": "ഈ ട്രാക്ക് വളരെ നീളമുള്ളതാണ് (15 മിനിറ്റിൽ കൂടുതൽ), അയക്കാൻ കഴിയില്ല. ചെറിയ വേർഷൻ തിരഞ്ഞെടുക്കുക.",
 "dl_wait": "⬇️ ഡൗൺലോഡ് ചെയ്യുന്നു, കുറച്ച് കാത്തിരിക്കുക (1-2 മിനിറ്റ് എടുക്കാം)...",
 "dl_fail": "ക്ഷമിക്കണം, ഇപ്പോൾ ഡൗൺലോഡ് ആയില്ല. അല്പസമയം കഴിഞ്ഞോ മറ്റൊരു വേർഷനോ ശ്രമിക്കുക.",
 "fallback_audio": "🎧 വീഡിയോ കിട്ടിയില്ല, ഓഡിയോയിൽ നിന്ന് പാട്ട് തിരിച്ചറിയുന്നു...",
 "link_fail": "ഈ ലിങ്കിൽ നിന്ന് ഓഡിയോ/വീഡിയോ കിട്ടിയില്ല. മറ്റൊരു ലിങ്കോ വോയ്സ് നോട്ടോ ശ്രമിക്കുക.",
 "send_fail": "ഫയൽ അയക്കുന്നതിൽ പ്രശ്നമായി. വീണ്ടും ശ്രമിക്കുക.",
 "btn_lyrics": "🔤 ലിറിക്സ്",
 "btn_video": "🎬 വീഡിയോ",
 "btn_recog": "🎵 പാട്ട് തിരിച്ചറിയുക",
 "recog_fail": "പാട്ട് തിരിച്ചറിയാൻ കഴിഞ്ഞില്ല. വ്യക്തമായ ഓഡിയോ അല്ലെങ്കിൽ പാട്ടിന്റെ പേര് എഴുതി അയക്കുക.",
 "listening": "🎧 കേൾക്കുന്നു, പാട്ട് തിരിച്ചറിയുന്നു...",
 "tg_dl_fail": "ഈ ഫയൽ ഡൗൺലോഡ് ആയില്ല. 20 MB-ൽ ചെറിയ ഫയൽ അയക്കുക.",
 "convert_fail": "ഈ ഓഡിയോ മനസ്സിലായില്ല. മറ്റൊരു ഫയൽ ശ്രമിക്കുക.",
 "old_search": "പഴയ സെർച്ച് ആണ്, പേര് വീണ്ടും അയക്കുക.",
 "old_audio": "ഈ ഓഡിയോ പഴയതായി, ലിങ്ക് വീണ്ടും അയക്കുക.",
 "lyrics_search": "🔍 ലിറിക്സ് തിരയുന്നു...",
 "lyrics_none": "ഈ ട്രാക്കിന്റെ ലിറിക്സ് കിട്ടിയില്ല.",
},
"pa": {
 "welcome": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! 🎵\n\nਮੈਂ ਗਾਣੇ ਲੱਭ ਕੇ MP3 ਭੇਜਦਾ ਹਾਂ ਤੇ ਲਿੰਕਾਂ ਤੋਂ ਵੀਡੀਓ ਡਾਊਨਲੋਡ ਕਰਦਾ ਹਾਂ। ਮੈਨੂੰ ਭੇਜੋ:\n\n📝 ਗਾਣੇ ਦਾ ਨਾਮ, ਸਿੰਗਰ ਜਾਂ ਲਿਰਿਕਸ ਦੀ ਲਾਈਨ\n🎤 ਗਾਣਾ ਵੱਜ ਰਿਹਾ ਵੌਇਸ ਨੋਟ\n🎬 ਗਾਣਾ ਹੋਵੇ ਅਜਿਹਾ ਆਡੀਓ ਜਾਂ ਵੀਡੀਓ\n🔗 YouTube, Instagram ਜਾਂ TikTok ਲਿੰਕ (ਵੀਡੀਓ ਡਾਊਨਲੋਡ ਹੋ ਜਾਵੇਗਾ)\n\nਹਰ ਗਾਣੇ ਹੇਠ Lyrics, Video ਅਤੇ Info ਬਟਨ ਮਿਲਦੇ ਹਨ।",
 "pick_lang": "🌐 ਆਪਣੀ ਭਾਸ਼ਾ ਚੁਣੋ:",
 "lang_set": "✅ ਭਾਸ਼ਾ ਪੰਜਾਬੀ ਚੁਣੀ ਗਈ। ਸ਼ੁਰੂ ਕਰਨ ਲਈ ਗਾਣੇ ਦਾ ਨਾਮ ਭੇਜੋ!",
 "btn_lang": "🌐 ਭਾਸ਼ਾ",
 "searching": "🔍 ਲੱਭ ਰਿਹਾ ਹਾਂ...",
 "choose": "ਗਾਣਾ ਚੁਣੋ:",
 "no_result": "ਇਸ ਨਾਮ ਨਾਲ ਕੁਝ ਨਹੀਂ ਮਿਲਿਆ। ਨਾਮ ਥੋੜ੍ਹਾ ਬਦਲ ਕੇ ਭੇਜੋ (ਸਿੰਗਰ ਦਾ ਨਾਮ ਜੋੜੋ)।",
 "no_more": "ਹੋਰ ਨਤੀਜੇ ਨਹੀਂ ਮਿਲੇ।",
 "btn_more": "➕ ਹੋਰ ਗਾਣੇ",
 "btn_cancel": "❌ ਰੱਦ ਕਰੋ",
 "too_long": "ਇਹ ਟ੍ਰੈਕ ਬਹੁਤ ਲੰਮਾ ਹੈ (15 ਮਿੰਟ ਤੋਂ ਵੱਧ), ਇਹ ਭੇਜ ਨਹੀਂ ਸਕਦਾ। ਛੋਟਾ ਵਰਜ਼ਨ ਚੁਣੋ।",
 "dl_wait": "⬇️ ਡਾਊਨਲੋਡ ਹੋ ਰਿਹਾ ਹੈ, ਥੋੜ੍ਹਾ ਇੰਤਜ਼ਾਰ ਕਰੋ (1-2 ਮਿੰਟ ਲੱਗ ਸਕਦੇ ਹਨ)...",
 "dl_fail": "ਮਾਫ਼ ਕਰਨਾ, ਹੁਣੇ ਡਾਊਨਲੋਡ ਨਹੀਂ ਹੋ ਸਕਿਆ। ਥੋੜ੍ਹੀ ਦੇਰ ਬਾਅਦ ਜਾਂ ਕੋਈ ਹੋਰ ਵਰਜ਼ਨ ਅਜ਼ਮਾਓ।",
 "fallback_audio": "🎧 ਵੀਡੀਓ ਨਹੀਂ ਨਿਕਲ ਸਕਿਆ, ਆਡੀਓ ਤੋਂ ਗਾਣਾ ਪਛਾਣ ਰਿਹਾ ਹਾਂ...",
 "link_fail": "ਇਸ ਲਿੰਕ ਤੋਂ ਆਡੀਓ/ਵੀਡੀਓ ਨਹੀਂ ਨਿਕਲ ਸਕਿਆ। ਹੋਰ ਲਿੰਕ ਜਾਂ ਵੌਇਸ ਨੋਟ ਅਜ਼ਮਾਓ।",
 "send_fail": "ਫਾਈਲ ਭੇਜਣ ਵਿੱਚ ਦਿੱਕਤ ਆਈ। ਦੁਬਾਰਾ ਕੋਸ਼ਿਸ਼ ਕਰੋ।",
 "btn_lyrics": "🔤 ਲਿਰਿਕਸ",
 "btn_video": "🎬 ਵੀਡੀਓ",
 "btn_recog": "🎵 ਗਾਣਾ ਪਛਾਣੋ",
 "recog_fail": "ਗਾਣਾ ਪਛਾਣ ਨਹੀਂ ਸਕਿਆ। ਸਾਫ਼ ਆਡੀਓ ਜਾਂ ਗਾਣੇ ਦਾ ਨਾਮ ਲਿਖ ਕੇ ਭੇਜੋ।",
 "listening": "🎧 ਸੁਣ ਰਿਹਾ ਹਾਂ, ਗਾਣਾ ਪਛਾਣ ਰਿਹਾ ਹਾਂ...",
 "tg_dl_fail": "ਇਹ ਫਾਈਲ ਡਾਊਨਲੋਡ ਨਹੀਂ ਹੋ ਸਕੀ। 20 MB ਤੋਂ ਛੋਟੀ ਫਾਈਲ ਭੇਜੋ।",
 "convert_fail": "ਇਹ ਆਡੀਓ ਸਮਝ ਨਹੀਂ ਆਇਆ। ਦੂਜੀ ਫਾਈਲ ਅਜ਼ਮਾਓ।",
 "old_search": "ਪੁਰਾਣੀ ਸਰਚ ਹੈ, ਨਾਮ ਦੁਬਾਰਾ ਭੇਜੋ।",
 "old_audio": "ਇਹ ਆਡੀਓ ਪੁਰਾਣਾ ਹੋ ਗਿਆ, ਲਿੰਕ ਦੁਬਾਰਾ ਭੇਜੋ।",
 "lyrics_search": "🔍 ਲਿਰਿਕਸ ਲੱਭ ਰਿਹਾ ਹਾਂ...",
 "lyrics_none": "ਇਸ ਟ੍ਰੈਕ ਦੇ ਲਿਰਿਕਸ ਨਹੀਂ ਮਿਲੇ।",
},
"ur": {
 "welcome": "السلام علیکم! 🎵\n\nمیں گانے ڈھونڈ کر MP3 بھیجتا ہوں اور لنکس سے ویڈیو ڈاؤن لوڈ کرتا ہوں۔ مجھے بھیجیں:\n\n📝 گانے کا نام، سنگر یا لیرکس کی لائن\n🎤 گانا بج رہا ہو ایسی وائس نوٹ\n🎬 گانا ہو ایسی آڈیو یا ویڈیو\n🔗 YouTube، Instagram یا TikTok لنک (ویڈیو ڈاؤن لوڈ ہو جائے گا)\n\nہر گانے کے نیچے Lyrics، Video اور Info بٹن ملتے ہیں۔",
 "pick_lang": "🌐 اپنی زبان منتخب کریں:",
 "lang_set": "✅ زبان اردو منتخب ہو گئی۔ شروع کرنے کے لیے گانے کا نام بھیجیں!",
 "btn_lang": "🌐 زبان",
 "searching": "🔍 ڈھونڈ رہا ہوں...",
 "choose": "گانا منتخب کریں:",
 "no_result": "اس نام سے کچھ نہیں ملا۔ نام تھوڑا بدل کر بھیجیں (سنگر کا نام جوڑیں)۔",
 "no_more": "مزید نتائج نہیں ملے۔",
 "btn_more": "➕ مزید گانے",
 "btn_cancel": "❌ منسوخ کریں",
 "too_long": "یہ ٹریک بہت لمبا ہے (15 منٹ سے زیادہ)، یہ نہیں بھیج سکتا۔ چھوٹا ورژن منتخب کریں۔",
 "dl_wait": "⬇️ ڈاؤن لوڈ ہو رہا ہے، تھوڑا انتظار کریں (1-2 منٹ لگ سکتے ہیں)...",
 "dl_fail": "معذرت، ابھی ڈاؤن لوڈ نہیں ہو سکا۔ تھوڑی دیر بعد یا کوئی اور ورژن آزمائیں۔",
 "fallback_audio": "🎧 ویڈیو نہیں نکل سکی، آڈیو سے گانا پہچان رہا ہوں...",
 "link_fail": "اس لنک سے آڈیو/ویڈیو نہیں نکل سکی۔ دوسرا لنک یا وائس نوٹ آزمائیں۔",
 "send_fail": "فائل بھیجنے میں دقت آئی۔ دوبارہ کوشش کریں۔",
 "btn_lyrics": "🔤 لیرکس",
 "btn_video": "🎬 ویڈیو",
 "btn_recog": "🎵 گانا پہچانیں",
 "recog_fail": "گانا پہچان نہیں سکا۔ صاف آڈیو یا گانے کا نام لکھ کر بھیجیں۔",
 "listening": "🎧 سن رہا ہوں، گانا پہچان رہا ہوں...",
 "tg_dl_fail": "یہ فائل ڈاؤن لوڈ نہیں ہو سکی۔ 20 MB سے چھوٹی فائل بھیجیں۔",
 "convert_fail": "یہ آڈیو سمجھ نہیں آئی۔ دوسری فائل آزمائیں۔",
 "old_search": "پرانی سرچ ہے، نام دوبارہ بھیجیں۔",
 "old_audio": "یہ آڈیو پرانا ہو گیا، لنک دوبارہ بھیجیں۔",
 "lyrics_search": "🔍 لیرکس ڈھونڈ رہا ہوں...",
 "lyrics_none": "اس ٹریک کے لیرکس نہیں ملے۔",
},
"es": {
 "welcome": "¡Hola! 🎵\n\nBusco canciones y envío MP3, y descargo videos de enlaces. Envíame:\n\n📝 Nombre de la canción, cantante o una línea de la letra\n🎤 Nota de voz con una canción sonando\n🎬 Audio o video con una canción\n🔗 Enlace de YouTube, Instagram o TikTok (descargaré el video)\n\nCada canción incluye botones de Lyrics, Video e Info (enlaces a todas las apps de música).",
 "pick_lang": "🌐 Elige tu idioma:",
 "lang_set": "✅ Idioma cambiado a Español. ¡Envía el nombre de una canción para empezar!",
 "btn_lang": "🌐 Idioma",
 "searching": "🔍 Buscando...",
 "choose": "Elige una canción:",
 "no_result": "No encontré nada con ese nombre. Prueba con otro (añade el nombre del cantante).",
 "no_more": "No hay más resultados.",
 "btn_more": "➕ Más canciones",
 "btn_cancel": "❌ Cancelar",
 "too_long": "Esa pista es muy larga (más de 15 min), no puedo enviarla. Elige una versión más corta.",
 "dl_wait": "⬇️ Descargando, espera un poco (puede tardar 1-2 min)...",
 "dl_fail": "Lo siento, no se pudo descargar ahora. Inténtalo más tarde o elige otra versión.",
 "fallback_audio": "🎧 No pude obtener el video, reconociendo la canción desde el audio...",
 "link_fail": "No pude sacar audio/video de este enlace. Prueba otro enlace o una nota de voz.",
 "send_fail": "Hubo un problema al enviar el archivo. Inténtalo de nuevo.",
 "btn_lyrics": "🔤 Letra",
 "btn_video": "🎬 Video",
 "btn_recog": "🎵 Reconocer canción",
 "recog_fail": "No pude reconocer la canción. Envía un audio más claro o escribe el nombre.",
 "listening": "🎧 Escuchando, reconociendo la canción...",
 "tg_dl_fail": "No pude descargar este archivo. Envía uno menor de 20 MB.",
 "convert_fail": "No entendí este audio. Prueba con otro archivo.",
 "old_search": "Búsqueda antigua, envía el nombre de nuevo.",
 "old_audio": "Este audio caducó, envía el enlace de nuevo.",
 "lyrics_search": "🔍 Buscando la letra...",
 "lyrics_none": "No encontré la letra de esta pista.",
},
})

LANG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_langs.json")

def _load_langs():
    try:
        with open(LANG_FILE) as f:
            return {int(k): v for k, v in json.load(f).items()}
    except Exception:
        return {}

ULANG = _load_langs()

def _save_langs():
    try:
        with open(LANG_FILE, "w") as f:
            json.dump(ULANG, f)
    except Exception as exc:
        log.info("lang save failed: %s", exc)

def lang_of(uid):
    return ULANG.get(uid, "hi")

def T(lang, key):
    d = STRINGS.get(lang) or STRINGS["hi"]
    return d.get(key) or STRINGS["en"].get(key) or key

def TM(message, key):
    return T(lang_of(message.chat_id), key)

def lang_keyboard():
    rows, row = [], []
    for code, name in LANGS:
        row.append(InlineKeyboardButton(name, callback_data=f"lang:{code}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)

def lang_btn(lang):
    return [InlineKeyboardButton(T(lang, "btn_lang"), callback_data="langmenu")]
MAX_SECONDS = 15 * 60  # refuse downloads longer than 15 min

SESSIONS = {}
VID_QUERY = {}  # token -> {"query": str, "ts": float}
LINK_AUD = {}  # token -> {"mp3": str, "ts": float}
MAX_VIDEO_BYTES = 49 * 1024 * 1024  # Telegram bot upload limit is 50 MB
shazam = Shazam()


# ---------- search ----------

def _walk(o, out):
    if isinstance(o, dict):
        v = o.get("videoRenderer")
        if v and v.get("videoId"):
            out.append({
                "vid": v["videoId"],
                "title": "".join(r.get("text", "") for r in v.get("title", {}).get("runs", [])) or "Unknown",
                "channel": "".join(r.get("text", "") for r in v.get("ownerText", {}).get("runs", [])) or "",
                "seconds": None,
                "dur": v.get("lengthText", {}).get("simpleText"),
            })
        for x in o.values():
            _walk(x, out)
    elif isinstance(o, list):
        for x in o:
            _walk(x, out)


def yt_search(query, page=1):
    """Return list of {vid,title,channel,seconds,dur}."""
    for host in INVIDIOUS:
        try:
            r = requests.get(f"{host}/api/v1/search",
                             params={"q": query, "type": "video", "page": page}, timeout=15)
            if r.status_code == 200:
                out = []
                for it in r.json():
                    if it.get("type") == "video" and it.get("videoId"):
                        sec = it.get("lengthSeconds")
                        out.append({
                            "vid": it["videoId"],
                            "title": it.get("title") or "Unknown",
                            "channel": it.get("author") or "",
                            "seconds": int(sec) if sec else None,
                            "dur": f"{int(sec)//60}:{int(sec)%60:02d}" if sec else None,
                        })
                        if len(out) >= 10:
                            return out
                if out:
                    return out
        except Exception as exc:
            log.info("invidious search failed: %s", exc)
    # fallback: scrape youtube (page param unsupported)
    try:
        r = requests.get("https://www.youtube.com/results",
                         params={"search_query": query}, headers=UA, timeout=15)
        m = re.search(r"var ytInitialData = (\{.*?\});</script>", r.text, re.S)
        if m:
            out = []
            _walk(json.loads(m.group(1)), out)
            return out[:10]
    except Exception as exc:
        log.info("scrape search failed: %s", exc)
    return []


def video_meta(vid):
    for host in INVIDIOUS:
        try:
            r = requests.get(f"{host}/api/v1/videos/{vid}", timeout=15)
            if r.status_code == 200:
                d = r.json()
                return {"title": d.get("title") or "Unknown",
                        "channel": d.get("author") or "",
                        "seconds": d.get("lengthSeconds")}
        except Exception:
            pass
    return None


# ---------- audio download / convert ----------

def download_mp3(vid, workdir):
    """Download audio via invidious proxy, convert to mp3. Returns path or None."""
    m4a = os.path.join(workdir, f"{vid}.m4a")
    mp3 = os.path.join(workdir, f"{vid}.mp3")
    for itag in ("140", "139", "251", "250", "249"):
        for host in INVIDIOUS:
            try:
                url = f"{host}/latest_version?id={vid}&itag={itag}&local=true"
                with requests.get(url, stream=True, timeout=(15, 300)) as r:
                    if r.status_code != 200:
                        continue
                    with open(m4a, "wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            f.write(chunk)
                if os.path.getsize(m4a) > 10000:
                    break
            except Exception as exc:
                log.info("download itag=%s host=%s failed: %s", itag, host, exc)
        else:
            continue
        break
    else:
        return None
    try:
        subprocess.run([FFMPEG, "-y", "-i", m4a, "-c:a", "libmp3lame", "-q:a", "4", mp3],
                       check=True, capture_output=True, timeout=300)
        return mp3
    except Exception as exc:
        log.info("ffmpeg failed: %s", exc)
        return None


def download_video(vid, workdir, max_bytes=MAX_VIDEO_BYTES):
    """Download muxed mp4 (360p/720p) via invidious proxy. Returns path or None."""
    mp4 = os.path.join(workdir, f"{vid}.mp4")
    for itag in ("18", "22"):
        for host in INVIDIOUS:
            try:
                url = f"{host}/latest_version?id={vid}&itag={itag}&local=true"
                with requests.get(url, stream=True, timeout=(15, 300)) as r:
                    if r.status_code != 200:
                        continue
                    cl = r.headers.get("Content-Length")
                    if cl and int(cl) > max_bytes:
                        log.info("video too big: %s bytes", cl)
                        return None
                    size = 0
                    with open(mp4, "wb") as f:
                        for chunk in r.iter_content(1 << 16):
                            size += len(chunk)
                            if size > max_bytes:
                                log.info("video exceeded %s bytes mid-stream", max_bytes)
                                return None
                            f.write(chunk)
                if os.path.getsize(mp4) > 10000:
                    return mp4
            except Exception as exc:
                log.info("video itag=%s host=%s failed: %s", itag, host, exc)
    return None


def file_to_mp3(src, workdir, name="aud", max_seconds=120):
    mp3 = os.path.join(workdir, name + ".mp3")
    subprocess.run([FFMPEG, "-y", "-i", src, "-t", str(max_seconds),
                    "-c:a", "libmp3lame", "-q:a", "4", mp3],
                   check=True, capture_output=True, timeout=120)
    return mp3


def download_video_link(text, workdir, max_bytes=MAX_VIDEO_BYTES):
    """Download video from non-YouTube sites (Instagram, TikTok etc.) via yt_dlp."""
    import yt_dlp
    out = os.path.join(workdir, "v.%(ext)s")
    opts = {"quiet": True, "format": "best[ext=mp4]/best",
            "outtmpl": out, "ffmpeg_location": FFMPEG,
            "max_filesize": max_bytes}
    with yt_dlp.YoutubeDL(opts) as y:
        y.download([text])
    for ext in ("mp4", "mkv", "webm", "mov", "ts"):
        p = os.path.join(workdir, f"v.{ext}")
        if os.path.exists(p) and os.path.getsize(p) > 10000:
            return p
    return None


def _janitor():
    """Drop stale link-audio tokens and old temp dirs (free tier has small disk)."""
    now = time.time()
    for tok, d in list(LINK_AUD.items()):
        if now - d["ts"] > 1800:
            LINK_AUD.pop(tok, None)
    try:
        names = os.listdir("/tmp")
    except OSError:
        return
    for name in names:
        if name.startswith(("dl_", "yt_", "ln_", "md_", "vd_")):
            p = os.path.join("/tmp", name)
            try:
                if now - os.path.getmtime(p) > 1800:
                    shutil.rmtree(p, ignore_errors=True)
            except OSError:
                pass


def bytes_to_mp3(data, workdir, name="in", max_seconds=90):
    src = os.path.join(workdir, name)
    with open(src, "wb") as f:
        f.write(data)
    mp3 = os.path.join(workdir, name + ".mp3")
    subprocess.run([FFMPEG, "-y", "-i", src, "-t", str(max_seconds),
                    "-c:a", "libmp3lame", "-q:a", "4", mp3],
                   check=True, capture_output=True, timeout=120)
    return mp3


# ---------- recognition / lyrics ----------

async def recognize_file(path):
    with open(path, "rb") as f:
        data = f.read()
    r = await shazam.recognize(data=data)
    t = (r or {}).get("track") or {}
    if not t.get("title"):
        return None
    return {"title": t["title"], "artist": t.get("subtitle") or ""}


def clean_title(t):
    t = t.split("|")[0]
    t = re.sub(r"[\(\[].*?[\)\]]", " ", t)
    t = re.sub(r"(?i)\b(official|video|audio|lyrical|lyric|lyrics|full song|hd|4k|8k|mv|music video)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip(" -")


def _lrclib(path, params):
    for attempt in range(3):
        try:
            r = requests.get(f"https://lrclib.net/api/{path}", params=params, timeout=8)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 503):
                time.sleep(1.5 * (attempt + 1))
                continue
            return None
        except Exception:
            return None
    return None


def get_lyrics(artist, title, query=None):
    arts = []
    for p in title.split("|")[1:]:
        p = p.strip()
        if 0 < len(p) <= 25 and len(p.split()) <= 3:
            arts.append(p)
    c = (artist or "").replace("VEVO", "").replace(" - Topic", "").strip()
    if c and len(c) < 40:
        arts.append(c)
    arts = list(dict.fromkeys(arts))[:6]

    qt = clean_title(title)
    tracks = []
    for seg in qt.split(" - "):
        seg = seg.strip()
        if seg:
            tracks.append(seg)
    tracks.append(qt)
    if query and query.strip():
        tracks.append(query.strip())
    tracks = list(dict.fromkeys(tracks))[:4]

    for t in tracks:
        for a in arts:
            d = _lrclib("get", {"track_name": t, "artist_name": a})
            if d and d.get("plainLyrics"):
                return d["plainLyrics"]
            time.sleep(0.3)

    qs = []
    if query and query.strip() and len(query.split()) >= 2:
        qs.append(query.strip())
    for t in tracks[:2]:
        for a in arts[:2]:
            qs.append(f"{t} {a}")
        if len(t.split()) >= 2:
            qs.append(t)
    seen = set()
    for q in qs:
        if q in seen:
            continue
        seen.add(q)
        items = _lrclib("search", {"q": q})
        if items:
            for item in items:
                if item.get("plainLyrics"):
                    return item["plainLyrics"]
        time.sleep(0.3)
    return None


# ---------- telegram helpers ----------

def fmt_line(t):
    dur = f"• {t['dur']} • " if t.get("dur") else ""
    ch = f" — {t['channel']}" if t.get("channel") else ""
    return f"{dur}{t['title']}{ch}"


def search_keyboard(query, page, results, lang="hi"):
    token = uuid.uuid4().hex[:8]
    SESSIONS[token] = {"query": query, "ts": time.time()}
    for t in results:
        VID_QUERY[t["vid"]] = query
    rows = [[InlineKeyboardButton(fmt_line(t)[:64], callback_data=f"d:{t['vid']}")]
            for t in results[:10]]
    nav = [InlineKeyboardButton(T(lang, "btn_more"), callback_data=f"p:{token}:{page + 1}"),
           InlineKeyboardButton(T(lang, "btn_cancel"), callback_data="x")]
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def card_keyboard(title, artist):
    q = quote_plus(f"{title} {artist}".strip())
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("Google", url=f"https://www.google.com/search?q={q}"),
        InlineKeyboardButton("YouTube Music", url=f"https://music.youtube.com/search?q={q}"),
        InlineKeyboardButton("Spotify", url=f"https://open.spotify.com/search/{q}"),
    ]])


async def send_song(message, vid, context):
    """Download vid as mp3 and send with a Lyrics button."""
    meta = video_meta(vid)
    if meta and meta.get("seconds") and meta["seconds"] > MAX_SECONDS:
        await message.reply_text(TM(message, "too_long"))
        return
    status = await message.reply_text(TM(message, "dl_wait"))
    workdir = f"/tmp/dl_{uuid.uuid4().hex[:8]}"
    os.makedirs(workdir, exist_ok=True)
    mp3 = await asyncio.to_thread(download_mp3, vid, workdir)
    if not mp3:
        await status.edit_text(TM(message, "dl_fail"))
        return
    title = meta["title"] if meta else "Song"
    artist = meta["channel"] if meta else ""
    fname = (f"{artist} - {title}".strip(" -") or "song")[:60] + ".mp3"
    try:
        with open(mp3, "rb") as f:
            await message.reply_audio(
                audio=f,
                filename=fname,
                title=title[:64], performer=artist[:64],
                duration=meta.get("seconds") if meta else None,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(T(lang_of(message.chat_id), "btn_lyrics"), callback_data=f"l:{vid}"),
                      InlineKeyboardButton(T(lang_of(message.chat_id), "btn_video"), callback_data=f"v:{vid}"),
                      InlineKeyboardButton("ℹ️ Info", url=f"https://song.link/y/{vid}")]]),
                write_timeout=300, read_timeout=300,
            )
        await status.delete()
    except Exception as exc:
        log.warning("send audio failed: %s", exc)
        await status.edit_text(TM(message, "send_fail"))


async def send_video_file(message, vid):
    """Download vid as mp4 and send it with an Info button."""
    meta = await asyncio.to_thread(video_meta, vid)
    if meta and meta.get("seconds") and meta["seconds"] > MAX_SECONDS:
        await message.reply_text(TM(message, "too_long"))
        return
    status = await message.reply_text(TM(message, "dl_wait"))
    workdir = f"/tmp/vd_{uuid.uuid4().hex[:8]}"
    os.makedirs(workdir, exist_ok=True)
    mp4 = await asyncio.to_thread(download_video, vid, workdir)
    if not mp4:
        await status.edit_text(TM(message, "dl_fail"))
        return
    title = meta["title"] if meta else "Video"
    try:
        with open(mp4, "rb") as f:
            await message.reply_video(
                video=f,
                caption=f"🎬 {title}"[:200],
                duration=meta.get("seconds") if meta else None,
                supports_streaming=True,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("ℹ️ Info", url=f"https://song.link/y/{vid}")]]),
                write_timeout=300, read_timeout=300,
            )
        await status.delete()
    except Exception as exc:
        log.warning("send video failed: %s", exc)
        await status.edit_text(TM(message, "send_fail"))


# ---------- handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ULANG:
        await update.message.reply_text(T("hi", "pick_lang") + " / " + T("en", "pick_lang"),
                                        reply_markup=lang_keyboard())
        return
    lang = lang_of(uid)
    await update.message.reply_text(T(lang, "welcome"),
                                    reply_markup=InlineKeyboardMarkup([lang_btn(lang)]))


async def lang_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(T(lang_of(update.effective_user.id), "pick_lang"),
                                    reply_markup=lang_keyboard())


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return
    m = re.search(r"(?:youtube\.com/(?:watch\?[^ ]*v=|shorts/)|youtu\.be/)([\w-]{11})", text)
    if m:
        await handle_youtube_link(update, m.group(1))
        return
    if re.search(r"https?://", text):
        await handle_other_link(update, text)
        return
    wait = await update.message.reply_text(TM(update.message, "searching"))
    results = await asyncio.to_thread(yt_search, text)
    if not results:
        await wait.edit_text(TM(update.message, "no_result"))
        return
    lang = lang_of(update.message.chat_id)
    await wait.edit_text(T(lang, "choose"),
                         reply_markup=search_keyboard(text, 1, results, lang))


async def handle_youtube_link(update: Update, vid):
    message = update.message
    _janitor()
    status = await message.reply_text(TM(message, "dl_wait"))
    meta = await asyncio.to_thread(video_meta, vid)
    if meta and meta.get("seconds") and meta["seconds"] > MAX_SECONDS:
        await status.edit_text(TM(message, "too_long"))
        return
    workdir = f"/tmp/yt_{uuid.uuid4().hex[:8]}"
    os.makedirs(workdir, exist_ok=True)
    mp4 = await asyncio.to_thread(download_video, vid, workdir)
    if not mp4:
        await status.edit_text(TM(message, "fallback_audio"))
        mp3 = await asyncio.to_thread(download_mp3, vid, workdir)
        if not mp3:
            await status.edit_text(TM(message, "link_fail"))
            return
        await finish_recognition(update, status, mp3)
        return
    title = meta["title"] if meta else "Video"
    token = uuid.uuid4().hex[:8]
    rows = []
    try:
        mp3 = await asyncio.to_thread(file_to_mp3, mp4, workdir)
        LINK_AUD[token] = {"mp3": mp3, "ts": time.time()}
        rows.append([InlineKeyboardButton(T(lang_of(message.chat_id), "btn_recog"), callback_data=f"r:{token}"),
                     InlineKeyboardButton("ℹ️ Info", url=f"https://song.link/y/{vid}")])
    except Exception as exc:
        log.info("link audio extract failed: %s", exc)
        rows.append([InlineKeyboardButton("ℹ️ Info", url=f"https://song.link/y/{vid}")])
    try:
        with open(mp4, "rb") as f:
            await update.message.reply_video(
                video=f,
                caption=f"🎬 {title}\n🔗 Source: https://youtu.be/{vid}"[:1024],
                duration=meta.get("seconds") if meta else None,
                supports_streaming=True,
                reply_markup=InlineKeyboardMarkup(rows),
                write_timeout=300, read_timeout=300,
            )
        await status.delete()
    except Exception as exc:
        log.warning("send yt video failed: %s", exc)
        await status.edit_text(TM(message, "send_fail"))


async def handle_other_link(update: Update, text):
    message = update.message
    _janitor()
    status = await message.reply_text(TM(message, "dl_wait"))
    workdir = f"/tmp/ln_{uuid.uuid4().hex[:8]}"
    os.makedirs(workdir, exist_ok=True)
    try:
        mp4 = await asyncio.to_thread(download_video_link, text, workdir)
    except Exception as exc:
        log.info("link video download failed: %s", exc)
        mp4 = None
    if mp4 and os.path.getsize(mp4) > MAX_VIDEO_BYTES:
        mp4 = None
    if not mp4:
        await status.edit_text(TM(message, "fallback_audio"))
        out = os.path.join(workdir, "a.%(ext)s")
        def _dl():
            import yt_dlp
            opts = {"quiet": True, "format": "bestaudio/best", "outtmpl": out,
                    "ffmpeg_location": FFMPEG,
                    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]}
            with yt_dlp.YoutubeDL(opts) as y:
                y.download([text])
            p = os.path.join(workdir, "a.mp3")
            return p if os.path.exists(p) else None
        try:
            mp3 = await asyncio.to_thread(_dl)
        except Exception as exc:
            log.info("link download failed: %s", exc)
            mp3 = None
        if not mp3:
            await status.edit_text(TM(message, "link_fail"))
            return
        await finish_recognition(update, status, mp3)
        return
    token = uuid.uuid4().hex[:8]
    rows = []
    try:
        mp3 = await asyncio.to_thread(file_to_mp3, mp4, workdir)
        LINK_AUD[token] = {"mp3": mp3, "ts": time.time()}
        rows.append([InlineKeyboardButton(T(lang_of(message.chat_id), "btn_recog"), callback_data=f"r:{token}")])
    except Exception as exc:
        log.info("link audio extract failed: %s", exc)
    try:
        with open(mp4, "rb") as f:
            await update.message.reply_video(
                video=f,
                caption=f"🔗 Source: {text}"[:1024],
                supports_streaming=True,
                reply_markup=InlineKeyboardMarkup(rows) if rows else None,
                write_timeout=300, read_timeout=300,
            )
        await status.delete()
    except Exception as exc:
        log.warning("send link video failed: %s", exc)
        await status.edit_text(TM(message, "send_fail"))


async def finish_recognition_msg(message, status, mp3_path):
    try:
        rec = await recognize_file(mp3_path)
    except Exception as exc:
        log.info("recognize failed: %s", exc)
        rec = None
    if not rec:
        await status.edit_text(TM(message, "recog_fail"))
        return
    title, artist = rec["title"], rec["artist"]
    await status.edit_text(f"🎵 {title} — {artist}",
                           reply_markup=card_keyboard(title, artist))
    q = f"{title} {artist}".strip()
    results = await asyncio.to_thread(yt_search, q)
    if results:
        await send_song(message, results[0]["vid"], None)


async def finish_recognition(update: Update, status, mp3_path):
    await finish_recognition_msg(update.message, status, mp3_path)


async def on_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    fileobj = msg.voice or msg.audio or msg.video or msg.video_note or msg.document
    if not fileobj:
        return
    status = await msg.reply_text(TM(msg, "listening"))
    try:
        tgfile = await context.bot.get_file(fileobj.file_id)
        data = await tgfile.download_as_bytearray()
    except Exception as exc:
        log.info("tg download failed: %s", exc)
        await status.edit_text(TM(msg, "tg_dl_fail"))
        return
    workdir = f"/tmp/md_{uuid.uuid4().hex[:8]}"
    os.makedirs(workdir, exist_ok=True)
    try:
        mp3 = await asyncio.to_thread(bytes_to_mp3, bytes(data), workdir)
    except Exception as exc:
        log.info("convert failed: %s", exc)
        await status.edit_text(TM(msg, "convert_fail"))
        return
    await finish_recognition(update, status, mp3)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""
    lang = lang_of(q.from_user.id)
    try:
        if data == "langmenu":
            await q.answer()
            await q.message.reply_text(T(lang, "pick_lang"), reply_markup=lang_keyboard())
        elif data.startswith("lang:"):
            code = data[5:]
            if code in dict(LANGS):
                ULANG[q.from_user.id] = code
                _save_langs()
                lang = code
            await q.answer()
            try:
                await q.message.edit_text(T(lang, "lang_set"))
            except Exception:
                pass
            await q.message.reply_text(T(lang, "welcome"),
                                       reply_markup=InlineKeyboardMarkup([lang_btn(lang)]))
        elif data == "x":
            await q.answer()
            await q.message.delete()
        elif data.startswith("p:"):
            _, token, page = data.split(":")
            sess = SESSIONS.get(token)
            if not sess:
                await q.answer(T(lang, "old_search"), show_alert=True)
                return
            results = await asyncio.to_thread(yt_search, sess["query"], int(page))
            if not results:
                await q.answer(T(lang, "no_more"), show_alert=True)
                return
            await q.answer()
            await q.message.edit_reply_markup(
                reply_markup=search_keyboard(sess["query"], int(page), results, lang))
        elif data.startswith("d:"):
            await q.answer()
            await send_song(q.message, data[2:], context)
        elif data.startswith("v:"):
            await q.answer()
            await send_video_file(q.message, data[2:])
        elif data.startswith("r:"):
            await q.answer()
            entry = LINK_AUD.get(data[2:])
            if not entry or not os.path.exists(entry["mp3"]):
                await q.message.reply_text(T(lang, "old_audio"))
                return
            rstatus = await q.message.reply_text(T(lang, "listening"))
            await finish_recognition_msg(q.message, rstatus, entry["mp3"])
        elif data.startswith("l:"):
            await q.answer()
            await q.message.reply_text(T(lang, "lyrics_search"))
            meta = await asyncio.to_thread(video_meta, data[2:])
            if not meta:
                await q.message.reply_text(T(lang, "lyrics_none"))
                return
            lyrics = await asyncio.to_thread(get_lyrics, meta["channel"], meta["title"], VID_QUERY.get(data[2:]))
            if not lyrics:
                await q.message.reply_text(T(lang, "lyrics_none"))
                return
            for i in range(0, len(lyrics), 4000):
                await q.message.reply_text(lyrics[i:i + 4000])
    except Exception as exc:
        log.warning("callback %s failed: %s", data, exc)


# ---------- health server / main ----------

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def run_http():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


def main():
    app = (ApplicationBuilder().token(TOKEN)
           .read_timeout(300).write_timeout(300).connect_timeout(60)
           .media_write_timeout(300).concurrent_updates(True).build())
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("language", lang_cmd))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO | filters.VIDEO | filters.VIDEO_NOTE | filters.ATTACHMENT,
        on_media))
    base = os.environ.get("RENDER_EXTERNAL_URL", "https://gana-finder-bot.onrender.com").rstrip("/")
    path = "tg-" + TOKEN.split(":")[-1][:24].replace("_", "x").replace("-", "y")
    port = int(os.environ.get("PORT", "10000"))
    log.info("bot starting (webhook, wakes sleeping server)")
    app.run_webhook(listen="0.0.0.0", port=port, url_path=path,
                    webhook_url=base + "/" + path,
                    drop_pending_updates=False,
                    allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
