"""Audit participant-facing text for a 12px font floor and 4.5:1 contrast floor.

Scans the participant stylesheet and component styles for font-size declarations
below 12px (at a 16px root) and for low-contrast text colors against the known
surface backgrounds. Offline; no model calls.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STYLE = ROOT / 'frontend' / 'src' / 'style.css'
COMPONENTS = (ROOT / 'frontend' / 'src' / 'components').glob('*.vue')

FONT_RE = re.compile(r'font-size\s*:\s*([0-9.]+)(rem|em|px)')
COLOR_RE = re.compile(r'color\s*:\s*(#[0-9a-fA-F]{6})')


def px(value, unit, base=16.0):
    if unit == 'px':
        return float(value)
    if unit == 'rem':
        return float(value) * base
    if unit == 'em':
        return float(value) * base
    return None


def luminance(hex_color):
    value = hex_color.lstrip('#')
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground, background):
    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def scan(path):
    text = path.read_text(encoding='utf-8')
    violations = []
    for match in FONT_RE.finditer(text):
        size = px(match.group(1), match.group(2))
        if size is not None and size < 12:
            violations.append((path.name, f'font-size {match.group(0)} resolves to {size:.1f}px'))
    for match in COLOR_RE.finditer(text):
        color = match.group(1)
        # Only flag dark text on a light surface; light colors are inverted text
        # on darker surfaces and need a different (non-white) contrast basis.
        if luminance(color) <= 0.55 and contrast(color, '#ffffff') < 4.5:
            violations.append((path.name, f'color {color} is below 4.5:1 against white'))
    return violations


def main():
    targets = [STYLE] + [path for path in COMPONENTS if path.name not in
                         ('DeliveryReview.vue', 'IntentEpisodeReview.vue')]
    violations = []
    for path in targets:
        if path.exists():
            violations += scan(path)
    if violations:
        print('Text-floor violations:')
        for name, detail in violations:
            print(f'  {name}: {detail}')
        return 1
    print('No font-size or contrast violations found.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
