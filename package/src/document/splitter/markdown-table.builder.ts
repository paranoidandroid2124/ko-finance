import { extractTextFromNode } from "./extractTextFromNode.js";
import { TableCellNode } from "./types.js";

export class MarkdownTableBuilder {
  private rowCount: number = 0;
  private table: string[][] = [];
  private currentRow: string[] = [];

  constructor() {}

  addRow() {
    this.table.push(this.currentRow);
    this.currentRow = [];
    this.rowCount++;
  }

  addColumn(node: TableCellNode) {
    const cellContent = extractTextFromNode(node);
    this.currentRow.push(cellContent);
  }

  build(): string {
    if (this.table.length === 0) return "";

    // 각 컬럼의 최대 너비 계산
    const maxWidths: number[] = [];

    this.table.forEach((row) => {
      row.forEach((cell, colIndex) => {
        maxWidths[colIndex] = Math.max(maxWidths[colIndex] || 0, cell.length);
      });
    });

    const formattedRows: string[] = [];

    this.table.forEach((row, rowIndex) => {
      const paddedCells = row.map((cell, colIndex) => {
        return cell.padEnd(maxWidths[colIndex] || 0);
      });

      formattedRows.push(`| ${paddedCells.join(" | ")} |`);

      // 첫 번째 행 (헤더) 다음에 구분선 추가
      if (rowIndex === 0) {
        const separators = maxWidths.map((width) => "-".repeat(width));
        formattedRows.push(
          `|${separators.map((sep) => `-${sep}-`).join("|")}|`
        );
      }
    });

    return formattedRows.join("\n");
  }
}
