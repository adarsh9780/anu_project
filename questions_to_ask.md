Multicollinearity: "In your E-commerce project, you mentioned high multicollinearity led you to switch from Linear Regression to a Random Forest Regressor. Which specific metric (like VIF) did you use to detect that multicollinearity?" 
+1


Random Forest Logic: "Why does a Random Forest Regressor handle multicollinearity better than a standard Linear Regression model?" 
+1


Class Imbalance: "For Loan Default Prediction, you used SMOTE. Can you explain how SMOTE creates synthetic samples differently than simple oversampling?" 


Missing Data: "You used 'Miss Forest' for imputation. In what scenario would you choose Miss Forest over simpler methods like mean or median imputation?"


🟢 Easy: Foundations & Prompting
Focus: Can they use LLMs and understand basic concepts like RAG and prompting?

System vs. User Prompts: What is the difference between a system message and a user message? How do they affect agent behavior?

Prompt Engineering: Can you explain "Few-shot prompting"? When would you use it over "Zero-shot"?

RAG Basics: What are the three main steps in a Retrieval-Augmented Generation (RAG) pipeline?

Tokenization: What is a token, and why should we care about "context window" limits when building an agent?

Temperature: If an agent needs to extract data from a PDF into a strict JSON format, would you set the temperature to 0 or 1.0? Why?

Embeddings: In simple terms, what is a vector embedding, and why do we use vector databases?

Hallucinations: What is an LLM hallucination, and what is one simple prompting technique to reduce it? (e.g., "Answer only from the provided text").

API Basics: How do you handle a "Rate Limit" error when calling an LLM API?

Tools/Libraries: Which libraries have you used for AI development? (e.g., LangChain, OpenAI SDK, LiteLLM).

JSON Formatting: Why is it sometimes difficult for an LLM to return valid JSON, and how would you fix it?

🟡 Medium: Workflows & Tool Use
Focus: Can they connect an LLM to the "real world" via tools and memory?

Function Calling: How does "Function Calling" (or Tool Use) actually work? Does the LLM execute the code itself?

Memory Management: If an agent needs to remember the last five messages in a conversation, how would you implement that memory?

ReAct Pattern: Can you explain the "Reason + Act" (ReAct) framework for agents?

Vector Search vs. Keyword Search: When would a vector search fail where a simple keyword search (BM25) might succeed?

Chain of Thought (CoT): How does asking an agent to "think step-by-step" improve its performance on complex tasks?

Data Extraction: You need to extract information from a 50-page document. The context window is too small. How do you approach this?

Parsing Errors: If an agent is supposed to call a "Weather Tool" but provides the wrong argument type, how would you programmatically handle that "loop" to fix it?

Streaming: Why is streaming (SSE) important for user experience in agentic POCs?

Evaluation: You built a chatbot for a POC. How do you decide if version A is "better" than version B without manually reading 100 logs?

Small Models: When would you choose a smaller model (like Llama 3 8B or GPT-4o-mini) over a "frontier" model like GPT-4o for a POC?

🔴 Advanced: Orchestration & Production Readiness
Focus: Can they handle complex logic and think about the limitations of agents?

Multi-Agent Systems: When should you break a single agent into a "Multi-Agent" team (e.g., a Researcher agent + a Writer agent)?

State Management: How do you maintain the "state" of an agent if it needs to pause for a human-in-the-loop approval and resume 24 hours later?

Prompt Injection: How would you protect an agent that has access to a "Delete User" tool from a malicious user prompt?

Agentic Loops (Infinite Loops): How do you prevent an agent from getting stuck in a loop where it keeps calling the same tool unsuccessfully?

Advanced RAG: What is "Reranking," and how does it improve retrieval quality in a POC?

Long-term Memory: How would you implement a "memory" that persists across different weeks or months for the same user?

Cost Optimization: Your POC is successful, but it's too expensive. What are three ways to reduce the cost per request?

Latency: If an agentic workflow takes 30 seconds to run, how would you identify the bottleneck? (Mentioning "Tracing" or "Observability").

Fine-tuning vs. RAG: Under what specific circumstances would you suggest fine-tuning a model instead of just using RAG?

Structured Outputs: How do you ensure an agent follows a complex Pydantic schema 100% of the time? (Mentioning "Constrained Sampling" or "instructor" library).

🛠 Practical "POC" Scenario (Bonus)
Since the role is about building POCs, give them a whiteboard/coding scenario:

"We need a POC for an agent that takes a URL, reads the website, and writes a 3-sentence summary into a Slack channel. Walk me through the architecture, the tools you'd use, and where you think it would most likely fail."

What to look for in their answer:

Tooling: Did they mention a scraper (BeautifulSoup/Firecrawl)?

Safety: Did they mention handling 404 errors or large websites?

Speed: Did they focus on getting it working (MVP) before making it perfect?