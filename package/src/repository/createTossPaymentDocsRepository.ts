import { CategoryWeightCalculator } from "../document/category-weight-calculator.js";
import { MarkdownDocumentFetcher } from "../document/markdown-document.fetcher.js";
import { parseLLMText } from "../document/parseLLMText.js";
import { TossPaymentsDocumentLoader } from "../document/toss-payments-document.loader.js";
import { TossPaymentDocsRepository } from "./toss-payment-docs.repository.js";
import { SynonymDictionary } from "../document/synonym-dictionary.js";

export async function createTossPaymentDocsRepository(
  link = "https://docs.tosspayments.com/llms.txt"
): Promise<TossPaymentDocsRepository> {
  const response = await fetch(link, {
    headers: {
      "user-agent": "TossPaymentsIntegrationGuide MCP",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch LLM text: ${response.statusText}`);
  }

  const llmText = await response.text();

  const rawDocs = parseLLMText(llmText);

  const loader = new TossPaymentsDocumentLoader(
    rawDocs,
    new MarkdownDocumentFetcher()
  );

  await loader.load();

  const documents = loader.getDocuments();

  return new TossPaymentDocsRepository(
    documents,
    new CategoryWeightCalculator(),
    new SynonymDictionary()
  );
}
