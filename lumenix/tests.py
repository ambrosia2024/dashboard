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


class GrowthPotentialMathTests(SimpleTestCase):
    """The WP4 FSKX index: left Riemann sum of max(0, y - y0) up to t_eval."""

    def test_curve_auc_matches_hand_computation(self):
        from lumenix.services.growth_potential import curve_auc

        curve = [[0.0, 4.0], [10.0, 4.5], [20.0, 5.0], [30.0, 5.0]]
        # left sum: 0.0*10 + 0.5*10 + 1.0*10
        self.assertAlmostEqual(curve_auc(curve, 30.0), 15.0)

    def test_curve_auc_truncates_at_t_eval(self):
        from lumenix.services.growth_potential import curve_auc

        curve = [[0.0, 4.0], [10.0, 4.5], [20.0, 5.0], [30.0, 5.0]]
        # 0.0*10 + 0.5*5: the second step is clipped at t_eval=15
        self.assertAlmostEqual(curve_auc(curve, 15.0), 2.5)

    def test_decay_below_y0_contributes_nothing(self):
        from lumenix.services.growth_potential import curve_auc

        curve = [[0.0, 4.0], [10.0, 3.0], [20.0, 2.0]]
        self.assertAlmostEqual(curve_auc(curve, 20.0), 0.0)

    def test_degenerate_curves_return_none(self):
        from lumenix.services.growth_potential import curve_auc

        self.assertIsNone(curve_auc([], 48.0))
        self.assertIsNone(curve_auc([[0.0, 4.0]], 48.0))

    def test_interpolation_is_linear_and_bounded(self):
        from lumenix.services.growth_potential import interpolate

        samples = [[0.0, 0.0], [10.0, 100.0]]
        self.assertAlmostEqual(interpolate(samples, 2.5), 25.0)
        self.assertAlmostEqual(interpolate(samples, 0.0), 0.0)
        self.assertIsNone(interpolate(samples, -0.1), "no extrapolation below the sampled range")
        self.assertIsNone(interpolate(samples, 10.1), "no extrapolation above the sampled range")
        self.assertIsNone(interpolate(samples, float("nan")))
        self.assertIsNone(interpolate(samples, None))
