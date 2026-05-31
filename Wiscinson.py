import os
import time
import csv
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

# ── Constants ─────────────────────────────────────────────────────────────────
URL        = "https://license.wi.gov/s/license-lookup"
OUTPUT_CSV = "wisconsin_health_active_links.csv"

PROFESSIONS = [
    "Acupuncturist", "Advanced Practice Nurse Prescriber", "Anesthesiologist Assistant",
    "Art Therapist", "Athletic Trainer", "Audiologist", "Behavior Analyst", "Body Piercer",
    "Chiropractic Radiological Technician", "Chiropractic Technician", "Chiropractor",
    "Clinical Substance Abuse Counselor", "Clinical Supervisor In-Training",
    "Clinical Supervisor, Independent", "Clinical Supervisor, Intermediate",
    "Controlled Substances Special Use Authorization",
    "Controlled Substances Special Use Authorization - Analytical Laboratory (450)",
    "Dance Therapist", "Dental Hygienist", "Dental Therapist", "Dentist", "Dietitian",
    "Expanded Function Dental Auxiliary", "Genetic Counselor", "Hearing Instrument Specialist",
    "Licensed Practical Nurse", "Licensed Professional Counselor",
    "Limited X-Ray Machine Operator Permit", "Limited-Scope Naturopathic Doctor",
    "Marriage and Family Therapist", "Marriage and Family Therapist Training License",
    "Massage Therapist or Bodywork Therapist", "Medicine and Surgery - DO",
    "Medicine and Surgery - MD", "Midwives, Licensed", "Music Therapist",
    "Naturopathic Doctor", "Nurse - Midwife", "Occupational Therapist",
    "Occupational Therapy Assistant", "Optometrist", "Perfusionist", "Pharmacist",
    "Pharmacy Technician", "Physical Therapist", "Physical Therapist Assistant",
    "Physician - DO", "Physician - DO Compact", "Physician - MD", "Physician - MD Compact",
    "Physician Assistant", "Podiatrist", "Prevention Specialist",
    "Prevention Specialist In-Training", "Professional Counselor Training License",
    "Provisional Physician Licensure", "Psychologist", "Radiographer, Licensed",
    "Registered Nurse", "Registered Sanitarian", "Resident Educational License",
    "Respiratory Care Practitioner", "Sign Language Interpreter - Advanced Deaf",
    "Sign Language Interpreter - Advanced Hearing", "Sign Language Interpreter - Intermediate Deaf",
    "Sign Language Interpreter - Intermediate Hearing", "Social Worker",
    "Social Worker - Advanced Practice", "Social Worker - Independent",
    "Social Worker - Licensed Clinical", "Social Worker - Training Certificate",
    "Speech-Language Pathologist", "Substance Abuse Counselor",
    "Substance Abuse Counselor In-Training", "Tattooist",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def clear_wdm_lock():
    """Remove stale webdriver-manager lock file if present."""
    lock_path = os.path.join(os.path.expanduser("~"), ".wdm", ".wdm-lock-chromedriver-win64")
    if os.path.exists(lock_path):
        try:
            os.remove(lock_path)
            print("Cleared stale wdm lock file.")
        except OSError as e:
            print(f"Could not remove lock file: {e}")


def js_click(driver, element):
    """Scroll element into view and click via JavaScript."""
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
    time.sleep(0.3)
    driver.execute_script("arguments[0].click();", element)


def wait_for_table(driver, timeout=40):
    """Wait until results table has rows or a no-results message appears."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: (
                d.find_elements(By.XPATH, "//table//tbody/tr") or
                d.find_elements(By.XPATH, "//*[contains(text(),'No results') or contains(text(),'No records')]")
            )
        )
    except TimeoutException:
        pass
    time.sleep(1)


def save_debug_html(driver, label):
    """Save page source for debugging."""
    filename = f"debug_{label[:30].replace(' ', '_')}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"  Debug HTML saved: {filename}")


# ── Combobox helpers ──────────────────────────────────────────────────────────

def open_combobox(driver, aria_label, timeout=20):
    """Click a Salesforce LWC combobox button by its aria-label."""
    xpaths = [
        f"//button[@role='combobox' and @aria-label='{aria_label}']",
        f"//button[@aria-haspopup='listbox' and @aria-label='{aria_label}']",
        f"//label[normalize-space()='{aria_label}']/following::button[@aria-haspopup='listbox'][1]",
        f"//*[normalize-space(text())='{aria_label}']/ancestor::*[contains(@class,'slds-form-element')]//button[@aria-haspopup='listbox']",
    ]
    for xp in xpaths:
        try:
            btn = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xp)))
            js_click(driver, btn)
            return btn
        except TimeoutException:
            continue
    raise TimeoutException(f"Cannot find combobox: '{aria_label}'")


def pick_option(driver, option_text, timeout=15):
    """Select an option from an open combobox by title or visible text."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.find_elements(By.XPATH, "//*[@role='option']")
        )
    except TimeoutException:
        pass
    time.sleep(0.5)

    xpaths = [
        f"//*[@role='option']//*[@title='{option_text}']",
        f"//*[@role='option']//*[normalize-space()='{option_text}']",
        f"//*[@role='option' and normalize-space()='{option_text}']",
        f"//*[contains(@class,'slds-listbox__option')]//*[@title='{option_text}']",
        f"//*[contains(@class,'slds-listbox__option')]//*[normalize-space()='{option_text}']",
        f"//lightning-base-combobox-item[.//*[@title='{option_text}']]",
        f"//lightning-base-combobox-item[.//*[normalize-space()='{option_text}']]",
    ]
    for xp in xpaths:
        try:
            opt = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.XPATH, xp)))
            js_click(driver, opt)
            print(f"    Selected: '{option_text}'")
            time.sleep(0.7)
            return
        except TimeoutException:
            continue

    save_debug_html(driver, f"option_{option_text}")
    raise TimeoutException(f"Cannot find option '{option_text}'")


def select_combobox(driver, aria_label, option_text):
    """Open a combobox and select an option."""
    print(f"  [{aria_label}] → '{option_text}'")
    open_combobox(driver, aria_label)
    pick_option(driver, option_text)


# ── Search & extraction ───────────────────────────────────────────────────────

def click_search(driver, timeout=30):
    """Click the Search button and wait briefly."""
    btn = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(
            (By.XPATH, '//button[contains(@class,"slds-button_brand") and contains(.,"Search")]')
        )
    )
    js_click(driver, btn)
    time.sleep(3)


def extract_active_rows(driver, profession):
    """
    Extract rows from the results table where state is Wisconsin/WI and status is Active.
    Returns a list of dicts with profession, link, and row_text.
    """
    results = []
    for row in driver.find_elements(By.XPATH, "//table//tbody/tr"):
        try:
            row_text = row.text.strip()
        except StaleElementReferenceException:
            continue

        if ("Wisconsin" not in row_text and "WI" not in row_text) or "Active" not in row_text:
            continue

        href = ""
        for xpath in (
            ".//a[contains(@href,'/s/') or contains(@href,'license')]",
            ".//lightning-formatted-url//a",
        ):
            try:
                href = row.find_element(By.XPATH, xpath).get_attribute("href") or ""
                if href:
                    break
            except NoSuchElementException:
                continue

        results.append({
            "profession": profession,
            "link": urljoin(URL, href) if href else "",
            "row_text": row_text,
        })
    return results


# ── Pagination ────────────────────────────────────────────────────────────────

def get_total_pages(driver):
    """Return total page count from the page-selector dropdown (default 1)."""
    try:
        sel = driver.find_element(By.XPATH, "//select[contains(@class,'page-selector')]")
        return len(sel.find_elements(By.TAG_NAME, "option"))
    except NoSuchElementException:
        return 1


def go_to_page(driver, page_number):
    """Navigate to a specific page via the page-selector dropdown."""
    try:
        sel = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//select[contains(@class,'page-selector')]"))
        )
        Select(sel).select_by_value(str(page_number))
        time.sleep(3)
        wait_for_table(driver)
        return True
    except (TimeoutException, NoSuchElementException):
        return False


# ── Per-profession scrape ─────────────────────────────────────────────────────

def scrape_profession(driver, profession):
    """Scrape all pages for the current search result and return deduplicated rows."""
    collected, seen = [], set()

    wait_for_table(driver)

    if driver.find_elements(By.XPATH, "//*[contains(text(),'No results') or contains(text(),'No records')]"):
        print(f"  No results for: {profession}")
        return collected

    total_pages = get_total_pages(driver)
    print(f"  Pages: {total_pages}")

    for page in range(1, total_pages + 1):
        if page > 1 and not go_to_page(driver, page):
            print(f"  Could not navigate to page {page}, stopping.")
            break

        wait_for_table(driver)

        for item in extract_active_rows(driver, profession):
            key = item["link"] or item["row_text"]
            if key not in seen:
                seen.add(key)
                collected.append(item)

        print(f"  Page {page}/{total_pages} | total so far: {len(collected)}")

    return collected


# ── CSV ───────────────────────────────────────────────────────────────────────

def save_csv(rows, output_file):
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["profession", "link", "row_text"])
        writer.writeheader()
        writer.writerows(rows)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    clear_wdm_lock()

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=webdriver.ChromeOptions(),
    )
    driver.maximize_window()

    all_results = []

    try:
        driver.get(URL)

        # Wait for Salesforce LWC to fully render
        WebDriverWait(driver, 40).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(8)
        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located((By.XPATH, "//button[@role='combobox']"))
        )
        time.sleep(2)

        # Set fixed filters once
        select_combobox(driver, "Search By", "Individual Name")
        time.sleep(1)

        # Print available category options for reference
        open_combobox(driver, "Category")
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.find_elements(By.XPATH, "//*[@role='option']")
            )
            time.sleep(0.5)
            opts = [o.get_attribute("title") for o in driver.find_elements(By.XPATH, "//*[@role='option']//*[@title]")]
            print("Category options:", opts)
        except TimeoutException:
            pass

        pick_option(driver, "Health")
        time.sleep(1)

        # Loop through each profession
        for profession in PROFESSIONS:
            print(f"\n{'='*60}\nProfession: {profession}\n{'='*60}")
            try:
                select_combobox(driver, "Professions", profession)
                time.sleep(0.5)
                click_search(driver)

                results = scrape_profession(driver, profession)
                all_results.extend(results)
                save_csv(all_results, OUTPUT_CSV)  # incremental save

                print(f"  Done: {len(results)} found | total: {len(all_results)}")

            except Exception as e:
                print(f"  ERROR for '{profession}': {e}")
                save_debug_html(driver, f"error_{profession[:20]}")

    finally:
        save_csv(all_results, OUTPUT_CSV)
        driver.quit()

    print(f"\nFinished. {len(all_results)} records saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
