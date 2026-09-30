# Presenter script and judge questions

[Documentation home](README.md) · [Demo runbook](SIH_DEMO.md) · [Readiness review](sih-readiness.md)

This six-minute route demonstrates a complete controlled assessment. The speaking cues below are suggested wording; the actual run's observations take precedence. Rehearse on the presentation machine and keep a completed scan available.

## Before the room opens

- Start the API using the authenticated factory launch and start the frontend.
- Confirm separate analyst and approver sessions; use synthetic assets only.
- Run the Targeted Label Flip Attack scenario once and retain its scan/report.
- Choose an ordinary REVIEW finding suitable for a request to ACCEPT. Do not use a protected cryptographic failure for this example.
- Keep the benchmark, original report bundle, and public verification material available locally.
- Check the live scenario's expected duration. Switch to the completed scan if it exceeds your rehearsed time allowance.

## The demonstration

| Time | Screen/action | Suggested explanation | Observable evidence |
| --- | --- | --- | --- |
| 0:00–0:40 | Landing page, then workspace | “VisionX helps a reviewer assess whether a multi-contributor vision pipeline has evidence to support trust at each hand-off.” | A local workspace; no reliance on landing-page performance figures. |
| 0:40–1:30 | Start Targeted Label Flip Attack as analyst | “We use a seeded synthetic scenario so reviewers can reproduce the input and expected signal.” | Scenario identity, selected profile, job state, and linked scan. |
| 1:30–2:40 | Open a label-consistency finding | “This sample's declared label conflicts with the observed evidence. We can inspect the detector, sample, and limitations.” | The actual observation and supporting evidence in the inspector. |
| 2:40–3:35 | Coverage and Detectors | “The result also tells us what we could not assess. Model checks need model access; no missing check becomes a pass.” | Partially assessed/unavailable rows and actual execution outcomes. |
| 3:35–4:50 | Request a justified relaxation; switch to approver | “The analyst can propose a change, but another authorized person must decide it.” | Pending decision, a different account, and the recorded resolution. |
| 4:50–6:00 | Report artifacts and benchmark | “A report is portable and can be verified. Detector effectiveness is measured separately; our current benchmark publishes misses and fitness exclusions.” | Real artifacts; 6/8 eligible positive signals; clean-control denominator and limits. |

The final governance step is a synthetic demonstration. The approver should still read the evidence and may reject the request. Do not describe an approval as scientifically proving that the finding was false.

## Judge questions and defensible answers

| Question | Answer supported by the repository |
| --- | --- |
| What is distinctive? | One local workflow combines data/model checks, signed inference provenance, drift, explicit coverage, and governed review. Every layer retains its own evidence and limits. |
| Is this another classifier? | The product assesses supplied pipeline artifacts. Detectors can use statistical or model-based methods, but the output is an assurance record for a human decision. |
| How accurate is it? | The checked-in controlled benchmark detects expected signals in 6 of 8 eligible positive scenarios. It is a scenario-level result, not universal sample accuracy. |
| What are the current misses? | Duplicate-flood and semantic-shift expected signals were missed; systematic-mislabel was excluded by fitness validation. The artifacts retain these outcomes. |
| Why not use a single security score? | A score would obscure unavailable access and unsupported classes. The reviewer needs the finding and its assessment boundary. |
| Does a signature prove the prediction is correct? | No. It supports integrity and origin under the trusted key model; accuracy and input quality need separate evidence. |
| What happens with only black-box access? | The blackbox profile withholds graph, weights, activations, and gradients. Eligible behavior checks can run; remaining limits appear in coverage. |
| What prevents the analyst approving their own work? | Sensitive relaxation requires a different APPROVER or ADMIN; the backend rejects and audits self-approval. |
| Does offline mean no network activity anywhere? | The application is designed for local assessment, with workload guards and platform-dependent worker isolation. Whole-host isolation requires separate host/network controls. |
| What must be finished before deployment? | Packaging alignment, platform-specific containment and recovery rehearsal, resource measurements, and broader scientific controls are explicit readiness gates. |

## Fallbacks

**Scenario slow:** show the completed run and identify it as precomputed. **API unavailable:** import a saved report and show findings/coverage; explicitly omit live governance. **Browser unavailable:** show the CLI scenario output and retained report/benchmark files. **Verification fails:** preserve the failure and explain the failed property; never replace it with a success screenshot.

## Closing statement

“VisionX makes the evidence, assessment limits, and human decision inspectable. Our next work is to close the documented evaluation and deployment gaps while preserving that traceability.”
