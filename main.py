import os
import time
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# .env faylı varsa yüklə
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
import chromedriver_autoinstaller

# ========================
# KONFİQURASİYA
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

TRACKED_COLUMNS = {
    "SDF1": 7,
    "SDF2": 8,
    "SEM": 9,
    "TSI": 10
}

# ========================
# EMAIL FUNKSİYASI
# ========================
def send_email(subject, body):
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
            print(f"📧 E-mail {len(EMAIL_TO_LIST)} alıcıya göndərildi!")
    except Exception as e:
        print("❌ E-mail göndərilə bilmədi:", e)

# ========================
# Qiymətləri çəkmək
# ========================
def fetch_grades():
    # ChromeDriver avtomatik quraşdırılır
    chromedriver_autoinstaller.install()

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--window-size=1920,1080")

    # Binary paths (Railway və Docker üçün)
    possible_paths = [
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
        "/app/.apt/usr/bin/chromium-browser",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            options.binary_location = path
            break

    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        raise Exception(f"ChromeDriver-i başlada bilmədi: {e}")

    driver.get(LOGIN_URL)

    # LOGIN
    driver.find_element(By.NAME, "username").send_keys(USERNAME)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)

    # GRADES SƏHİFƏSİNƏ KEÇİŞ
    driver.get(GRADES_URL)
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.box"))
        )
        print("✅ Hesaba uğurla giriş edildi")
    except:
        driver.quit()
        raise Exception("❌ Qiymət cədvəli tapılmadı.")

    table_html = driver.execute_script("return document.querySelector('table.table.box').outerHTML;")
    driver.quit()

    soup = BeautifulSoup(table_html, "html.parser")
    rows = soup.find_all("tr")[1:]
    grades = []

    required_cols = max(TRACKED_COLUMNS.values()) + 1

    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cols) < required_cols or "Cəmi akts" in cols[0]:
            continue

        grade_data = {"ders_kodu": cols[0], "ders_adi": cols[4]}
        for col_name, index in TRACKED_COLUMNS.items():
            grade_data[col_name.lower()] = cols[index] or None
        grades.append(grade_data)

    return grades

# ========================
# Fayldan oxu / yaz
# ========================
def load_previous_grades():
    if not os.path.exists(STORED_FILE):
        return []
    try:
        with open(STORED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ Köhnə fayl zədələnib.")
        return []

def save_grades(grades):
    with open(STORED_FILE, "w", encoding="utf-8") as f:
        json.dump(grades, f, ensure_ascii=False, indent=2)

# ========================
# Müqayisə və xəbər
# ========================
def compare_and_notify(old, new):
    changes_detected = False
    old_dict = {item['ders_kodu']: item for item in old}
    for n in new:
        o = old_dict.get(n['ders_kodu'])
        if not o:
            continue

        body_msg = ""
        for col_name in TRACKED_COLUMNS.keys():
            key = col_name.lower()
            old_val_clean = o.get(key) or ""
            new_val_clean = n.get(key) or ""
            if old_val_clean != new_val_clean:
                changes_detected = True
                body_msg += f"Dəyişiklik aşkar edildi: **{col_name}**\nDərs: {n['ders_adi']} ({n['ders_kodu']})\n"

        if body_msg:
            send_email(f"📢 YENİ DƏYİŞİKLİK: {n['ders_adi']}", body_msg)

    if not changes_detected:
        print("🔄 Dəyişiklik yoxdur.")

# ========================
# MAIN LOOP
# ========================
if __name__ == "__main__":
    if not (USERNAME and PASSWORD and EMAIL_FROM and EMAIL_PASS and EMAIL_TO_LIST):
        print("FATAL XƏTA: Bütün mühit dəyişənlərini təyin edin!")
        exit(1)

    while True:
        start_time = time.time()
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 🔑 Qiymətlər yoxlanılır...")
            current = fetch_grades()
            previous = load_previous_grades()
            if not previous:
                print("ℹ️ İlk yoxlama icra edildi. Qiymətlər fayla saxlanılır.")
            else:
                compare_and_notify(previous, current)
            save_grades(current)
        except Exception as e:
            print(f"❌ Əsas dövrdə xəta baş verdi: {e}")
            if EMAIL_FROM and EMAIL_PASS and EMAIL_TO_LIST:
                send_email("KRİTİK XƏTA: Qiymət İzləyicisi", f"Xəta: {e}")

        elapsed_time = time.time() - start_time
        sleep_duration = max(0, 60 - elapsed_time)
        print(f"⏸️ {int(sleep_duration)} saniyə gözlənilir...")
        time.sleep(sleep_duration)
