import fs from "node:fs";
import path from "node:path";

type EndpointCheck = {
  label: string;
  path: string;
};

const DASHBOARD_ROOT = path.resolve(__dirname, "..");
const DEFAULT_BASE_URL = "http://localhost:8000";

const ENDPOINTS: EndpointCheck[] = [
  { label: "filings_list", path: "/api/v1/filings/?limit=1" },
  { label: "dashboard_overview", path: "/api/v1/dashboard/overview" },
];

function loadEnvBaseUrl(): string | undefined {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }

  const envPath = path.join(DASHBOARD_ROOT, ".env.local");
  if (!fs.existsSync(envPath)) {
    return undefined;
  }

  const content = fs.readFileSync(envPath, "utf-8");
  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const [key, ...rest] = trimmed.split("=");
    if (key === "NEXT_PUBLIC_API_BASE_URL") {
      return rest.join("=").trim();
    }
  }
  return undefined;
}

function normalizeBaseUrl(candidate: string | undefined): string {
  const base = (candidate || DEFAULT_BASE_URL).trim();
  if (!base) {
    return DEFAULT_BASE_URL;
  }
  return base.endsWith("/") ? base.slice(0, -1) : base;
}

async function main() {
  const baseUrl = normalizeBaseUrl(loadEnvBaseUrl());
  console.log(`🔍 Checking API health against: ${baseUrl}`);

  let failures = 0;
  for (const endpoint of ENDPOINTS) {
    const target = `${baseUrl}${endpoint.path}`;
    try {
      const response = await fetch(target, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        failures += 1;
        console.error(`✗ ${endpoint.label} → HTTP ${response.status}`);
        continue;
      }
      // We do not consume the entire body to keep the script fast/lightweight.
      console.log(`✓ ${endpoint.label}`);
    } catch (error) {
      failures += 1;
      const message = error instanceof Error ? error.message : String(error);
      console.error(`✗ ${endpoint.label} → ${message}`);
    }
  }

  if (failures > 0) {
    console.error(`API health checks completed with ${failures} failure(s).`);
    process.exitCode = 1;
  } else {
    console.log("✅ All endpoints responded successfully.");
  }
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`Unexpected error: ${message}`);
  process.exitCode = 1;
});

