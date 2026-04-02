# SyzGPT in the Era of Agent

As the authors of SyzGPT, we have been thinking about what the rise of AI agents means for our work. This document shares our perspective on why SyzGPT's core ideas remain relevant, and where we see opportunities for evolution.

## The Context

SyzGPT was built in the GPT-3.5/4 era, when context windows were small and models struggled with complex kernel system calls. Our response was DRAG (Dependency-based Retrieval-Augmented Generation): extracting syscall dependencies from manpages and syzlang definitions, then feeding carefully selected context to the LLM for one-shot generation.

The landscape has changed. Modern agents like Claude Code and Codex CLI can plan multi-step tasks, call tools, and iterate based on feedback. They handle 200k+ token contexts and reason about complex systems. This raises a fair question: does SyzGPT's carefully engineered retrieval and single-shot generation still matter?

We believe it does. The main difficulty of the effectiveness of the Syz-program generation still exists. Our preliminary testing suggests that even advanced agent configurations (e.g., claude code + kimi-k2.5 and codex cli + gpt-5.4) struggle to generate valid Syz-programs that pass the syntax checker.


But we also see real opportunities for improvement that agents open up.

## Why DRAG Still Matters

The core insight of DRAG is that generating valid Syz-programs requires understanding dependencies. You cannot meaningfully call ioctl$KVM_CREATE_VM without first calling openat on /dev/kvm. You cannot use a file descriptor without knowing how it was created.

DRAG captures these relationships in two forms: call-level dependencies from manpages (what syscalls prepare resources for others), and syz-level dependencies from syzlang (what resource types flow between operations). This structured knowledge does not become obsolete just because models get smarter. If anything, it becomes more valuable as a foundation that agents can build upon.

There is also an efficiency argument. DRAG retrieves a few thousand tokens of highly relevant context. Throwing an entire manpage or the full syzlang specification at a model may work, but it is wasteful. For the specific task of syscall seed generation, targeted retrieval beats broad context.

## Where Agents Can Help

That said, SyzGPT has limitations that agents are well-suited to address.

**Dynamic Dependency Extraction.** DRAG's dependencies are pre-computed from static sources. This works well for standard patterns, but kernel interfaces are messy. Some syscalls have implicit dependencies that only appear in actual usage. Others have conditional dependencies that depend on flag combinations or prior state. An agent could explore these dynamically: reading documentation, examining existing corpus programs, and testing hypotheses about what prerequisites are actually needed for a given target syscall. The goal is not to replace DRAG's dependency graph, but to enrich it with context that static analysis misses.

**Smarter Program Retrieval.** SyzGPT's current reference program retrieval is fairly basic. It looks up programs containing the target syscall or its dependencies, ranks them by some heuristics, and includes the top-k as in-context examples. This works, but it is naive. It does not distinguish between a good example and a bad one. It does not understand why a particular program structure succeeds or fails. An agent could do better: analyzing candidate programs for validity, coverage contribution, or structural patterns that generalize. It could retrieve programs based on semantic similarity to the generation task, not just literal syscall presence. It could even synthesize fragments from multiple programs rather than copying whole examples.

**Adaptive Context Assembly.** Currently, SyzGPT assembles context using fixed rules: include these dependencies, add these examples, wrap in this prompt template. An agent could make these choices dynamically based on what it knows about the target. For a simple, well-documented syscall, minimal context might suffice. For a complex ioctl with dozens of flag combinations, the agent might choose to retrieve more extensive examples or query the syzlang schema in detail. The assembly strategy becomes part of the generation task rather than a fixed pipeline stage.

**Cross-Program Learning.** SyzGPT generates programs one syscall at a time. An agent could maintain memory across generations, learning which patterns tend to produce valid programs, which dependency chains are fragile, and what validation errors are common for particular syscall families. This accumulated knowledge could guide future retrievals and generation attempts in a way that isolated one-shot generation cannot.

## What We Are Not Changing

Some aspects of SyzGPT do not need agentic enhancement. The Feedback-Guided Seed Generation (FGSD) mechanism consists of syntax-feedback and coverage-feedback components. The syntax repair mechanism, for instance, works fine as a rule-based post-processor. We considered using LLM-based iterative repair early on, but the token cost was prohibitive and the latency unacceptable for batch generation. Rule-based repair is fast and effective enough.

Similarly, the coverage-feedback re-generation loop that SyzGPT already implements serves its purpose. When programs fail to execute correctly or achieve coverage, the system includes them in the context for subsequent attempts. This is not fundamentally broken; it just operates at the batch level rather than the individual program level.

## A Path Forward

Our working hypothesis is that the future of SyzGPT lies in a hybrid approach: keep the DRAG+FGSD foundation, but let agents operate on top of it.

The dependency graph stays. The static analysis stays. The efficient retrieval stays. But we add an agent layer that decides what to retrieve, evaluates what it gets, and dynamically adjusts the generation strategy. The agent is not generating from scratch every time; it is orchestrating the existing SyzGPT components more intelligently.

This feels like the right balance. It preserves what works while addressing the genuine limitations that have become apparent with hindsight and changing technology. We are exploring implementations of this approach and will share what we learn.

---

*Last updated by Zhiyu: April 2026*
