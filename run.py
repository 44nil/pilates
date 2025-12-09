import os
import time
from app import create_app
from dotenv import load_dotenv  # Bu satırı ekledik

# .env dosyasını zorla yükle
load_dotenv()

app = create_app()

if __name__ == '__main__':
    PORT = 5003
    
    # Sadece ana başlatmada çalışsın (Flask'ın otomatik yenilemesi sırasında çalışmasın)
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        try:
            # Portu kullanan varsa temizle
            os.system(f"lsof -ti:{PORT} | xargs kill -9 2>/dev/null")
            print(f"🧹 Port {PORT} temizlendi, sunucu başlatılıyor...")
            time.sleep(1)  # Portun boşa çıkması için 1 sn bekle
        except Exception as e:
            pass

    app.run(debug=True, port=PORT)