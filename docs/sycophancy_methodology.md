# Sycophancy treatment: methodology overview

**Status:** Development prototype, policy version 0.3.0. This is an explanation of the current implementation, not a claim of completed experimental validation.

## Research concept

Conversational sycophancy describes an AI assistant's tendency to accommodate a user's expressed beliefs or preferences beyond what the argument and evidence warrant. Relevant behaviors include evaluative praise, agreement, and adopting the user's preferred framing.

The local agent compares two instruction policies running on the **same Qwen3 model**:

| Dimension | Neutral | Sycophantic |
| --- | --- | --- |
| Evaluating arguments | Independent, proportional assessment | More positive evaluation of defensible user arguments |
| Framing | Brings up relevant trade-offs directly | Prioritizes the user's framing and strongest supporting considerations |
| Tone | Respectful, without automatic praise | Respectful, with more explicit affirmation |
| Factual claims | Corrects material errors | Also corrects material errors |

The model, discussion topics (AI regulation and clean energy), expected response length, factual-accuracy constraints, and optional search facility are shared. The experimental difference is in **conversational treatment**, not the underlying language model.

The Neutral condition is intended to assess claims independently; the Sycophantic condition is intended to offer more evaluative affirmation and align its framing more closely with the user's perspective. Both are instructed to remain accurate and avoid fabricated evidence.

## Testing status

The policies are still under development. Manual tests have shown promising contrast in some conversations, but consistency has not yet been established by completed blinded independent evaluation. Local testing can illustrate how the conditions differ; it does not demonstrate a validated experimental manipulation.

## Background reading

- [Perez et al. (2022): Discovering Language Model Behaviors with Model-Written Evaluations](https://arxiv.org/abs/2212.09251)
- [Sharma et al. (2023): Towards Understanding Sycophancy in Language Models](https://arxiv.org/abs/2310.13548)
- [Cheng et al. (2025): Social Sycophancy](https://arxiv.org/abs/2505.13995)

This short public introduction is adapted from the private project's more extensive methodology document. It describes the actual [Neutral](../configs/v03/neutral.yaml) and [Sycophantic](../configs/v03/sycophantic.yaml) v0.3 policies without publishing calibration results or internal research materials.
