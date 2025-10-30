import { Category } from "../constants/category.js";
import { EnhancedChunk } from "./splitter/types.js";

export interface DocumentMetadata {
  title: string;
  description: string;
  keyword: string[];
}

export interface MarkdownDocument {
  markdown: string;
  metadata: DocumentMetadata;
  enhancedChunks: EnhancedChunk[]; // 새로운 필드 추가
}

export interface DocumentChunk {
  id: number;
  chunkId: number;
  originTitle: string;
  text: string; // 컨텍스트 포함 전체 텍스트
  rawText: string; // 원본 텍스트만
  wordCount: number;
  estimatedTokens: number; // 컨텍스트 포함 토큰 수
  headerStack: string[]; // 헤더 경로
}

export interface RemoteMarkdownDocument extends MarkdownDocument {
  link: string;
}

export interface RawDocs {
  text: string;
  title: string;
  link: string;
  version?: "v1" | "v2";
  description: string;
  category: Category;
}
