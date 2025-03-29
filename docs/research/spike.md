# Foundation Model Data Extraction Spike

## Overview

This spike is to explore the feasibility of creating the Person profile import dataset for the new University of Idaho website. The alternative approach is to use our legacy database that's poorly documented and not well understood. I want to see if we can use a foundation model to extract the data we need from the new website.

### Approach

I'll use a foundation model (Gemini 2.0 Flash) to extract the data from the new website based on the [Cost Benefit Analysis](./model-cost-benefit-analysis.md) I've already done. If there are any issues, I'll evaluate Claude 3.5 Sonnet and OpenAI GPT-4o for the more complex pages.

First, I need to identify the profile pages on the existing website to extract the data from. Then, I will crawl and extract the data from a subset of those profile pages to test the accuracy of the foundation model. I'll use the llm-as-a-judge pattern to evaluate the accuracy as well as the cost of the extraction before making any decisions.

## Results

## Recommendations

## Next Steps
