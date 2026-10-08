"""Detect fresh main/helper crash reports without reading app UI or report bodies."""
from pathlib import Path
import json
import plistlib
import subprocess


def mapped_build_matches(pid,app):
    """Kernel-mapped executable/framework inodes prove the running build.

    Paths alone can refer to stale images after an atomic bundle exchange.
    No app UI, memory contents or application IPC is inspected.
    """
    app=Path(app)
    expected=[app/'Contents/MacOS/ChatGPT',app/'Contents/Frameworks/Codex Framework.framework/Versions/Current/Codex Framework']
    expected={str(path.resolve()):path.stat().st_ino for path in expected}
    result=subprocess.run(['/usr/sbin/lsof','-a','-p',str(pid),'-d','txt','-Fni'],capture_output=True,text=True,timeout=15)
    if result.returncode:return False
    observed={};inode=None
    for line in result.stdout.splitlines():
        if line.startswith('i') and line[1:].isdigit():inode=int(line[1:])
        elif line.startswith('n') and inode is not None:
            name=line[1:]
            if name in expected:observed[name]=inode
    return all(observed.get(path)==inode for path,inode in expected.items())


class CrashMonitor:
    def __init__(self,app,reports=None):
        self.reports = Path(reports) if reports else Path.home()/'Library/Logs/DiagnosticReports'
        app = Path(app)
        hosts = [app] + list((app/'Contents/Frameworks/Codex Framework.framework/Versions/Current/Helpers').glob('*.app'))
        self.identifiers, self.names = set(), set()
        for host in hosts:
            info = plistlib.loads((host/'Contents/Info.plist').read_bytes())
            self.identifiers.add(info['CFBundleIdentifier'])
            self.names.add(info.get('CFBundleExecutable',host.stem))
            self.names.add(host.stem)
        self.before = self.inventory()

    def inventory(self):
        if not self.reports.exists():return {}
        result = {}
        for path in self.reports.iterdir():
            if path.suffix=='.ips' and path.name.lower().startswith(('codex','chatgpt')):
                stat = path.stat()
                result[path] = (stat.st_mtime_ns,stat.st_size)
        return result

    def check(self):
        for path,stamp in self.inventory().items():
            if self.before.get(path)==stamp:continue
            try:
                with path.open() as file:header=json.loads(file.readline(1024*1024))
            except (ValueError,OSError):
                raise ValueError('New Codex crash report could not be verified: ' + path.name)
            if header.get('bundleID') in self.identifiers or header.get('app_name') in self.names:
                raise ValueError('Codex main/helper crashed during startup: ' + path.name)
