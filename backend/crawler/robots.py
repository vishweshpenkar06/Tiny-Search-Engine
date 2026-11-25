import re
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class RobotRule:
    path: str
    allowed: bool


@dataclass(frozen=True)
class RobotsRules:
    rules: tuple[RobotRule, ...] = ()
    crawl_delay: float | None = None

    def is_allowed(self, url: str, user_agent: str = "*") -> bool:
        target = urlsplit(url)
        path = target.path or "/"
        if target.query:
            path = f"{path}?{target.query}"
        best_length = -1
        allowed = True
        for rule in self.rules:
            pattern = rule.path
            exact = pattern.endswith("$")
            if exact:
                pattern = pattern[:-1]
            expression = "^" + re.escape(pattern).replace(r"\*", ".*")
            expression += "$" if exact else ""
            if re.match(expression, path) is None:
                continue
            length = len(pattern)
            if length > best_length or (length == best_length and rule.allowed and not allowed):
                best_length = length
                allowed = rule.allowed
        return allowed

    def delay_for(self, user_agent: str = "*") -> float:
        return max(0.0, self.crawl_delay or 0.0)


def parse_robots(text: str, user_agent: str = "*") -> RobotsRules:
    groups: list[tuple[tuple[str, ...], tuple[RobotRule, ...], float | None]] = []
    agents: list[str] = []
    rules: list[RobotRule] = []
    delay: float | None = None

    def flush() -> None:
        nonlocal agents, rules, delay
        if agents or rules or delay is not None:
            groups.append((tuple(agents), tuple(rules), delay))
        agents = []
        rules = []
        delay = None

    for raw_line in (text or "").replace("\r\n", "\n").split("\n"):
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if rules or delay is not None:
                flush()
            agents.append(value.lower())
        elif key in ("allow", "disallow"):
            if not agents:
                agents = ["*"]
            if not value:
                continue
            rules.append(RobotRule(path=value, allowed=key == "allow"))
        elif key in ("crawl-delay", "crawldelay"):
            if not agents:
                agents = ["*"]
            try:
                delay = float(value)
            except ValueError:
                continue

    flush()

    wanted = (user_agent or "*").lower()
    selected = [
        group
        for group in groups
        if any(agent == "*" for agent in group[0])
    ]
    named = [
        group
        for group in groups
        if any(agent != "*" and wanted.startswith(agent) for agent in group[0])
    ]
    if named:
        selected = named

    matching_rules: list[RobotRule] = []
    delays: list[float] = []
    for _, group_rules, group_delay in selected:
        matching_rules.extend(group_rules)
        if group_delay is not None:
            delays.append(group_delay)
    return RobotsRules(
        rules=tuple(matching_rules),
        crawl_delay=max(delays) if delays else None,
    )
