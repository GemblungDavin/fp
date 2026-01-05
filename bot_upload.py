import os
import json
import sys
import requests
import yt_dlp
import time

# Konfigurasi File
SOURCE_FILE = 'videos.txt'
LOG_FILE = 'processed_log.txt'
VIDEO_FILENAME = 'ready_to_upload.mp4'

def get_last_video_url():
    """Membaca file dan mengambil 1 URL paling bawah"""
    if not os.path.exists(SOURCE_FILE):
        return None, []

    with open(SOURCE_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return None, []

    target_url = lines[-1]      # Ambil paling bawah
    remaining_lines = lines[:-1] # Sisanya
    return target_url, remaining_lines

def update_database(remaining_lines):
    """Menulis ulang file txt setelah 1 video berhasil diproses"""
    with open(SOURCE_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(remaining_lines))

def download_video(url):
    print(f"\n⬇️ Sedang mendownload: {url}")
    
    # Hapus file sisa sebelumnya
    if os.path.exists(VIDEO_FILENAME):
        os.remove(VIDEO_FILENAME)

    ydl_opts = {
        # Tetap gunakan 720p agar file ringan & upload sukses
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
            return False, None, None
            
        return True, video_title, video_desc

    except Exception as e:
        print(f"❌ Gagal Download: {e}")
        return False, None, None

def upload_to_specific_page(page_config, title, description):
    """Upload ke halaman spesifik"""
    if not os.path.exists(VIDEO_FILENAME):
        return False

    page_id = page_config.get('page_id')
    access_token = page_config.get('access_token')
    page_name = page_config.get('name', page_id)
    
    print(f"🚀 Mengupload ke Halaman: {page_name} ...")

    url = f"https://graph-video.facebook.com/v19.0/{page_id}/videos"
    
    params = {
        'access_token': access_token,
        'description': f"{title}\n\n{description}\n\n#viral #video #reels",
        'title': title,
        'published': 'true', # Paksa publish agar tidak masuk draft
    }
    
    try:
        with open(VIDEO_FILENAME, 'rb') as video_file:
            files = {'source': video_file}
            s = requests.Session()
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
        print(f"🔥 Bot siap! Akan memproses {len(pages_config)} halaman sekaligus.")
    except:
        print("❌ JSON Config Error.")
        sys.exit(1)

    # 2. LOOPING SEMUA HALAMAN
    for i, page in enumerate(pages_config):
        print(f"\n--- 🔄 MEMPROSES HALAMAN KE-{i+1}: {page.get('name', 'Unknown')} ---")
        
        # A. Cek Stok Video
        target_url, remaining_lines = get_last_video_url()
        
        if not target_url:
            print("🏁 Stok video di videos.txt HABIS! Bot berhenti.")
            break # Keluar dari loop jika video habis

        # B. Download
        dl_success, title, desc = download_video(target_url)

        if dl_success:
            # C. Upload ke Halaman Terkait
            up_success = upload_to_specific_page(page, title, desc)
            
            if up_success:
                # D. JIKA SUKSES: Hapus baris dari file & Lanjut ke halaman berikutnya
                update_database(remaining_lines)
                
                log_msg = f"DONE: {target_url} -> {page.get('name')} | {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                with open(LOG_FILE, 'a', encoding='utf-8') as f:
                    f.write(log_msg)
                
                print(f"🎉 Video berhasil diproses. Sisa antrian: {len(remaining_lines)}")
                
                # Jeda istirahat agar tidak dianggap SPAM oleh Facebook
                if i < len(pages_config) - 1:
                    print("⏳ Istirahat 30 detik sebelum lanjut ke halaman berikutnya...")
                    time.sleep(30) 
            else:
                # E. JIKA GAGAL UPLOAD: Berhenti (Sesuai permintaan 'lanjut jika sukses')
                print("⚠️ Gagal upload ke halaman ini. Menghentikan proses berantai untuk sesi ini.")
                break 
        else:
            # Jika download gagal, biasanya URL rusak. Hapus saja atau stop?
            # Di sini kita stop untuk keamanan.
            print("⚠️ Gagal download video. Menghentikan sesi.")
            break
            
        # Bersihkan file temp sebelum lanjut
        if os.path.exists(VIDEO_FILENAME):
            os.remove(VIDEO_FILENAME)

if __name__ == "__main__":
    main()
