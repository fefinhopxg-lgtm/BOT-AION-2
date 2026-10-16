import unittest
from PIL import Image, ImageDraw
from aion_healer.core import Member, Planner, Rule, health_percent


class HealthTests(unittest.TestCase):
    def bar(self, percent):
        image = Image.new("RGB", (100, 10), "#151515")
        if percent:
            ImageDraw.Draw(image).rectangle((0, 0, percent - 1, 9), fill=(0, 200, 60))
        return image

    def test_health_levels(self):
        for percent in [1, 20, 30, 60, 80, 100]:
            with self.subTest(percent=percent):
                self.assertEqual(health_percent(self.bar(percent), (0, 200, 60)), percent)

    def test_empty_or_hidden_is_unknown(self):
        self.assertIsNone(health_percent(self.bar(0), (0, 200, 60)))

    def test_wrong_color_is_unknown(self):
        self.assertIsNone(health_percent(self.bar(100), (200, 0, 0)))

    def test_fragmented_region_is_unknown(self):
        image = self.bar(30)
        ImageDraw.Draw(image).rectangle((80, 0, 99, 9), fill=(0, 200, 60))
        self.assertIsNone(health_percent(image, (0, 200, 60)))

    def test_tiny_region_is_unknown(self):
        self.assertIsNone(health_percent(Image.new("RGB", (3, 3)), (0, 0, 0)))

    def test_small_color_variations(self):
        self.assertEqual(health_percent(self.bar(60), (2, 195, 65)), 60)


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.a = Member("A", "f1", (0, 0, 100, 10), (0, 200, 60))
        self.b = Member("B", "f2", (0, 20, 100, 10), (0, 200, 60))
        self.rules = [Rule(80, "3", 2), Rule(30, "1", 8), Rule(60, "2", 3)]
        self.planner = Planner()

    def choose(self, readings, now=0):
        return self.planner.choose(readings, self.rules, now, 1.5)

    def test_lowest_health_first_and_emergency_rule(self):
        member, hp, rule = self.choose([(self.a, 55), (self.b, 20)])
        self.assertEqual((member.name, hp, rule.key), ("B", 20, "1"))

    def test_global_delay(self):
        self.planner.record(self.rules[1], 0)
        self.assertIsNone(self.choose([(self.a, 10)], 1))

    def test_cooldown_falls_back_to_other_rule(self):
        self.planner.record(self.rules[1], 0)
        self.assertEqual(self.choose([(self.a, 20)], 2)[2].key, "2")

    def test_cooldown_expires(self):
        self.planner.record(self.rules[1], 0)
        self.assertEqual(self.choose([(self.a, 20)], 8)[2].key, "1")

    def test_unknown_dead_full_and_invalid_no_action(self):
        for hp in [None, 0, 100, -1, 101, float("nan")]:
            with self.subTest(hp=hp):
                self.assertIsNone(self.choose([(self.a, hp)]))

    def test_threshold_is_inclusive(self):
        self.assertEqual(self.choose([(self.a, 30)])[2].key, "1")

    def test_no_action_when_all_rules_cooling_down(self):
        for rule in self.rules:
            self.planner.record(rule, 0)
        self.assertIsNone(self.choose([(self.a, 20)], 1.6))

    def test_image_to_heal_end_to_end(self):
        image = Image.new("RGB", (100, 10), "black")
        ImageDraw.Draw(image).rectangle((0, 0, 24, 9), fill=self.a.color)
        hp = health_percent(image, self.a.color)
        self.assertEqual(self.choose([(self.a, hp)])[2].key, "1")


if __name__ == "__main__":
    unittest.main()
