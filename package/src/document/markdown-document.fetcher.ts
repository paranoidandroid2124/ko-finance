import { BasicHttpHeaders } from "../constants/basic-http-headers.js";

import { RemoteMarkdownDocument } from "./types.js";
import { MarkdownSplitter } from "./splitter/markdown-splitter.js";

export class MarkdownDocumentFetcher {
  async fetch(link: string): Promise<RemoteMarkdownDocument> {
    const response = await fetch(link, { headers: BasicHttpHeaders });

    if (!response.ok) {
      throw new Error(`Failed to fetch resource: ${response.statusText}`);
    }

    const resourceText = await response.text();

    const splitter = MarkdownSplitter.create(resourceText);
    return {
      ...splitter.split(),
      link,
    };
  }
}
