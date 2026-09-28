# VisionSentinel

**Air-Gapped Computer Vision Integrity & Assurance Platform** — Smart India Hackathon 2026, problem
statement SIH26228: *Trustworthy Computer Vision Integrity Assurance for Data, Models and Inference
Outputs in Multi-Contributor Pipelines.*

VisionSentinel does not claim that a system is "secure". For every attack class it states whether it
was **assessed**, **partially assessed**, **not assessed**, **failed to execute** or is
**unsupported**, which evidence supports each conclusion, which access assumptions were required,
and whether that evidence has been altered since.

The architecture, contracts and design corrections are recorded in
[ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md).

## Quick start (development)

```bash
make install          # Python 3.12 virtualenv with the engine and test extras
make test             # full test suite (runs under an egress guard: no network access allowed)
make detectors        # list detectors and declared-unsupported attack classes
```
