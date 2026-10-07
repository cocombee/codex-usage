"""Real atomic exchanges on disposable bundles; guards mocked only for toy archives."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mod

for fail_validation in [False,True]:
    with tempfile.TemporaryDirectory(prefix='codex-usage-install-test-') as directory:
        root=Path(directory)
        for name in ['APP','NEW','SAFE']:
            setattr(mod,name,root/name)
        mod.RECEIPT=root/'receipt.json'
        for folder,data in [(mod.APP,b'previous-working-mod'),(mod.SAFE,b'original'),(mod.NEW,b'candidate')]:
            (folder/mod.ASAR).parent.mkdir(parents=True);(folder/mod.ASAR).write_bytes(data)
        mod.BASELINE=mod.sha(mod.SAFE/mod.ASAR)
        old=mod.sha(mod.APP/mod.ASAR);candidate=mod.sha(mod.NEW/mod.ASAR)
        mod.save_receipt({'candidate_sha256':candidate,'preinstall_sha256':old,
                          'candidate_entitlements':{},'preinstall_entitlements':{},'candidate_fingerprint':'candidate','preinstall_fingerprint':'working','state':'candidate_verified'})
        def guard(app,fingerprint):
            if fail_validation and app==mod.APP and fingerprint=='candidate':
                raise ValueError('Simulated post-exchange validation failure')
        with patch.object(mod,'running_app',return_value=[]),patch.object(mod.integrity,'guard',side_effect=guard),patch.object(mod.signing,'verify'):
            if fail_validation:
                try:mod.install();raise AssertionError('Expected failed validation')
                except ValueError:pass
                assert mod.sha(mod.APP/mod.ASAR)==old
                assert mod.sha(mod.NEW/mod.ASAR)==candidate
            else:
                mod.install()
                assert mod.sha(mod.NEW/mod.ASAR)==old
                assert mod.sha(mod.APP/mod.ASAR)==candidate
                mod.install(rollback=True)
                assert mod.sha(mod.APP/mod.ASAR)==old
                assert mod.sha(mod.NEW/mod.ASAR)==candidate
            assert mod.sha(mod.SAFE/mod.ASAR)==mod.BASELINE
print('Atomic promotion, retained working mod, recovery and failed-validation reversal passed')
