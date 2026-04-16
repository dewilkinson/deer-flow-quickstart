import os, re

p = 'src'
for r, d, files in os.walk(p):
    for f in files:
        if f.endswith('.tsx') or f.endswith('.ts'):
            path = os.path.join(r, f)
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            new_content = re.sub(r'env\.NEXT_PUBLIC_STATIC_WEBSITE_ONLY\s*===\s*"true"', 'env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === true', content)
            
            if new_content != content:
                with open(path, 'w', encoding='utf-8') as file:
                    file.write(new_content)
                print(f"Fixed {path}")
