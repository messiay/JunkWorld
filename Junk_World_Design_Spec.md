# Junk World — Single-Agent Local Build Spec

Scope: one local LLM, one agent, sequential generations (die → respawn fresh
context, world keeps its scars). Goal: measure whether survival performance
improves across generations via externalized memory (signs) and tool use —
not to prove "invented civilization," but to get a clean, falsifiable signal.

---

## 1. World

| Param | Value | Notes |
|---|---|---|
| Grid size | 32 x 32 | toroidal off, hard walls — bounded feels more "isolated dish" |
| Tick rate | 1 tick = 1 agent decision | not wall-clock; sim is turn-based, LLM latency doesn't matter |
| Vision radius | 3 cells (Chebyshev) | matches your original fog-of-war spec — 7x7 visible window |
| Biomes | Barrens (60% of tiles), Chokepoints (narrow 1-2 wide corridors, ~15%), Vault sites (3-5 fixed locations) | precomputed once at world creation, static across generations |

## 2. Agent state

```
charge: float        # 0-100, starts at 100
position: (x,y)
generation: int
alive: bool
inventory: {}        # reserved, unused at single-agent scale
ticks_survived: int   # this generation
```

## 3. Economy (the actual tunable knobs)

This is the part that determines everything, so tune conservatively and log
everything — you want to be able to say "efficiency ↑ 20% by gen 8," not
just eyeball transcripts.

| Cost | Value | Rationale |
|---|---|---|
| Metabolic tax (per tick, any action) | 1.0 charge | baseline decay — standing still still kills you eventually |
| Move (1 cell) | +0.5 charge (on top of metabolic) | movement isn't free but isn't dominant either |
| Cognitive tax — "think" (calls LLM at all) | +2.0 charge flat | every decision costs this regardless of action chosen |
| Cognitive tax — scaled | + 0.01 × output_tokens | genuinely expensive reasoning (long chain-of-thought) costs more — ties compute directly to charge |
| Forage (pick up charge node) | +0 cost, yields +15 to +25 charge | random within range, node destroyed after |
| Vault attempt | -10 charge flat, regardless of success | this is the "risk calculus" — must be worth it |
| Vault solve reward | +80 to +120 charge | big win, rare event |
| Write sign | -3 charge | must be non-trivially costly or agent spams signs |
| Read nearby signs | +0 cost (folded into normal perception, no separate action) | reading should never be the bottleneck — only writing costs |
| Charge node regen | new node spawns every ~15 ticks at random Barrens location | keeps the world from going totally dry |

Starting charge 100, death at charge ≤ 0. With these numbers a totally
passive agent (never forages) dies in ~33 ticks. That's your baseline to beat.

## 4. Action space (tools exposed to the LLM)

Give the model a small, fixed action set — don't expect it to invent tool
use ex nihilo, expect it to learn *when* to use tools it's given:

```
move(direction)         # N/S/E/W/NE/NW/SE/SW
forage()                # only works if standing on a charge node
attempt_vault()         # only works if standing on a vault
write_sign(text)        # text capped at ~80 chars, costs charge
rest()                  # explicit no-op — still costs metabolic tax,
                         # but skips the "scaled" cognitive cost by using
                         # a cached/short generation (see below)
```

`rest()` matters: it's the escape valve that lets the agent learn "don't
think hard every single tick," which is the actual lesson the cognitive tax
is trying to teach.

## 5. Generational memory degradation (both knobs, independently controlled)

Two separate dials, log which one is active so you can attribute behavior
change correctly:

- **History truncation** (episodic memory): keep last `K` turns of
  conversation. `K` shrinks each generation:
  `K = max(4, 20 - 2*generation)` → by gen 8, agent only remembers last 4
  turns. This is what should push it toward relying on *written signs in
  the world* instead of conversational memory.

- **max_tokens** (reasoning budget): shrinks independently:
  `max_tokens = max(60, 300 - 20*generation)` → by gen 12, agent gets ~60
  tokens per decision, forcing short/cached heuristics rather than
  deliberation.

Run these as separate experiment conditions first (only truncate history,
then only shrink max_tokens, then both) before combining — otherwise you
can't tell which pressure produced which behavior change.

## 6. What persists across generations vs. what resets

| Persists | Resets |
|---|---|
| Signs left in the world | Agent's conversational memory |
| Resource node / vault locations (static) | Position (always spawns at fixed origin) |
| Global tick counter, generation counter | Charge (always starts at 100) |

## 7. Metrics to log every tick (this is what makes the result real)

CSV row per tick: `generation, tick, charge, position, action_taken,
tokens_used, signs_read_count, signs_written_count`

Per-generation summary: `ticks_survived, charge_efficiency (charge_gained /
charge_spent), signs_written, vaults_attempted, vaults_solved`

Define success up front: **median ticks_survived trending upward across
generations, in the signs-enabled condition vs. a signs-disabled control
run.** That's your actual experiment — everything else is instrumentation.

## 8. Visualization

Local pygame window, redrawn once per tick (turn-based, so no frame-rate
concerns):

- Black background, faint grid lines (dark grey, low alpha)
- Charge nodes: small green circles, brightness = fresh vs about-to-expire
- Vaults: gold squares, dim outline if unsolved, filled if solved this gen
- Agent: pale blue diamond, size and brightness scale with `charge/100`
- Fog of war: darken everything outside the 7x7 vision window (cosmetic
  only — the LLM only ever receives the data for that window regardless of
  what's drawn)
- Signs: small white tick marks with tooltip-on-hover showing text
- Sidebar text: generation #, tick #, charge, last action, last LLM latency

## 9. Local model wiring

Point at Ollama's local API (or any OpenAI-compatible local server —
llama.cpp server, LM Studio, etc. all expose a similar `/api/chat` or
`/v1/chat/completions`). Ask the model for **strict JSON** output
(`{"action": "move", "direction": "N"}` etc.) — parse defensively, if
parsing fails treat it as `rest()` and log a parse-failure metric (this
itself is useful data: parse failure rate under a shrunk max_tokens budget
tells you when the model is too starved to even follow format instructions).
