import os
import time
import csv
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager


# ── Constants ────────────────────────────────────────────────────────────────
URL        = "https://license.wi.gov/s/license-lookup"
OUTPUT_CSV = "wisconsin_health_active_links.csv"

PROFESSIONS = [
    "Acupuncturist",
    "Advanced Practice Nurse Prescriber",
    "Anesthesiologist Assistant",
    "Art Therapist",
    "Athletic Trainer",
    "Audiologist",
    "Behavior Analyst",
    "Body Piercer",
    "Chiropractic Radiological Technician",
    "Chiropractic Technician",
    "Chiropractor",
    "Clinical Substance Abuse Counselor",
    "Clinical Supervisor In-Training",
    "Clinical Supervisor, Independent",
    "Clinical Supervisor, Intermediate",
    "Controlled Substances Special Use Authorization",
    "Controlled Substances Special Use Authorization - Analytical Laboratory (450)",
    "Dance Therapist",
    "Dental Hygienist",
    "Dental Therapist",
    "Dentist",
    "Dietitian",
    "Expanded Function Dental Auxiliary",
    "Genetic Counselor",
    "Hearing Instrument Specialist",
    "Licensed Practical Nurse",
    "Licensed Professional Counselor",
    "Limited X-Ray Machine Operator Permit",
    "Limited-Scope Naturopathic Doctor",
    "Marriage and Family Therapist",
    "Marriage and Family Therapist Training License",
    "Massage Therapist or Bodywork Therapist",
    "Medicine and Surgery - DO",
    "Medicine and Surgery - MD",
    "Midwives, Licensed",
    "Music Therapist",
    "Naturopathic Doctor",
    "Nurse - Midwife",
    "Occupational Therapist",
    "Occupational Therapy Assistant",
    "Optometrist",
    "Perfusionist",
    "Pharmacist",
    "Pharmacy Technician",
    "Physical Therapist",
    "Physical Therapist Assistant",
    "Physician - DO",
    "Physician - DO Compact",
    "Physician - MD",
    "Physician - MD Compact",
    "Physician Assistant",
    "Podiatrist",
    "Prevention Specialist",
    "Prevention Specialist In-Training",
    "Professional Counselor Training License",
    "Provisional Physician Licensure",
    "Psychologist",
    "Radiographer, Licensed",
    "Registered Nurse",
    "Registered Sanitarian",
    "Resident Educational License",
    "Respiratory Care Practitioner",
    "Sign Language Interpreter - Advanced Deaf",
    "Sign Language Interpreter - Advanced Hearing",
    "Sign Language Interpreter - Intermediate Deaf",
    "Sign Language Interpreter - Intermediate Hearing",
    "Social Worker",
    "Social Worker - Advanced Practice",
    "Social Worker - Independent",
    "Social Worker - Licensed Clinical",
    "Social Worker - Training Certificate",
    "Speech-Language Pathologist",
    "Substance Abuse Counselor",
    "Substance Abuse Counselor In-Training",
    "Tattooist",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def clear_wdm_lock():
    """Remove stale webdriver-manager lock file if it exists."""
    lock_path = os.path.join(os.path.expanduser("~"), ".wdm", ".wdm-lock-chromedriver-win64")
    if os.path.exists(lock_path):
        try:
            os.remove(lock_path)
            print("Cleared stale wdm lock file.")
        except Exception as e:
            print(f"Could not remove lock file: {e}")


def js_click(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.3)
    driver.execute_script("arguments[0].click();", element)


def wait_for_table_to_load(driver, timeout=40):
    """Wait until the results table has rows OR a no-results message appears."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: (
                len(d.find_elements(By.XPATH, "//table//tbody/tr")) > 0
                or len(d.find_elements(
                    By.XPATH,
                    "//*[contains(text(),'No results') or contains(text(),'No records')]"
                )) > 0
            )
        )
    except TimeoutException:
        pass
    time.sleep(1)


# ── Combobox selector ─────────────────────────────────────────────────────────

def open_combobox(driver, aria_label, timeout=20):
    """
    Click the Salesforce LWC combobox button identified by its aria-label.
    Returns the button element.
    """
    xpaths = [
        f"//button[@role='combobox' and @aria-label='{aria_label}']",
        f"//button[@aria-haspopup='listbox' and @aria-label='{aria_label}']",
        f"//label[normalize-space()='{aria_label}']/following::button[@aria-haspopup='listbox'][1]",
        f"//*[normalize-space(text())='{aria_label}']/ancestor::*[contains(@class,'slds-form-element')]//button[@aria-haspopup='listbox']",
    ]
    btn = None
    for xp in xpaths:
        try:
            btn = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.XPATH, xp)))
            break
        except TimeoutException:
            continue
    if btn is None:
        raise TimeoutException(f"Cannot find combobox with aria-label='{aria_label}'")
    js_click(driver, btn)
    return btn


def pick_option(driver, option_text, timeout=15):
    """
    After a combobox is open, wait for options to load and click the matching one.
    Matches by title attribute or visible text.
    """
    # Wait for at least one option to appear
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.find_elements(By.XPATH, "//*[@role='option']")) > 0
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
            print(f"    Selected option: '{option_text}'")
            time.sleep(0.7)
            return
        except TimeoutException:
            continue

    # Debug dump
    with open(f"debug_option_{option_text[:30].replace(' ','_')}.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    raise TimeoutException(
        f"Cannot find option '{option_text}'. Debug HTML saved."
    )


def select_combobox(driver, aria_label, option_text):
    """Open a combobox by aria-label and select an option by text."""
    print(f"  Selecting [{aria_label}] = '{option_text}'")
    open_combobox(driver, aria_label)
    pick_option(driver, option_text)


# ── Search ────────────────────────────────────────────────────────────────────

def click_search(driver, timeout=30):
    btn = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(
            (By.XPATH, '//button[contains(@class,"slds-button_brand") and contains(.,"Search")]')
        )
    )
    js_click(driver, btn)
    time.sleep(3)


# ── Data extraction ───────────────────────────────────────────────────────────

def extract_active_wisconsin_from_page(driver, profession):
    """
    From the current results page, collect rows where:
      - State column contains 'Wisconsin' (or 'WI')
      - Status column contains 'Active'
    Returns list of dicts with profession, link, row_text.
    """
    data = []
    rows = driver.find_elements(By.XPATH, "//table//tbody/tr")

    for row in rows:
        try:
            row_text = row.text.strip()
        except StaleElementReferenceException:
            continue

        # Filter: must contain Wisconsin (or WI) and Active
        if ("Wisconsin" not in row_text and "WI" not in row_text):
            continue
        if "Active" not in row_text:
            continue

        # Try to grab the detail link
        try:
            link_el = row.find_element(
                By.XPATH,
                ".//a[contains(@href,'/s/') or contains(@href,'license')]"
            )
            href = link_el.get_attribute("href") or ""
        except NoSuchElementException:
            href = ""

        # Fallback: lightning-formatted-url
        if not href:
            try:
                link_el = row.find_element(
                    By.XPATH,
                    ".//lightning-formatted-url//a"
                )
                href = link_el.get_attribute("href") or ""
            except NoSuchElementException:
                href = ""

        full_url = urljoin(URL, href) if href else ""

        data.append({
            "profession": profession,
            "link": full_url,
            "row_text": row_text,
        })

    return data


# ── Pagination ────────────────────────────────────────────────────────────────

def get_total_pages(driver):
    """
    Read the native <select class="page-selector"> to find total page count.
    Returns int (1 if selector not found).
    """
    try:
        sel_el = driver.find_element(By.XPATH, "//select[contains(@class,'page-selector')]")
        options = sel_el.find_elements(By.TAG_NAME, "option")
        return len(options)
    except NoSuchElementException:
        return 1


def go_to_page(driver, page_number):
    """
    Navigate to a specific page using the native <select class="page-selector">.
    """
    try:
        sel_el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//select[contains(@class,'page-selector')]")
            )
        )
        Select(sel_el).select_by_value(str(page_number))
        time.sleep(3)
        wait_for_table_to_load(driver)
        return True
    except (TimeoutException, NoSuchElementException):
        return False


# ── Per-profession scrape ─────────────────────────────────────────────────────

def scrape_all_pages(driver, profession):
    """
    Scrape all pages for the current search result.
    Uses the native page-selector <select> for pagination.
    """
    collected = []
    seen_links = set()

    wait_for_table_to_load(driver)

    # Check for no results
    no_results = driver.find_elements(
        By.XPATH,
        "//*[contains(text(),'No results') or contains(text(),'No records')]"
    )
    if no_results:
        print(f"  No results for: {profession}")
        return collected

    total_pages = get_total_pages(driver)
    print(f"  Total pages: {total_pages}")

    for page in range(1, total_pages + 1):
        # Navigate to page (page 1 is already loaded)
        if page > 1:
            success = go_to_page(driver, page)
            if not success:
                print(f"  Could not navigate to page {page}, stopping.")
                break

        wait_for_table_to_load(driver)
        page_data = extract_active_wisconsin_from_page(driver, profession)

        new_count = 0
        for item in page_data:
            key = item["link"] or item["row_text"]
            if key not in seen_links:
                seen_links.add(key)
                collected.append(item)
                new_count += 1

        print(f"  Page {page}/{total_pages} | new: {new_count} | total so far: {len(collected)}")

    return collected


# ── CSV ───────────────────────────────────────────────────────────────────────

def save_to_csv(rows, output_file):
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["profession", "link", "row_text"])
        writer.writeheader()
        writer.writerows(rows)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    clear_wdm_lock()

    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(service=service, options=options)

    all_results = []

    try:
        driver.get(URL)

        # Wait for page to fully render (Salesforce LWC is slow)
        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(8)
        WebDriverWait(driver, 40).until(
            EC.presence_of_element_located(
                (By.XPATH, "//button[@role='combobox']")
            )
        )
        time.sleep(2)

        # ── Step 1: Set Search By = Individual Name (set once, never change) ──
        select_combobox(driver, "Search By", "Individual Name")
        time.sleep(1)

        # ── Step 2: Set Category = Health (set once, never change) ────────────
        # Open category and print available options first
        open_combobox(driver, "Category")
        try:
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.XPATH, "//*[@role='option']")) > 0
            )
            time.sleep(0.5)
            opts = driver.find_elements(By.XPATH, "//*[@role='option']//*[@title]")
            print("Category options available:", [o.get_attribute("title") for o in opts])
        except TimeoutException:
            pass

        pick_option(driver, "Health")
        time.sleep(1)

        # ── Step 3: Loop through professions ──────────────────────────────────
        for profession in PROFESSIONS:
            print(f"\n{'='*60}")
            print(f"Profession: {profession}")
            print(f"{'='*60}")

            try:
                # Select profession (only profession changes each iteration)
                select_combobox(driver, "Professions", profession)
                time.sleep(0.5)

                # Click Search
                click_search(driver)

                # Scrape all pages for this profession
                profession_results = scrape_all_pages(driver, profession)
                all_results.extend(profession_results)

                # Save incrementally after each profession
                save_to_csv(all_results, OUTPUT_CSV)
                print(f"  Done: {profession} | found: {len(profession_results)} | total: {len(all_results)}")

            except Exception as e:
                print(f"  ERROR for profession '{profession}': {e}")
                # Save debug snapshot
                with open(f"debug_error_{profession[:20].replace(' ','_')}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                continue

    finally:
        save_to_csv(all_results, OUTPUT_CSV)
        driver.quit()

    print(f"\nFinished. Total links collected: {len(all_results)}")
    print(f"Saved to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
