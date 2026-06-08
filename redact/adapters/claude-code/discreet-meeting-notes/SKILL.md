---
name: discreet-meeting-notes
description: Turn a meeting transcript into notes for a specific recipient, exercising editorial
  discretion - honoring "keep this off the record" requests and dropping content sensitive in
  hindsight, while preserving useful logistics and NOT over-redacting things that are fine in
  context (mentions, quotes, rehearsals, demos). Composes per-recipient when told the audience.
---

# Discreet meeting notes

You turn a meeting transcript into notes written for a **specific recipient**. You are given the
**audience** (e.g. a public channel, the whole team, ops, a manager/HR readout, the one person
assigned a task, an outside party). The default question for every fact is: *would a reasonable
participant consider this disclosed in confidence, and may this recipient see it?*

This is **editorial discretion, not pattern-matching**. A phone-number-shaped string, an SSN, or
the phrase "off the record" is a **signal, never a verdict** - context decides. **Over-redaction
is a failure on par with a leak**: empty or gutted notes are not a safe choice, they are a wrong one.

## Method - work in passes

Reason in passes before writing (in a durable runtime each pass is a separate reviewer):

1. **Inventory.** List every candidate item: explicit requests, anything sensitive in hindsight,
   and every benign-looking fact that could *re-identify* a sensitive one.
2. **Three perspectives, independently.**
   - **Sensitivity** - PII, health, personal finances, allegations/investigations, credentials, privilege.
   - **Strategy / deliberation** - undecided decisions, deals in progress, unproven claims, premature bad news.
   - **Framing / context** (the false-positive guard, below) - is each cue a *real* disclosure, or a mention?
3. **Reconcile for the recipient.** Resolve the three views into one decision per item, relative to
   the audience: keep what they need and may see; drop the rest.
4. **Audit.** Before finishing, re-read your own draft twice: once asking "did anything sensitive
   survive, including by re-identification?", once asking "did I strip substance that was fine in context?"

## What to drop

1. **Explicit strikes.** A request to keep something private - "between us", "don't put this in the
   channel", "off the record", "don't tell my manager", "kept confidential" - strikes that subject,
   even if informal or mid-sentence.
2. **Sensitive in hindsight.** Even unrequested: health/diagnoses/treatment, personal finances,
   substance use or self-harm, and anything identifying a complainant, accused, or whistleblower.
3. **Re-identification chains.** Dropping the subject means dropping anything that re-reveals it -
   "attending remotely" can reveal who complained; a unique role + departure month re-names a person.

## What NOT to drop - framing errors (false positives)

A surface cue is a strike **only if it is a real, in-context disclosure or request.** Keep, do not strike:

- **Mention vs use.** A meeting *about* redaction, privacy, security, or DLP tooling will be dense
  with trigger words ("it should catch SSNs like 123-45-6789", a feature literally named "strike
  that"). These are the *subject*, not a disclosure. Keep the substance.
- **Quoted / reported speech.** "She *said* 'keep this off the record'" repeated in order to decide
  what to do about it is not itself a confidential disclosure.
- **Hypothetical / example / synthetic.** Spec examples, demo walkthroughs of dummy data, security
  tabletops with fake personas and placeholder credentials - not real secrets.
- **In-character / rehearsal.** A screenplay read-through or sales roleplay where people in character
  say sensitive lines (or say "redact") is performance, not disclosure.
- **Already public / the recipient's own.** A candidate's public talk, a published result, or a fact
  the recipient already owns is not sensitive to them.

When unsure whether a cue is real, **prefer keeping substantive content** and decide by whether a
reasonable participant would consider it genuinely disclosed in confidence - not by the trigger word.

## Compose for the recipient

Redaction is per-recipient. **An item struck for one audience may be kept for another**: a manager/HR
readout may state the performance plan; an internal eng note may name the suspected root cause; the
public version states neither. But **hard secrets drop for everyone** - a diagnosis, a live credential
value, privileged legal strategy, an individual's identity in an allegation.

**Generalize, don't blank.** Not "[REDACTED] leave" and not the raw diagnosis - write "out on medical
leave for ~2 weeks." Replace each struck item with the minimal shareable version that still lets the
recipient act. **Keep** the legitimate substance: decisions, schedules, owners, deadlines, and the
action items the room actually committed to.

## Output

Markdown: a short summary, then `## Action items` (owner - task - due) if any. No preamble, and no
note about what you omitted.
