# Chart Reference Labeller — 90-second walkthrough narration

**Format:** captioned visual walkthrough; currently silent. The attached MP4 contains original synthetic demo material and a screenshot of the review interface. Speak at a steady, conversational pace if recording a voiceover.

**00:00–00:08 — The problem.** A trading lesson might say “this bar” or “these three bars”. To build useful training data, we need to know exactly which candlesticks the instructor indicated—without inventing a label when the evidence is unclear.

**00:08–00:25 — Input.** Here is the generated lesson video and synchronized SRT transcript. The demo deliberately changes chart slides, with a moving pointer and different candle shapes. These are synthetic examples, not any client's real recordings.

**00:25–00:46 — Matching.** The pipeline identifies slide changes, reconstructs the clean chart, numbers the bars and tracks pointer movement. It uses a settled pointer for a single bar and a pointer sweep for groups, checking any spoken count.

**00:46–00:58 — Concrete output.** “These three bars” resolves to bars eight, nine and ten. Every accepted label has an explanation and crop. Ambiguous pointing produces an abstention with a reason instead.

**00:58–01:15 — Review.** The human review interface shows each decision with its crop. A reviewer can approve, correct or reject the label; only reviewed examples are exported. The screenshot is from the supplied prototype.

**01:15–01:30 — Evidence and limits.** On the generated lesson, all twelve labels match the answer key, and all four ambiguous references are withheld. The source and reproducible checks are public on GitHub. Accuracy on actual customer footage is still untested, and validating it would be the first delivery milestone.

**Note:** the accompanying official 90-second walkthrough now includes recorded voice-over audio and captions. The narration text is a recording guide and may differ slightly from the spoken version. Only synthetic footage is used.