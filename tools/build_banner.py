"""Generates the attention-arc banner used at the top of the profile README.

The banner is an arc diagram of one attention head over a 20-token sequence:
dots on a baseline are tokens, arcs above are attention weights. On load the
baseline draws itself, the name fades up, and the arcs draw outward token by
token from left to right, then stay. It runs once and settles -- an infinite
loop next to a profile is motion the reader cannot dismiss.

Because every arc is still on screen when the animation ends, the edge set has
to be sparse and varied. A denser pattern was fine while only three queries were
lit at a time, but as a resting state it collapses into a scalloped fence.

Everything animates through CSS *inside* the SVG. That is the one animation
technique that survives GitHub: README <script> and <style> are stripped by the
HTML sanitizer, but an SVG referenced as an image is rendered by the browser as
an image, where declarative CSS animation still runs. The same sandbox blocks
external requests, so the type stack has to be fonts already on the machine --
no webfonts, hence GitHub's own ui-monospace stack rather than Space Mono.

Four files, one per (theme, motion) pair. Both axes have to be resolved by the
README rather than by the SVG:

  * Theme, because an SVG loaded via <img> gets no signal about the page
    background it is sitting on.
  * Motion, because `@media (prefers-reduced-motion: reduce)` *inside* an
    image-mode SVG does not track the viewer's actual preference -- measured in
    Chromium, it matched even with the host page reporting no-preference, which
    froze the animation for everyone. Selecting a still file from the README's
    <picture> puts that query back in the page context, where it works.

Height is deliberately tight: the whole README has to clear the fold so the
contribution graph is visible without scrolling.

Run:  python tools/build_banner.py
"""

import pathlib
import random

W, H = 880, 152
N_TOKENS = 20
X0, X1 = 48, 832          # first and last token centre
BASE_Y = 128              # the token baseline; arcs bulge above it
MAX_ARC_H = 74

RULE_DRAW = 0.8           # seconds for the baseline to draw
ARC_DRAW = 0.9            # seconds for one arc to draw
STAGGER = 0.11            # seconds between adjacent tokens
ARC_START = 0.35          # arcs begin after the rule is underway

THEMES = {
    "light": dict(ink="#1a1a1a", muted="#8a8a8a", rule="#d8d8d8"),
    "dark": dict(ink="#e6edf3", muted="#8b949e", rule="#30363d"),
}

MONO = ("ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, "
        "'Liberation Mono', monospace")


def token_x(i):
    return X0 + (X1 - X0) * i / (N_TOKENS - 1)


def edges():
    """Attention edges as (query, key, weight), weight in 0..1.

    Around fifteen edges, and the sparseness is the whole point. Giving every
    token an outgoing edge -- even with mixed spans -- chains the arcs into one
    continuous arcade, which is the scalloped fence this diagram keeps trying to
    become. Skipping tokens is what breaks it up, so the walk below advances by
    one to three tokens at a time and leaves deliberate gaps.

    Spans are drawn from a wide set for the same reason: arc height scales with
    span, so a narrow span distribution yields a row of near-identical arches.
    A few queries also keep a thin edge back to token 0 -- the attention sink
    that shows up in practically every trained transformer.
    """
    rng = random.Random(11)   # fixed seed: regenerating must not churn the diff
    out = []

    spans = (1, 2, 3, 4, 6, 8, 11, 14)
    q, last = 0, None
    while q < N_TOKENS:
        # Only spans that stay inside the sequence. Sampling first and dropping
        # what overshoots thins the right-hand side badly, since that is exactly
        # where the long spans no longer fit.
        fits = [s for s in spans if q + s < N_TOKENS]
        if not fits:
            break
        # Prefer a span unlike its neighbour: adjacent arcs of similar span sit
        # at near-identical heights and read as a repeat.
        varied = [s for s in fits if last is None or abs(s - last) >= 2]
        span = rng.choice(varied or fits)
        w = max(0.32, 0.95 - span * 0.06)
        out.append((q, q + span, w * rng.uniform(0.85, 1.0)))
        last = span
        q += rng.choice((1, 2, 2, 3))

    # Two sinks, not three -- they all land on token 0, so a third just thickens
    # the same bundle at the left edge without adding information.
    for q in (7, 15):
        out.append((q, 0, rng.uniform(0.24, 0.38)))

    return out


def arc_path(q, k):
    """Path running query -> key, always bulging above the baseline.

    Direction matters: because stroke-dashoffset draws a path from its start,
    beginning at the query makes each edge appear to grow out of its own token.
    """
    xq, xk = token_x(q), token_x(k)
    dx = abs(xk - xq)
    rx = dx / 2
    ry = 10 + (MAX_ARC_H - 10) * (dx / (X1 - X0)) ** 0.62
    sweep = 1 if xk > xq else 0
    return (f"M{xq:.1f},{BASE_Y} A{rx:.1f},{ry:.1f} 0 0,{sweep} "
            f"{xk:.1f},{BASE_Y}")


def build(theme_name, animated):
    t = THEMES[theme_name]

    if animated:
        motion = f"""
  .rule {{ stroke-dasharray: 100; stroke-dashoffset: 100;
          animation: draw {RULE_DRAW}s ease-out forwards; }}
  .name {{ opacity: 0; animation: rise .6s ease-out .15s forwards; }}
  .arc  {{ opacity: 0; animation: sweep {ARC_DRAW}s ease-out forwards; }}
  .dot circle {{ opacity: 0; animation: pop .45s ease-out forwards; }}
  .cap  {{ opacity: 0; animation: fade .6s ease-out forwards; }}

  @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
  @keyframes rise {{
    from {{ opacity: 0; transform: translateY(4px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes sweep {{
    0%   {{ stroke-dashoffset: 100; opacity: 0; }}
    15%  {{ opacity: var(--w); }}
    100% {{ stroke-dashoffset: 0; opacity: var(--w); }}
  }}
  @keyframes pop {{
    from {{ opacity: 0; transform: scale(.4); }}
    to   {{ opacity: 1; transform: scale(1); }}
  }}
  @keyframes fade {{ to {{ opacity: 1; }} }}"""
    else:
        # Reduced motion: the settled end state, painted directly.
        motion = """
  .arc { opacity: var(--w); stroke-dashoffset: 0; }"""

    p = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        f'aria-label="michael tarekegn - an attention arc diagram">'
    )
    p.append("<!-- generated by tools/build_banner.py - edit that, not this -->")
    p.append(f"""<style>
  .t {{ font-family: {MONO}; }}
  .name {{ font-size: 27px; fill: {t['ink']}; letter-spacing: .5px; }}
  .cap  {{ font-size: 9.5px; fill: {t['muted']}; letter-spacing: 1.1px; }}
  .rule {{ stroke: {t['rule']}; stroke-width: 1; fill: none; }}
  .arc  {{ fill: none; stroke: {t['ink']}; stroke-linecap: round;
          stroke-dasharray: 100; stroke-dashoffset: 100; }}
  .dot  {{ fill: {t['ink']}; fill-opacity: .34; }}
{motion}
</style>""")

    p.append('<text class="t name" x="48" y="44">michael tarekegn</text>')
    p.append(
        f'<path class="rule" pathLength="100" d="M48,{BASE_Y} L832,{BASE_Y}"/>'
    )

    p.append("<g>")
    for q, k, w in edges():
        # Delay off the query index so the draw-in reads as a left-to-right
        # wave. Sink edges run backwards to token 0 and so appear to peel off
        # late, which is the behaviour they have in a real head anyway.
        delay = ARC_START + q * STAGGER
        p.append(
            f'<path class="arc" pathLength="100" d="{arc_path(q, k)}" '
            f'stroke-width="{0.7 + w * 0.9:.2f}" '
            f'style="--w:{0.2 + w * 0.68:.2f};'
            f'animation-delay:{delay:.2f}s"/>'
        )
    p.append("</g>")

    for i in range(N_TOKENS):
        delay = ARC_START + i * STAGGER
        p.append(
            f'<g class="dot" transform="translate({token_x(i):.1f},{BASE_Y})">'
            f'<circle r="1.9" style="animation-delay:{delay:.2f}s"/></g>'
        )

    settled = ARC_START + (N_TOKENS - 1) * STAGGER
    p.append(
        f'<text class="t cap" x="832" y="{BASE_Y + 18}" text-anchor="end" '
        f'style="animation-delay:{settled:.2f}s">'
        f'one head &#183; {N_TOKENS} tokens</text>'
    )
    p.append("</svg>")
    return "\n".join(p) + "\n"


if __name__ == "__main__":
    root = pathlib.Path(__file__).resolve().parent.parent
    for theme in THEMES:
        for animated in (True, False):
            suffix = "" if animated else "-still"
            f = root / "assets" / f"attention-{theme}{suffix}.svg"
            f.write_text(build(theme, animated), encoding="utf-8")
            print(f"wrote {f.relative_to(root)}  ({f.stat().st_size:,} bytes)")
    print(f"settles at {ARC_START + (N_TOKENS - 1) * STAGGER + ARC_DRAW:.2f}s")
