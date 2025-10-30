import { MarkdownDocumentFetcher } from "./markdown-document.fetcher.js";
import { TossPaymentsDocument } from "./toss-payments-document.js";
import { RawDocs } from "./types.js";

export class TossPaymentsDocumentLoader {
  private documentId: number = 0;
  private readonly links: string[] = [];
  private readonly tossPaymentsDocuments: Map<string, TossPaymentsDocument> =
    new Map();

  constructor(
    private readonly rawDocs: RawDocs[],
    private readonly documentFetcher: MarkdownDocumentFetcher
  ) {
    this.rawDocs.forEach((doc) => {
      if (doc.link) {
        this.links.push(doc.link);
      }
    });
  }

  async load(): Promise<void> {
    await this.collectAll();
  }

  getDocuments(): TossPaymentsDocument[] {
    return Array.from(this.tossPaymentsDocuments.values());
  }

  private async collectAll() {
    await Promise.all(
      this.rawDocs.map(async (docs) => {
        try {
          if (this.tossPaymentsDocuments.has(docs.link)) {
            return [];
          }

          const tossPaymentDocument = await this.collect(docs);

          this.tossPaymentsDocuments.set(docs.link, tossPaymentDocument);
        } catch (error) {
          console.error(`Failed to fetch document from ${docs.link}:`, error);
        }
      })
    );
  }

  private async collect(docs: RawDocs) {
    const document = await this.documentFetcher.fetch(docs.link);

    const keywordSet = new Set<string>();

    document.metadata.keyword.forEach((keyword) => {
      keywordSet.add(keyword.toLowerCase());
      keywordSet.add(keyword.toUpperCase());
      keywordSet.add(keyword);
    });

    const tossPaymentDocument = new TossPaymentsDocument(
      keywordSet,
      document,
      docs.version,
      this.documentId++,
      docs.category
    );
    return tossPaymentDocument;
  }
}
