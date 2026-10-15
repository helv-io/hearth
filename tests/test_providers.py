import unittest

from hearth import ai, grok_sso, presets


class PresetTests(unittest.TestCase):
    def test_the_list_matches_skgate(self):
        self.assertEqual(
            [item["id"] for item in presets.PRESETS],
            ["grok", "openai", "anthropic", "gemini", "mistral", "deepseek", "groq", "openrouter", "ollama", "lmstudio", "custom"],
        )
        self.assertEqual(presets.by_id("openai")["base"], "https://api.openai.com/v1")
        self.assertEqual(presets.by_id("anthropic")["adapter"], "anthropic")
        self.assertEqual(presets.by_id("gemini")["base"], "https://generativelanguage.googleapis.com/v1beta/openai")
        self.assertFalse(presets.by_id("ollama")["needs_key"])
        self.assertTrue(presets.by_id("custom")["custom"])
        self.assertTrue(presets.by_id("grok")["sso"])

    def test_a_known_base_selects_its_provider(self):
        self.assertEqual(presets.match_base("https://api.mistral.ai/v1/"), "mistral")
        self.assertEqual(presets.match_base("http://127.0.0.1:9/v1"), "custom")


class GrokSignInTests(unittest.TestCase):
    def test_device_payload_hides_nothing_required_and_reports_failure(self):
        flow = grok_sso._device_from_payload(200, {
            "device_code": "secret-device",
            "user_code": "ABCD-EFGH",
            "verification_uri": "https://auth.example/device",
            "expires_in": 60,
            "interval": 2,
        })
        self.assertEqual(flow["user_code"], "ABCD-EFGH")
        self.assertNotIn("error", flow)
        failed = grok_sso._device_from_payload(400, {"error": "invalid_client"})
        self.assertIn("400", failed["error"])
        self.assertNotIn("device_code", failed)

    def test_pending_and_denial(self):
        self.assertEqual(grok_sso._token_outcome(400, {"error": "authorization_pending"}), "pending")
        self.assertEqual(grok_sso._token_outcome(400, {"error": "slow_down"}), "slow")
        self.assertIn("denied", grok_sso._token_outcome(400, {"error": "access_denied"}))
        tokens = grok_sso._token_outcome(200, {
            "access_token": "a",
            "refresh_token": "r",
            "expires_in": 30,
        })
        self.assertEqual(tokens["access_token"], "a")
        self.assertEqual(tokens["refresh_token"], "r")


class AnthropicTests(unittest.TestCase):
    def test_chat_becomes_a_message_and_back(self):
        body = {
            "model": "claude-test",
            "messages": [
                {"role": "system", "content": "Reply with JSON."},
                {"role": "user", "content": "One folder."},
            ],
        }
        message = ai._to_anthropic(body)
        self.assertEqual(message["model"], "claude-test")
        self.assertEqual(message["system"], "Reply with JSON.")
        self.assertEqual(message["messages"][0]["role"], "user")
        self.assertNotIn("response_format", message)
        payload = ai._from_anthropic({
            "model": "claude-test",
            "content": [{"type": "text", "text": "{\"dock\": []}"}],
        }, "claude-test")
        self.assertIn("dock", payload["choices"][0]["message"]["content"])

    def test_cli_headers_are_only_for_the_grok_host(self):
        self.assertTrue(ai._host(grok_sso.FALLBACK_BASE).endswith("grok.com"))
        self.assertFalse(ai._host("https://api.x.ai/v1").endswith("grok.com"))
        self.assertTrue(ai._fallback_status(RuntimeError("The model endpoint returned 403. no")))
        self.assertFalse(ai._fallback_status(RuntimeError("The model endpoint returned 401. no")))


if __name__ == "__main__":
    unittest.main()
