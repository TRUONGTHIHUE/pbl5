"""Reproducible LOCAL checks. Never deploys or touches real Firebase."""
from pathlib import Path
import compileall
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
if not compileall.compile_dir(ROOT/'pc',quiet=1):raise SystemExit('Python syntax failed')
subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,check=True)
node=shutil.which('node')
if node:
    for file in (ROOT/'functions').glob('*.js'):subprocess.run([node,'--check',str(file)],check=True)
    subprocess.run([node,'--test','tests/api.test.js','tests/repository.test.js'],cwd=ROOT/'functions',check=True)
else:print('NOT RUN: Node tests (Node unavailable).')
if shutil.which('gcc'):
    with tempfile.TemporaryDirectory() as tmp:
        for name,sources,extras in [
            ('policy',['main/wifi_policy.c','tests/test_wifi_policy.c'],[]),
            ('firmware_host',['tests/test_firmware_host.c','main/wifi_policy.c'],['-I','tests/esp_stubs','-ffunction-sections','-fdata-sections','-Wl,--gc-sections'])]:
            output=Path(tmp)/(name+('.exe' if sys.platform=='win32' else ''))
            subprocess.run(['gcc','-std=c11','-Wall','-Wextra','-Werror','-I','main',*extras,*sources,'-o',str(output)],cwd=ROOT,check=True)
            subprocess.run([str(output)],check=True)
else:print('NOT RUN: native C tests (gcc unavailable).')
print('These checks do NOT run an ESP-IDF build, real Firebase, physical USB/Wi-Fi or camera/model inference.')
