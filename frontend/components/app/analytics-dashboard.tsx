'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Activity,
  ArrowLeft,
  CheckCircle2,
  Monitor,
  Percent,
  PhoneCall,
  PhoneIncoming,
  RefreshCw,
  XCircle,
} from 'lucide-react';
import { cn } from '@/lib/shadcn/utils';

type RecentCall = {
  started_at: string;
  channel: string;
  outcome: string;
  duration_seconds: number | null;
};

type AnalyticsSummary = {
  total: number;
  successful: number;
  failed: number;
  success_rate: number;
  last_updated: string | null;
  recent: RecentCall[];
};

const POLL_INTERVAL_MS = 8000;

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '—';
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, '0');
  const s = Math.floor(seconds % 60)
    .toString()
    .padStart(2, '0');
  return `${m}:${s}`;
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function MetricCard({
  label,
  value,
  hint,
  icon,
  iconClassName,
}: {
  label: string;
  value: string;
  hint?: string;
  icon: React.ReactNode;
  iconClassName: string;
}) {
  return (
    <section className="border-border bg-card rounded-2xl border p-6 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-muted-foreground text-xs font-semibold tracking-widest uppercase">
          {label}
        </h2>
        <span
          className={cn(
            'flex h-9 w-9 shrink-0 items-center justify-center rounded-xl',
            iconClassName
          )}
          aria-hidden="true"
        >
          {icon}
        </span>
      </div>
      <p className="text-foreground mt-4 font-mono text-4xl font-bold tracking-tight tabular-nums">
        {value}
      </p>
      {hint && <p className="text-muted-foreground mt-1.5 text-xs">{hint}</p>}
    </section>
  );
}

function SkeletonCard() {
  return (
    <section aria-hidden="true" className="border-border bg-card rounded-2xl border p-6 shadow-sm">
      <div className="h-3 w-24 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
      <div className="mt-5 h-9 w-16 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
      <div className="mt-2 h-3 w-28 animate-pulse rounded bg-slate-200 dark:bg-slate-700" />
    </section>
  );
}

export function AnalyticsDashboard() {
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [status, setStatus] = useState<'loading' | 'ok' | 'error'>('loading');
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());

  const load = useCallback(async () => {
    try {
      const res = await fetch('/api/analytics', { cache: 'no-store' });
      if (!res.ok) {
        throw new Error('analytics unavailable');
      }
      const json = (await res.json()) as AnalyticsSummary;
      setData(json);
      setStatus('ok');
      setUpdatedAt(Date.now());
    } catch {
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  // 1s ticker for the "Last updated" indicator while data is loaded.
  useEffect(() => {
    if (status !== 'ok') return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [status]);

  const lastUpdatedText =
    updatedAt !== null
      ? `Last updated ${Math.max(0, Math.round((now - updatedAt) / 1000))}s ago`
      : null;

  const successRate = data?.success_rate ?? 0;

  return (
    <main className="bg-background text-foreground flex min-h-[100dvh] w-full flex-col">
      {/* Header */}
      <header className="border-border bg-card/80 sticky top-0 z-40 flex items-center justify-between border-b px-6 py-4 backdrop-blur-md lg:px-12">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-600 text-lg font-bold text-white shadow-md">
            S
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-foreground text-sm font-bold">Saathi Swasthya</span>
            <span className="text-muted-foreground text-[10px] tracking-widest uppercase">
              Call Analytics
            </span>
          </div>
        </div>
        <Link
          href="/"
          className="border-border bg-background text-muted-foreground inline-flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold transition-colors hover:border-teal-300 hover:text-teal-700 dark:hover:text-teal-300"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Back to assistant
        </Link>
      </header>

      <div className="mx-auto w-full max-w-6xl flex-1 px-6 py-8 lg:px-12 lg:py-12">
        {/* Page intro */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-foreground text-2xl font-bold tracking-tight sm:text-3xl">
              Call analytics
            </h1>
            <p className="text-muted-foreground mt-1.5 max-w-xl text-sm">
              How many callers received safe guidance or an appropriate escalation — measured from
              real voice calls.
            </p>
          </div>
          <p className="text-muted-foreground text-xs tabular-nums" aria-live="polite">
            {status === 'ok' && lastUpdatedText ? lastUpdatedText : '\u00a0'}
          </p>
        </div>

        {/* Metric cards */}
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {status === 'loading' && !data && (
            <>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </>
          )}

          {status === 'ok' && data && (
            <>
              <MetricCard
                label="Total calls"
                value={data.total.toString()}
                hint="All completed and in-progress calls"
                icon={<PhoneCall className="h-4.5 w-4.5 text-teal-600" />}
                iconClassName="bg-teal-50 dark:bg-teal-950"
              />
              <MetricCard
                label="Successful calls"
                value={data.successful.toString()}
                hint="Safe guidance or escalation delivered"
                icon={<CheckCircle2 className="h-4.5 w-4.5 text-emerald-600" />}
                iconClassName="bg-emerald-50 dark:bg-emerald-950"
              />
              <MetricCard
                label="Failed calls"
                value={data.failed.toString()}
                hint="Ended without reaching a success condition"
                icon={<XCircle className="h-4.5 w-4.5 text-rose-600" />}
                iconClassName="bg-rose-50 dark:bg-rose-950"
              />
              <MetricCard
                label="Success rate"
                value={`${successRate.toFixed(successRate % 1 === 0 ? 0 : 1)}%`}
                hint="Successful ÷ total calls"
                icon={<Percent className="h-4.5 w-4.5 text-teal-600" />}
                iconClassName="bg-teal-50 dark:bg-teal-950"
              />
            </>
          )}

          {status === 'error' && (
            <>
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
              <SkeletonCard />
            </>
          )}
        </div>

        {/* Success-rate bar (only when data is available) */}
        {status === 'ok' && data && (
          <section
            className="border-border bg-card mt-6 rounded-2xl border p-6 shadow-sm"
            aria-label="Success rate breakdown"
          >
            <div className="flex items-center justify-between gap-4">
              <p className="text-foreground text-sm font-medium">Successful calls</p>
              <p className="text-muted-foreground text-sm tabular-nums">
                {data.successful} of {data.total} calls
              </p>
            </div>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={successRate}
              aria-label={`Success rate ${successRate}%`}
              className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
            >
              <div
                className="h-full rounded-full bg-teal-600 transition-[width] duration-500"
                style={{ width: `${Math.min(100, Math.max(0, successRate))}%` }}
              />
            </div>
          </section>
        )}

        {/* Zero state */}
        {status === 'ok' && data && data.total === 0 && (
          <section className="border-border bg-card mt-8 rounded-2xl border border-dashed p-10 text-center">
            <Activity className="mx-auto h-10 w-10 text-teal-600" aria-hidden="true" />
            <h2 className="text-foreground mt-4 text-lg font-semibold">No calls yet</h2>
            <p className="text-muted-foreground mx-auto mt-1.5 max-w-md text-sm">
              Start a voice conversation with Saathi. When a call ends, its outcome appears here
              automatically.
            </p>
            <Link
              href="/"
              className="mt-6 inline-flex items-center gap-2 rounded-full bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-teal-700"
            >
              <PhoneIncoming className="h-4 w-4" aria-hidden="true" />
              Speak with Saathi
            </Link>
          </section>
        )}

        {/* Error state */}
        {status === 'error' && (
          <section
            role="alert"
            className="border-border bg-card mt-8 rounded-2xl border p-10 text-center"
          >
            <XCircle className="mx-auto h-10 w-10 text-rose-500" aria-hidden="true" />
            <h2 className="text-foreground mt-4 text-lg font-semibold">
              Analytics are temporarily unavailable
            </h2>
            <p className="text-muted-foreground mx-auto mt-1.5 max-w-md text-sm">
              We could not load call analytics right now. The voice assistant is not affected — try
              again in a moment.
            </p>
            <button
              type="button"
              onClick={() => {
                setStatus('loading');
                void load();
              }}
              className="border-border bg-background text-foreground mt-6 inline-flex items-center gap-2 rounded-full border px-5 py-2.5 text-sm font-semibold transition-colors hover:border-teal-300 hover:text-teal-700 dark:hover:text-teal-300"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Try again
            </button>
          </section>
        )}

        {/* Recent calls (metadata only) */}
        {status === 'ok' && data && data.recent.length > 0 && (
          <section className="mt-8">
            <h2 className="text-foreground text-base font-semibold tracking-tight">Recent calls</h2>
            <div className="border-border bg-card mt-3 overflow-x-auto rounded-2xl border shadow-sm">
              <table className="w-full min-w-[520px] text-left text-sm">
                <caption className="sr-only">
                  Recent calls with time, channel, duration, and outcome
                </caption>
                <thead>
                  <tr className="border-border text-muted-foreground border-b text-xs tracking-widest uppercase">
                    <th scope="col" className="px-6 py-3 font-semibold">
                      Time
                    </th>
                    <th scope="col" className="px-6 py-3 font-semibold">
                      Channel
                    </th>
                    <th scope="col" className="px-6 py-3 font-semibold">
                      Duration
                    </th>
                    <th scope="col" className="px-6 py-3 font-semibold">
                      Outcome
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent.map((call, index) => {
                    const isSuccess = call.outcome === 'success';
                    return (
                      <tr
                        key={`${call.started_at}-${index}`}
                        className="border-border/60 border-b last:border-0"
                      >
                        <td className="text-muted-foreground px-6 py-3 tabular-nums">
                          {formatTime(call.started_at)}
                        </td>
                        <td className="px-6 py-3">
                          <span className="text-foreground inline-flex items-center gap-1.5">
                            {call.channel === 'sip' ? (
                              <PhoneIncoming
                                className="h-3.5 w-3.5 text-slate-400"
                                aria-hidden="true"
                              />
                            ) : (
                              <Monitor className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                            )}
                            {call.channel === 'sip' ? 'SIP' : 'Browser'}
                          </span>
                        </td>
                        <td className="text-muted-foreground px-6 py-3 tabular-nums">
                          {formatDuration(call.duration_seconds)}
                        </td>
                        <td className="px-6 py-3">
                          <span
                            className={cn(
                              'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold',
                              isSuccess
                                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                                : 'bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300'
                            )}
                          >
                            <CheckCircle2
                              className={cn(
                                'h-3.5 w-3.5',
                                isSuccess ? 'text-emerald-600' : 'text-rose-500'
                              )}
                              aria-hidden="true"
                            />
                            {isSuccess ? 'Success' : 'Failed'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Footer note */}
        <p className="text-muted-foreground mt-10 text-xs">
          For emergencies, call <strong className="text-foreground font-bold">112</strong> or{' '}
          <strong className="text-foreground font-bold">108</strong>. Saathi is an AI triage
          assistant, not a doctor. Analytics show aggregate metadata only — no transcripts, medical
          details, or personal information.
        </p>
      </div>
    </main>
  );
}
