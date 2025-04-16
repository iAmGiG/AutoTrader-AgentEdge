# Verbal reinforcement Learning vs. Numeric RL

## Expressiveness

**Numberic RL**: has a single scalar reward, some system of -1 -> 1, often times a floating point value. we can combine mulitple metrics into a single reward, but this is coumbersome or opaque.
**Verbal RL**: these agents receive rich, text-based feedback. "Focus on XYZ first, then cross-verify with ABC". this is a descripte tool to encoidng intented, context, and rationale, for directing behavior.

## learning singal

- NRL: agents takes the 1 or 0 as a stop/go mesure, adjusting a policy to maximize cumulative reward.
- VRL: agents parse teh linguistic message to a glean "why" a decision was "good" or "bad", with a how to correct it.

## overfitting vs. generalization

- NRL: overfitting when the reward function is too narrow or if the feedback is sparse. indicating that we didn't have enough variablity in the metric (meaing we have more 1 and 0 and less 1.54 and 0.23).
- VRL: can help an agent generalize better when instructions are broad or domain-rich (does depend on teh agent's ability ot interpret language correctly).

## VRL and the LLM?

- Without an LLM: VRL might need a rule-based or even small language processing modules to interpret commands. like increase speed, alert mode, and treat them as discrete actions or rewards.

- With the LLM
  - interpretation: LLMs enable nuanced understanding of more complex or ambiguous feedback.
  - generation: agents can produce more detailed textual feedback for other agents.
  - reflection: an LLM-driven agent can reflect on text-based feedback internally, examples: summarizing, sel-asking "why was that feedback negative".

- but what about RH2MAS - the LLM is a 'reflective' head - thus we can do adv reasoning upon receiving textual reinformcent. which can be extermly powerful but also computationally heavier.

## Foundational needs of a VRL system

1. common language or protocol - agents need a consistent way to interpret and respond toe text.
   - grammer, key terms, or structured templates reduce ambiuity some.
2. parsing and interpretation mechanism
   - with an LLM we can have a built-in parser for complex language.
   - or we can have a simpler modules or cmd interpreters.
3. feedback and reward structure
   - still want some measure of success/failure. **Verbal** feedback can be comlemented by a numeric or symbolic "score" or the system might purely rely on interpretative instructions.
   - agents' policy updates in response to the text require and internal mapping from verbal feedback to policy changes or memory updates.
4. memory integration
   - VRL is particually potent when tracing peervious instructions and how well they worked.
   - given layered memory stem, short-term memory holds the immediate feedback, reflective memory might store the reasoning chain, and long-term memory accumulates broader lessons.
5. interactive loop
   - the differences from a numeric system is that hte dialog can happen at multiple points in the agent's decision process.
   - agetns might share partical progress, get verbal feedback, adjust, and continue. this fosters a more fluid (human-like) learning process, rather than waiting until the very end to issue a reward.

## considering VRL in the RH2MAS

1. scenario: the system is analyzing a sentiment. with the sentiment agent, an analysis is procedue "The public sentiment is neutral".
2. Verbal feedback: another agent or even the user might respond, 'mentions of the company have increased negativity recently-- re-check that analysis focusing on shoter and near term rumors'.
3. agent's update: given the sentiment agent, rerunning or reweighting its analysis with an emphasis on shorter or near term rumors. this adjust strategy or weigthing paramters accordingly.
4. reflective storage: the agent logs the textual feedback in reflective memory, so next time it sees a similar clue, it will incorporate that knowledge immediately.
5. long-term policy: overmany such interactions, the agent develops more refined approach to weighting "short-term" rumors in the sentiment analysis.
