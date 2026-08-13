import { NextResponse } from 'next/server';
import { Pool } from 'pg';

// Don't cache the results — the dashboard must always show live call data.
export const revalidate = 0;

// Keep a single lazy connection pool across requests (and HMR reloads in dev).
const globalForPg = globalThis as unknown as { __analyticsPool?: Pool };

function getPool(): Pool | null {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    return null;
  }
  if (!globalForPg.__analyticsPool) {
    globalForPg.__analyticsPool = new Pool({
      connectionString,
      max: 5,
      idleTimeoutMillis: 30_000,
      connectionTimeoutMillis: 5_000,
    });
  }
  return globalForPg.__analyticsPool;
}

export type RecentCall = {
  started_at: string;
  channel: string;
  outcome: string;
  duration_seconds: number | null;
};

export type AnalyticsSummary = {
  total: number;
  successful: number;
  failed: number;
  success_rate: number;
  last_updated: string | null;
  recent: RecentCall[];
};

// A safe, generic error payload — never leaks DATABASE_URL, SQL, or stack traces.
const UNAVAILABLE = { error: 'analytics_unavailable' };

export async function GET() {
  const pool = getPool();
  if (!pool) {
    return NextResponse.json(UNAVAILABLE, { status: 503 });
  }

  try {
    const client = await pool.connect();
    try {
      const summaryResult = await client.query<{
        total: string;
        successful: string;
        failed: string;
        last_updated: Date | null;
      }>(`
        SELECT
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE outcome = 'success') AS successful,
          COUNT(*) FILTER (WHERE outcome = 'failed') AS failed,
          MAX(ended_at) AS last_updated
        FROM call_analytics
      `);

      const recentResult = await client.query<{
        started_at: Date;
        channel: string;
        outcome: string;
        duration_seconds: number | null;
      }>(`
        SELECT started_at, channel, outcome, duration_seconds
        FROM call_analytics
        WHERE outcome IS NOT NULL
        ORDER BY started_at DESC
        LIMIT 8
      `);

      const row = summaryResult.rows[0];
      const total = Number(row?.total ?? 0);
      const successful = Number(row?.successful ?? 0);
      const failed = Number(row?.failed ?? 0);

      const body: AnalyticsSummary = {
        total,
        successful,
        failed,
        success_rate: total > 0 ? Math.round((successful / total) * 1000) / 10 : 0,
        last_updated: row?.last_updated ? row.last_updated.toISOString() : null,
        recent: recentResult.rows.map((r) => ({
          started_at: r.started_at.toISOString(),
          channel: r.channel,
          outcome: r.outcome,
          duration_seconds: r.duration_seconds,
        })),
      };

      return NextResponse.json(body, {
        headers: { 'Cache-Control': 'no-store' },
      });
    } finally {
      client.release();
    }
  } catch {
    return NextResponse.json(UNAVAILABLE, { status: 503 });
  }
}
