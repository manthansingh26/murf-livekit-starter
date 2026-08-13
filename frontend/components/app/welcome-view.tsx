'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  BarChart3,
  Globe,
  Heart,
  MapPin,
  MessageSquareText,
  Mic,
  Phone,
  Shield,
} from 'lucide-react';
import { motion } from 'motion/react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/shadcn/utils';

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
  micError?: string;
}

const fadeInUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
};

const staggerContainer = {
  animate: {
    transition: {
      staggerChildren: 0.1,
    },
  },
};

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  micError,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  // Hydration-safe: detect reduced motion only after mount
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    setPrefersReducedMotion(mediaQuery.matches);

    const handler = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, []);

  return (
    <div
      ref={ref}
      className="flex min-h-[100dvh] w-full flex-col overflow-x-hidden bg-slate-50 text-slate-900 selection:bg-teal-200 selection:text-teal-900"
    >
      {/* Navigation */}
      <nav className="sticky top-0 z-50 flex w-full items-center justify-between border-b border-slate-100 bg-white/80 px-6 py-4 backdrop-blur-md lg:px-12">
        <div className="flex items-center gap-3">
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-teal-600 text-lg font-bold text-white shadow-md">
            S
            <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full border-2 border-white bg-emerald-500">
              <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400 opacity-75"></span>
            </span>
          </div>
          <span className="text-lg font-bold tracking-tight text-slate-800">Saathi Swasthya</span>
        </div>
        <div className="hidden items-center gap-4 sm:flex">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-4 py-1.5 text-xs font-semibold text-slate-600 transition-colors hover:border-teal-300 hover:text-teal-700"
          >
            <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" />
            Analytics
          </Link>
          <span className="rounded-full border border-slate-200 bg-slate-100 px-4 py-1.5 text-xs font-semibold text-slate-600">
            English | हिन्दी | ગુજરાતી
          </span>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col items-center gap-16 px-6 py-12 lg:flex-row lg:gap-20 lg:px-12 lg:py-20">
        {/* Left: Value Proposition (55%) */}
        <motion.section
          className="flex w-full flex-col items-start gap-6 text-left lg:w-[55%]"
          initial={false}
          animate={prefersReducedMotion ? { opacity: 1, y: 0 } : { opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          {/* Eyebrow */}
          <div className="inline-flex items-center gap-2 rounded-full border border-teal-100 bg-teal-50 px-4 py-2 text-xs font-semibold text-teal-700">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal-400 opacity-75"></span>
              <span className="relative inline-flex h-2 w-2 rounded-full bg-teal-500"></span>
            </span>
            Voice-First Health Access
          </div>

          {/* Headline */}
          <h1 className="text-4xl leading-[1.1] font-extrabold tracking-tight text-slate-900 sm:text-5xl lg:text-6xl">
            Your health, <span className="text-teal-600">understood.</span>
          </h1>

          {/* Subheadline */}
          <p className="max-w-lg text-lg leading-relaxed text-slate-600">
            Speak naturally in English, Hindi, or Gujarati. Saathi listens, understands, and guides
            you to the care you need.
          </p>

          {/* Error Message */}
          {micError && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex w-full max-w-lg items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4"
            >
              <span className="mt-0.5 text-red-500">
                <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
              </span>
              <p className="text-sm font-medium text-red-800">{micError}</p>
            </motion.div>
          )}

          {/* CTA */}
          <div className="flex w-full flex-col gap-3 pt-2 sm:w-auto sm:flex-row">
            <Button
              size="lg"
              onClick={onStartCall}
              className="h-14 w-full rounded-full bg-teal-600 px-8 text-base font-semibold text-white shadow-lg shadow-teal-600/25 transition-all duration-200 hover:bg-teal-700 hover:shadow-xl hover:shadow-teal-600/30 active:scale-[0.98] sm:w-auto"
            >
              <Mic className="mr-2 h-5 w-5" />
              {startButtonText}
            </Button>
          </div>

          {/* Trust Indicators */}
          <motion.div
            className="flex flex-wrap items-center gap-4 pt-4"
            initial={false}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4, duration: 0.5 }}
          >
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Shield className="h-4 w-4 text-teal-600" />
              <span>AI-assisted, not AI-diagnosed</span>
            </div>
            <div className="h-4 w-px bg-slate-200"></div>
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Globe className="h-4 w-4 text-teal-600" />
              <span>Built for India</span>
            </div>
            <div className="h-4 w-px bg-slate-200"></div>
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Heart className="h-4 w-4 text-teal-600" />
              <span>Privacy by design</span>
            </div>
          </motion.div>
        </motion.section>

        {/* Right: Voice Orb Visual (45%) */}
        <motion.section
          className="flex w-full items-center justify-center lg:w-[45%]"
          initial={false}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="relative flex h-[320px] w-[320px] items-center justify-center sm:h-[400px] sm:w-[400px]">
            {/* Animated Rings */}
            <motion.div
              className="absolute inset-0 rounded-full border-2 border-teal-200/40"
              animate={
                prefersReducedMotion
                  ? {}
                  : {
                      scale: [1, 1.1, 1],
                      opacity: [0.3, 0.6, 0.3],
                    }
              }
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            />
            <motion.div
              className="absolute inset-4 rounded-full border-2 border-teal-300/30"
              animate={
                prefersReducedMotion
                  ? {}
                  : {
                      scale: [1, 1.15, 1],
                      opacity: [0.4, 0.7, 0.4],
                    }
              }
              transition={{ duration: 3.5, repeat: Infinity, ease: 'easeInOut', delay: 0.3 }}
            />
            <motion.div
              className="absolute inset-8 rounded-full border-2 border-teal-400/20"
              animate={
                prefersReducedMotion
                  ? {}
                  : {
                      scale: [1, 1.2, 1],
                      opacity: [0.5, 0.8, 0.5],
                    }
              }
              transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut', delay: 0.6 }}
            />

            {/* Central Orb */}
            <motion.div
              className="relative z-10 flex h-48 w-48 items-center justify-center rounded-full bg-gradient-to-br from-teal-400 via-teal-500 to-teal-600 shadow-2xl shadow-teal-500/30 sm:h-64 sm:w-64"
              animate={
                prefersReducedMotion
                  ? {}
                  : {
                      scale: [1, 1.05, 1],
                    }
              }
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
            >
              <div className="flex flex-col items-center gap-2 text-white">
                <Mic className="h-12 w-12 sm:h-16 sm:w-16" />
                <span className="text-sm font-semibold opacity-90">Listen & Guide</span>
              </div>
            </motion.div>

            {/* Floating Labels */}
            <motion.div
              className="absolute top-1/4 -right-4 rounded-full bg-white px-4 py-2 shadow-lg"
              initial={false}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.8, duration: 0.5 }}
            >
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-emerald-500"></div>
                <span className="text-xs font-semibold text-slate-700">3 Languages</span>
              </div>
            </motion.div>

            <motion.div
              className="absolute bottom-1/4 -left-4 rounded-full bg-white px-4 py-2 shadow-lg"
              initial={false}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 1, duration: 0.5 }}
            >
              <div className="flex items-center gap-2">
                <MapPin className="h-3 w-3 text-teal-600" />
                <span className="text-xs font-semibold text-slate-700">Facility Lookup</span>
              </div>
            </motion.div>
          </div>
        </motion.section>
      </main>

      {/* How It Works Section */}
      <section className="w-full border-t border-slate-100 bg-white py-16 lg:py-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-12">
          <motion.div
            className="mb-12 text-center"
            initial={false}
            whileInView={prefersReducedMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: 0.5 }}
          >
            <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
              How Saathi Works
            </h2>
            <p className="mt-3 text-base text-slate-600">
              Three simple steps to understand your health needs
            </p>
          </motion.div>

          <motion.div
            className="grid grid-cols-1 gap-8 md:grid-cols-3"
            variants={staggerContainer}
            initial="initial"
            whileInView="animate"
            viewport={{ once: true, amount: 0.2 }}
          >
            {[
              {
                icon: <Mic className="h-6 w-6" />,
                title: 'Speak',
                description: 'Tell Saathi how you feel, in your language',
                step: '01',
              },
              {
                icon: <MessageSquareText className="h-6 w-6" />,
                title: 'Understand',
                description: 'Saathi listens and asks the right questions',
                step: '02',
              },
              {
                icon: <MapPin className="h-6 w-6" />,
                title: 'Guide',
                description: 'Get directed to the right care, with safety built in',
                step: '03',
              },
            ].map((item, index) => (
              <motion.div
                key={item.step}
                className="relative flex flex-col items-center gap-4 rounded-2xl border border-slate-100 bg-slate-50 p-8 text-center transition-all duration-300 hover:border-teal-200 hover:bg-teal-50/50"
                variants={fadeInUp}
              >
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-teal-100 text-teal-600">
                  {item.icon}
                </div>
                <div className="absolute -top-3 right-4 rounded-full bg-teal-600 px-3 py-1 text-xs font-bold text-white">
                  {item.step}
                </div>
                <h3 className="text-lg font-bold text-slate-900">{item.title}</h3>
                <p className="text-sm leading-relaxed text-slate-600">{item.description}</p>
              </motion.div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section className="w-full bg-slate-50 py-16 lg:py-24">
        <div className="mx-auto max-w-7xl px-6 lg:px-12">
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-2 lg:items-center">
            {/* Left: Feature List */}
            <motion.div
              initial={false}
              whileInView={prefersReducedMotion ? { opacity: 1, x: 0 } : { opacity: 0, x: -30 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.6 }}
            >
              <h2 className="mb-8 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
                Built for real healthcare needs
              </h2>
              <div className="space-y-6">
                {[
                  {
                    icon: <Globe className="h-5 w-5" />,
                    title: 'Multilingual voice AI',
                    description: 'Natural conversation in English, Hindi, and Gujarati',
                  },
                  {
                    icon: <MapPin className="h-5 w-5" />,
                    title: 'Health facility lookup',
                    description: 'Real-world data from OpenStreetMap to find nearby care',
                  },
                  {
                    icon: <MessageSquareText className="h-5 w-5" />,
                    title: 'Persistent memory',
                    description: 'Saathi remembers across conversations with your consent',
                  },
                  {
                    icon: <Shield className="h-5 w-5" />,
                    title: 'Safety-first triage',
                    description: 'Emergency detection and appropriate care guidance built in',
                  },
                ].map((feature, index) => (
                  <div key={index} className="flex gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-teal-100 text-teal-600">
                      {feature.icon}
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-900">{feature.title}</h3>
                      <p className="mt-1 text-sm text-slate-600">{feature.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>

            {/* Right: Stats */}
            <motion.div
              className="grid grid-cols-2 gap-6"
              initial={false}
              whileInView={prefersReducedMotion ? { opacity: 1, x: 0 } : { opacity: 0, x: 30 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              {[
                { value: '3', label: 'Languages supported' },
                { value: '24/7', label: 'Always available' },
                { value: '<2s', label: 'Response time' },
                { value: '100%', label: 'Privacy by design' },
              ].map((stat, index) => (
                <div
                  key={index}
                  className="flex flex-col items-center justify-center rounded-2xl border border-slate-100 bg-white p-6 text-center shadow-sm"
                >
                  <span className="text-3xl font-bold text-teal-600">{stat.value}</span>
                  <span className="mt-2 text-sm text-slate-600">{stat.label}</span>
                </div>
              ))}
            </motion.div>
          </div>
        </div>
      </section>

      {/* Emergency Footer Banner */}
      <div className="w-full border-t border-rose-100 bg-rose-50 py-4">
        <div className="mx-auto max-w-7xl px-6 lg:px-12">
          <div className="flex items-center justify-center gap-3 text-sm text-rose-700">
            <Phone className="h-4 w-4" />
            <span>
              In emergencies, call <strong className="font-bold">112</strong> or{' '}
              <strong className="font-bold">108</strong>. Saathi is an AI triage assistant, not a
              doctor.
            </span>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="w-full border-t border-slate-100 bg-white py-6">
        <div className="mx-auto max-w-7xl px-6 lg:px-12">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-600 text-sm font-bold text-white">
                S
              </div>
              <span className="text-sm font-semibold text-slate-700">Saathi Swasthya</span>
            </div>
            <p className="text-xs text-slate-500">
              &copy; {new Date().getFullYear()} Saathi Swasthya &middot; Built for the Murf AI Voice
              Agents Challenge
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};
