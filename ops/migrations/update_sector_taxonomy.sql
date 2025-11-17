BEGIN;

-- Rename legacy fallback slug to the new default (when safe).
UPDATE sectors
SET slug = 'others'
WHERE slug = 'misc'
  AND NOT EXISTS (SELECT 1 FROM sectors WHERE slug = 'others');

-- Upsert the expanded taxonomy (slug -> label).
WITH sector_data (slug, name) AS (
    VALUES
        ('semiconductor', '반도체'),
        ('hardware', '전자장비/디스플레이'),
        ('software', '소프트웨어/SaaS'),
        ('internet', '인터넷/플랫폼'),
        ('telecom', '통신'),
        ('media', '미디어/게임/엔터'),
        ('mobility', '모빌리티/완성차'),
        ('battery', '2차전지'),
        ('energy', '에너지/발전/정유'),
        ('renewables', '신재생에너지/수소'),
        ('finance', '금융'),
        ('bio', '바이오/헬스케어'),
        ('materials', '소재/화학/철강'),
        ('industrials', '산업재/기계/조선'),
        ('logistics', '물류/운송'),
        ('real_estate', '부동산/건설/REITs'),
        ('defense', '방위산업/항공우주'),
        ('consumer', '소비재'),
        ('others', '기타')
)
INSERT INTO sectors (slug, name)
SELECT slug, name FROM sector_data
ON CONFLICT (slug) DO UPDATE
SET name = EXCLUDED.name;

COMMIT;
