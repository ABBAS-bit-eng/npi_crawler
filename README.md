# Wisconsin Health License Crawler

A Selenium-based scraper that collects **active Wisconsin health professional license links** from the [Wisconsin License Lookup portal](https://license.wi.gov/s/license-lookup).

---

## What It Does

- Iterates through 75+ health profession types (Physicians, Nurses, Dentists, etc.)
- Filters results to **Wisconsin / WI** state and **Active** status only
- Extracts detail page links for each matching license record
- Saves results incrementally to a CSV after each profession (crash-safe)
- Handles multi-page results via the native page-selector dropdown

---

## Project Structure

```
npi_crawler/
├── Wiscinson.py       # Main crawler — scrapes license data and saves to CSV
├── parse_debug.py     # Debug utility — parses saved HTML snapshots for combobox options
├── README.md
└── wisconsin_health_active_links.csv   # Output (generated on run)
```

---

## Requirements

- Python 3.8+
- Google Chrome installed

Install dependencies:

```bash
pip install selenium webdriver-manager
```

---

## Usage

```bash
python Wiscinson.py
```

Output is saved to `wisconsin_health_active_links.csv` with columns:

| Column      | Description                          |
|-------------|--------------------------------------|
| profession  | License profession type              |
| link        | Full URL to the license detail page  |
| row_text    | Raw text from the result table row   |

---

## Debug Utilities

If a combobox option fails to load, the crawler auto-saves a `debug_<label>.html` snapshot.  
Use `parse_debug.py` to inspect those snapshots:

```bash
python parse_debug.py
```

Update the `DEBUG_FILE` path in `parse_debug.py` to point to the saved HTML file.

---

## Notes

- The portal is built on Salesforce LWC, which renders slowly — initial page load waits up to 8 seconds.
- `Search By` is fixed to **Individual Name** and `Category` is fixed to **Health** for all searches.
- Only the `Professions` dropdown changes per iteration.
- Results are deduplicated by link URL or row text within each profession run.
