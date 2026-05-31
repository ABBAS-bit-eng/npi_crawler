import re

DEBUG_FILE = r'C:\Users\Abbas\Documents\NPI_data\debug_Category_options.html'

with open(DEBUG_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# All data-value attributes
print("data-value attributes:")
for val in re.findall(r'data-value="([^"]+)"', content):
    print(f"  {val}")

# Text inside role=option blocks
print("\nOption block texts:")
for block in re.findall(r'role="option"[^>]*>(.*?)</lightning-base-combobox-item>', content, re.DOTALL)[:30]:
    text = re.sub(r'<[^>]+>', '', block).strip()
    if text:
        print(f"  {text}")

# Combobox aria-labels and name attributes
print("\nCombobox aria-labels:", re.findall(r'aria-label="([^"]+)"[^>]*role="combobox"', content))
print("Combobox names:", re.findall(r'name="([^"]+)"[^>]*role="combobox"', content))
