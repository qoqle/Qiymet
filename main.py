import os
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# LOKAL TEST ÜÇÜN: .env faylını oxuyur (Serverdə lazım deyil)
try:
    from dotenv import load_dotenv 
    load_dotenv() 
except ImportError:
    pass 

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# ========================
# KONFİQURASİYA VƏ MƏLUMATLAR
# ========================
USERNAME = os.environ.get("BEU_USERNAME")
PASSWORD = os.environ.get("BEU_PASSWORD")
EMAIL_FROM = os.environ.get("GMAIL_USER")
EMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_TO_STRING = os.environ.get("RECIPIENTS", "")
EMAIL_TO_LIST = [addr.strip() for addr in EMAIL_TO_STRING.split(',') if addr.strip()]

LOGIN_URL = "https://my.beu.edu.az/?mod=login"
GRADES_URL = "https://my.beu.edu.az/?mod=grades"
STORED_FILE = "grades.json" 

# Linux chromedriver faylının repozitoriyada gözlənilən yeri
DRIVER_PATH = os.path.join(os.getcwd(), 'bin', 'chromedriver')

TRACKED_COLUMNS = {
    "SDF1": 7,  # Semestr daxili fəaliyyət 1
    "SDF2": 8,  # Semestr daxili fəaliyyət 2
    "SEM": 9,   # Seminar (Məşğələ) balı
    "TSI": 10   # Tələbənin Sərbəst İşi balı
}

# ========================
# EMAIL FUNKSİYASI (Dəyişməyib)
# ========================
def send_email(subject, body):
    # ... (Əvvəlki kod eyni qalır)
    if not EMAIL_TO_LIST:
        print("❌ E-mail göndərilmədi: Alıcı siyahısı boşdur.")
        return
        
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = ", ".join(EMAIL_TO_LIST)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASS)
            server.sendmail(EMAIL_FROM, EMAIL_TO_LIST, msg.as_string()) 
            print(f"📧 E-mail {len(EMAIL_TO_LIST)} alıcıya uğurla göndərildi!")
    except Exception as e:
        print("❌ E-mail göndərilə bilmədi. Gmail App Şifrəsini və ya icazələri yoxlayın:", e)


# ========================
# Qiymətləri çəkmək (Əsas Dəyişiklik)
# ========================
def fetch_grades():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    
    # -------------------------------------------------------------
    # Sürücünün yolu birbaşa repozitoriyadakı fayla göstərilir
    # -------------------------------------------------------------
    if not os.path.exists(DRIVER_PATH):
        # Fayl tapılmazsa, kritik xəta verilir
        raise FileNotFoundError(f"❌ DRIVER_PATH: {DRIVER_PATH} yolunda 'chromedriver' faylı tapılmadı. Zəhmət olmasa, repozitoriyanı yoxlayın.")

    # Sürücünü yerli fayldan işə salırıq
    service = Service(executable_path=DRIVER_PATH)

    try:
        # Brauzer sürücüsü aktivləşdirilir
        driver = webdriver.Chrome(service=service, options=options)
        
    except Exception as e:
        # Sürücü işə düşməzdirsə, xəta atırıq (məsələn, icra icazəsi yoxdur)
        raise Exception(f"❌ ChromeDriver-i başlada bilmədi: {e}. Zəhmət olmasa, Render.com quraşdırmasını və icazələri yoxlayın.")
        
    # -------------------------------------------------------------
    # Qalan hissə eyni qalır
    # -------------------------------------------------------------
    
    driver.get(LOGIN_URL)
    
    # LOGIN
    # ... (Giriş kodu eyni qalır)
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)

    # GRADES SƏHİFƏSİNƏ KEÇİŞ
    driver.get(GRADES_URL)

    try:
        # Gözləmə müddəti 30 saniyə (yavaş yükləmə üçün)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.box"))
        )
        print("✅ Hesaba uğurla giriş edildi")
    except:
        driver.quit()
        raise Exception("❌ Qiymət cədvəli tapılmadı. Giriş uğursuz ola bilər.")

    table_html = driver.execute_script("return document.querySelector('table.table.box').outerHTML;")
    driver.quit()

    # ... (HTML analizi və qiymət çıxarılması kodu eyni qalır)
    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")[1:]
    grades = []
    required_cols = max(TRACKED_COLUMNS.values()) + 1
    
    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        
        if len(cols) < required_cols or "Cəmi akts" in cols[0]:
            continue
            
        grade_data = {}
        grade_data["ders_kodu"] = cols[0]
        grade_data["ders_adi"] = cols[4]
        
        for col_name, index in TRACKED_COLUMNS.items():
            key = col_name.lower() 
            grade_data[key] = cols[index] or None
            
        grades.append(grade_data)
        
    return grades


# ========================
# MAIN LOOP (Dəyişməyib)
# ========================
if __name__ == "__main__":
    
    if not (USERNAME and PASSWORD and EMAIL_FROM and EMAIL_PASS and EMAIL_TO_LIST):
        print("FATAL XƏTA: Zəhmət olmasa bütün mühit dəyişənlərini təyin edin.")
        exit(1)

    while True: 
        start_time = time.time()
        
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🔑 Qiymətlər yoxlanılır...")
            current = fetch_grades()
            previous = load_previous_grades() # ... (bu və digər funksiyalar buradadır)
            
            if not previous:
                print("ℹ️ İlk yoxlama icra edildi. Qiymətlər fayla saxlanılır.")
            else:
                compare_and_notify(previous, current)
            
            save_grades(current)
            
        except Exception as e:
            print(f"❌ Əsas dövrdə xəta baş verdi: {e}")
            if EMAIL_FROM and EMAIL_PASS and EMAIL_TO_LIST:
                 send_email("KRİTİK XƏTA: Qiymət İzləyicisi", f"Qiymət çəkilməsi zamanı xəta: {e}")
            
        elapsed_time = time.time() - start_time
        sleep_duration = max(0, 60 - elapsed_time)
        
        print(f"⏸️ {int(sleep_duration)} saniyə gözlənilir...")
        time.sleep(sleep_duration)