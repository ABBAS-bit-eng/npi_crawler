import re

with open(r'C:\Users\Abbas\Documents\NPI_data\debug_Category_options.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all data-value attributes
options = re.findall(r'data-value="([^"]+)"', content)
print("All data-value attributes:")
for o in options:
    print(" ", o)

# Find all role=option elements and nearby text
option_blocks = re.findall(r'role="option"[^>]*>(.*?)</lightning-base-combobox-item>', content, re.DOTALL)
print("\nOption block texts:")
for b in option_blocks[:30]:
    text = re.sub(r'<[^>]+>', '', b).strip()
    if text:
        print(" ", text)

# Find aria-label on combobox buttons
labels = re.findall(r'aria-label="([^"]+)"[^>]*role="combobox"', content)
print("\nCombobox aria-labels:", labels)

# Find name attributes on comboboxes
names = re.findall(r'name="([^"]+)"[^>]*role="combobox"', content)
print("Combobox names:", names)
