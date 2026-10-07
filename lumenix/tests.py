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


from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class GrowthComparisonEndpointTests(TestCase):
    """The baseline-versus-future endpoint, on synthetic records with known AUC."""

    @classmethod
    def setUpTestData(cls):
        from lumenix.models import AssessmentRun, PathogenConcentrationRecord

        from lumenix.models import UserProfile

        # A complete profile, or EnforceProfileCompletionMiddleware redirects
        # every page to the profile/preferences flow instead of answering.
        cls.user = get_user_model().objects.create_user(
            "tester", password="x", first_name="Test", last_name="User"
        )
        UserProfile.objects.update_or_create(user=cls.user, defaults={"role": "farmer"})

        from lumenix.models import Concept, Vocabulary

        vocab = Vocabulary.objects.create(id="plants")
        crop = Concept.objects.create(
            vocabulary=vocab, uri="https://example.org/vocab#concept/plant/lettuce"
        )
        hazard = Concept.objects.create(
            vocabulary=vocab, uri="https://example.org/vocab#concept/pathogen/salmonella"
        )
        rows = []
        # June 1st of every year 2000-2019: index 10 in the first decade, 30 in
        # the second, so the window means are unambiguous.
        for year in range(2000, 2020):
            rows.append(PathogenConcentrationRecord(
                plant="lettuce", pathogen="salmonella", nuts_code="ZZ99",
                observed_on=date(year, 6, 1), pathogen_model_value=5.0,
                growth_potential_auc=10.0 if year < 2010 else 30.0, status=1,
            ))
        PathogenConcentrationRecord.objects.bulk_create(rows)
        cls.assessment = AssessmentRun.objects.create(
            user=cls.user, name="t", nuts2_code="ZZ99", nuts2_name="Testland",
            crop=crop, hazard=hazard,
            start_date=date(2000, 1, 1), end_date=date(2019, 12, 31),
            resolution="yearly", run_status="completed", snapshot={},
        )

    def test_split_defaults_and_window_means(self):
        self.client.force_login(self.user)
        data = self.client.get(reverse("assessment-growth-comparison", args=[self.assessment.id])).json()
        self.assertEqual((data["baseline"]["start"], data["baseline"]["end"]), (2000, 2009))
        self.assertEqual((data["future"]["start"], data["future"]["end"]), (2010, 2019))
        june_base = next(m for m in data["baseline"]["months"] if m["month"] == 6)
        june_fut = next(m for m in data["future"]["months"] if m["month"] == 6)
        self.assertEqual(june_base["value"], 10.0)
        self.assertEqual(june_fut["value"], 30.0)
        self.assertIsNone(next(m for m in data["baseline"]["months"] if m["month"] == 1)["value"])

    def test_short_window_is_refused(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse("assessment-growth-comparison", args=[self.assessment.id]),
            {"base_start": "2000", "base_end": "2002"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("at least 5 years", resp.json()["error"])

    def test_snapshot_upgrade_waits_for_backfill(self):
        from lumenix.models import PathogenConcentrationRecord
        from lumenix.views.assessment import _ensure_snapshot_schema

        PathogenConcentrationRecord.objects.filter(nuts_code="ZZ99").update(growth_potential_auc=None)
        self.assessment.snapshot = {"schema": 1, "series": [{"date": "2000-01-01", "value": 5.0}]}
        self.assessment.save(update_fields=["snapshot"])
        snap = _ensure_snapshot_schema(self.assessment)
        self.assertEqual(snap.get("schema"), 1, "old snapshot must survive until the index is backfilled")
