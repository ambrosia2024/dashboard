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
            for code in ("ZZ99", "ZZ88"):
                rows.append(PathogenConcentrationRecord(
                    plant="lettuce", pathogen="salmonella", nuts_code=code,
                    observed_on=date(year, 6, 1), pathogen_model_value=5.0,
                    growth_potential_auc=(10.0 if year < 2010 else 30.0) + (0.0 if code == "ZZ99" else 5.0),
                    temperature_c=(12.0 if year < 2010 else 15.0), status=1,
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

    def test_month_carries_temperature_and_deltas(self):
        """The feedback asked for the temperature change beside the index change."""
        self.client.force_login(self.user)
        data = self.client.get(reverse("assessment-growth-comparison", args=[self.assessment.id])).json()
        june_base = next(m for m in data["baseline"]["months"] if m["month"] == 6)
        june_fut = next(m for m in data["future"]["months"] if m["month"] == 6)
        june_delta = next(d for d in data["deltas"] if d["month"] == 6)
        self.assertEqual(june_base["temperature_c"], 12.0)
        self.assertEqual(june_fut["temperature_c"], 15.0)
        self.assertEqual(june_delta["delta_temperature_c"], 3.0)
        self.assertEqual(june_delta["delta"], 20.0)
        self.assertEqual(june_delta["delta_pct"], 200.0)
        self.assertEqual(data["baseline"]["mean_temperature_c"], 12.0)

    def test_regional_change_map(self):
        self.client.force_login(self.user)
        data = self.client.get(reverse("assessment-regional-change", args=[self.assessment.id])).json()
        self.assertEqual(data["regions"], 2)
        self.assertEqual(data["selected"], "ZZ99")
        self.assertEqual(data["values"]["ZZ99"]["baseline"], 10.0)
        self.assertEqual(data["values"]["ZZ99"]["future"], 30.0)
        self.assertEqual(data["values"]["ZZ99"]["delta"], 20.0)
        self.assertEqual(data["values"]["ZZ88"]["delta"], 20.0)
        self.assertEqual(data["values"]["ZZ99"]["delta_temperature_c"], 3.0)

    def test_relative_change_floor_suppresses_tiny_baselines(self):
        """A near-zero baseline must not report a vast percentage change."""
        from lumenix.models import PathogenConcentrationRecord

        PathogenConcentrationRecord.objects.filter(
            nuts_code="ZZ99", observed_on__year__lt=2010
        ).update(growth_potential_auc=0.01)
        self.client.force_login(self.user)
        data = self.client.get(reverse("assessment-growth-comparison", args=[self.assessment.id])).json()
        june_delta = next(d for d in data["deltas"] if d["month"] == 6)
        self.assertIsNotNone(june_delta["delta"], "the absolute change is still reported")
        self.assertIsNone(june_delta["delta_pct"], "the relative change is suppressed below the floor")

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


from datetime import timedelta

from lumenix.services.cardinal_growth import INDICES, mu, response_curve


class CardinalModelMathTests(SimpleTestCase):
    """The Rosso (1993) CTMI as used for the Europe growth map."""

    def setUp(self):
        self.ecoli = INDICES["ecoli"]

    def test_cardinal_points(self):
        self.assertAlmostEqual(mu(self.ecoli.t_opt, self.ecoli), 1.0)
        self.assertEqual(mu(self.ecoli.t_min, self.ecoli), 0.0)
        self.assertEqual(mu(self.ecoli.t_max, self.ecoli), 0.0)
        self.assertEqual(mu(-5.0, self.ecoli), 0.0, "too cold: no growth")
        self.assertEqual(mu(50.0, self.ecoli), 0.0, "too hot: no growth")
        self.assertIsNone(mu(None, self.ecoli))
        self.assertIsNone(mu(float("nan"), self.ecoli))

    def test_rises_to_the_optimum_and_falls_after(self):
        rising = [mu(t, self.ecoli) for t in range(7, 37)]
        self.assertEqual(rising, sorted(rising))
        self.assertGreater(mu(40.0, self.ecoli), mu(44.0, self.ecoli))
        self.assertTrue(all(0.0 <= mu(t / 10, self.ecoli) <= 1.0 for t in range(-100, 500)))

    def test_registered_parameters_are_valid_for_the_ctmi(self):
        # The model is only defined for Topt above the midpoint of Tmin and Tmax.
        for index in INDICES.values():
            self.assertLess(index.t_min, index.t_opt)
            self.assertLess(index.t_opt, index.t_max)
            self.assertGreater(index.t_opt, (index.t_min + index.t_max) / 2, index.key)

    def test_response_curve_samples_the_plot_range(self):
        curve = response_curve(self.ecoli)
        self.assertEqual(curve[0], [-10.0, 0.0])
        self.assertEqual(curve[-1], [50.0, 0.0])
        self.assertIn([36.0, 1.0], curve)


class CardinalGrowthDataTests(TestCase):
    """Frames and the monthly table, on synthetic temperatures with known growth rates."""

    @classmethod
    def setUpTestData(cls):
        from lumenix.models import PathogenConcentrationRecord, UserProfile

        cls.user = get_user_model().objects.create_user("mapper", password="x", first_name="Map", last_name="User")
        UserProfile.objects.update_or_create(user=cls.user, defaults={"role": "farmer"})
        cls.ecoli = INDICES["ecoli"]

        def record(code, day, temperature, pathogen="salmonella"):
            return PathogenConcentrationRecord(
                plant="lettuce", pathogen=pathogen, nuts_code=code, observed_on=day,
                temperature_c=temperature, status=1,
            )

        rows = []
        day = date(2001, 1, 1)
        while day <= date(2003, 12, 31):
            # ZZ01 is warm and one degree warmer each year; ZZ02 is below Tmin.
            rows.append(record("ZZ01", day, 20.0 + (day.year - 2001)))
            rows.append(record("ZZ02", day, 4.0))
            day += timedelta(days=1)
        for d in range(10):
            # A second crop + hazard pair on the same region-days: must count once.
            rows.append(record("ZZ01", date(2001, 1, 1) + timedelta(days=d), 20.0, pathogen="listeria"))
            # ZZ03 has only ten days: too few for a month or a year.
            rows.append(record("ZZ03", date(2001, 1, 1) + timedelta(days=d), 25.0))
        PathogenConcentrationRecord.objects.bulk_create(rows)
        # A day without a climate input.
        PathogenConcentrationRecord.objects.filter(
            nuts_code="ZZ01", observed_on=date(2001, 2, 1)
        ).update(temperature_c=float("nan"))

    def value(self, data, label, code, key="mu"):
        return data[key][data["frames"].index(label)][data["regions"].index(code)]

    def test_day_frames_match_the_python_formula(self):
        from lumenix.services.cardinal_growth import frames

        data = frames(self.ecoli, "day", 2001, 2001)
        self.assertEqual(len(data["frames"]), 365)
        self.assertEqual(data["regions"], ["ZZ01", "ZZ02", "ZZ03"])
        self.assertAlmostEqual(self.value(data, "2001-01-05", "ZZ01"), mu(20.0, self.ecoli), delta=0.001)
        self.assertAlmostEqual(self.value(data, "2001-01-05", "ZZ03"), mu(25.0, self.ecoli), delta=0.001)
        self.assertEqual(self.value(data, "2001-01-05", "ZZ02"), 0.0)
        self.assertIsNone(self.value(data, "2001-02-01", "ZZ01"), "a NaN day has no value")
        self.assertEqual(self.value(data, "2001-01-05", "ZZ01", "temperature"), 20.0)

    def test_monthly_build_counts_each_day_once(self):
        from lumenix.models import CardinalGrowthMonthly
        from lumenix.services.cardinal_growth import build_monthly

        build_monthly(self.ecoli)
        jan = CardinalGrowthMonthly.objects.get(index_key="ecoli", nuts_code="ZZ01", month=date(2001, 1, 1))
        self.assertEqual(jan.days, 31, "the second crop + hazard pair must not add days")
        self.assertAlmostEqual(jan.mu_mean, mu(20.0, self.ecoli), places=6)
        feb = CardinalGrowthMonthly.objects.get(index_key="ecoli", nuts_code="ZZ01", month=date(2001, 2, 1))
        self.assertEqual(feb.days, 27, "the NaN day is skipped")

        rows = CardinalGrowthMonthly.objects.count()
        build_monthly(self.ecoli)
        self.assertEqual(CardinalGrowthMonthly.objects.count(), rows, "a rebuild replaces, never duplicates")

        from lumenix.models import PathogenConcentrationRecord
        PathogenConcentrationRecord.objects.filter(nuts_code="ZZ03").delete()
        build_monthly(self.ecoli)
        self.assertFalse(CardinalGrowthMonthly.objects.filter(nuts_code="ZZ03").exists())

    def test_month_step_leaves_thin_months_empty(self):
        from lumenix.services.cardinal_growth import build_monthly, frames

        build_monthly(self.ecoli)
        data = frames(self.ecoli, "month", 2001, 2001)
        self.assertEqual(data["frames"][0], "2001-01")
        self.assertEqual(len(data["frames"]), 12)
        self.assertNotIn("ZZ03", data["regions"], "ten days do not make a month")
        self.assertAlmostEqual(self.value(data, "2001-01", "ZZ01"), mu(20.0, self.ecoli), delta=0.001)

    def test_year_step_and_rolling_window(self):
        from lumenix.services.cardinal_growth import build_monthly, frames

        build_monthly(self.ecoli)
        yearly = frames(self.ecoli, "year", 2001, 2003)
        self.assertEqual(yearly["frames"], ["2001", "2002", "2003"])
        self.assertNotIn("ZZ03", yearly["regions"], "ten days do not make a year")
        for year, temperature in ((2001, 20.0), (2002, 21.0), (2003, 22.0)):
            self.assertAlmostEqual(self.value(yearly, str(year), "ZZ01"), mu(temperature, self.ecoli), delta=0.001)

        windowed = frames(self.ecoli, "year", 2001, 2003, window=3)
        self.assertEqual(windowed["frames"], ["2001–2003"])
        expected = (mu(20.0, self.ecoli) * 364 + mu(21.0, self.ecoli) * 365 + mu(22.0, self.ecoli) * 365) / 1094
        self.assertAlmostEqual(self.value(windowed, "2001–2003", "ZZ01"), expected, delta=0.001)

    def test_gaps_name_the_missing_periods(self):
        from lumenix.models import PathogenConcentrationRecord
        from lumenix.services.cardinal_growth import build_monthly, frames

        PathogenConcentrationRecord.objects.filter(observed_on__range=(date(2002, 7, 1), date(2002, 12, 31))).delete()
        build_monthly(self.ecoli)
        self.assertEqual(frames(self.ecoli, "day", 2002, 2002)["gaps"], [{"from": "2002-07-01", "to": "2002-12-31", "frames": 184}])
        self.assertEqual(frames(self.ecoli, "week", 2002, 2002)["gaps"], [{"from": "2002-07-01", "to": "2002-12-23", "frames": 26}])
        self.assertEqual(frames(self.ecoli, "month", 2002, 2002)["gaps"], [{"from": "2002-07", "to": "2002-12", "frames": 6}])
        yearly = frames(self.ecoli, "year", 2001, 2003)
        self.assertEqual(yearly["frames"], ["2001", "2003"])
        self.assertEqual(yearly["gaps"], [{"from": "2002", "to": "2002", "frames": 1}])
        self.assertEqual(yearly["short_years"], [2002])
        self.assertEqual(frames(self.ecoli, "day", 2001, 2001)["gaps"], [], "one region's NaN day is not a gap")

    def test_endpoint_validates_the_period(self):
        url = reverse("pathogen-growth-frames")
        self.assertEqual(self.client.get(url, {"step": "day", "start": "2001", "end": "2001"}).status_code, 302)
        self.client.force_login(self.user)

        resp = self.client.get(url, {"step": "day", "start": "2001", "end": "2002"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("at most 1 year", resp.json()["error"])
        resp = self.client.get(url, {"step": "year", "start": "2001", "end": "2003", "window": "5"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("at least 5 years", resp.json()["error"])
        self.assertEqual(self.client.get(url, {"index": "nope", "start": "2001", "end": "2001"}).status_code, 400)
        self.assertEqual(self.client.get(url, {"step": "hour", "start": "2001", "end": "2001"}).status_code, 400)

        data = self.client.get(url, {"step": "week", "start": "2001", "end": "2001"}).json()
        self.assertEqual(data["index"]["key"], "ecoli")
        self.assertEqual(len(data["mu"]), len(data["frames"]))
        self.assertEqual(len(data["mu"][0]), len(data["regions"]))

    def test_month_step_before_a_build_says_so(self):
        self.client.force_login(self.user)
        data = self.client.get(reverse("pathogen-growth-frames"), {"step": "month", "start": "2001", "end": "2001"}).json()
        self.assertEqual(data["frames"], [])
        self.assertIn("build_cardinal_growth", data["message"])

    def test_page_renders_with_its_config(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("pathogen-growth"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="gm-config"')
        self.assertContains(resp, "What this map is made of")
        self.assertNotContains(resp, "SCiO", msg_prefix="no partner names on the page")
        self.assertEqual(resp.context["default_year"], 2001, "2000 is not in the data, so the first year is used")
