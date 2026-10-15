import os
import re

template_dir = r"c:\Users\jeronshiya\OneDrive\Desktop\Smart-Emergency-Citizen-Service-Portal\templates"

templates_to_update = [
    "about.html",
    "admin_dashboard.html", 
    "admin_login.html",
    "admin_sos.html",
    "admin_users.html",
    "citizen_complaint.html",
    "complaint.html",
    "contact.html",
    "dashboard.html",
    "index.html",
    "nearby_hospitals.html",
    "profile.html",
    "sos.html",
    "staff_dashboard.html",
    "status.html"
]

for template in templates_to_update:
    filepath = os.path.join(template_dir, template)
    if not os.path.exists(filepath):
        continue
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add style.css link if not present
    if 'style.css' not in content:
        content = content.replace(
            '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">',
            '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">\n    <link rel="stylesheet" href="{{ url_for(\'static\', filename=\'css/style.css\') }}">'
        )
    
    # Change bg-light to bg-dark
    content = content.replace('class="bg-light"', 'class="bg-dark"')
    
    # Wrap content in main tag if not present
    if '<main>' not in content:
        # Find the closing nav tag and add main after it
        content = re.sub(
            r'(</nav>)\s*\n',
            r'\1\n\n<main>\n',
            content
        )
    
    # Add footer and close main if missing
    if '</main>' not in content and '<footer>' not in content:
        content = re.sub(
            r'(</body>)',
            r'</main>\n\n<footer class="bg-dark text-white text-center py-4">\n<h5>Smart Emergency & Citizen Service Portal</h5>\n<p>© 2026 All Rights Reserved.</p>\n</footer>\n\n\1',
            content
        )
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Updated: {template}")

print("All templates updated!")
