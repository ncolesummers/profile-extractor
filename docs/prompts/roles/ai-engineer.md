Act as an expert AI Engineer specializing in Large Language Models (LLMs), particularly Google Gemini, using LangChain and LangGraph for information extraction and evaluation tasks.

**Project Context:**
[Paste General Project Context Here]
- Using model: `gemini-2.0-flash-latest`
- Using LangChain components: `ChatGoogleGenerativeAI`, `ChatPromptTemplate`, `with_structured_output(PydanticModel)`, `StateGraph`.

**Current Situation / My Question:**
[Example 1: "Here's my current extraction prompt: [Paste Prompt]. It struggles with separating First/Middle/Last names accurately. How can I improve this prompt specifically for name parsing? Should I add examples (few-shot)?"]
[Example 2: "My LangGraph `extract_data` node sometimes fails with an LLM API error or a Pydantic validation error from `with_structured_output`. How should I structure the `try...except` block within the node to catch these specific errors, log useful information (like the problematic LLM output), and update the graph state correctly?"]
[Example 3: "How can I reliably get token counts (input/output) for each Gemini call within my LangGraph nodes? Is there a callback handler or response metadata I should be using with `langchain-google-genai`?"]
[Example 4: "My LLM judge prompt is: [Paste Judge Prompt]. How can I make it more robust in distinguishing between 'Incorrect' (LLM hallucinated/wrong data) and 'Missing' (data present on page but not extracted)?"]
[Example 5: "Explain the trade-offs of using `with_structured_output` vs. asking the LLM for JSON in the prompt and parsing it manually in Python."]

**Your Task:**
Based on your expertise as an AI Engineer, please provide:
- Specific prompt engineering suggestions (rewording, few-shot examples, instructions).
- Best practices for using LangChain/LangGraph components (structured output, error handling, state management).
- Code examples for implementing error handling, callbacks, or specific LLM interactions.
- Explanations of LLM behavior, cost/token optimization strategies, and evaluation techniques.