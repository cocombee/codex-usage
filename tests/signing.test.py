"""Regression checks for the approved local-signing scope."""
from pathlib import Path
import sys
import unittest
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from signing import local_entitlements,assert_local_entitlements,RESTRICTED_VENDOR_KEYS,LIBRARY_LOADING_KEY

class SigningPolicyTests(unittest.TestCase):
    def test_vendor_claims_removed_runtime_and_supported_caps_preserved(self):
        value={key:'synthetic-vendor-claim' for key in RESTRICTED_VENDOR_KEYS}
        value.update({'com.apple.security.cs.allow-jit':True,'com.apple.security.cs.allow-unsigned-executable-memory':True,'com.apple.security.network.client':True})
        result=local_entitlements(value)
        self.assertFalse(set(result)&RESTRICTED_VENDOR_KEYS)
        self.assertTrue(all(result[key] is True for key in result))
        self.assertIn('com.apple.application-identifier',value)
    def test_loading_exception_requires_explicit_verified_host(self):
        with self.assertRaises(ValueError):local_entitlements({},allow_library_loading=True)
        self.assertEqual(local_entitlements({}),{})
        self.assertEqual(local_entitlements({},allow_library_loading=True,verified_executable_host=True),{LIBRARY_LOADING_KEY:True})
    def test_unknown_vendor_claim_fails_closed(self):
        with self.assertRaises(ValueError):assert_local_entitlements({'com.apple.developer.unexpected':True})
    def test_boolean_scope_cannot_be_accidentally_enabled(self):
        with self.assertRaises(ValueError):local_entitlements({},allow_library_loading='false')

unittest.main(verbosity=2)
