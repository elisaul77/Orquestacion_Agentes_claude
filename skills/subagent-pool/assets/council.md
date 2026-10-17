# Plan council — protocol (subagent-pool v9.9)

A plan decides most of the outcome; a wrong spec fails every phase after it. The council builds the plan with four
lenses instead of one, and makes them disagree on purpose.

| Member | `subagent_type` | Name in the team | Question |
|--------|-----------------|------------------|----------|
| Specifier | `council-spec` | `spec` | What exactly counts as done, and how will we know? |
| Architect + synthesizer | `council-architect` | `architect` | How do we build it, in what order, in which real files? |
| Lateral thinker | `council-lateral` | `lateral` | What is the non-obvious solution? (asks Codex when on, else Opus) |
| Risk + verification | `council-risk` | `risk` | What breaks, and how do we prove it didn't? |

## Why this shape (verified / measured)

- Same-model agents that see each other's ideas converge on one answer → **R1 is blind**: nobody reads another draft.
- Open-ended agent chats drift into polite agreement → **one debate round with hard limits**, then synthesis.
- A second voice thinks differently from the drafters: the lateral member asks **Codex** when `CODEX: on`; otherwise **Opus** as the second voice (same family, less diverse than another vendor, still better than four Sonnet drafts).
- Claude Code agent teams (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, verified 2026-10-17 on 2.1.302, headless and
  interactive): agents spawned with `Agent(name=…)` message each other directly with `SendMessage`; messages wake an
  idle agent. Agents with a closed `tools:` list need `SendMessage` in it (verified: without it they can't send).

## Where to run it

Run the council from a session opened **in the project folder**. Members get the project by absolute path either way,
but the project's own `.claude/rules/*.md` (path-scoped rules such as a UI design system) load only for the session's
working directory, and implementers will need them.

## Layout

```
plans/council/{task}/
  brief.md        Conductor: task, tier, operation, context, constraints, CODEX on|off, member names
  spec.md         R1 drafts (blind)
  architect.md
  lateral.md
  risk.md
  debate.log      R2: one line per message, "{from}->{to}: {text}"
  decisions.md    R3: decision record (architect)
plans/{task}-draft.md   R3: the plan (architect), same format as planning-agent
```

## Rounds — the Conductor is a clock, not a postman

The Conductor never carries content between members. It only starts each round and waits for everyone to finish it.

| Round | Conductor does | Members do | Ends when |
|-------|----------------|------------|-----------|
| **R1 draft** | Writes `brief.md`; spawns the members in ONE message, each with `name` and the brief path | Write their own draft, blind | Every member has said `R1 done` |
| **R2a objections** | Sends each member `R2a` (one short SendMessage each, in one response) | Read all drafts; send each objection to its author **and** append it to `debate.log` before ending the turn | Every member has said `R2a done: {n} sent` |
| **R2b replies** | Sends each member `R2b` | Read `debate.log` for objections addressed to you; reply to each (SendMessage + append) | Every member has said `R2b done: {m} answered` |
| **R3 synthesis** | Sends `architect` `R3`. `debate.log` is now frozen | Architect writes plan + decisions | Architect returns `PLAN_READY` or `NEED_CLARIFICATION` |

**`debate.log` is the source of truth, not the inbox.** A member appends each message before its turn ends, so after
the R2a barrier every objection is in the log even if delivery is late; R2b works from the log. Nobody writes to the
log after R2b, so R3 reads a closed transcript.

**An acceptance restates the result.** "accept" alone is not a reply: write the resulting wording
(`accept → ready = printer online and idle`). Two members can each accept the *other's* version and swap positions;
restated results make that visible in the log.

**Message limits (per member):** R2a at most **one objection per other draft**; R2b one reply per objection addressed
to you — at most 6 messages. An objection is concrete: it names a criterion, file, input, phase or command.
"I agree" is not sent; silence means no objection. No further round: anything still disputed goes to `decisions.md`
as an open disagreement for the user. If R2a produced no objections, skip R2b.

**R3 starts with a consistency pass.** Before writing, the architect lists every decision that has two different
restated results in `debate.log` (crossed acceptances) and settles each one in `decisions.md` with the reason, or
marks it open. The Conductor never forwards a late point from one member to another: a member that finds something
after R2b messages the architect directly (one message, logged), and the architect takes it into account.

**The Conductor presents the plan only after the architect's final return.** If a member's late message reaches the
architect during R3, wait for the architect's updated return; never present a plan and correct it seconds later.

**`NEED_CLARIFICATION` from R3:** the Conductor asks the user the architect's questions (prose, §4), appends the answers
to `brief.md` under `## Answers`, and sends `architect` `R3` again. No new debate unless an answer changes the scope.

**Skip rule:** if every R1 draft agrees on approach and no risk is High, the Conductor may skip R2 and go to R3
(`debate.log` then doesn't exist; the architect treats it as "no objections").

## Levels

| Level | Members | Drafts in R1 | R2 | Architect also covers |
|-------|---------|--------------|----|-----------------------|
| duo | architect, lateral | `architect.md`, `lateral.md` | none | acceptance criteria (spec role) and top risks (risk role) in its own draft |
| council | all four | all four | R2a + R2b | — |

The architect synthesizes from **whatever drafts the level produced**; a missing `spec.md`, `risk.md` or `debate.log`
is expected at duo level, not an error.

**Silence until the barrier.** Members going idle send notifications. Write nothing to the user and send nothing
to members until every member has finished the round. Then one short update per round at most (what changed the
plan), and the full presentation after R3.

## Fallback — teams flag off (or names unsupported)

Same rounds, carried by files instead of messages, still without content passing through the Conductor:
- R1: four parallel `Task` calls (fresh agents, no `name`), each writes its draft.
- R2a: four parallel `Task` calls: "read the other three drafts in `{council_dir}`, append your objections to
  `debate.log` (limits above)". R2b: one call per member that received objections: "answer the objections to you in
  `debate.log`". Skip R2b if no objections were written.
- R3: architect synthesizes, as above.
Costs one more wave of agent starts; same output.

## Cost (estimate, not measured yet)

| Level | Agents | Extra tokens vs one planner |
|-------|--------|-----------------------------|
| single | planning-agent | 0 |
| duo | architect + lateral (blind drafts, synthesis by architect) | about +1× |
| council | 4 members, 1 debate round | about +4–6× |

The plan is the cheap part of the cycle; one avoided rework phase usually pays for the council.
