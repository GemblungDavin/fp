import os
import json
import sys
import requests
import yt_dlp
import time

# Konfigurasi File
SOURCE_FILE = 'videos.txt'
LOG_FILE = 'processed_log.txt'
VIDEO_FILENAME = 'ready_to_upload.mp4' # Langsung simpan dengan nama final

def get_last_video_url():
    if not os.path.exists(SOURCE_FILE):
        print(f"❌ File {SOURCE_FILE} tidak ditemukan!")
        return None, [], 0

    with open(SOURCE_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return None, [], 0

    target_url = lines[-1]
    remaining_lines = lines[:-1]
    # Kita butuh jumlah sisa antrian untuk menentukan giliran halaman
    queue_count = len(remaining_lines) 
    return target_url, remaining_lines, queue_count

def download_video(url):
    print(f"⬇️ Sedang mendownload (Tanpa Render): {url}")
    
    # Hapus file lama jika ada
    if os.path.exists(VIDEO_FILENAME):
        os.remove(VIDEO_FILENAME)

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': VIDEO_FILENAME, # Langsung ke nama final
        'quiet': True,
        'cookiefile': 'cookies.txt', 
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'nocheckcertificate': True,
    }
    
    video_title = "Video Viral"
    video_desc = "Tonton sampai habis!"
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', video_title)
            raw_desc = info.get('description', '')
            video_desc = raw_desc[:400] + "..." if len(raw_desc) > 400 else raw_desc
            
        if not os.path.exists(VIDEO_FILENAME):
            print("❌ File video tidak ditemukan.")
            return False, None, None
            
        return True, video_title, video_desc

    except Exception as e:
        print(f"❌ Gagal Download: {e}")
        return False, None, None

def upload_to_single_page(page_config, title, description):
    if not os.path.exists(VIDEO_FILENAME):
        return False

    page_id = page_config.get('page_id')
    access_token = page_config.get('access_token')
    page_name = page_config.get('name', page_id)
    
    print(f"🚀 Giliran Upload ke Halaman: {page_name} ...")

    url = f"https://graph-video.facebook.com/v18.0/{page_id}/videos"
    params = {
        'access_token': access_token,
        'description': f"{title}\n\n{description}\n\n#viral #video",
        'title': title,
    }
    
    try:
        with open(VIDEO_FILENAME, 'rb') as video_file:
            files = {'source': video_file}
            r = requests.post(url, params=params, files=files, timeout=300)
            
        if r.status_code == 200:
            print(f"   ✅ SUKSES! Video ID: {r.json().get('id')}")
            return True
        else:
            print(f"   ⚠️ Gagal (Code {r.status_code}): {r.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error koneksi: {e}")
        return False

def main():
    # 1. Load Config
    config_json = os.environ.get('FB_PAGES_CONFIG')
    if not config_json:
        print("❌ Secret FB_PAGES_CONFIG belum diatur!")
        sys.exit(1)
    
    try:
        pages_config = json.loads(config_json)
    except:
        print("❌ JSON Config Error.")
        sys.exit(1)

    # 2. Ambil URL & Tentukan Giliran
    target_url, remaining_lines, queue_count = get_last_video_url()
    
    if not target_url:
        print("🏁 Antrian Habis.")
        sys.exit(0)

    # LOGIKA BERGANTIAN (Round-Robin)
    # Kita pakai sisa jumlah video untuk menentukan index halaman
    # Contoh: Sisa 10 video, Halaman ada 5. Maka 10 % 5 = 0 (Halaman ke-1)
    # Besoknya: Sisa 9 video. Maka 9 % 5 = 4 (Halaman ke-5), dst.
    total_pages = len(pages_config)
    target_page_index = queue_count % total_pages
    selected_page = pages_config[target_page_index]

    # 3. Download
    success, title, desc = download_video(target_url)

    if success:
        # 4. Upload ke SATU Halaman Terpilih
        upload_success = upload_to_single_page(selected_page, title, desc)
        
        if upload_success:
            # Hapus URL dari daftar
            with open(SOURCE_FILE, 'w', encoding='utf-8') as f:
                f.write('\n'.join(remaining_lines))
            
            # Catat Log
            log_msg = f"UPLOADED: {target_url} -> {selected_page.get('name')} | {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(log_msg)
            
            print("🎉 Selesai! URL dihapus.")
        else:
            print("⚠️ Upload Gagal. URL disimpan untuk dicoba lagi.")
            sys.exit(1)
            
        if os.path.exists(VIDEO_FILENAME): os.remove(VIDEO_FILENAME)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
    
