import { DocumentMetadata } from "../types.js";

export function extractMetadata(markdown: string): DocumentMetadata {
  const startIndex = markdown.indexOf("***");
  const endIndex = markdown.indexOf("-----", startIndex + 3);

  if (startIndex === -1 || endIndex === -1) {
    return { title: "No Title", description: "No Description", keyword: [] };
  }

  const metadata = markdown.substring(startIndex + 3, endIndex).trim();

  const [rawTitle, rawDescription, rawKeyword] = metadata
    .split("\n")
    .map((line) => line.trim());

  const titleMatch = rawTitle?.match(/title:\s*(.*)/);
  const descriptionMatch = rawDescription?.match(/description:\s*(.*)/);
  const keywordMatch = rawKeyword?.match(/keyword:\s*(.*)/);

  return {
    title: titleMatch ? titleMatch[1].trim() : "No Title",
    description: descriptionMatch
      ? descriptionMatch[1].trim()
      : "No Description",
    keyword: keywordMatch
      ? keywordMatch[1].split(",").map((k) => k.trim())
      : [],
  };
}
