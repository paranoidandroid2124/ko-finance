import { describe, it } from "vitest";

import { SearchMode } from "../../constants/search-mode.js";
import { createTossPaymentDocsRepository } from "../createTossPaymentDocsRepository.js";

describe("docs", () => {
  it("v1 문서의 keywords 를 가져온다", async () => {
    const repository = await createTossPaymentDocsRepository();
    const keywords = repository.getAllV1Keywords();

    console.log(JSON.stringify(keywords));
  });

  it("v2 문서의 keywords 를 가져온다", async () => {
    const repository = await createTossPaymentDocsRepository();
    const keywords = repository.getAllV2Keywords();

    console.log(JSON.stringify(keywords));
  });

  it("v1 docs 를 잘 가져온다", async () => {
    const repository = await createTossPaymentDocsRepository();
    const text = await repository.findV1DocumentsByKeyword(
      ["결제위젯", "연동"],
      SearchMode.BALANCED,
      25000
    );

    console.log("V1 검색 결과:");
    console.log(text);
  });

  it("v2 docs 를 잘 가져온다", async () => {
    const repository = await createTossPaymentDocsRepository();
    const text = await repository.findV2DocumentsByKeyword(
      ["JavaScript", "SDK", "토스페이먼츠", "초기화", "결제위젯"],
      // ["결제위젯", "위젯", "메서드"],
      SearchMode.BALANCED,
      25000
    );

    console.log("V2 검색 결과:");
    console.log(text);
  });

  it("offset과 limit으로 페이지네이션이 잘 동작한다", async () => {
    const repository = await createTossPaymentDocsRepository();

    // 첫 번째 페이지
    const firstPage = await repository.findV2DocumentsByKeyword(
      ["결제"],
      SearchMode.BALANCED,
      25000
    );

    // 두 번째 페이지
    const secondPage = await repository.findV2DocumentsByKeyword(
      ["결제"],
      SearchMode.BALANCED,
      25000
    );

    console.log("첫 번째 페이지 (0-2):");
    console.log(firstPage);
    console.log("\n두 번째 페이지 (3-5):");
    console.log(secondPage);
  });

  it("다양한 searchMode로 결과가 달라진다", async () => {
    const repository = await createTossPaymentDocsRepository();
    const keywords = ["가상계좌", "발급"];

    const broadResults = await repository.findV2DocumentsByKeyword(
      keywords,
      SearchMode.BROAD,
      25000
    );

    const balancedResults = await repository.findV2DocumentsByKeyword(
      keywords,
      SearchMode.BALANCED,
      25000
    );

    const preciseResults = await repository.findV2DocumentsByKeyword(
      keywords,
      SearchMode.PRECISE,
      25000
    );

    console.log("BROAD 모드 결과:");
    console.log(broadResults);
    console.log("\nBALANCED 모드 결과:");
    console.log(balancedResults);
    console.log("\nPRECISE 모드 결과:");
    console.log(preciseResults);
  });
});
