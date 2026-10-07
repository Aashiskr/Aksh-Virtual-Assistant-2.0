import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "frontend" / "mobile" / "android" / "app" / "src" / "main"


class SecureRemoteLoginTests(unittest.TestCase):
    def test_phone_biometric_signs_the_windows_unlock_challenge(self):
        launcher = (
            ANDROID
            / "java"
            / "com"
            / "aksh"
            / "remote"
            / "SecureRemoteLoginLauncher.java"
        ).read_text(encoding="utf-8")
        activity = (
            ANDROID
            / "java"
            / "com"
            / "aksh"
            / "remote"
            / "UnlockActivity.java"
        ).read_text(encoding="utf-8")
        signing_key = (
            ANDROID
            / "java"
            / "com"
            / "aksh"
            / "remote"
            / "PhoneSigningKey.java"
        ).read_text(encoding="utf-8")
        self.assertIn("UnlockActivity", launcher)
        self.assertIn("BiometricPrompt", activity)
        self.assertIn("SHA256withECDSA", signing_key)
        self.assertIn("setUserAuthenticationRequired(true)", signing_key)
        self.assertNotIn("com.google.chromeremotedesktop", launcher)

    def test_android_manifest_declares_biometric_and_background_monitor(self):
        manifest = (ANDROID / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertIn("android.permission.USE_BIOMETRIC", manifest)
        self.assertIn("FOREGROUND_SERVICE_REMOTE_MESSAGING", manifest)
        self.assertIn(".UnlockActivity", manifest)
        self.assertNotIn("com.google.chromeremotedesktop", manifest)

    def test_backend_uses_signed_challenge_without_password_payload(self):
        backend = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "backend").rglob("*.py")
        ).casefold()
        self.assertIn("/v1/unlock/challenge", backend)
        self.assertIn("/v1/unlock/approve", backend)
        self.assertIn("public_key.verify", backend)
        self.assertNotIn("windows_password", backend)

    def test_windows_provider_preserves_standard_credential_options(self):
        provider = (
            ROOT
            / "native"
            / "windows_credential_provider"
            / "AkshCredentialProvider.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("CPUS_UNLOCK_WORKSTATION", provider)
        self.assertIn("AkshPhoneUnlockCredential", provider)
        self.assertNotIn("ICredentialProviderFilter", provider)


if __name__ == "__main__":
    unittest.main()
