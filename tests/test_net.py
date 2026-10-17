import io
import json
import ssl
import unittest
from unittest import mock

import certifi

from hearth import ai, grok_sso, icons, net


class Reply(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def reply(data=b"{}"):
    return Reply(data)


class SecureContextTests(unittest.TestCase):
    def test_it_checks_certificates_and_hostnames(self):
        context = net.secure_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_it_trusts_the_bundled_list_so_a_packaged_mac_app_can_connect(self):
        wanted = len(ssl.create_default_context().get_ca_certs())
        context = ssl.create_default_context()
        context.load_verify_locations(cafile=certifi.where())
        self.assertGreater(len(context.get_ca_certs()), 50)
        self.assertGreaterEqual(len(net.secure_context().get_ca_certs()), wanted)
        self.assertEqual(len(net.secure_context().get_ca_certs()), len(context.get_ca_certs()))

    def test_without_certifi_it_still_gives_the_system_list(self):
        net.secure_context.cache_clear()
        try:
            with mock.patch.dict("sys.modules", {"certifi": None}):
                context = net.secure_context()
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        finally:
            net.secure_context.cache_clear()


class EveryRequestUsesItTests(unittest.TestCase):
    def assert_secure(self, opened):
        self.assertIs(opened.call_args.kwargs["context"], net.secure_context())

    def test_model_requests(self):
        with mock.patch("urllib.request.urlopen", return_value=reply()) as opened:
            ai._request("https://api.example.com/v1", "key", "chat/completions", {"model": "m"})
        self.assert_secure(opened)

    def test_grok_sign_in_requests(self):
        with mock.patch("urllib.request.urlopen", return_value=reply()) as opened:
            grok_sso.endpoints()
        self.assert_secure(opened)
        with mock.patch("urllib.request.urlopen", return_value=reply()) as opened:
            grok_sso._post_form("https://auth.example.com/token", {"a": "b"})
        self.assert_secure(opened)

    def test_app_store_art_requests(self):
        png = b"x" * 100
        with mock.patch("urllib.request.urlopen", return_value=reply(png)) as opened:
            icons._get_bytes("https://example.com/a.png")
        self.assert_secure(opened)
        with mock.patch("urllib.request.urlopen", return_value=reply(json.dumps({}).encode())) as opened:
            icons._get_json("https://itunes.apple.com/lookup?bundleId=x")
        self.assert_secure(opened)


if __name__ == "__main__":
    unittest.main()
