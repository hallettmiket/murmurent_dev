# Writing guide: the PI's own examples

**Private: kept in the development repository only, never released.** It
quotes unpublished manuscripts. The public guide,
[`scientific_writing.md`](scientific_writing.md), has the same rules with
invented examples. The Scribe reads both when both are on the machine, and the
real examples here outrank the invented ones there.

This is the guide as first written from the PI's hand edits (issue #153),
kept whole so that no real pair is lost. When a rule changes, change it in the
public guide; add new real pairs here.

## Where these rules come from

They are taken from Mike's own edits, not from general advice. Every
"Updates from Overleaf" commit in two manuscripts is Mike editing by hand, and
git shows which passages he rewrote were first written in a Claude Code
session: **728 rewrites and 74 outright deletions** across
`murmurent_manuscript` and `dlr_versus_ilr`, read in full in October 2026. The
finished papers were also profiled section by section.

Three findings shape everything below:

1. **About 70 to 85% of his edits change voice, not facts.** The content was
   usually right. The register was wrong.
2. **His main move is to cut.** Even when he corrects a fact, the sentence
   usually gets shorter.
3. **What he cuts is the writer explaining itself:** why a sentence is there,
   how candid it is being, what the alternative was, and what a reviewer might
   object to.

His drafts contain typos. They are not part of the voice; do not copy them.

---

## The rules

### 1. Cut what explains yourself

The most common edit. State the fact and stop.

- **No justification tails.** Cut ", which is the failure they were built
  for", ", so that an ordering cannot be read without the warrant for it",
  "because ...", "which is why ...".
- **No "rather than" foils.** The reader did not ask what the alternative was.
  "Four rules are enforced automatically rather than left to good intentions"
  becomes "Four rules are enforced automatically." (The "rather than" count
  fell from 68 to 24 in the passages he edited.)
- **No comments on your own candour or purpose.** Cut "We state this plainly
  because", "The limitations are stated plainly rather than hidden", "This is
  deliberately not ...", "the distinction matters", "which is the point".
- **No pre-empting the reviewer.** Delete caveats whose only job is to answer
  an objection nobody has raised yet, and do not repeat a point already made.
- **Cut whole sentences, not only words.** Trimming inside sentences is not
  enough. Ask of each sentence whether a reader of the paper needs it, and
  delete it when it does not. The kinds Mike deletes most:
  - the reasoning behind a design or security choice ("because the opposite
    rule would hand an attacker an easy move"), when the paper only needs the
    choice;
  - the motivation for an analysis step ("which motivates pooling the eras
    below"), when the next paragraph simply does it;
  - analysis settings outside Methods (fold counts, bootstraps, permutation
    nulls in the Introduction);
  - a second sentence that restates or elaborates the first.

  Cutting is not changing the facts: a deleted sentence leaves every remaining
  claim as true as it was. In a data paper, though, he often *adds* a plain
  "That is," sentence, so the median rewrite there is about as long as the
  original. Cut what serves the writer; keep and add what serves the reader.

  For an editor that is not the author (the Scribe, or any session), the line
  is drawn in two places. Delete what plainly serves the writer: roadmaps,
  restatements, comments on the writing. Propose, but leave in place, cuts of
  detail the paper may not need: deciding those takes the whole manuscript and
  the author's intent.

### 2. Say it literally

- **No metaphors, aphorisms or epigrams.** "walked down to chance" becomes
  "reduced to mere chance"; "shared blast radius" becomes "an obvious risk";
  "would crowd out the work the session is there to do" becomes "would fill the
  context"; "that loss is structural" becomes "this type of information loss
  will be recurrent".
- **No "not X but Y", "neither X nor Y but Z", or cleft sentences** ("What X
  does is ..."). State the positive claim, with a person or the system as the
  actor.
- **No punchline fragments.** "It does not." becomes "We show that this is not
  the case." "It is." becomes "Indeed, ...".
- **No coined names for things.** "Dance with Inhibition" became "the Pin1
  choreography".

### 3. Turn the volume down

- **No intensifiers:** decisively, critically, crucially, serious, far more,
  genuinely, actually, precisely, inevitably, easily, notably, importantly
  (rare, and never as a paragraph opener), "to us, the strongest".
- **No italic or bold on ordinary words** for emphasis ("in \emph{both}
  eras"). Italics are for a term at its definition, species, gene names and
  *in situ*.
- **Hedge to match the evidence.** Weak results are named as weak ("at best
  exploratory", "suggestive at most"). Mechanistic explanations are hypotheses
  ("perhaps", "may explain", "There are several overlapping hypotheses").
  Candidates are "putative". A strong claim is earned by agreement between
  independent lines of evidence, and then said once.
- **No absolutes about settings or people.** "Academic centres also carry
  constraints" becomes "Academic centres may also carry some constraints". Never
  imply that people are replaced: "may decrease the load placed upon them".

### 4. Shape sentences for a reader

- **One result per sentence.** Split semicolon chains and ", which" chains into
  separate sentences.
- **Do not go choppy.** The finished papers run at a median of 23 to 27 words
  a sentence. The rhythm is a long sentence carrying the evidence, then a short
  one carrying the verdict: "No construction cleared the discussion bar in any
  era."
- **Use "of" rather than stacked possessives:** "the bulk transcriptome of the
  primary lesion", not "the primary lesion's bulk transcriptome".
- **In the `.tex`, one clause per line.** Never rewrap a paragraph: Overleaf
  reads it as a change to every line.

### 5. Lead with the science and the person

- **Context first, then the claim; purpose first, then the mechanism.** "Two
  rules about files are checked by hooks" became "Murmurent manages several
  directories ... in order to minimize the chance that either a user or an
  agent accidentally deletes precious information."
- **Make a person the actor.** A PI, a student, "we", or the system named as
  doing something. "the agent has less to guess at" became "This frees the
  researcher from restating project conventions in each new session".
- **Say what it buys the researcher.** When describing a feature, state the
  benefit to the person using it.
- **Frame the biology, not the pipeline.** "we systematically evaluated, for
  every diagnostic era × PAM50 subtype × endpoint cell, differential
  expression, ..." became "we investigated the prognostic capacity of gene
  expression ... above and beyond standard clinico-pathological features".

### 6. Leave the engineering out of the story

- **No implementation detail in the Introduction, Results or Discussion:** file
  paths, environment variables, configuration keys, tags, URLs, internal code
  labels (`event.10`), counts nobody needs ("51 such records" became "many such
  records"), and the history of renames.
- **Report the outcome, not the process.** No step-by-step narrative of what an
  agent did first and then, and no debugging stories. "on the first pass it
  held neither document, so it returned a blueprint ... Once ..." became "The
  Conscience ... read both documents and identified 22 items".
- **Methods is the exception.** There, give what someone needs to reproduce
  the work: software and versions, random seeds, hyperparameters, permutation
  counts, thresholds ("Python 3.11 with sklearn 1.8.0", "random\_state = 42",
  "1,000 permutations"). Not the reasoning that chose them, unless a reviewer
  would ask.

### 7. No signposting

Cut roadmaps and throat-clearing: "The three results subsections below
correspond to the three questions posed in the Introduction", "The subsections
that follow describe ...", "Where it is useful we name ...", "is taken up next".
Keep cross-references (`\S\ref`) to the ones a reader will actually follow. Get
to the scientific question: "We illustrate the properties of Murmurent using a
choreography with the stated challenge as follows: find a small molecule that
inhibits human Pin1".

### 8. Structure

- **Number parallel points.** Use "First, ... Second, ... Third," or inline
  "(i) ... (ii) ... (iii)". Prefer these to bullet lists, which are rare in the
  finished papers (one to two `itemize` each).
- **Run-in headings** (`\paragraph{}` or underlined labels) only when each one
  states a claim ("The clinically dangerous recurrence is the molecularly
  cryptic one.") or names a fixed component ("Scoped.", "Attributed."). Never
  as decoration.
- **Short plain headings and captions.** "System architecture: shared agents
  and group toolkits" became "System architecture".
- **Move dense statistics into a table** and keep the prose to the claim.

### 9. Words

- **Field terms over formal or house terms:** lab, not laboratory; PI, not
  principal investigator (after defining it once); members, not HQP; "the
  agents", not "the commons"; "chat (Slack here)", not "Slack".
- **Define every term and abbreviation at first use, then use the short
  form:** "clinico-pathological features (CPFs)"; "an \emph{agentic operating
  system}; that is, the layer beneath ...". Software and industry terms most of
  all.
- **Give examples with "e.g."**: "core facilities (e.g. genomics,
  proteomics)".
- **Spelling: Canadian.** tumour, colour, centre, behaviour, analysed,
  modelled, program; but -ize (organized, normalized). Match the surrounding
  text.
- **Dashes:** no em dashes, and no `---` or ` -- ` used as a pause. LaTeX en
  dashes (`--`) only in ranges (`$7$--$17$-fold`) and compound names
  (Benjamini--Hochberg). Use a comma, brackets, a colon or a new sentence.
- **Words that do not appear:** leverage, crucial, cutting-edge, delve,
  state-of-the-art, seamless, empower, unlock, revolutionary, powerful,
  comprehensive (except in a precise sense), novel (rarely, and only of a
  finding), robust (only in its statistical sense), "it is important to note",
  "In recent years", "Additionally", "Furthermore", "In summary".

### 10. Numbers

- **Always give the number, the test, the threshold and the multiple-testing
  context:** "A direct moderated-$t$ contrast ... did not identify any DEGs at a
  Benjamini--Hochberg false-discovery rate of $q_{\text{mod}}<0.25$".
- **Put statistics in brackets after the claim, then say what they mean in one
  plain sentence,** often beginning "That is," or "For example,": "That is, iLR
  samples look like no-LR samples, and not like dLRs."
- **Qualify a result by its weakness straight away:** "however $\approx36$
  false positives are expected by chance among the $712$ genes tested."
- Numbers in LaTeX math (`$886$`, `$p=0.008$`); confidence intervals as
  `[0.03\text{--}0.66]`.

---

## Section by section

**Abstract.** One block, four movements: what is established; what is not
(the gap, stated as a fact); what we did, with the cohort or system in
brackets; what we found, with statistics inline, and one sentence on what it
means. Present tense for the field and conclusions, past for what was done.
Lead with the biology or the clinical stakes, never the pipeline.

**Introduction.** Field, then gap, then contribution, in prose. Define the
central term first. Survey prior work as "First, ... Second, ... Third," with
named examples and citations at clause ends. State the gap plainly
("Nevertheless, almost all molecular work in DCIS pools the two histologies").
Questions may be listed. Close by weighing what each possible answer would
mean. Present tense; sentences of 20 to 35 words.

**Methods.** Short, factual, procedural, reproducible: versions, seeds,
thresholds, exclusions with the reason ("Five housekeeping genes were excluded
due to low expression"). Past tense for a study; present tense is acceptable
for describing a system. Inline lists use (i) to (v).

**Results.** Subsection titles state the finding as a sentence ("Recurrence
prediction is endpoint-specific and adds little beyond CPFs."). A paragraph
opens on the test and its result together, qualifies the result at once, and
closes on a summary sentence that names the table or figure. Past tense for
what was done and seen, present for interpretation ("We cannot conclude").
Point to Methods with `\S\ref` rather than repeating them.

**Discussion.** Open by restating the questions and the answer in brief ("We
asked three questions ... In brief, we do not find any evidence ..."). Then
run-in paragraphs titled with claims, each raising the natural objection and
answering it ("A natural concern is that ... We show that this is not the
case."). Then limitations, frankly. End on a measured recommendation, not a
flourish.

**Figure and table legends.** A bold title that states the finding; then how
to read the figure; a one-sentence definition of any unfamiliar method; the key
numbers; footnotes marked a, b, c. Description only: no interpretation, no
caveats, no defence of the analysis.

---

## Before and after

All are real: Claude Code's text, then Mike's revision.

1. *Cut the justification.*
   - Before: "Its verdict vocabulary is accordingly two words wide,
     \emph{Explained} and \emph{Gap}, with nothing between them, on the
     reasoning that an intermediate verdict would absorb every \emph{Gap} the
     agent ought to have returned."
   - After: "The Teacher has only two verdicts: \emph{Explained} and
     \emph{Gap}."

2. *No commentary on your own candour.*
   - Before: "The limits are worth stating plainly, because this is a guardrail
     and not a locked door."
   - After: "There are limits to this guardrail."

3. *No cleft sentence, no restating tail.*
   - Before: "What they reliably prevent is an agent destroying a result by
     mistake, which is the failure they were built for."
   - After: "They prevent an agent destroying a result by mistake."

4. *Literal, not figurative.*
   - Before: "enrichment of the covalent control is walked down to chance over
     two days."
   - After: "statistical significance of the covalent control is reduced to
     mere chance over two days."

5. *Name the action, not an abstraction; two sentences, not an epigram.*
   - Before: "The thesis is a trade and we state it as one: simultaneity buys
     comparability and shared-control strength, and it spends error
     independence."
   - After: "Our thesis is that building the four approaches together
     facilitates comparability and a single set of controls. The price is that
     their errors are no longer independent."

6. *No antithesis; state the aim in the first person.*
   - Before: "The decisive test is not whether a molecular model beats chance
     but whether it beats --- and adds information \emph{beyond} --- the five
     standard clinico-pathological features"
   - After: "Our focus is on whether the inclusion of the molecular components
     adds information to the predictions beyond five standard
     clinico-pathological features"

7. *No punchline; numbers, then one plain sentence.*
   - Before: "asked whether it is prognostic for one recurrence type but not
     the other. It is. The score is elevated in patients who go on to a dLR
     (median $z=+0.22$) but sits near the recurrence-free baseline in those who
     go on to an iLR ..."
   - After: "asked whether it marks one recurrence type but not the other.
     Indeed, patients who incur a dLR carry an elevated score (median
     $z=+0.22$) compared to iLR patients who sit near the recurrence-free
     baseline ($-0.09$ vs $-0.25$ for no-LR). That is, iLR samples look like
     no-LR samples, and not like dLRs."

8. *The person as actor, and the benefit to them.*
   - Before: "For a principal investigator with little information-technology
     support, the gain is that a plan for how data, code and analyses are
     organized can be stated once and then upheld by the hooks and the
     reviewing agents rather than by reminding people, which matters most for
     students early in training"
   - After: "Now a PI can describe how they want data, code and analyses
     organized, and Murmurent will uphold this vision with hooks and agentic
     review. This is far more efficient than repeatedly reminding people,
     especially those early in training"

9. *Purpose first, plain heading.*
   - Before: "\paragraph{Two rules an agent cannot talk its way past.} Two
     rules about files are checked by hooks ..., which inspect the operation
     before it reaches the disk."
   - After: "\paragraph{Inescapable rules.} Murmurent creates and manages
     several named directories with specific permission systems in order to
     minimize the chance that either a user or an agent accidentally deletes
     precious information."

10. *Methods: the order, not the debugging history.*
    - Before: "It searches patent collections in a fixed order, which is set by
      how dependable each one proved rather than by how convenient it is.
      United States granted claim text is read first, from the grant documents
      themselves, because that source was never refused during a full day of
      testing. ..."
    - After: "It searches patent collections in a fixed order: United States
      granted claim text is read first, then WIPO PatentScope, then Google
      Patents."

11. *Hedge speculation; drop emphasis and slang.*
    - Before: "proliferation and chromosomal instability are a
      \emph{quantitative} property of the in-situ disease, whereas invasion is
      a \emph{qualitative} ... transition. A second \emph{in situ} lesion is,
      mechanistically, a regrowth ... machinery is already running hot"
    - After: "proliferation and chromosomal instability are a quantitative
      property of \emph{in situ} lesions, whereas invasion is a more
      qualitative ... transition. A second \emph{in situ} lesion is perhaps,
      mechanistically, a regrowth ... machinery is already running
      aggressively"

12. *No signposting; get to the question.*
    - Before: "The subsections that follow describe the properties of
      Murmurent one at a time, and each of them is illustrated by the same
      choreography, which we introduce here so that those illustrations are
      concrete."
    - After: "We illustrate the properties of Murmurent using a choreography
      with the stated challenge as follows: find a small molecule that inhibits
      human Pin1"

(Typos in the originals are corrected here.)

---

## Integrity

- **Never invent a citation, a number or a behaviour of the system.** Where one
  is missing, leave a visible gap (`[CITE: ...]`, `[N=?]`) and say so.
- **Cite only bibliography keys that already exist.** Ask for a missing
  reference to be added; do not edit the exported `.bib` files.
- **Flag a clinical or empirical claim you cannot source** rather than soften
  it into vagueness.
- Citations go through the bookworm; reporting checklists (TRIPOD+AI,
  PROBAST+AI, REMARK) through the adversary; wording about people and
  communities through the conscience.

## Keeping this guide current

When Mike rewrites a passage the Scribe produced, the pair is evidence. Add the
clearest ones to *Before and after*, and change a rule when the pairs
contradict it. The extraction is repeatable: pair each "Updates from Overleaf"
commit's changes with the lines it replaced, and keep those whose earlier
version came from a commit co-authored by Claude.
