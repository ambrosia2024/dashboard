from django.test import SimpleTestCase, override_settings

from lumenix.views.chart_ai import (
    _delta_reasoning,
    _scaleway_chat_url,
    _scaleway_request_payload,
)


class ScalewayChatConfigurationTests(SimpleTestCase):
    @override_settings(
        SCW_AI_BASE_URL="https://api.scaleway.ai/project-id/v1/",
        SCW_AI_MODEL="qwen3.5-397b-a17b",
        SCW_AI_MAX_TOKENS=16384,
        SCW_AI_TEMPERATURE=0.6,
        SCW_AI_TOP_P=0.95,
        SCW_AI_PRESENCE_PENALTY=0,
    )
    def test_scaleway_request_configuration(self):
        self.assertEqual(
            _scaleway_chat_url(),
            "https://api.scaleway.ai/project-id/v1/chat/completions",
        )

        payload = _scaleway_request_payload("system prompt", "user prompt")

        self.assertEqual(payload["model"], "qwen3.5-397b-a17b")
        self.assertEqual(payload["max_tokens"], 16384)
        self.assertEqual(payload["temperature"], 0.6)
        self.assertEqual(payload["top_p"], 0.95)
        self.assertEqual(payload["presence_penalty"], 0)
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["response_format"], {"type": "text"})
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": "system prompt"},
                {"role": "user", "content": "user prompt"},
            ],
        )


class ScalewayReasoningTests(SimpleTestCase):
    """qwen3.5-397b-a17b reasons by default, which is what made answers feel slow."""

    @override_settings(SCW_AI_REASONING_EFFORT="none")
    def test_reasoning_disabled_by_default(self):
        payload = _scaleway_request_payload("system prompt", "user prompt")
        self.assertEqual(payload["reasoning_effort"], "none")

    @override_settings(SCW_AI_REASONING_EFFORT="medium")
    def test_reasoning_effort_is_configurable(self):
        payload = _scaleway_request_payload("system prompt", "user prompt")
        self.assertEqual(payload["reasoning_effort"], "medium")

    @override_settings(SCW_AI_REASONING_EFFORT="")
    def test_blank_effort_omits_the_field(self):
        """An empty value must leave the upstream default untouched."""
        payload = _scaleway_request_payload("system prompt", "user prompt")
        self.assertNotIn("reasoning_effort", payload)

    def test_delta_reasoning_accepts_both_spellings(self):
        self.assertEqual(_delta_reasoning({"reasoning": "a"}), "a")
        self.assertEqual(_delta_reasoning({"reasoning_content": "b"}), "b")
        self.assertIsNone(_delta_reasoning({"content": "c"}))
