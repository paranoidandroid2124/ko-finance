import { ImageResponse } from "next/server";

export const runtime = "edge";
export const dynamic = "force-dynamic";

const WIDTH = 1200;
const HEIGHT = 630;

type EventData = {
  receiptNo: string;
  corpName?: string | null;
  ticker?: string | null;
  reportName?: string | null;
  eventName?: string | null;
  eventType?: string | null;
  caar?: number | null;
  pValue?: number | null;
  focusScore?: number | null;
};

async function fetchEvent(receiptNo: string): Promise<EventData | null> {
  const base =
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.API_BASE_URL ||
    `${process.env.NEXT_PUBLIC_SITE_URL || ""}`.replace(/\/$/, "") ||
    "";
  const url = base ? `${base}/api/v1/public/events/${receiptNo}` : undefined;
  if (!url) return null;
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as EventData;
  } catch {
    return null;
  }
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const receiptNo = searchParams.get("receiptNo") || searchParams.get("rcept_no");
  if (!receiptNo) {
    return new ImageResponse(
      (
        <div
          style={{
            height: HEIGHT,
            width: WIDTH,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "#0f172a",
            color: "#e2e8f0",
            fontSize: 42,
            fontWeight: 700,
          }}
        >
          Nuvien Proactive Insight
        </div>
      ),
      { width: WIDTH, height: HEIGHT }
    );
  }

  const data = await fetchEvent(receiptNo);
  const corp = data?.corpName || data?.ticker || "기업";
  const headline = data?.eventName || data?.reportName || "주요 이벤트";
  const caar = data?.caar !== undefined && data?.caar !== null ? `${data.caar.toFixed(2)}%` : "-";
  const pval =
    data?.pValue !== undefined && data?.pValue !== null ? data.pValue.toExponential(2) : "-";
  const focus =
    data?.focusScore !== undefined && data?.focusScore !== null ? `${Math.round(data.focusScore)}점` : "-";

  return new ImageResponse(
    (
      <div
        style={{
          height: HEIGHT,
          width: WIDTH,
          display: "flex",
          flexDirection: "column",
          padding: "60px",
          background: "linear-gradient(135deg, #0f172a 0%, #111827 60%, #0b1224 100%)",
          color: "#e2e8f0",
          fontFamily: "Pretendard, Arial",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, color: "#60a5fa", fontSize: 22, letterSpacing: 2 }}>
          <span>Nuvien</span>
          <span style={{ color: "#94a3b8" }}>·</span>
          <span>Proactive Insight</span>
        </div>
        <div style={{ marginTop: 18, fontSize: 48, fontWeight: 800, lineHeight: 1.2 }}>
          {corp} · {headline}
        </div>
        <div style={{ marginTop: 12, fontSize: 24, color: "#cbd5e1" }}>receipt no. {receiptNo}</div>
        <div
          style={{
            marginTop: 36,
            display: "grid",
            gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
            gap: 16,
          }}
        >
          <Stat label="CAAR" value={caar} helper="-2,+5 윈도우" />
          <Stat label="p-value" value={pval} helper="통계적 유의성" />
          <Stat label="Focus Score" value={focus} helper="이벤트 연구 가치" />
        </div>
      </div>
    ),
    { width: WIDTH, height: HEIGHT }
  );
}

function Stat({ label, value, helper }: { label: string; value: string; helper?: string }) {
  return (
    <div
      style={{
        border: "1px solid rgba(255,255,255,0.1)",
        borderRadius: 16,
        padding: 20,
        background: "rgba(255,255,255,0.03)",
      }}
    >
      <div style={{ fontSize: 16, color: "#cbd5e1", letterSpacing: 1.5, textTransform: "uppercase" }}>
        {label}
      </div>
      <div style={{ fontSize: 32, fontWeight: 800, marginTop: 6 }}>{value}</div>
      {helper ? <div style={{ fontSize: 16, color: "#94a3b8" }}>{helper}</div> : null}
    </div>
  );
}
