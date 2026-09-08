"""Figures as SVG so matplotlib is not required."""

from __future__ import annotations

from pathlib import Path


def write_svg_bar(path: Path, title: str, labels: list[str], values: list[float], ylabel: str) -> None:
    width = max(640, 28 * len(labels) + 80)
    height = 360
    vmax = max(values) if values else 1.0
    vmax = vmax if vmax > 0 else 1.0
    bar_w = (width - 80) / max(len(labels), 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        f'<rect width="100%" height="100%" fill="white"/>',
        f'<text x="12" y="24" font-size="16">{title}</text>',
        f'<text x="12" y="44" font-size="11">{ylabel}</text>',
    ]
    for i, (label, value) in enumerate(zip(labels, values)):
        h = (value / vmax) * 260
        x = 50 + i * bar_w
        y = 320 - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w*0.7:.1f}" height="{h:.1f}" fill="#335577"/>')
        parts.append(f'<text x="{x:.1f}" y="340" font-size="8" transform="rotate(-60 {x:.1f} 340)">{label}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_architecture_svg(path: Path) -> None:
    path.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" width="920" height="420">
<rect width="100%" height="100%" fill="white"/>
<text x="16" y="28" font-size="16">Deterministic mailbox workflow versus monolithic controller</text>
<text x="16" y="48" font-size="12">No runtime LLM. Same encode/solve/validate callables. Evidence type: policy_replay / local software.</text>
<rect x="40" y="80" width="160" height="60" fill="#eef5ff" stroke="#335577"/>
<text x="50" y="115" font-size="12">Coordinator mailbox</text>
<rect x="260" y="80" width="160" height="60" fill="#eef5ff" stroke="#335577"/>
<text x="275" y="115" font-size="12">Encoder mailbox</text>
<rect x="480" y="80" width="160" height="60" fill="#eef5ff" stroke="#335577"/>
<text x="490" y="115" font-size="12">Solver adapter</text>
<rect x="700" y="80" width="180" height="60" fill="#eef5ff" stroke="#335577"/>
<text x="710" y="115" font-size="12">Validator mailbox</text>
<line x1="200" y1="110" x2="260" y2="110" stroke="#333" marker-end="url(#arrow)"/>
<line x1="420" y1="110" x2="480" y2="110" stroke="#333"/>
<line x1="640" y1="110" x2="700" y2="110" stroke="#333"/>
<text x="40" y="180" font-size="12">Messages: encode request, candidates, timeout, specification update, accept/fallback/abstain.</text>
<rect x="40" y="220" width="840" height="70" fill="#fff8ee" stroke="#885522"/>
<text x="50" y="250" font-size="13">Monolithic controller baseline: coordinator.encode(); solver.solve(); validator.validate() on the same objects, no mailboxes.</text>
<text x="50" y="272" font-size="12">Compare functional equivalence and orchestration overhead. Do not assume actors improve decision quality.</text>
<text x="40" y="330" font-size="12">Hardware SamplerV2 is an interchangeable solver adapter. Dispatch is experimental, not an economic recommendation.</text>
<text x="40" y="355" font-size="12">P0 unguarded modal; P1 feasibility+incumbent; P2 strict version; P3 compatible revalidation. Exact oracle is not a hidden fallback.</text>
<text x="40" y="390" font-size="12">Local hashes check integrity; they do not independently prove IBM provenance.</text>
</svg>
""",
        encoding="utf-8",
    )
