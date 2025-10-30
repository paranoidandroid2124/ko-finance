/**
 * Join short chunks of text into larger ones if they are below a certain word count.
 * @param chunks
 * @param minWords
 */
export function joinShortChunks(chunks: string[], minWords = 150): string[] {
  const result: string[] = [];

  let buffer = "";
  let bufferCount = 0;

  for (const chunk of chunks) {
    const wc = chunk.split(/\s+/).length;
    if (wc < minWords) {
      buffer += (buffer ? "\n\n" : "") + chunk;
      bufferCount += wc;
      continue;
    }

    if (buffer) {
      result.push(buffer.trim());
      buffer = "";
      bufferCount = 0;
    }

    result.push(chunk.trim());
  }

  if (buffer) {
    result.push(buffer.trim());
  }

  return result;
}
