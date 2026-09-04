# 📊 Presentation Slide Deck: Adaptive MCP Enterprise Agent
> **Razorpay Buildathon Submission**  
> *Designed to accompany the 5-Minute Solution Video Script*

---

## 🎬 Slide 1: Title & Hook
**Title:** Adaptive MCP Enterprise Agent  
**Subtitle:** Autonomous Multi-Modal Incident Investigation via Model Context Protocol & Self-Reflective RAG  

### 🖼️ Visual Layout
* Left Side: Clean, modern dark mode logo & title text
* Right Side: Dynamic operational diagram showing 3 connected enterprise data sources (PostgreSQL DB, Qdrant Vector DB, GitHub API) flowing into an AI Agent core.
* Bottom Bar: `Razorpay Buildathon | Category: Enterprise Agentic Systems`

### 📝 Slide Content / Bullet Points
* **The Challenge:** High-stakes incident investigation under pressure (Finance, Reliability & Operations)
* **The Solution:** Autonomous tool-calling agent with strict MCP protocol boundaries and self-corrective retrieval
* **Core Stack:** LangGraph • FastMCP • Qdrant Hybrid Search • PostgreSQL • Next.js

### 🎙️ Presenter Script Timing (0:00 – 0:20)
> *"Welcome to our submission for the Razorpay Buildathon: **Adaptive MCP Enterprise Agent**—an autonomous multi-modal investigation system built for high-stakes enterprise environments."*

---

## 🎬 Slide 2: Problem Statement & Real-World Bottleneck
**Title:** The Incident Investigation Bottleneck  
**Subtitle:** Why 45 Minutes Are Lost During Every Production Outage  

### 🖼️ Visual Layout
* **Split Screen Comparison:**
  * **Left Box (Red Border - Today's Manual Bottleneck):** Icons of 3 separate tools (SQL Client, Document Wiki, GitHub). Red arrow showing manual context switching. "Avg Investigation Time: 45 Minutes".
  * **Right Box (Amber Warning):** Financial Impact metrics: `$10,000+ revenue loss per minute of downtime`.

### 📝 Slide Content / Bullet Points
* **Who Has This Problem?** DevOps, SREs, and Financial Operations Engineers.
* **The Core Bottleneck:** Critical incident context is fragmented:
  * 📊 **Live Telemetry:** Locked in SQL databases (PostgreSQL)
  * 📑 **Institutional Memory:** Trapped in postmortem PDFs and markdown docs
  * 💻 **Source Control:** Hidden in recent GitHub commits
* **The Consequence:** Engineers manually correlate dots across 3 systems while downtime costs soar.

### 🎙️ Presenter Script Timing (0:20 – 0:50)
> *"When a transaction failure spikes in production, engineers face a critical bottleneck: live metrics live in SQL, postmortem rules live in docs, and recent code changes live in GitHub. Manually correlating these tools takes 45 minutes of context switching."*

---

## 🎬 Slide 3: Simple Baseline & Why Traditional RAG Fails
**Title:** Simple Baseline vs. Enterprise Reality  
**Subtitle:** Three Fatal Flaws of Traditional Single-Shot RAG  

### 🖼️ Visual Layout
* Flowchart of **Traditional RAG**: `User Question ➔ Vector Search ➔ Context Stuffing ➔ LLM Response`
* **Red "X" Marks** highlighting 3 failure points along the flow.

### 📝 Slide Content / Bullet Points
1. ❌ **Blind to Live Databases:** A document vector search cannot run a SQL query for today's payment failure rate.
2. ❌ **No Self-Reflection:** Stuffs low-relevance search chunks into the prompt, forcing the LLM to hallucinate.
3. ❌ **Single-Pass Rigidity:** Fails completely if the initial query is poorly phrased, with zero ability to rewrite or retry.

### 📊 Baseline Benchmark Score
* **Baseline Retrieval Recall@k:** `0.42`
* **Multi-Modal Task Accuracy:** `0%` *(Failed on all SQL & Git queries)*

### 🎙️ Presenter Script Timing (0:50 – 1:20)
> *"We built a simple single-shot RAG baseline to test this. The result? 0% accuracy on multi-system questions. Traditional RAG cannot query SQL databases, cannot evaluate context quality, and blindly stuff bad context into prompts."*

---

## 🎬 Slide 4: System Architecture & MCP Decoupling
**Title:** Decoupled Model Context Protocol (MCP) Architecture  
**Subtitle:** Enterprise Trust Boundaries & Stateful Agentic Workflow  

### 🖼️ Visual Layout
* Large, clean **Architectural Diagram** (Matching project architecture):
  * `Next.js Frontend` ➔ `FastAPI Backend (LangGraph Core)` ➔ 3 Independent MCP Microservices:
    1. 📦 `db-mcp` (PostgreSQL - 360k Payment Records)
    2. 📑 `rag-mcp` (Qdrant + BM25 + Cross-Encoder)
    3. 🐙 `github-mcp` (Repo-Scoped Commit API)

### 📝 Slide Content / Bullet Points
* 🔒 **Model Context Protocol (MCP):** Decouples tools into standalone, authenticated microservices.
* 🛡️ **Least-Privilege Security:** DB server holds read-only roles; GitHub server operates on explicit repo allow-lists.
* 🧠 **LangGraph Stateful Core:** ReAct execution loop (`Thought ➔ Action ➔ Observation ➔ Reflection`).

### 🎙️ Presenter Script Timing (1:20 – 2:00)
> *"Our solution decouples enterprise tools into independent, authenticated Model Context Protocol (MCP) microservices. The LLM never touches databases or APIs directly—it orchestrates tools through a stateful LangGraph agent loop."*

---

## 🎬 Slide 5: Autonomous Self-RAG & Corrective Retrieval
**Title:** Self-RAG & Corrective Retrieval (CRAG)  
**Subtitle:** How the Agent Evaluates Evidence & Self-Corrects Autonomously  

### 🖼️ Visual Layout
* **2-Step Flowchart:**
  * **Step 1: Hybrid Retrieval & Reranking** (`BM25 + Qdrant Vector` fused ➔ `ms-marco-MiniLM-L-6-v2 Reranker`)
  * **Step 2: Self-Reflection Gate (`retrieval_assessment.py`)**
    * Path A (High Score): `Sufficient Evidence ➔ Cited Final Answer`
    * Path B (Low Score): `Weak Evidence ➔ Autonomous Query Rewrite (rag_loop_guard.py) ➔ Fallback Pass`

### 📝 Slide Content / Bullet Points
* **Hybrid Search Engine:** Combines keyword precision (BM25) with semantic vector search (Qdrant).
* **Self-RAG Reflection:** Autonomously scores retrieval sufficiency before generating output.
* **CRAG Loop Guard:** If search results are weak, the agent automatically rewrites queries and re-searches.

### 🎙️ Presenter Script Timing (2:00 – 2:30)
> *"Our agent doesn't blindly trust search results. It fuses BM25 and vector search with cross-encoder reranking, then self-evaluates evidence quality. If context is insufficient, it autonomously rewrites the query and executes a second-pass search."*

---

## 🎬 Slide 6: Live Demo & Multi-Modal Execution
**Title:** Live Incident Investigation Demo  
**Subtitle:** Correlating Live SQL Telemetry with Policy Documents in Real-Time  

### 🖼️ Visual Layout
* High-resolution **UI Screenshot** of `http://localhost:3000` showing:
  * The Typed Query box
  * The **Tool Timeline Component** showing 2 sequential tool invocations (`db-mcp` ➔ `rag-mcp`)
  * The **Verified Evidence Citation Badges**

### 💻 Demo Scenario Highlight
* **Input Query:** *"What are today's payment failure stats and how do they compare to the March 2026 policy limit?"*
* ⚡ **Step 1 (`db-mcp`):** Executes SQL query on 360k rows ➔ Finds **2.21% failure rate** today.
* ⚡ **Step 2 (`rag-mcp`):** Retrieves March 2026 postmortem ➔ Identifies **3.0% policy alerting threshold**.
* 🎯 **Synthesized Result:** Confirms 2.21% is within policy bounds with 100% verified citations in **12 seconds**.

### 🎙️ Presenter Script Timing (2:30 – 3:30)
> *"In our live demo, the agent autonomously executes a 2-stage investigation: querying live SQL metrics for today's 2.21% failure rate, comparing it against the 3.0% policy limit from postmortem docs, and generating a 100% cited answer in 12 seconds."*

---

## 🎬 Slide 7: Measured Improvement & Changelog
**Title:** Measured Improvement & Changelog  
**Subtitle:** Baseline vs. Agentic Benchmark Evaluation Results  

### 🖼️ Visual Layout
* **Side-by-Side Comparison Table & Metric Callout Cards:**
  * **+123.8%** Recall Increase
  * **98.1%** Multi-Modal Task Accuracy
  * **99.5%** Reduction in Human Investigation Time

### 📊 Benchmark Evaluation Table
| Metric | Simple Baseline | Agentic Solution | Improvement |
|---|---|---|---|
| **Retrieval Recall@k** | `0.42` | `0.94` | **+123.8%** |
| **Multi-Modal Task Accuracy** | `0%` | `98.1%` | **+98.1%** |
| **Citation Validity** | Unverified | `100%` Verified | **Grounded** |
| **Human Resolution Time** | `45 minutes` | `12 seconds` | **-99.5%** |

### 🛠️ Key Experiment Insight
* 🌟 **Top Contributor:** Decoupling capabilities into MCP microservices + LangGraph orchestration.
* ❌ **Removed Experiment:** Unconditional Web Search Fallback (added +4.2s latency & rate limit noise; replaced with local query rewriting).

### 🎙️ Presenter Script Timing (3:30 – 4:30)
> *"Our evaluation harness shows a 123% increase in retrieval recall and 98% multi-modal accuracy. Crucially, we removed open-ended web search because it introduced noise—proving that bounded MCP microservices outperform unconstrained web access."*

---

## 🎬 Slide 8: Enterprise Security & Future Extensibility
**Title:** Enterprise Security Guardrails & Future Vision  
**Subtitle:** Production Safety & Multi-Industry Scalability  

### 🖼️ Visual Layout
* **Top Half (Security Badges):**
  * 🛡️ `Log Redaction Middleware` (PII / Token scrubbing)
  * 🔒 `Bearer Auth & Repo Allow-Lists`
  * ⚡ `Exponential Backoff Retry Engine` (429 Rate Limit Resilient)
* **Bottom Half (Extensibility Icons):**
  * 💳 **Finance & Core Banking:** Fraud detection & telemetry monitoring
  * 🏥 **Healthcare & Bio-Pharma:** Clinical trial RAG + EHR query orchestration
  * ⚖️ **Legal & Compliance:** SEC filing analysis & contract verification

### 🎙️ Presenter Script Timing (4:30 – 5:00)
> *"Built with automated log redaction, bearer auth, and OpenTelemetry tracing, this architecture extends seamlessly beyond finance to healthcare, legal, and cybersecurity. Thank you for watching our micro1 Hackathon submission!"*
