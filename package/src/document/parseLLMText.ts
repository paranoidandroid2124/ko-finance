import { categories, Category } from "../constants/category.js";
import { RawDocs } from "./types.js";

export function parseLLMText(text: string): RawDocs[] {
  return text
    .split("\n")
    .filter((line) => line.includes("https://docs.tosspayments.com"))
    .map((line) => parse({ text: line, link: extractLink(line) }));
}

function extractLink(line: string) {
  const start = line.indexOf("](");
  const end = line.indexOf(")", start);
  return line.substring(start + 2, end);
}

function parseVersionFromUrl(url: string): "v1" | "v2" | undefined {
  if (existsVersion(url)) {
    return extractVersion(url);
  }

  if (["sdk", "guides"].some((keyword) => url.includes(keyword))) {
    return "v1";
  }

  return;
}

function parseVersionFromTitle(title: string): "v1" | "v2" | undefined {
  title = title.toLowerCase();

  if (title.includes("version 1")) {
    return "v1";
  } else if (title.includes("version 2")) {
    return "v2";
  }

  return;
}

function parse(link: { text: string; link: string }): RawDocs {
  const { text, link: url } = link;
  const title = extractTitle(text);
  const version = parseVersionFromUrl(url) ?? parseVersionFromTitle(title);
  const description = extractDescription(text);

  return {
    text,
    title,
    link: url,
    version,
    description,
    category: extractCategory(url),
  };
}

function extractTitle(text: string): string {
  const start = text.indexOf("[") + 1;
  const end = text.indexOf("](", start);
  return text.substring(start, end).trim();
}

function extractVersion(link: string): "v1" | "v2" {
  const matched = /\/v\d+\//[Symbol.match](link);

  if (matched === null) {
    throw new Error(`Unable to parse version: ${matched}`);
  }

  const version = matched[0];

  return version.substring(1, version.length - 1) as "v1" | "v2";
}

function existsVersion(link: string): boolean {
  return /\/v\d+\//.test(link);
}

function extractDescription(text: string): string {
  const start = text.indexOf("):") + 2;
  return text.substring(start).trim();
}

function extractCategory(link: string): Category {
  const url = new URL(link);

  for (const category of categories) {
    if (url.pathname.startsWith(`/${category}`)) {
      return category;
    }
  }

  return "unknown";
}
