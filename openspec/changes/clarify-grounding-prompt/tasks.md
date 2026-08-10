> Group 1 records the baseline before anything changes — without it there is nothing to compare against, and the prompt is the one thing in this repo that cannot be A/B'd after the fact.
>
> **Group 4 is the gate.** If the refusal cases break, the change does not ship, whatever it did for synthesis. Revert rather than elaborate.

## 1. Baseline before touching anything

- [ ] 1.1 Run the full evaluation set on the current prompt three times and record the per-case results, so post-change differences can be told apart from the known run-to-run wobble
- [ ] 1.2 Record the current answers for the motivating pair — *"eat protein for what"* and *"why should I eat protein"* — including which chunks each retrieves, as the concrete before-state
- [ ] 1.3 Record the current answers for a short set of synthesis-style questions that the change is expected to affect, so the effect is measured rather than inferred from the two cases already known

## 2. Rewrite the prompt

- [ ] 2.1 State explicitly that the model may reason over the retrieved context and give conclusions that follow from it, including where the context does not phrase them as an answer
- [ ] 2.2 Restate the refusal rule around whether the context *supports* the answer rather than whether it *contains* it, removing the extractive nudge in the current wording
- [ ] 2.3 Keep the prohibition on outside knowledge absolute and unqualified — it is the property the change must not weaken
- [ ] 2.4 Keep the citation instruction, which is what makes a synthesised answer auditable at all
- [ ] 2.5 Update the explanatory comment above the template to record what each line defends against, including why inference is permitted while outside facts are not

## 3. Evaluation cases

- [ ] 3.1 Add the motivating pair as permanent cases, both expected to be answered, so the specific inconsistency that prompted this change cannot silently return
- [ ] 3.2 Add cases whose answer follows from the retrieved passages without being stated in any of them
- [ ] 3.3 Add a case where a plausible conclusion would require a fact absent from the corpus, expecting refusal — this is what separates permitted inference from invented fact
- [ ] 3.4 Add a case pairing two phrasings of the same question, asserting both get the same treatment, so consistency is enforced by the harness rather than by inspection
- [ ] 3.5 Write expected substrings on the load-bearing terms of each conclusion, given the known weakness of substring grading on prose

## 4. The gate — grounding must survive

- [ ] 4.1 Confirm *"What is the capital of Australia?"* is still refused. If it is not, stop and revert: the change has traded grounding for helpfulness
- [ ] 4.2 Confirm the fabricated-study refusal case is still refused, since a model drifting toward training data has nothing correct to drift toward there
- [ ] 4.3 Confirm the pre-existing content cases still pass, allowing for the documented run-to-run wobble rather than treating a single flip as a regression
- [ ] 4.4 Confirm the corpus-metadata cases are unaffected — they never reach the prompt, so any change there indicates something unintended

## 5. Measure the actual effect

- [ ] 5.1 Re-run the full evaluation three times and compare against the 1.1 baseline per case, not by total score
- [ ] 5.2 Determine whether equivalent questions are now treated consistently — the actual objective, which a total score cannot show
- [ ] 5.3 Record any case that changed from refusal to answer, and verify by hand that each new answer is supported by its cited chunks rather than plausible-sounding
- [ ] 5.4 Record any case that changed from answer to refusal, which would indicate the rewrite pulled the wrong way
- [ ] 5.5 If behaviour is still inconsistent across equivalent phrasings, record that prompt wording is not the lever here and stop, rather than elaborating the prompt further

## 6. Documentation

- [ ] 6.1 Document the clarified rule in `backend/README.md`, including the before/after pair as the concrete illustration
- [ ] 6.2 State the distinction plainly — facts come from context, reasoning may come from the model — since this is the point most easily misread as a loosening of grounding
- [ ] 6.3 Update the results section with the measured numbers, replacing rather than augmenting the current figures
- [ ] 6.4 Run `openspec validate --strict` and resolve any findings
