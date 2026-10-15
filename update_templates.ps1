# PowerShell script to update all templates with dark theme

$templateDir = "c:\Users\jeronshiya\OneDrive\Desktop\Smart-Emergency-Citizen-Service-Portal\templates"

$templates = @(
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
)

foreach ($template in $templates) {
    $filePath = Join-Path $templateDir $template
    
    if (-not (Test-Path $filePath)) {
        Write-Host "Skipping: $template (not found)"
        continue
    }
    
    $content = Get-Content -Path $filePath -Raw -Encoding UTF8
    
    # Add style.css if not present
    if ($content -notlike "*style.css*") {
        $content = $content -replace 
            '(<link href="https://cdn\.jsdelivr\.net/npm/bootstrap@5\.3\.3/dist/css/bootstrap\.min\.css" rel="stylesheet">)',
            '$1' + "`n    " + '<link rel="stylesheet" href="{{ url_for(''static'', filename=''css/style.css'') }}">'
    }
    
    # Change bg-light to bg-dark
    $content = $content -replace 'class="bg-light"', 'class="bg-dark"'
    $content = $content -replace '<body class="bg-dark">', '<body class="bg-dark">'
    
    # Add main tag after nav if not present
    if ($content -notlike "*<main>*") {
        $content = $content -replace '(</nav>)\s*\n', "`$1`n`n<main>`n"
    }
    
    # Add footer and close main if missing
    if ($content -notlike "*</main>*" -and $content -notlike "*<footer>*") {
        $content = $content -replace '(</body>)', 
            '</main>' + "`n`n" + '<footer class="bg-dark text-white text-center py-4">' + "`n" +
            '<h5>Smart Emergency & Citizen Service Portal</h5>' + "`n" +
            '<p>© 2026 All Rights Reserved.</p>' + "`n" +
            '</footer>' + "`n`n" + '$1'
    }
    
    Set-Content -Path $filePath -Value $content -Encoding UTF8
    Write-Host "Updated: $template"
}

Write-Host "All templates updated!"
