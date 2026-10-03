#!/usr/bin/env python3
"""Render the public GitHub contribution calendar in warm ink tones."""

import argparse
from datetime import date, timedelta
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

BACKGROUND = "#F5F2EA"
PALETTE = ("#E1DED5", "#C6C4BA", "#959A90", "#646E65", "#3E4A42")


class CalendarParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = []
        self.counts = {}
        self.tip_id = None
        self.tip_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs:
            self.days.append({
                "date": date.fromisoformat(attrs["data-date"]),
                "level": int(attrs["data-level"]),
                "id": attrs.get("id", ""),
            })
        if tag == "tool-tip":
            self.tip_id = attrs.get("for")
            self.tip_text = []

    def handle_data(self, text):
        if self.tip_id:
            self.tip_text.append(text)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tip_id:
            text = "".join(self.tip_text).strip()
            first = text.split()[0].replace(",", "")
            self.counts[self.tip_id] = int(first) if first.isdigit() else 0
            self.tip_id = None


def calendar_svg(days, counts, username):
    days = sorted(days, key=lambda day: day["date"])
    first, last = days[0]["date"], days[-1]["date"]
    start = first - timedelta(days=(first.weekday() + 1) % 7)
    weeks = (last - start).days // 7 + 1
    step = 13.1
    origin = (900 - (weeks - 1) * step) / 2
    y0 = 89
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="250" viewBox="0 0 900 250" role="img" aria-labelledby="calendar-title calendar-desc">',
             "<title id=\"calendar-title\">GitHub contributions</title>",
             f"<desc id=\"calendar-desc\">{escape(username)} public GitHub contributions, {first.isoformat()} to {last.isoformat()}. Darker ink means more contributions.</desc>",
             f'<rect width="900" height="250" fill="{BACKGROUND}"/>',
             "<defs><filter id=\"calendar-soft\" x=\"-50%\" y=\"-50%\" width=\"200%\" height=\"200%\"><feGaussianBlur stdDeviation=\"0.55\"/></filter></defs>",
             "<style>.calendar-week{animation:calendar-breathe 19s ease-in-out infinite}@keyframes calendar-breathe{0%,100%{opacity:.72}35%,70%{opacity:1}}@media(prefers-reduced-motion:reduce){.calendar-week{animation:none}}</style>",
             f'<text x="{900-origin:.1f}" y="37" text-anchor="end" font-family="Georgia,serif" font-size="10" letter-spacing="1.1" fill="#989C92">{first:%Y.%m} — {last:%Y.%m}</text>']
    month_seen = None
    for day in days:
        day_date = day["date"]
        week = (day_date - start).days // 7
        if day_date.month != month_seen:
            if day_date.day == 1:
                parts.append(f'<text x="{origin + week * step:.1f}" y="68" font-family="Georgia,serif" font-size="9" fill="#A0A497">{day_date.month:02d}</text>')
            month_seen = day_date.month
    for week in range(weeks):
        parts.append(f'<g class="calendar-week" style="animation-delay:{-week * .24:.2f}s">')
        for day in days:
            day_date = day["date"]
            if (day_date - start).days // 7 != week:
                continue
            level = day["level"]
            x = origin + week * step
            y = y0 + ((day_date.weekday() + 1) % 7) * step
            count = counts.get(day["id"])
            label = f"{day_date.isoformat()}: {count} contributions" if count is not None else f"{day_date.isoformat()}: contribution level {level}"
            radius = 2.8 if level == 0 else 3.15
            parts.append(f'<g><title>{escape(label)}</title>')
            if level:
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius + .45}" fill="{PALETTE[level]}" opacity=".24" filter="url(#calendar-soft)"/>')
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{PALETTE[level]}"/></g>')
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def compose(signature, calendar):
    signature_height = float(ET.fromstring(signature).attrib["viewBox"].split()[3])
    calendar_height = float(ET.fromstring(calendar).attrib["viewBox"].split()[3])
    signature = signature[signature.index("<svg"):]
    calendar = calendar[calendar.index("<svg"):].replace("<svg ", f'<svg y="{signature_height:g}" ', 1)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{signature_height + calendar_height:g}" viewBox="0 0 900 {signature_height + calendar_height:g}">\n'
            f'<title>{escape("shuiqinhh — ink and time")}</title>\n'
            f'<rect width="900" height="100%" fill="{BACKGROUND}"/>\n'
            + signature + "\n" + calendar + "\n</svg>\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="shuiqinhh")
    parser.add_argument("--assets", type=Path, default=Path("assets"))
    parser.add_argument("--html", type=Path, help="Use a previously fetched public calendar HTML file")
    args = parser.parse_args()
    if args.html:
        source = args.html.read_text(encoding="utf-8")
    else:
        request = Request(f"https://github.com/users/{args.username}/contributions", headers={"User-Agent": "ink-profile", "Accept": "text/html"})
        with urlopen(request, timeout=30) as response:
            source = response.read().decode("utf-8")
    calendar = CalendarParser()
    calendar.feed(source)
    svg = calendar_svg(calendar.days, calendar.counts, args.username)
    signature = (args.assets / "ink-signature.svg").read_text(encoding="utf-8")
    profile = compose(signature, svg)
    args.assets.mkdir(parents=True, exist_ok=True)
    (args.assets / "ink-commits.svg").write_text(svg, encoding="utf-8")
    (args.assets / "ink-profile.svg").write_text(profile, encoding="utf-8")
    print(f"Rendered {len(calendar.days)} real contribution days for {args.username}")


if __name__ == "__main__":
    main()
