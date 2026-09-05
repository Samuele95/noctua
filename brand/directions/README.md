# C1 — three logo directions

Open **`contact-sheet.png`**. Three rows, one per direction; each row is the same mark on a dark
panel and a light panel, at 512, 64 and 16 px, with the lockup, the palette and the type pairing.
Every size on that sheet is a true rasterisation at that size — the 16 px tile is a 16 px render,
not a shrunken 512 — because a favicon made by downscaling tells you nothing about the favicon.

Files per direction: `<n>/mark.svg` (the mark alone, 64×64 viewBox) and `<n>/logo.svg` (the
lockup: mark + wordmark). Palettes and type pairings are in `directions.json`. All six SVGs are
valid XML and pass `svgo@3.3.5 --multipass` with no warnings.

Both themes are one drawing, not two: the ink is `currentColor` and the accent is literal, so the
mark inverts with the theme while its accent stays put. An accent that flips with the theme is a
second logo.

---

## 1 — The verifying pair

**The idea.** The framework's whole epistemology is that the LLM proposes and the symbolic engines
verify, and this mark is that sentence as a drawing: the owl's two eyes are the *same aperture
drawn twice* — on the left a continuous circle, on the right the same circle resolved into
straight segments. One eye is the smooth proposal, the other is the discrete check, and the face
only works because both are there. Above them sits *Athene noctua*'s brow, which is the little
owl's actual signature (it has no ear tufts — the flat crown and the stern brow are the species),
and below, the beak.

**What it gives up.** It says nothing about the chain. There is no sequence in it, no lanes, no
orchestration — it is a portrait of the method, not of the pipeline, so the chain diagram on the
site would have to carry that meaning alone. It is also the most conventional silhouette of the
three: a frontal owl face is the shape people expect from a project called Noctua, which is why it
is instantly legible and also why it surprises least.

**Palette** Night `#0A0F1C` · Bone `#EEF0F6` · Iris `#F5B43C` · Moon `#8FA8D8` · Slate `#1A2440`.
**Type** Fraunces SemiBold + Inter — a soft-serif display with an academic register, which suits a
thesis project, over a neutral UI face.

---

## 2 — The additive stack

**The idea.** Every skill in the chain is a pure function over one HTML file: the input is never
modified, the output is a strict superset, and `strip(apply(x)) == x` byte for byte. So this owl is
*built out of its layers* — a little owl in profile, perched, its body divided by two seams into
head, mantle and belly, each layer keeping everything above it, all of them resting on the perch
that is the base model. It is the only direction that draws the architecture rather than the
subject, and the only one in profile, which makes it the most distinctive shape of the three.

**What it gives up.** Legibility at small sizes. At 16 px the seams close and the perch turns to a
grey smudge — what survives is a plump bird with an orange eye, recognisable once you know it,
ambiguous if you don't. It also gives up the stare: an owl in profile is not looking at you, so
the mark loses the frontal, watching quality that the other two have and that the name trades on.

**Palette** Ink `#12100E` · Paper `#F4F1EA` · Terracotta `#C8622B` · Moss `#4A6B5F` · Stone
`#8C8579` — earth rather than tech, and the only palette here whose accents already carry text in
both themes (terracotta 4.74:1 on dark, moss 5.23:1 on light).
**Type** Space Grotesk Medium + IBM Plex Sans — structural, engineered, slightly odd.

---

## 3 — The watcher over the lane

**The idea.** `/noctua` is not a stage; it is the thing that watches the stages. So the mark is one
hooded eye — the **O** of OWL, the language the engines actually run — above a lane of four stage
nodes, and its pupil is *off centre because it is looking at the node that is running*. The mark
therefore has a state: it depicts the orchestrator mid-chain, at stage two. That gives the site a
live element for free — the pupil and the lit node can move along the lane as the chain diagram is
scrolled or a stage is selected, and the logo becomes the diagram's smallest instance.

**What it gives up.** Owl-ness. Strip the hood and it is a ring with a dot: the least figurative of
the three, and the one that leans on the wordmark to say "owl" at all. It also spends its lower
half on the lane, so the eye is smaller than it would otherwise be, and at 16 px the four nodes
flatten into a dotted bar rather than reading as stages.

**Palette** Void `#07090D` · Signal `#DCE3EC` · Beam `#F0C24B` · Rust `#B4453A` · Graphite
`#3F4A57`.
**Type** JetBrains Mono Medium + Inter, with the wordmark set as `/noctua` — it is a slash command,
and the mono says so.

---

## What I would pick, and why

**Direction 1.** It is the only one that reads instantly at 16 px (the contact sheet's ×6 tiles
show it: two amber eyes, brow, beak — unmistakable), the only one whose idea is the framework's
central claim rather than one of its properties, and the one whose mark survives being reduced to
a favicon, a section marker and an OG image without losing the thought. Direction 3 is the most
*intelligent* of the three and the most fun on the page, but it needs the wordmark to be an owl at
all. Direction 2 is the most beautiful at 512 px and the weakest at 16.

If the chain diagram is going to be the centrepiece of the landing anyway, direction 1's silence
about the chain is a smaller loss than it looks: the diagram says the chain, and the mark says the
method.
