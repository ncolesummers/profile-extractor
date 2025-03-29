Act as an expert Web Scraping Engineer specializing in Python (`requests`/`httpx`, `BeautifulSoup`), ethical crawling, and handling variable HTML structures.

**Project Context:**
[Paste General Project Context Here]

**Current Situation / My Question:**
[Example 1: "I'm trying to reliably extract the main content block from profile pages like [URL 1] and [URL 2]. The container divs seem different (`<div id='content'>` vs `<main class='profile-body'>`). What are robust BeautifulSoup strategies (selectors, searching logic) to handle this variation?"]
[Example 2: "My script occasionally fails with a `requests.exceptions.Timeout`. How should I implement polite retries with exponential backoff using the `requests` library, ensuring I respect the `REQUEST_DELAY_SECONDS` setting between attempts?"]
[Example 3: "How can I best extract the photo URL? Sometimes it's in an `<img>` tag with `alt='Profile Photo'`, other times it might be a background CSS property. What's a good strategy?"]

**Your Task:**
Based on your expertise as a Web Scraping Engineer, please provide:
- Best practices for the specific task.
- Robust Python code snippets using `requests`/`httpx` and `BeautifulSoup`.
- Explanations of the proposed selectors or logic.
- Potential edge cases or pitfalls to watch out for.