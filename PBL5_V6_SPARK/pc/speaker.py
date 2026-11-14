"""Optional Windows speech, not a certified assistive navigation system.
No credentials enter speech. Pending/inflight speech is dropped on session change.
"""
import json
import queue
import subprocess
import sys
import threading

SCRIPT = r'''
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$vi = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'vi-*' } | Select-Object -First 1
if (-not $vi) { exit 42 }
$s.SelectVoice($vi.VoiceInfo.Name)
$payload = [Console]::In.ReadLine() | ConvertFrom-Json
$s.Speak($payload.text)
$s.Dispose()
'''

class Speaker(threading.Thread):
    def __init__(self, stop, get_identity, notices):
        super().__init__(daemon=True)
        self.stop, self.get_identity, self.notices = stop, get_identity, notices
        self.jobs = queue.Queue(maxsize=8)
        self.enabled = sys.platform == 'win32'

    def say(self, identity, text):
        if not self.enabled: return
        try: self.jobs.put_nowait((identity, str(text)[:1000]))
        except queue.Full: pass

    def run(self):
        while not self.stop.is_set():
            try: identity, text = self.jobs.get(timeout=.2)
            except queue.Empty: continue
            if not self.enabled or identity != self.get_identity(): continue
            process = None
            try:
                process = subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-Command',SCRIPT],
                    stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                process.stdin.write((json.dumps({'text':text},ensure_ascii=True)+'\n').encode('ascii'))
                process.stdin.close()
                elapsed = 0
                while process.poll() is None:
                    if self.stop.wait(.1) or identity != self.get_identity() or elapsed >= 30:
                        process.terminate(); break
                    elapsed += .1
                process.wait(timeout=3)
                if process.returncode == 42:
                    self.enabled = False
                    self.notices.put(('notice','Chua co giong vi-VN trong Windows System.Speech. Chua du dieu kien thu ho tro nguoi mu. Xem BAT_DAU_SPARK.md.'))
            except (OSError, subprocess.SubprocessError):
                self.enabled = False
                self.notices.put(('notice','Khong mo duoc doc giong Windows. Kiem tra tai nghe/voice; khong coi am thanh da hoat dong.'))
            finally:
                if process is not None and process.poll() is None:
                    process.kill(); process.wait()
