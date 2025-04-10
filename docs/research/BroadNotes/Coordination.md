# Agent coordination issues and resolutions

1. We know that a problem comes about when we consider the following.
   - How might you handle contradictory or conflicting commands? For instance, if one agent says “Increase currency weighting by +0.2” and another says “Decrease currency weighting by –0.1” around the same time?
      - consider a intervention solution, this could increase latency denepding on the requiement.
      - we can take a note out of databases and have a lock-and-queue mechanism, but this might prove to be a bottleneck if too many conflicting instructions pile up.
   - Would you rely on a manager/orchestrator to prioritize or merge these commands, or might the agent attempt an internal compromise via the LLM’s reasoning?
      - the blackboard or shared data system could clarityf the who can change what and when, but might prove a point of failure and performance constraints if used heavily.
      - the Negotiation or voding solution does align well with the MAS autonmy and reflection. at the exchagne of more computational overhead and compliexity, need a negotation protocol or voting system.
      - the weighted aggregation will avoid abrupt contraditions, and maintins partical synergy. the downside determing those weights fairly can be tricky.
2. There are several ways to address this with coordination architecture.
    - centralized manager: using a single point of failure and redued autonomy of agetns, could hanlde concurrency, wiht a manger agetn that keeps track of who is authorized to instruct which parameters.
    - decentralized blackboard: agents post updates to a shared board, and the agents pull releveant updates with the abilty to ignore or partially apply them if it detects conflict, combinign the mediator agent or voting for the tricky conflicts.
    - hierarchical control: company org sytle with a supervisor to override paramaters, employees to accept instructions from the manger, ignoring or deproritizing instructions from peers.
3. the RH2MAS and VRL:
    - the reflective layer can reason about conflicts more "intelligently", consider summarizing contraditory instructions and promosing the compromised policy.
    - reflective step can be triggered only when a direct conflict is detected, reducing overhead.
    - VRL mechanism: given an agent receives contradictory instructions, might verbalize back: "conflict of interest, pelease clarify" prompt either a manger agnet or the issuing agnet to re-check the logic.
       - more interactive resolution stragegy, more human negoation in presentation.
    - Dynamic risk profiling: given the system we plan to used this for, investment analysis, contradictory instruction around risk thresholds are critical. a small mismatch will lead to major consequences. with a risk agent given authority to override conflicitng instructions, this might be essential to avoid catestrophic misaligned updates.
4. next steps?
    - consider deadlocks, if n+1 agents or more keep toggling a paramter, this results in a deadlock, the manageer/blackboard or some concurrency lock might be needed to mitigate this.
    - partial sync + authority model: if each parameter or domain belongs to a specific agent who has final say, or if we want true collabority updates.
5. maybe we try a concurrency rule to keep agents decentialized to start, keeping the agents specialied in their topic as to minimize interation that might drive parameter change.
    - then add prioirty to each instruction, designat a trust level, which we might base on the agent's track record?
    - then as the system gets more complex intorduce a negotiation system.
    - monitor and log the conflicts.
