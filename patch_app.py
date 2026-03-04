"""Fix app.py:
  1. Restore the corrupted CSS comment line
  2. Remove orphaned trace_tabs lines injected into the CSS area
  3. Remove the claim_935_trace tab reference and shift tab indices
"""

with open('app.py', encoding='utf-8') as f:
    lines = f.readlines()

# --- Pass 1: Fix the corrupted CSS comment + remove orphaned trace_tabs lines ---
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Detect the corrupted line: CSS comment merged with trace_tabs
    if 'Custom CSS' in line and 'trace_tabs' in line:
        print(f"Fixing corrupted CSS line at {i+1}")
        new_lines.append('# \u2500\u2500 Custom CSS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n')
        # Skip the orphaned trace_tabs/tab label/]) lines that follow
        i += 1
        while i < len(lines):
            orphan = lines[i].strip()
            if orphan.startswith('"') or orphan.startswith('])') or orphan == '':
                print(f"  Skipping orphan line {i+1}: {repr(lines[i][:50])}")
                i += 1
            else:
                break
        continue
    new_lines.append(line)
    i += 1

lines = new_lines

# --- Pass 2: Remove claim_935_trace and renumber subsequent tab indices ---
new_lines2 = []
for line in lines:
    if 'claim_935_trace' in line:
        print(f"Removing: {repr(line.strip())}")
        continue
    line = line.replace('with trace_tabs[3]:', 'with trace_tabs[2]:')
    line = line.replace('with trace_tabs[4]:', 'with trace_tabs[3]:')
    line = line.replace('with trace_tabs[5]:', 'with trace_tabs[4]:')
    new_lines2.append(line)

lines = new_lines2

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"Done. Final line count: {len(lines)}")

import ast
with open('app.py', encoding='utf-8') as f:
    content = f.read()
ast.parse(content)
print("Syntax OK")
