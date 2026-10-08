"""Fresh helper crashes fail startup; historical and unrelated reports do not."""
from pathlib import Path
import json
import plistlib
import sys
import tempfile
import unittest
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from startup_health import CrashMonitor


class StartupHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.app=root/'ChatGPT.app';self.reports=root/'Reports';self.reports.mkdir()
        helper=self.app/'Contents/Frameworks/Codex Framework.framework/Versions/Current/Helpers/Codex (Renderer).app'
        for host,identifier,name in [(self.app,'com.openai.codex','ChatGPT'),(helper,'com.openai.codex.helper','Codex (Renderer)')]:
            info=host/'Contents/Info.plist';info.parent.mkdir(parents=True)
            info.write_bytes(plistlib.dumps({'CFBundleIdentifier':identifier,'CFBundleExecutable':name}))
    def tearDown(self):self.temp.cleanup()
    def report(self,name,identifier):
        (self.reports/name).write_text(json.dumps({'bundleID':identifier})+'\n{}\n')
    def test_historical_failure_does_not_trigger_recovery(self):
        self.report('ChatGPT-old.ips','com.openai.codex');monitor=CrashMonitor(self.app,self.reports);monitor.check()
    def test_fresh_helper_failure_is_detected_even_if_main_is_alive(self):
        monitor=CrashMonitor(self.app,self.reports);self.report('Codex-new.ips','com.openai.codex.helper')
        with self.assertRaisesRegex(ValueError,'main/helper crashed'):monitor.check()
    def test_unrelated_new_report_is_ignored(self):
        monitor=CrashMonitor(self.app,self.reports);self.report('Codex-other.ips','org.example.unrelated');monitor.check()
    def test_incomplete_new_report_cannot_pass_startup_health(self):
        monitor=CrashMonitor(self.app,self.reports);(self.reports/'ChatGPT-partial.ips').write_text('{')
        with self.assertRaisesRegex(ValueError,'could not be verified'):monitor.check()


unittest.main(verbosity=2)
