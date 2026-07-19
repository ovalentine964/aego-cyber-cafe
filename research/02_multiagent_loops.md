# Multi-Agent Systems & Loop Systems — Research Report
**Week Ending July 19, 2026 | Aego Cyber Cafe Intelligence Brief**

---

## Executive Summary

The multi-agent AI landscape has reached an inflection point in mid-2026. Five orchestration patterns now dominate production systems (fan-out, pipeline, debate, supervisor, swarm). The A2A protocol has surpassed 150 organizations and reached v1.0 stable. Agent self-improvement through "harness engineering" is emerging as the key differentiator. For Valentine's ecosystem — Alphastack's 17-agent trading system, Cohusdex's economic intelligence, Aego's service automation, and Hadhi's voice-based CFO — these developments represent immediate opportunities to reduce costs, improve reliability, and scale operations across Africa's informal economy.

---

## 1. Multi-Agent Framework Updates

### 1.1 OpenAI Agents SDK & AgentKit

**Status:** The OpenAI Agents SDK is now the primary orchestration backbone. OpenAI's AgentKit (launched Oct 2025) added visual Agent Builder, Connector Registry, and ChatKit for embedded agent UIs. However, OpenAI announced in June 2026 that Agent Builder and Evals products are being wound down (effective Nov 30, 2026), redirecting developers to the Agents SDK for code-based workflows and Workspace Agents in ChatGPT for natural-language use cases.

**Key Architecture:** The SDK uses explicit **handoffs** — one-way control transfers implemented as tool calls. An orchestrator agent delegates to specialist agents via handoff primitives, maintaining transparent control flow. The SDK supports guardrails (open-source, modular safety for PII masking, jailbreak detection), tracing, and state management.

**Real-World Deployment (May 2026):** OBaI, a multi-agent research platform, migrated from a monolithic orchestrator prompt to SandboxAgent with lazy-loaded skills. Key lessons:
- Monolithic orchestrator prompts become bottlenecks — rules drift into conflict
- Lazy-loaded skills reduce context cost by loading specialist instructions only when needed
- Bigger models aren't automatically better everywhere — smaller, focused models outperform on narrow tasks
- Regression testing matters more than expected in multi-agent systems

**Sources:**
- [OpenAI AgentKit Announcement](https://openai.com/index/introducing-agentkit/) (Oct 2025, updated June 2026)
- [OBaI Multi-Agent Scaling](https://blog.gopenai.com/how-the-openai-agents-sdk-helped-obai-scale-its-multi-agent-research-stack-f0fd73e57b34) (May 11, 2026)

### 1.2 LangChain / LangGraph / Deep Agents

LangChain's ecosystem has evolved significantly with three distinct layers:

**LangGraph v1.0** — The most broadly capable framework, supporting all five orchestration patterns natively (fan-out, pipeline, debate, supervisor, swarm). Uses graph-based state machines where agents are nodes and connections are edges. The `create_agent` API (replacing legacy `create_react_agent`) is now the standard.

**Deep Agents** — Long-running agent framework for complex tasks. Key innovation: **Recursive Language Models (RLMs)** support (July 1, 2026). Instead of turn-by-turn execution, models write code in a REPL that dispatches subagents recursively. This enables:
- Processing inputs 100× beyond a model's context window
- Deterministic coverage (code guarantees iteration, not model judgment)
- Bespoke orchestration (arbitrary branching, parallel, sequential pipelines)

**LangSmith Engine** (July 7, 2026) — "Improving Agents is a Data Mining Problem." Uses specialized agents to mine traces at scale, find issues, create code fixes, generate evals, and commit improvements to memory/context stores. Key insight: traces are the currency of long-horizon agent improvement. Open models fine-tuned for narrow trace-judging tasks outperform frontier models at 100× lower cost.

**NemoClaw Blueprint** (July 8, 2026) — Partnership with NVIDIA combining LangChain Deep Agents Code + Nemotron 3 Ultra + NVIDIA OpenShell runtime. Achieved 0.86 aggregate score on agent eval suite at $4.48 cost vs $43.48 for next-closest model — roughly 10× lower inference cost.

**Sources:**
- [LangChain Blog](https://www.langchain.com/blog) (multiple articles, July 2026)
- [RLMs in Deep Agents](https://www.langchain.com/blog/how-to-use-rlms-in-deep-agents) (July 1, 2026)
- [Improving Agents is a Data Mining Problem](https://www.langchain.com/blog/improving-agents-is-a-data-mining-problem) (July 7, 2026)
- [NemoClaw Deep Agents Blueprint](https://www.langchain.com/blog/langchain-and-nvidia-launch-the-nemoclaw-deep-agents-blueprint) (July 8, 2026)

### 1.3 Google Agent Development Kit (ADK)

Google ADK now supports **Python, TypeScript, Go, Java, and Kotlin**. ADK 2.0 GA introduced **graph workflows** and collaborative agents. Key features:
- **Graph Workflows:** Weave deterministic code with adaptive AI reasoning through structured, graph-based architectures with explicit execution paths
- **Context Management:** Sessions, memory, tool outputs, and artifacts assembled into structured views; automatic filtering of irrelevant events, summarization of older turns, lazy-loading of artifacts
- **Agent-as-Builder:** "Build agents with agents" — AI-enabled scaffolding, building, testing, evaluating, and deploying ADK agents
- **Multi-protocol support:** Native A2A integration via `google.adk.a2a.utils`

**Source:** [ADK Documentation](https://adk.dev/) (2026)

### 1.4 Strands Agents (Amazon/AWS)

Open-source agent SDK built from production systems inside Amazon. 6,600+ GitHub stars. Available in Python and TypeScript. Key features:
- **Hooks system:** `BeforeToolCallEvent` allows policy enforcement (e.g., cancel tool calls that lack source citations)
- **Model-agnostic:** Works with Amazon Bedrock, Anthropic, OpenAI, and more
- **MCP integration** natively supported
- **Strands Evals:** Production evaluation framework for multi-agent systems
- **Multi-agent patterns** documented with customer support examples on Amazon Bedrock

**Source:** [Strands Agents](https://strandsagents.com/) (2026)

### 1.5 CrewAI

CrewAI has matured into a production platform with:
- **Agents, Crews, and Flows** as core abstractions
- **Flows:** Orchestrate start/listen/router steps, manage state, persist execution, resume long-running workflows
- **Enterprise features:** Triggers (Gmail, Slack, Salesforce, HubSpot), team management with RBAC, deployment console
- **Integration tools:** Call existing CrewAI automations or Amazon Bedrock Agents directly from crews
- **Memory, knowledge, and observability** baked in

**Source:** [CrewAI Documentation](https://docs.crewai.com/) (2026)

### 1.6 Anthropic Claude Agent SDK

Renamed from Claude Code SDK in early 2026. Excels at **supervisor** and **fan-out** patterns with subagents (one level deep). The Claude ecosystem also includes:
- **Tool Search Tool:** Probes tool catalogues and loads only relevant ones (addresses context window bloat from large tool definitions)
- **Context engineering focus:** Anthropic published guidance on effective context engineering for AI agents

**Source:** [Morphllm Framework Comparison](https://www.morphllm.com/ai-agent-framework) (2026)

---

## 2. Five Production Orchestration Patterns (2026)

A landmark analysis (Digital Applied, May 17, 2026) identifies five distinct patterns dominating production:

### Pattern 1: Fan-Out (Parallel Scatter-Gather)
- Coordinator dispatches tasks to multiple agents simultaneously
- Wall-clock latency = slowest branch (not sum)
- Best for: parallel research, parallel code review, parallel document processing
- Failure mode: partial — one branch fails, must decide how to aggregate remaining

### Pattern 2: Pipeline (Sequential Chain)
- Agents execute in sequence, each refining the previous output
- Failure mode: cascade — bad mid-stage contaminates everything after
- Best for: multi-stage processing where order matters

### Pattern 3: Debate (Multi-Perspective Critique)
- Same question sent to multiple agents, judge adjudicates conflicting answers
- Cost: ~2.5× single-model baseline (Microsoft Copilot Council pattern)
- Two-stage Critique variant adds ~20% more
- Use when stakes justify the premium

### Pattern 4: Supervisor (Hierarchical Delegation) ⭐ **2026 Production Default**
- Orchestrator delegates non-overlapping tasks to specialist sub-agents
- Claude Code subagents, LangGraph Supervisor, OpenAI Agents SDK handoffs all converge here
- Cost scales with distinct subtasks, not perspectives
- Best starting point for most cross-domain tasks

### Pattern 5: Swarm (Dynamic Peer Agents)
- Frontier pattern — Kimi K2.6 scales to 300-agent swarms with 12-hour autonomous sessions
- Parallel-Agent Reinforcement Learning coordinates up to 100 sub-agents with 1,500 parallel tool calls
- No other framework ships swarm as first-class native at this scale

**Source:** [Multi-Agent Orchestration: 5 Patterns That Work](https://www.digitalapplied.com/blog/multi-agent-orchestration-5-patterns-that-work) (May 17, 2026)

---

## 3. Agent-to-Agent Communication Protocols

### 3.1 A2A (Agent-to-Agent) Protocol

**Milestone:** A2A surpassed 150 organizations and reached v1.0 stable specification (April 9, 2026). Hosted by the Linux Foundation under the Agentic AI Foundation (AAIF).

**Key v1.0 features:**
- **Signed Agent Cards** for cryptographic identity verification
- **Enterprise-grade multi-tenancy**
- **Modernized security flows**
- **Web-aligned architecture** supporting familiar security and load-balancing patterns
- **Defined migration path** for early adopters

**Platform integration:** Deep integration across Google Cloud, Microsoft, and AWS. Production deployments in supply chain, financial services, insurance, and IT operations.

**What A2A solves:** How agents discover each other, negotiate capabilities, and hand off tasks — the coordination layer between independent agent systems.

**Source:** [Linux Foundation A2A Press Release](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) (April 9, 2026)

### 3.2 MCP (Model Context Protocol)

**Status:** Created by Anthropic, donated to Linux Foundation AAIF in December 2025. Crossed 97 million monthly SDK downloads (Python + TypeScript combined) by February 2026. Adopted by every major AI provider.

**What MCP solves:** How an agent talks to tools — the interface between an AI brain and its hands. Uses JSON-RPC 2.0 with four capability types: Resources, Tools, Prompts, Sampling.

**Key distinction:** MCP = agent↔tool. A2A = agent↔agent. They solve completely different problems and are complementary.

**Broad ecosystem support:** Claude, ChatGPT, VS Code, Cursor, and many others support MCP.

**Sources:**
- [MCP Official Site](https://modelcontextprotocol.io/) (2026)
- [MCP vs A2A Complete Guide](https://dev.to/pockit_tools/mcp-vs-a2a-the-complete-guide-to-ai-agent-protocols-in-2026-30li) (March 4, 2026)

### 3.3 Agent Identity & Authentication

A critical unsolved problem identified by n8n (July 10, 2026):
- Agents have slipped between human and non-human identity frameworks
- No standard way to formally define agent identity, assign policies, and monitor activities
- Google Gemini Enterprise Agent Platform leads with SPIFFE-based Agent Identity
- Critiques exist: SPIFFE treats all replicas as identical, mismatching agents' non-deterministic behavior
- Microsoft Entra Agent ID is emerging but requires complex setup

**Source:** [n8n Blog: Agent Identity](https://blog.n8n.io/agent-identity-reliable-execution-and-intent-are-only-half-way-solved/) (July 10, 2026)

---

## 4. Loop Systems & Self-Improving Agents

### 4.1 Harness Engineering for Self-Improvement

Lilian Weng's seminal post (July 4, 2026) defines the emerging field of **harness engineering** — the system surrounding a base model that orchestrates execution. Three key design patterns:

**Pattern 1: Workflow Automation**
- Goal-oriented loop: plan → execute → observe/test → improve → execute again
- Karpathy's autoresearch as canonical example
- Agent analyzes its own trajectories and failure cases, iterating through an "agent runtime"

**Pattern 2: File System as Persistent Memory**
- Harness should not carry entire workflow in context — keep durable state in files
- Artifacts (experiment logs, code diffs, error traces, past trajectories) grow beyond context windows
- File system operations (read, write, edit via bash) are foundational LLM skills

**Pattern 3: Sub-agent and Backend Jobs**
- Main agent spawns parallel subagents for hypothesis search, concurrent experiments
- Key: make parallelism explicit and inspectable
- Store outputs as files/logs/status records (not transient chat context)

**Prediction:** Harness engineering will evolve toward meta-methodology — the harness itself becomes an optimization target with fewer heuristic rules and more general mechanisms. Mature harnesses enable auto-research for model self-improvement.

**Source:** [Lilian Weng: Harness Engineering for Self-Improvement](https://lilianweng.github.io/posts/2026-07-04-harness/) (July 4, 2026)

### 4.2 ICLR 2026 Workshop on Recursive Self-Improvement

Held April 26, 2026. Workshop abstract: "Recursive self-improvement (RSI) is moving from thought experiments to deployed AI systems. LLM agents now rewrite their own codebases or prompts, scientific discovery pipelines schedule continual fine-tuning, and robotics stacks patch controllers from streaming telemetry."

Organized around five lenses:
1. Change targets inside the system
2. Temporal regime of adaptation
3. Mechanisms and drivers
4. Operating contexts
5. Evidence of improvement

**Source:** [ICLR 2026 RSI Workshop](https://iclr.cc/virtual/2026/workshop/10000796) (April 26, 2026)

### 4.3 Self-Harness: Propose-Evaluate-Accept Loop

Referenced in Weng's post: Self-Harness uses a loop of weakness mining, proposal generation, evaluation, and acceptance to improve agent harnesses automatically. The agent identifies its own failure modes, proposes fixes, evaluates them, and accepts improvements.

### 4.4 Evolutionary Search for Agent Optimization

Evolutionary program search is emerging as a method to optimize agent harnesses — treating the harness configuration as a genome that can be mutated, crossed over, and selected based on performance metrics.

### 4.5 Continual Learning as Agent Improvement

LangSmith Engine (July 7, 2026) frames agent improvement as a data mining problem:
- Mine traces to find improvement signals
- Curate evals (training data) to fit on
- Run experiments to hill-climb on specific axes
- Traces are the currency of long-horizon agent improvement
- "Scaling Dreaming" — processing large data scales over long time-horizons

---

## 5. Agent Orchestration Tools & Platforms

### 5.1 n8n (162K+ GitHub Stars)

The leading open-source workflow automation platform has embraced AI agents deeply. Recent blog posts (July 2026) cover:
- **Context Engineering for LLMs** (July 7): Managing context rot, token budgets, and dynamic context assembly
- **AI Agent Memory** (July 7): CoALA framework (working, semantic, episodic, procedural memory types)
- **Agent Identity** (July 10): The unsolved problem of agent identity, reliable execution, and intent analysis
- **LLM Tool Calling Error Handling** (recent): Architectural guide for production error handling

Key insight from n8n: Context windows alone don't solve agent memory. Long-context LLMs degrade well before stated limits. Information in the middle of long context gets lost (the "lost in the middle" problem).

**Sources:**
- [n8n Blog](https://blog.n8n.io/) (July 2026 articles)

### 5.2 Dify

Open-source platform for building AI applications. Supports agents, agentic workflows, and chatbots. Key features:
- Cloud or self-hosted deployment
- Plugin system for extending with custom tools/models
- API reference for integration
- Marketplace for community-built integrations
- CLI (`difyctl`) for terminal/CI/agent usage

**Source:** [Dify Documentation](https://docs.dify.ai/) (2026)

### 5.3 Coze

ByteDance's agent development platform (referenced in framework comparisons). Supports multi-agent workflows and is popular in the Asian market.

### 5.4 Agent Payments Protocol (AP2)

Google announced AP2 (September 2025), building on A2A for agent-to-agent payments. Relevant for fintech applications where agents need to transact with each other.

---

## 6. Real-World Multi-Agent Deployments

### 6.1 Financial Services (LangChain + Pay-i, July 17, 2026)

**RFP Processing:** Multi-agent system ingests RFP packages, extracts requirements, maps to internal capabilities, generates structured responses with citations. 65% of AI-generated drafts pass SME review without major revisions.

**AML Compliance Monitoring:** Multi-agent system for Anti-Money Laundering with specialized agents for different compliance domains.

**Key insight:** Traditional FinOps tools can't handle multi-agent cost structures. A single agent invocation involves multiple LLM calls across providers, tool calls, retries, reasoning loops — all varying per execution. Need observability platforms that connect cost to business outcomes.

**Source:** [Proving ROI of Agentic AI in Financial Services](https://www.langchain.com/blog/proving-the-roi-of-agentic-ai-in-financial-services) (July 17, 2026)

### 6.2 Agentic Finance Research (arXiv, March 14, 2026)

UCL paper proposes a four-layer architecture for financial AI agents:
1. **Data Perception** — information gathering
2. **Reasoning Engine** — analysis and decision-making
3. **Strategy Generation** — action planning
4. **Execution and Control** — trade execution with risk management

Introduces the **Agentic Financial Market Model (AFMM)** linking agent design parameters (autonomy depth, model heterogeneity, execution coupling) to market outcomes (efficiency, liquidity resilience, volatility, systemic risk).

**Source:** [AI Agents in Financial Markets](https://arxiv.org/html/2603.13942v1) (March 14, 2026)

### 6.3 HedgeAgents (ACM, 2026)

Multi-agent financial trading system using "hedging" strategies for system robustness. Each agent specializes in different aspects of portfolio management with built-in risk mitigation.

**Source:** [HedgeAgents](https://dl.acm.org/doi/10.1145/3701716.3715232) (2026)

### 6.4 Multi-Agent Trading on Alpaca (May 14, 2026)

Building multi-agent AI trading systems on the Alpaca platform, demonstrating practical architecture for cryptocurrency and stock trading with multiple specialized agents.

**Source:** [Alpaca Multi-Agent Trading](https://alpaca.markets/learn/building-a-multi-agent-ai-trading-system-on-alpaca) (May 14, 2026)

### 6.5 Schneider Electric (LangSmith, July 7, 2026)

Built LLMOps foundations at enterprise scale using LangSmith for multi-agent observability and evaluation across a large industrial enterprise.

**Source:** [Schneider Electric Case Study](https://www.langchain.com/blog/how-schneider-electric-built-their-llmops-foundations-at-enterprise-scale-with-langsmith) (July 7, 2026)

---

## 7. Analysis: Implications for the Aego Ecosystem

### 7.1 Alphastack's 17-Agent Trading System

**Current architecture:** 17 agents with a 12-phase pipeline for multi-agent forex trading.

**Recommended improvements based on research:**

1. **Adopt the Supervisor Pattern as Default:** The research consensus is clear — supervisor is the 2026 production default. Restructure Alphastack to use a clear orchestrator-worker topology where a supervisor agent delegates to specialist agents (market data, technical analysis, sentiment, risk, execution, etc.) via explicit handoffs.

2. **Implement Harness Engineering:** Following Lilian Weng's framework:
   - Use file system as persistent memory for trade logs, strategy states, error traces
   - Implement propose-evaluate-accept loops for strategy refinement
   - Make sub-agent parallelism explicit and inspectable

3. **Use RLMs for Large-Scale Data Processing:** Recursive Language Models can process forex market data 100× beyond context windows. Instead of feeding all market data into context, use code-based orchestration to partition, analyze, and reduce data programmatically.

4. **Implement Trace Mining:** Following LangSmith Engine's approach, mine trading traces to identify failure patterns, create evals, and hill-climb on strategy performance. Every trade execution becomes a training signal.

5. **Cost Optimization:** The NemoClaw blueprint shows 10× cost reduction is possible by tuning the harness around open models. Consider using Nemotron 3 Ultra or similar open models for the 17 agents instead of expensive frontier models for every agent.

6. **A2A Protocol for Agent Communication:** Adopt A2A's Agent Cards for cryptographic identity verification between trading agents. This prevents spoofing and ensures audit trails.

**Estimated impact:** 30-50% cost reduction, improved strategy iteration speed, better failure recovery.

### 7.2 Cohusdex Economic Intelligence

**Challenge:** Gathering economic intelligence across Africa's $1.4T informal economy requires processing vast amounts of unstructured data from diverse sources.

**Recommended improvements:**

1. **Fan-Out Pattern for Data Gathering:** Deploy parallel specialist agents — each focused on a different data source (mobile money APIs, government statistics, market prices, social media sentiment, news). Aggregate results at the end.

2. **MCP for Tool Integration:** Use MCP to standardize connections to diverse African data sources (M-Pesa APIs, government databases, commodity exchanges). One MCP server per data source, reusable across all agents.

3. **Context Engineering:** Follow n8n's guidance on managing context rot. As Cohusdex accumulates economic data, implement:
   - Dynamic context assembly per query
   - Semantic memory (vector stores for historical economic data)
   - Episodic memory (temporal indexing of past analyses)

4. **Debate Pattern for Economic Forecasts:** When generating economic forecasts for specific regions, deploy debate pattern — send same question to multiple analyst agents with different methodological perspectives, use a judge to synthesize.

5. **Self-Improving Loops:** Implement trace mining on economic predictions vs actual outcomes. Agents that predicted incorrectly generate training signals for improvement.

**Estimated impact:** Broader data coverage, more reliable economic forecasts, continuous improvement.

### 7.3 Aego Cyber Cafe Service Automation

**Services:** Government forms, CV generation, digital literacy training, document processing.

**Recommended improvements:**

1. **Pipeline Pattern for Document Processing:** Sequential agents for document intake → OCR/extraction → validation → formatting → submission. Each agent specializes in one stage.

2. **Dify for No-Code Agent Building:** Use Dify's visual workflow builder to create service automation flows that Aego staff can modify without coding. Self-host on Aego's infrastructure for offline capability.

3. **n8n for Workflow Orchestration:** Connect government APIs, document templates, and user interfaces through n8n workflows with AI agent nodes. The 162K+ star community means extensive integration support.

4. **Agent Memory for Returning Customers:** Implement semantic and episodic memory so returning customers don't need to re-enter information. Store document history, preferences, and past interactions.

5. **Offline-First Architecture:** Following harness engineering patterns, use file system as persistent memory. Agents can queue operations when offline and sync when connectivity returns.

**Estimated impact:** 3-5× faster document processing, better customer experience, reduced training needs.

### 7.4 Hadhi — AI CFO for Informal Workers

**Challenge:** Voice-based, offline, multi-language AI CFO for 500M informal African workers.

**Recommended improvements:**

1. **Small Model + Harness Approach:** The NemoClaw research shows that harness engineering around smaller open models can match frontier model performance at 10× lower cost. Deploy a tuned small model with a strong harness rather than expensive API calls.

2. **Procedural Memory for Financial Behaviors:** Following the CoALA framework, implement procedural memory that encodes financial advisory patterns — how to categorize expenses, when to save, how to handle irregular income. These become encoded behaviors that don't need re-learning each session.

3. **Pipeline Pattern for Financial Analysis:** Sequential agents: income categorization → expense analysis → savings recommendation → goal tracking. Each agent is small and focused.

4. **Offline RLMs:** Recursive Language Models can work with local data processing. The code-based orchestration means the model writes analysis scripts that run locally, reducing API dependency.

5. **Multi-Language Agent Specialization:** Use the supervisor pattern with language-specialist sub-agents. One supervisor routes to Swahili, Yoruba, Amharic, etc. specialists.

**Estimated impact:** 10× cost reduction enabling free service, offline capability, culturally appropriate financial advice.

### 7.5 Uhakix (Government Transparency)

**Recommended:** Use the fan-out pattern to simultaneously analyze government data from multiple sources. MCP servers for each government database. A2A protocol for inter-agency agent communication if government systems adopt agent architectures.

### 7.6 Msaidizi/Biashara AI (Business Assistant)

**Recommended:** CrewAI's enterprise features (triggers, team management, deployment) make it ideal for business automation. Use CrewAI flows for multi-step business processes (invoicing, inventory, customer follow-up). The trigger system connects to Gmail, Slack, and other tools small businesses already use.

---

## 8. Cost & Complexity Analysis

| Approach | Setup Cost | Monthly Operating Cost | Complexity | Best For |
|----------|-----------|----------------------|------------|----------|
| OpenAI Agents SDK | Low (API-based) | $50-500/agent/month | Low | Quick prototyping, supervisor patterns |
| LangGraph + Deep Agents | Medium (self-hosted) | $20-200/agent/month | Medium-High | All 5 patterns, long-running agents |
| CrewAI | Low-Medium | $30-300/agent/month | Low-Medium | Business automation, enterprise triggers |
| Google ADK | Medium | $30-250/agent/month | Medium | Multi-language, graph workflows |
| Strands Agents | Low (open source) | $20-150/agent/month | Low | AWS-native, model-agnostic |
| n8n + AI Nodes | Very Low (self-hosted) | $10-100/month total | Low | Workflow automation, non-developers |
| Dify | Very Low (self-hosted) | $10-100/month total | Low | No-code agent building, rapid iteration |

**For Alphastack (17 agents):** LangGraph + Deep Agents recommended. Cost: ~$340-3,400/month. With NemoClaw-style optimization: ~$34-340/month.

**For Cohusdex:** Fan-out pattern with LangGraph or Strands. Cost: ~$100-500/month.

**For Aego/Hadhi:** n8n + Dify for local operations + small model harness for offline. Cost: ~$50-200/month total.

---

## 9. Key Trends & Predictions

1. **Harness > Model:** The harness layer is becoming as important as model intelligence. Teams that master harness engineering will outperform those chasing frontier models.

2. **Traces as Currency:** Agent traces are the new training data. Mining traces for improvement signals is the highest-leverage capability teams can build.

3. **Protocol Convergence:** MCP (tool protocol) + A2A (agent protocol) are becoming the dual standards. Build on both.

4. **Cost Deflation:** 10× cost reductions through open model + harness tuning are achievable today. This makes free-tier AI services viable for African markets.

5. **Identity Crisis:** Agent identity remains unsolved. Early adopters of agent identity solutions will have governance advantages.

6. **Swarm Scaling:** 300-agent swarms are production reality. The question is no longer "can we coordinate many agents?" but "should we?"

7. **Self-Improvement Loops:** The propose-evaluate-accept loop is becoming the standard for continuous agent improvement. Every deployment should have one.

---

## 10. Action Items for Valentine's Ecosystem

### Immediate (This Week)
- [ ] Audit Alphastack's 17-agent architecture against the 5 patterns — identify which pattern each phase uses
- [ ] Set up LangSmith or equivalent tracing for Alphastack to start collecting improvement data
- [ ] Prototype MCP servers for Cohusdex's key African data sources

### Short-Term (This Month)
- [ ] Refactor Alphastack to use explicit supervisor pattern with handoffs
- [ ] Implement file-system-based persistent memory for trading state
- [ ] Deploy n8n + Dify for Aego service automation pilot
- [ ] Test NemoClaw-style open model + harness approach for Hadhi

### Medium-Term (This Quarter)
- [ ] Implement trace mining pipeline for Alphastack strategy improvement
- [ ] Build A2A-compliant agent cards for all ecosystem agents
- [ ] Deploy RLM-based data processing for Cohusdex economic intelligence
- [ ] Create self-improvement loops for Hadhi financial advice quality

### Long-Term (This Year)
- [ ] Achieve 10× cost reduction through harness engineering
- [ ] Build agent identity infrastructure across the ecosystem
- [ ] Scale Cohusdex to cover 20+ African economies with fan-out pattern
- [ ] Implement evolutionary search for Alphastack strategy optimization

---

## Sources Index

| # | Source | Date | URL |
|---|--------|------|-----|
| 1 | OpenAI AgentKit | Oct 2025, updated June 2026 | https://openai.com/index/introducing-agentkit/ |
| 2 | OBaI Multi-Agent Scaling | May 11, 2026 | https://blog.gopenai.com/how-the-openai-agents-sdk-helped-obai-scale-its-multi-agent-research-stack-f0fd73e57b34 |
| 3 | LangChain Blog (multiple) | July 2026 | https://www.langchain.com/blog |
| 4 | RLMs in Deep Agents | July 1, 2026 | https://www.langchain.com/blog/how-to-use-rlms-in-deep-agents |
| 5 | Improving Agents = Data Mining | July 7, 2026 | https://www.langchain.com/blog/improving-agents-is-a-data-mining-problem |
| 6 | NemoClaw Blueprint | July 8, 2026 | https://www.langchain.com/blog/langchain-and-nvidia-launch-the-nemoclaw-deep-agents-blueprint |
| 7 | ROI of Agentic AI in Finance | July 17, 2026 | https://www.langchain.com/blog/proving-the-roi-of-agentic-ai-in-financial-services |
| 8 | Agents Need Their Own Computer | July 15, 2026 | https://www.langchain.com/blog/agents-need-their-own-computer |
| 9 | Google ADK Documentation | 2026 | https://adk.dev/ |
| 10 | Strands Agents | 2026 | https://strandsagents.com/ |
| 11 | CrewAI Documentation | 2026 | https://docs.crewai.com/ |
| 12 | A2A Protocol v1.0 | April 9, 2026 | https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year |
| 13 | MCP Official Site | 2026 | https://modelcontextprotocol.io/ |
| 14 | MCP vs A2A Guide | March 4, 2026 | https://dev.to/pockit_tools/mcp-vs-a2a-the-complete-guide-to-ai-agent-protocols-in-2026-30li |
| 15 | 5 Orchestration Patterns | May 17, 2026 | https://www.digitalapplied.com/blog/multi-agent-orchestration-5-patterns-that-work |
| 16 | Harness Engineering (Lilian Weng) | July 4, 2026 | https://lilianweng.github.io/posts/2026-07-04-harness/ |
| 17 | ICLR 2026 RSI Workshop | April 26, 2026 | https://iclr.cc/virtual/2026/workshop/10000796 |
| 18 | n8n Blog: Agent Identity | July 10, 2026 | https://blog.n8n.io/agent-identity-reliable-execution-and-intent-are-only-half-way-solved/ |
| 19 | n8n Blog: Context Engineering | July 7, 2026 | https://blog.n8n.io/context-engineering-llm/ |
| 20 | n8n Blog: Agent Memory | July 7, 2026 | https://blog.n8n.io/ai-agent-memory/ |
| 21 | AI Agents in Financial Markets | March 14, 2026 | https://arxiv.org/html/2603.13942v1 |
| 22 | HedgeAgents | 2026 | https://dl.acm.org/doi/10.1145/3701716.3715232 |
| 23 | Alpaca Multi-Agent Trading | May 14, 2026 | https://alpaca.markets/learn/building-a-multi-agent-ai-trading-system-on-alpaca |
| 24 | Dify Documentation | 2026 | https://docs.dify.ai/ |
| 25 | Agent Framework Comparison | 2026 | https://www.morphllm.com/ai-agent-framework |

---

*Report compiled July 19, 2026 | Aego Cyber Cafe Research Division*
*Research agent: Multi-Agent Systems & Loop Systems*
*Next update: Week ending July 26, 2026*
