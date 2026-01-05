import os
import json
import sys
import requests
import yt_dlp
import time

# --- KONFIGURASI ---
SOURCE_FILE = 'videos.txt'
LOG_FILE = 'processed_log.txt'
VIDEO_FILENAME = 'ready_to_upload.mp4'
MAX_VIDEO_SIZE_MB = 120  # Batas aman upload (Facebook API limit sekitar 100MB)

def get_last_video_url():
    """Membaca file dan mengambil 1 URL paling bawah"""
    if not os.path.exists(SOURCE_FILE):
        return None, []

    with open(SOURCE_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return None, []

    target_url = lines[-1]       # Ambil paling bawah
    remaining_lines = lines[:-1] # Sisanya
    return target_url, remaining_lines

def remove_failed_url(remaining_lines):
    """Menghapus URL yang gagal/kebesaran agar tidak diambil lagi"""
    with open(SOURCE_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(remaining_lines))

def download_video(url):
    print(f"\n⬇️ Sedang mendownload: {url}")
    
    if os.path.exists(VIDEO_FILENAME):
        os.remove(VIDEO_FILENAME)

    ydl_opts = {
        # Kita set max 720p, tapi kadang durasi panjang tetap bikin file besar
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
        'outtmpl': VIDEO_FILENAME,
        'quiet': True,
        'cookiefile': 'cookies.txt', 
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'nocheckcertificate': True,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
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
            return False, None, None, 0
            
        # Cek ukuran file dalam MB
        file_size_mb = os.path.getsize(VIDEO_FILENAME) / (1024 * 1024)
        print(f"📦 Ukuran File: {file_size_mb:.2f} MB")
        
        return True, video_title, video_desc, file_size_mb

    except Exception as e:
        print(f"❌ Gagal Download: {e}")
        return False, None, None, 0

def upload_to_specific_page(page_config, title, description):
    if not os.path.exists(VIDEO_FILENAME):
        return False

    page_id = page_config.get('page_id')
    access_token = page_config.get('access_token')
    page_name = page_config.get('name', page_id)
    
    print(f"🚀 Mengupload ke Halaman: {page_name} ...")

    url = f"https://graph-video.facebook.com/v19.0/{page_id}/videos"
    
    params = {
        'access_token': access_token,
        'description': f"{title}\n\n{description}\n\n#viral #video",
        'title': title,
        'published': 'true',
    }
    
    try:
        with open(VIDEO_FILENAME, 'rb') as video_file:
            files = {'source': video_file}
            s = requests.Session()
            # Timeout 10 menit
            r = s.post(url, params=params, files=files, timeout=600)
            
        if r.status_code == 200:
            print(f"   ✅ SUKSES TERBIT! Video ID: {r.json().get('id')}")
            return True
        else:
            print(f"   ⚠️ Gagal Upload (Code {r.status_code}): {r.text}")
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
        print(f"🔥 Bot siap! Mode: Skip Video Bermasalah.")
    except:
        print("❌ JSON Config Error.")
        sys.exit(1)

    # 2. LOOP HALAMAN
    for i, page in enumerate(pages_config):
        print(f"\n==================================================")
        print(f"🔄 TARGET HALAMAN KE-{i+1}: {page.get('name', 'Unknown')}")
        print(f"==================================================")
        
        # LOOP RETRY: Terus mencoba video baru SAMPAI berhasil upload di halaman ini
        # atau sampai video habis.
        while True:
            # A. Ambil Video Paling Bawah
            target_url, remaining_lines = get_last_video_url()
            
            if not target_url:
                print("🏁 Stok video di videos.txt HABIS TOTAL! Bot berhenti.")
                sys.exit(0) # Keluar total karena video habis

            # B. Download
            dl_success, title, desc, size_mb = download_video(target_url)

            if dl_success:
                # C. FILTER UKURAN: Cek apakah video terlalu besar?
                if size_mb > MAX_VIDEO_SIZE_MB:
                    print(f"⚠️ Video terlalu besar ({size_mb:.2f} MB > {MAX_VIDEO_SIZE_MB} MB).")
                    print("🗑️ Menghapus video ini dari antrian dan mencoba video berikutnya...")
                    
                    # Hapus URL ini, file video, lalu lanjut loop (continue)
                    remove_failed_url(remaining_lines)
                    if os.path.exists(VIDEO_FILENAME): os.remove(VIDEO_FILENAME)
                    continue 

                # D. Upload
                up_success = upload_to_specific_page(page, title, desc)
                
                if up_success:
                    # SUKSES: Hapus URL, simpan log, dan KELUAR dari loop retry (pindah halaman)
                    remove_failed_url(remaining_lines)
                    
                    log_msg = f"DONE: {target_url} -> {page.get('name')} | Size: {size_mb:.2f}MB | {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    with open(LOG_FILE, 'a', encoding='utf-8') as f:
                        f.write(log_msg)
                    
                    print(f"🎉 Sukses! Lanjut ke halaman berikutnya.")
                    if os.path.exists(VIDEO_FILENAME): os.remove(VIDEO_FILENAME)
                    
                    # Istirahat sebentar sebelum pindah halaman
                    time.sleep(10)
                    break 
                else:
                    # GAGAL UPLOAD (Misal Error API):
                    print("⚠️ Upload gagal (mungkin ditolak FB). Mencoba video berikutnya...")
                    remove_failed_url(remaining_lines)
                    if os.path.exists(VIDEO_FILENAME): os.remove(VIDEO_FILENAME)
                    continue # Loop lagi, ambil video baru untuk halaman yang SAMA

            else:
                # GAGAL DOWNLOAD (URL Rusak):
                print("⚠️ Download gagal. Mencoba video berikutnya...")
                remove_failed_url(remaining_lines)
                continue

if __name__ == "__main__":
    main()
