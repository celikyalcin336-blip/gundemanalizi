$src = 'C:\Users\celik\.gemini\antigravity\scratch\social-news-bot'
$dest = 'C:\Users\celik\Desktop\gundemanalizi_guncel.zip'
if (Test-Path $dest) { Remove-Item $dest -Force }
$tempDir = 'C:\Users\celik\.gemini\antigravity\scratch\temp_zip_pack'
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
New-Item -ItemType Directory -Path $tempDir | Out-Null

Copy-Item "$src\*.py" $tempDir\
Copy-Item "$src\Procfile" $tempDir\
Copy-Item "$src\requirements.txt" $tempDir\
Copy-Item "$src\runtime.txt" $tempDir\
Copy-Item "$src\.gitignore" $tempDir\
Copy-Item "$src\assets" $tempDir\ -Recurse
Copy-Item "$src\templates" $tempDir\ -Recurse
Copy-Item "$src\data" $tempDir\ -Recurse
Copy-Item "$src\output" $tempDir\ -Recurse

Compress-Archive -Path "$tempDir\*" -DestinationPath $dest -Force
Remove-Item $tempDir -Recurse -Force
Get-Item $dest | Select-Object Name, Length
