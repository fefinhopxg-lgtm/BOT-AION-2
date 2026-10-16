from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Member:
    name: str
    target_key: str
    region: tuple[int, int, int, int]
    color: tuple[int, int, int]


@dataclass(frozen=True)
class Rule:
    threshold: float
    key: str
    cooldown: float


def health_percent(image, color, tolerance=65):
    """Estimate a left-to-right solid bar; reject blank/fragmented readings.

    The calibrated rectangle must contain ONLY the bar interior, without text,
    borders or icons. This is a color measurement, not game telemetry.
    """
    image = image.convert("RGB")
    width, height = image.size
    if width < 10 or height < 2:
        return None
    columns = []
    for x in range(width):
        matches = sum(math.dist(image.getpixel((x, y)), color) <= tolerance
                      for y in range(height))
        columns.append(matches / height >= 0.5)
    if not columns[0]:
        return None  # Empty, hidden, dead or invalid: never infer a heal target.
    last = max(i for i, present in enumerate(columns) if present) + 1
    if sum(columns[:last]) / last < 0.95:
        return None
    return round(100 * last / width, 1)


class Planner:
    def __init__(self):
        self.last_cast = float("-inf")
        self.last_by_key = {}

    def choose(self, readings, rules, now, global_delay):
        if now - self.last_cast < global_delay:
            return None
        for member, hp in sorted(readings, key=lambda item: 101 if item[1] is None else item[1]):
            if hp is None or not 0 < hp <= 100:
                continue
            for rule in sorted(rules, key=lambda rule: rule.threshold):
                if hp <= rule.threshold and now - self.last_by_key.get(rule.key, float("-inf")) >= rule.cooldown:
                    return member, hp, rule
        return None

    def record(self, rule, now):
        self.last_cast = now
        self.last_by_key[rule.key] = now
