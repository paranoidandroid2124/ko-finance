export type SectorTaxonomyItem = {
  slug: string;
  label: string;
};

export const DEFAULT_SECTOR_SLUG = "others";

export const SECTOR_TAXONOMY: SectorTaxonomyItem[] = [
  { slug: "semiconductor", label: "반도체" },
  { slug: "hardware", label: "전자장비/디스플레이" },
  { slug: "software", label: "소프트웨어/SaaS" },
  { slug: "internet", label: "인터넷/플랫폼" },
  { slug: "telecom", label: "통신" },
  { slug: "media", label: "미디어/게임/엔터" },
  { slug: "mobility", label: "모빌리티/완성차" },
  { slug: "battery", label: "2차전지" },
  { slug: "energy", label: "에너지/발전/정유" },
  { slug: "renewables", label: "신재생에너지/수소" },
  { slug: "finance", label: "금융" },
  { slug: "bio", label: "바이오/헬스케어" },
  { slug: "materials", label: "소재/화학/철강" },
  { slug: "industrials", label: "산업재/기계/조선" },
  { slug: "logistics", label: "물류/운송" },
  { slug: "real_estate", label: "부동산/건설/REITs" },
  { slug: "defense", label: "방위산업/항공우주" },
  { slug: "consumer", label: "소비재" },
  { slug: "others", label: "기타" },
];

export const SECTOR_LABEL_BY_SLUG = SECTOR_TAXONOMY.reduce<Record<string, string>>((acc, item) => {
  acc[item.slug] = item.label;
  return acc;
}, {});
