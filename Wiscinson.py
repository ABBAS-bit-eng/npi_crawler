import os, time, csv
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

URL = "https://license.wi.gov/s/license-lookup"
OUT = "wisconsin_health_active_links.csv"

PROFESSIONS = [
    "Acupuncturist","Advanced Practice Nurse Prescriber","Anesthesiologist Assistant",
    "Art Therapist","Athletic Trainer","Audiologist","Behavior Analyst","Body Piercer",
    "Chiropractic Radiological Technician","Chiropractic Technician","Chiropractor",
    "Clinical Substance Abuse Counselor","Clinical Supervisor In-Training",
    "Clinical Supervisor, Independent","Clinical Supervisor, Intermediate",
    "Controlled Substances Special Use Authorization",
    "Controlled Substances Special Use Authorization - Analytical Laboratory (450)",
    "Dance Therapist","Dental Hygienist","Dental Therapist","Dentist","Dietitian",
    "Expanded Function Dental Auxiliary","Genetic Counselor","Hearing Instrument Specialist",
    "Licensed Practical Nurse","Licensed Professional Counselor",
    "Limited X-Ray Machine Operator Permit","Limited-Scope Naturopathic Doctor",
    "Marriage and Family Therapist","Marriage and Family Therapist Training License",
    "Massage Therapist or Bodywork Therapist","Medicine and Surgery - DO",
    "Medicine and Surgery - MD","Midwives, Licensed","Music Therapist",
    "Naturopathic Doctor","Nurse - Midwife","Occupational Therapist",
    "Occupational Therapy Assistant","Optometrist","Perfusionist","Pharmacist",
    "Pharmacy Technician","Physical Therapist","Physical Therapist Assistant",
    "Physician - DO","Physician - DO Compact","Physician - MD","Physician - MD Compact",
    "Physician Assistant","Podiatrist","Prevention Specialist","Prevention Specialist In-Training",
    "Professional Counselor Training License","Provisional Physician Licensure","Psychologist",
    "Radiographer, Licensed","Registered Nurse","Registered Sanitarian",
    "Resident Educational License","Respiratory Care Practitioner",
    "Sign Language Interpreter - Advanced Deaf","Sign Language Interpreter - Advanced Hearing",
    "Sign Language Interpreter - Intermediate Deaf","Sign Language Interpreter - Intermediate Hearing",
    "Social Worker","Social Worker - Advanced Practice","Social Worker - Independent",
    "Social Worker - Licensed Clinical","Social Worker - Training Certificate",
    "Speech-Language Pathologist","Substance Abuse Counselor",
    "Substance Abuse Counselor In-Training","Tattooist",
]

W = None  # global driver

def jclick(el):
    W.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.3)
    W.execute_script("arguments[0].click();", el)

def wait_table():
    try:
        WebDriverWait(W, 40).until(lambda d:
            d.find_elements(By.XPATH, "//table//tbody/tr") or
            d.find_elements(By.XPATH, "//*[contains(text(),'No results') or contains(text(),'No records')]"))
    except TimeoutException: pass
    time.sleep(1)

def open_combo(label):
    for xp in [
        f"//button[@role='combobox' and @aria-label='{label}']",
        f"//button[@aria-haspopup='listbox' and @aria-label='{label}']",
        f"//label[normalize-space()='{label}']/following::button[@aria-haspopup='listbox'][1]",
        f"//*[normalize-space(text())='{label}']/ancestor::*[contains(@class,'slds-form-element')]//button[@aria-haspopup='listbox']",
    ]:
        try:
            btn = WebDriverWait(W, 20).until(EC.element_to_be_clickable((By.XPATH, xp)))
            jclick(btn); return
        except TimeoutException: continue
    raise TimeoutException(f"Combobox not found: {label}")

def pick(text):
    try: WebDriverWait(W, 15).until(lambda d: d.find_elements(By.XPATH, "//*[@role='option']"))
    except TimeoutException: pass
    time.sleep(0.5)
    for xp in [
        f"//*[@role='option']//*[@title='{text}']",
        f"//*[@role='option']//*[normalize-space()='{text}']",
        f"//*[@role='option' and normalize-space()='{text}']",
        f"//*[contains(@class,'slds-listbox__option')]//*[@title='{text}']",
        f"//lightning-base-combobox-item[.//*[@title='{text}']]",
        f"//lightning-base-combobox-item[.//*[normalize-space()='{text}']]",
    ]:
        try:
            jclick(WebDriverWait(W, 8).until(EC.element_to_be_clickable((By.XPATH, xp))))
            time.sleep(0.7); return
        except TimeoutException: continue
    with open(f"debug_{text[:20].replace(' ','_')}.html","w",encoding="utf-8") as f: f.write(W.page_source)
    raise TimeoutException(f"Option not found: {text}")

def combo(label, text):
    open_combo(label); pick(text)

def search():
    jclick(WebDriverWait(W, 30).until(EC.element_to_be_clickable(
        (By.XPATH, '//button[contains(@class,"slds-button_brand") and contains(.,"Search")]'))))
    time.sleep(3)

def get_rows(prof):
    rows = []
    for row in W.find_elements(By.XPATH, "//table//tbody/tr"):
        try: txt = row.text.strip()
        except StaleElementReferenceException: continue
        if ("Wisconsin" not in txt and "WI" not in txt) or "Active" not in txt: continue
        href = ""
        for xp in (".//a[contains(@href,'/s/') or contains(@href,'license')]", ".//lightning-formatted-url//a"):
            try:
                href = row.find_element(By.XPATH, xp).get_attribute("href") or ""
                if href: break
            except NoSuchElementException: continue
        rows.append({"profession": prof, "link": urljoin(URL, href) if href else "", "row_text": txt})
    return rows

def total_pages():
    try:
        sel = W.find_element(By.XPATH, "//select[contains(@class,'page-selector')]")
        return len(sel.find_elements(By.TAG_NAME, "option"))
    except NoSuchElementException: return 1

def goto_page(n):
    try:
        sel = WebDriverWait(W, 10).until(EC.presence_of_element_located(
            (By.XPATH, "//select[contains(@class,'page-selector')]")))
        Select(sel).select_by_value(str(n)); time.sleep(3); wait_table(); return True
    except (TimeoutException, NoSuchElementException): return False

def scrape(prof):
    wait_table()
    if W.find_elements(By.XPATH, "//*[contains(text(),'No results') or contains(text(),'No records')]"):
        return []
    pages, collected, seen = total_pages(), [], set()
    for p in range(1, pages + 1):
        if p > 1 and not goto_page(p): break
        wait_table()
        for item in get_rows(prof):
            k = item["link"] or item["row_text"]
            if k not in seen: seen.add(k); collected.append(item)
        print(f"  p{p}/{pages} | {len(collected)} total")
    return collected

def save(rows):
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["profession","link","row_text"])
        w.writeheader(); w.writerows(rows)

def main():
    global W
    lock = os.path.join(os.path.expanduser("~"), ".wdm", ".wdm-lock-chromedriver-win64")
    if os.path.exists(lock):
        try: os.remove(lock)
        except OSError: pass

    W = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=webdriver.ChromeOptions())
    W.maximize_window()
    all_rows = []

    try:
        W.get(URL)
        WebDriverWait(W, 40).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(8)
        WebDriverWait(W, 40).until(EC.presence_of_element_located((By.XPATH, "//button[@role='combobox']")))
        time.sleep(2)

        combo("Search By", "Individual Name"); time.sleep(1)
        combo("Category", "Health"); time.sleep(1)

        for prof in PROFESSIONS:
            print(f"\n--- {prof} ---")
            try:
                combo("Professions", prof); time.sleep(0.5)
                search()
                rows = scrape(prof)
                all_rows.extend(rows); save(all_rows)
                print(f"  {len(rows)} found | {len(all_rows)} total")
            except Exception as e:
                print(f"  ERROR: {e}")
                with open(f"debug_err_{prof[:15].replace(' ','_')}.html","w",encoding="utf-8") as f: f.write(W.page_source)
    finally:
        save(all_rows); W.quit()

    print(f"\nDone. {len(all_rows)} records → {OUT}")

if __name__ == "__main__":
    main()
