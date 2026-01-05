import os
import json
import sys
import requests
import yt_dlp
import subprocess
import time

# Nama file database
SOURCE_FILE = 'videos.txt'
LOG_FILE = 'processed_log.txt'
VIDEO_FILENAME = 'downloaded_video.mp4'
FINAL_FILENAME = 'ready_to_upload.mp4'

def get_last_video_url():
    """Mengambil satu URL dari baris paling bawah"""
    if not os.path.exists(SOURCE_FILE):
        print(f"❌ File {SOURCE_FILE} tidak ditemukan!")
        return None, []

    with open(SOURCE_FILE, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return None, []

    target_url = lines[-1] # Ambil paling bawah
    remaining_lines = lines[:-1] # Sisa data
    return target_url, remaining_lines

def download_and_process(url):
    print(f"⬇️ Sedang mendownload: {url}")
    
    # 1. Download Video
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': 'temp_video.%(ext)s',
        'quiet': True,
    }
    
    video_title = "Video Menarik Hari Ini" # Default title
    video_desc = "Tonton video seru ini sampai habis!" # Default desc
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', video_title)
            video_desc = info.get('description', video_desc)[:400] + "..." # Potong jika kepanjangan
            
            # Rename file hasil download ke nama standar
            downloaded = ydl.prepare_filename(info)
            if os.path.exists(downloaded):
                os.rename(downloaded, VIDEO_FILENAME)
            else:
                # Fallback untuk jaga-jaga format nama file
                for f in os.listdir('.'):
                    if f.startswith('temp_video'):
                        os.rename(f, VIDEO_FILENAME)
                        break

        # 2. Render Ulang (FFmpeg) untuk hash baru
        # Mengubah metadata dan sedikit re-encode audio agar dianggap file baru
        print("🔄 Melakukan Render Ulang (Fresh Hash)...")
        cmd = [
            'ffmpeg', '-y', '-i', VIDEO_FILENAME,
            '-c:v', 'copy', # Copy video stream (cepat)
            '-c:a', 'aac',  # Re-encode audio (membuat hash file berubah)
            '-metadata', 'creation_time=now',
            FINAL_FILENAME
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return True, video_title, video_desc

    except Exception as e:
        print(f"❌ Gagal Download/Render: {e}")
        return False, None, None

def upload_to_facebook(pages_config, title, description):
    if not os.path.exists(FINAL_FILENAME):
        print("❌ File video tidak ditemukan untuk diupload.")
        return

    file_size = os.path.getsize(FINAL_FILENAME)
    print(f"🚀 Memulai Upload ke {len(pages_config)} Halaman Facebook...")

    for page in pages_config:
        page_id = page.get('page_id')
        access_token = page.get('access_token')
        
        if not page_id or not access_token:
            continue

        url = f"https://graph-video.facebook.com/v18.0/{page_id}/videos"
        
        # Setup Payload
        params = {
            'access_token': access_token,
            'description': f"{title}\n\n{description}\n\n#viral #video",
            'title': title,
        }
        
        # Upload
        try:
            with open(FINAL_FILENAME, 'rb') as video_file:
                files = {'source': video_file}
                print(f"   📤 Mengupload ke Page ID: {page_id} ...")
                r = requests.post(url, params=params, files=files, timeout=300)
                
            if r.status_code == 200:
                print(f"   ✅ Berhasil! Video ID: {r.json().get('id')}")
            else:
                print(f"   ⚠️ Gagal: {r.text}")
                
        except Exception as e:
            print(f"   ❌ Error koneksi: {e}")

def main():
    # Load Config
    config_json = os.environ.get('FB_PAGES_CONFIG')
    if not config_json:
        print("❌ Secret FB_PAGES_CONFIG belum diatur di GitHub!")
        sys.exit(1)
    
    try:
        pages_config = json.loads(config_json)
    except:
        print("❌ Format JSON pada Secret salah.")
        sys.exit(1)

    # 1. Cek URL
    target_url, remaining_lines = get_last_video_url()
    
    if not target_url:
        print("🏁 Tidak ada URL tersisa di videos.txt. Bot berhenti.")
        sys.exit(0)

    # 2. Proses Video
    success, title, desc = download_and_process(target_url)

    if success:
        # 3. Upload
        upload_to_facebook(pages_config, title, desc)
        
        # 4. Update Database (Hapus URL yang sudah diproses)
        with open(SOURCE_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(remaining_lines))
        
        # Simpan log history (opsional)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"Processed: {target_url} | Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
        print("🎉 Selesai! URL telah dihapus dari daftar antrian.")
        
        # Bersihkan file sampah
        if os.path.exists(VIDEO_FILENAME): os.remove(VIDEO_FILENAME)
        if os.path.exists(FINAL_FILENAME): os.remove(FINAL_FILENAME)
    else:
        print("❌ Gagal memproses video, URL tidak dihapus (akan dicoba lagi nanti).")
        sys.exit(1)

if __name__ == "__main__":
    main()
      
