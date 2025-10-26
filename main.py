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
# main.py faylinda olmalidir

# ... diger importlar ...
# DRIVER_PATH-a ehtiyac qalmir, onu silin

def fetch_grades():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    
    # -------------------------------------------------------------
    # CHROMIUM BİNARY YOLUNU MƏCBUR ET (RAILWAY ÜÇÜN YALNIZ ŞANS)
    # -------------------------------------------------------------
    
    # Railway'in qurasdirdigi 'chromium' brauzerinin ehtimal olunan yolu
    CHROME_BINARY_PATH = "/usr/bin/chromium" 
    
    # Eger brauzer tapilsa, Selenium-a yolunu gosterir
    if os.path.exists(CHROME_BINARY_PATH):
        options.binary_location = CHROME_BINARY_PATH
    else:
        # Brauzer tapilmasa, xeta atiriq
        raise Exception(f"❌ Chromium Brauzeri ({CHROME_BINARY_PATH}) tapilmadi. Railway build xetasi.")

    try:
        # SERVICE obyektini istifade etmeden, driveri birbasa ise saliriq.
        # Options-da binary location teyin edildiyi ucun, Selenium ozu driver axtarmalidir.
        driver = webdriver.Chrome(options=options)
        
    except Exception as e:
        # Mesajin icinde 'wrong permissions' yoxdursa, bu yaxsi isaredir.
        raise Exception(f"❌ Brauzer/Driver Baslatma Xetasi: {e}. Platforma problemi davam edir.")
        
    # -------------------------------------------------------------
    # Qalan hissə eyni qalır
    # -------------------------------------------------------------
    
    driver.get(LOGIN_URL)
    
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

    # ... (Qalan kod eyni qalır)
    table_html = driver.execute_script("return document.querySelector('table.table.box').outerHTML;")
    driver.quit()
    
    # ... (Qalan kod eyni qalır)
    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")[1:]
    grades = []
    required_cols = max(TRACKED_COLUMNS.values()) + 1
    # ... (qiymetlerin cixarilmasi kodu)
    
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