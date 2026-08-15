'use client';

import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';
import { ArrowRight, Mic, Phone, RotateCcw, Shield } from 'lucide-react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { useSessionContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { SaathiSessionView } from '@/components/app/saathi-session-view';
import { WelcomeView } from '@/components/app/welcome-view';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/shadcn/utils';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionDiv = motion.create('div');

const VIEW_MOTION_PROPS = {
  variants: {
    visible: { opacity: 1 },
    hidden: { opacity: 0 },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] },
};

// --- Premium Connecting View ---
const ConnectingView = () => {
  const shouldReduceMotion = useReducedMotion();
  const [stage, setStage] = useState(0);

  // Connection stages
  useEffect(() => {
    const timers = [
      setTimeout(() => setStage(1), 1000),
      setTimeout(() => setStage(2), 2500),
      setTimeout(() => setStage(3), 4000),
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  const stages = [
    'Requesting microphone access...',
    'Establishing secure connection...',
    'Preparing your session...',
  ];

  return (
    <div className="fixed inset-0 flex min-h-[100dvh] w-full flex-col items-center justify-center bg-slate-50">
      {/* Animated Background Rings */}
      <div className="absolute inset-0 flex items-center justify-center overflow-hidden">
        {[...Array(3)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute rounded-full border border-teal-200/30"
            initial={{ width: 100, height: 100, opacity: 0 }}
            animate={
              shouldReduceMotion
                ? {}
                : {
                    width: [100, 600],
                    height: [100, 600],
                    opacity: [0.5, 0],
                  }
            }
            transition={{
              duration: 3,
              repeat: Infinity,
              delay: i * 1,
              ease: 'easeOut',
            }}
          />
        ))}
      </div>

      {/* Content */}
      <motion.div
        className="relative z-10 flex flex-col items-center gap-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-500 to-teal-600 text-xl font-bold text-white shadow-lg shadow-teal-500/30">
            S
            <motion.div
              className="absolute inset-0 rounded-2xl border-2 border-teal-400"
              animate={shouldReduceMotion ? {} : { scale: [1, 1.2, 1], opacity: [0.5, 0, 0.5] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          </div>
          <span className="text-xl font-bold text-slate-800">Saathi Swasthya</span>
        </div>

        {/* Loading Indicator */}
        <div className="relative">
          <motion.div
            className="h-16 w-16 rounded-full border-4 border-teal-100"
            style={{ borderTopColor: '#0d9488' }}
            animate={shouldReduceMotion ? {} : { rotate: 360 }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
          />
          <div className="absolute inset-0 flex items-center justify-center">
            <Mic className="h-6 w-6 text-teal-600" />
          </div>
        </div>

        {/* Status Text */}
        <div className="text-center">
          <h2 className="text-xl font-bold text-slate-800">Connecting to Saathi...</h2>
          <motion.p
            key={stage}
            className="mt-2 text-sm text-slate-500"
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            {stages[stage]}
          </motion.p>
        </div>

        {/* Progress Dots */}
        <div className="flex items-center gap-2">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className={cn(
                'h-2 w-2 rounded-full transition-colors duration-300',
                stage >= i ? 'bg-teal-500' : 'bg-slate-200'
              )}
              animate={shouldReduceMotion ? {} : stage === i ? { scale: [1, 1.3, 1] } : {}}
              transition={{ duration: 1, repeat: Infinity }}
            />
          ))}
        </div>

        {/* Security Badge */}
        <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2">
          <Shield className="h-4 w-4 text-teal-600" />
          <span className="text-xs font-medium text-slate-600">Encrypted in transit</span>
        </div>
      </motion.div>
    </div>
  );
};

// --- Premium Call Ended View ---
const CallEndedView = ({ onRestart }: { onRestart: () => void }) => {
  const shouldReduceMotion = useReducedMotion();

  return (
    <div className="fixed inset-0 flex min-h-[100dvh] w-full flex-col items-center justify-center bg-gradient-to-b from-slate-50 to-teal-50/30 px-6">
      <motion.div
        className="flex flex-col items-center gap-6 text-center"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-teal-600 text-lg font-bold text-white shadow-md">
            S
          </div>
          <span className="text-lg font-bold text-slate-800">Saathi Swasthya</span>
        </div>

        {/* Completion Icon */}
        <motion.div
          className="flex h-20 w-20 items-center justify-center rounded-full bg-teal-100"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
        >
          <svg
            className="h-10 w-10 text-teal-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <motion.path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M5 13l4 4L19 7"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ delay: 0.5, duration: 0.5 }}
            />
          </svg>
        </motion.div>

        {/* Text */}
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Session complete</h2>
          <p className="mt-2 max-w-sm text-sm text-slate-500">
            Thank you for using Saathi Swasthya. Your health is our priority.
          </p>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3 pt-2">
          <Button
            size="lg"
            onClick={onRestart}
            className="h-12 rounded-full bg-teal-600 px-8 font-semibold text-white shadow-lg shadow-teal-600/25 transition-all duration-200 hover:bg-teal-700 hover:shadow-xl active:scale-[0.98]"
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            Start a new conversation
          </Button>
          <button
            onClick={onRestart}
            className="text-sm font-medium text-slate-500 transition-colors hover:text-slate-700"
          >
            Return to home
          </button>
        </div>

        {/* Safety Reminder */}
        <div className="mt-4 flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2">
          <Phone className="h-4 w-4 text-rose-500" />
          <span className="text-xs text-slate-600">
            For emergencies, call <strong className="font-bold">112</strong> or{' '}
            <strong className="font-bold">108</strong>
          </span>
        </div>
      </motion.div>
    </div>
  );
};

// --- Error View ---
const ErrorView = ({ onRetry, onHome }: { onRetry: () => void; onHome: () => void }) => {
  return (
    <div className="fixed inset-0 flex min-h-[100dvh] w-full flex-col items-center justify-center bg-slate-50 px-6">
      <motion.div
        className="flex flex-col items-center gap-6 text-center"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-200 text-lg font-bold text-slate-500">
            S
          </div>
          <span className="text-lg font-bold text-slate-800">Saathi Swasthya</span>
        </div>

        {/* Icon */}
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-100">
          <svg
            className="h-8 w-8 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
        </div>

        {/* Text */}
        <div>
          <h2 className="text-xl font-bold text-slate-800">Connection lost</h2>
          <p className="mt-2 max-w-sm text-sm text-slate-500">
            Your session data is safe. This sometimes happens with voice connections.
          </p>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3 pt-2">
          <Button
            size="lg"
            onClick={onRetry}
            className="h-12 rounded-full bg-teal-600 px-8 font-semibold text-white shadow-lg transition-all duration-200 hover:bg-teal-700 active:scale-[0.98]"
          >
            <ArrowRight className="mr-2 h-4 w-4" />
            Try again
          </Button>
          <button
            onClick={onHome}
            className="text-sm font-medium text-slate-500 transition-colors hover:text-slate-700"
          >
            Return to home
          </button>
        </div>
      </motion.div>
    </div>
  );
};

interface ViewControllerProps {
  appConfig: AppConfig;
}

export function ViewController({ appConfig }: ViewControllerProps) {
  const { isConnected, start } = useSessionContext();
  const { resolvedTheme } = useTheme();

  type AppState = 'ready' | 'connecting' | 'connected' | 'ended' | 'error';
  const [appState, setAppState] = useState<AppState>('ready');
  const [micError, setMicError] = useState<string | undefined>();

  // Sync LiveKit's isConnected with our state machine
  useEffect(() => {
    if (isConnected) {
      setAppState('connected');
    } else if (appState === 'connected') {
      setAppState('ended');
    }
  }, [isConnected]);

  const handleStartCall = async () => {
    setMicError(undefined);
    setAppState('connecting');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      await start({ tracks: { microphone: { enabled: true } } });
    } catch (err: unknown) {
      setAppState('ready');
      const error = err as Error;
      if (
        error.name === 'NotAllowedError' ||
        error.message?.toLowerCase().includes('permission denied')
      ) {
        setMicError(
          'Microphone access is blocked. Please allow microphone access in your browser settings and try again.'
        );
      } else {
        setMicError(`Unable to start voice session. ${error.message || 'Unknown device error.'}`);
      }
    }
  };

  const handleRestart = () => {
    setAppState('ready');
    setMicError(undefined);
  };

  const handleRetry = () => {
    setMicError(undefined);
    handleStartCall();
  };

  return (
    <AnimatePresence mode="wait">
      {appState === 'ready' && (
        <MotionWelcomeView
          key="welcome"
          {...VIEW_MOTION_PROPS}
          startButtonText={appConfig.startButtonText}
          onStartCall={handleStartCall}
          micError={micError}
        />
      )}

      {appState === 'connecting' && (
        <MotionDiv key="connecting" {...VIEW_MOTION_PROPS} className="fixed inset-0 z-50">
          <ConnectingView />
        </MotionDiv>
      )}

      {appState === 'connected' && (
        <SaathiSessionView
          audioVisualizerType={appConfig.audioVisualizerType}
          audioVisualizerColor={
            resolvedTheme === 'dark'
              ? appConfig.audioVisualizerColorDark
              : appConfig.audioVisualizerColor
          }
          audioVisualizerColorShift={appConfig.audioVisualizerColorShift}
          audioVisualizerBarCount={appConfig.audioVisualizerBarCount}
          audioVisualizerRadialBarCount={appConfig.audioVisualizerRadialBarCount}
          audioVisualizerRadialRadius={appConfig.audioVisualizerRadialRadius}
          audioVisualizerGridRowCount={appConfig.audioVisualizerGridRowCount}
          audioVisualizerGridColumnCount={appConfig.audioVisualizerGridColumnCount}
          audioVisualizerWaveLineWidth={appConfig.audioVisualizerWaveLineWidth}
          className="fixed inset-0 z-40"
        />
      )}

      {appState === 'ended' && (
        <MotionDiv key="ended" {...VIEW_MOTION_PROPS} className="fixed inset-0 z-50">
          <CallEndedView onRestart={handleRestart} />
        </MotionDiv>
      )}

      {appState === 'error' && (
        <MotionDiv key="error" {...VIEW_MOTION_PROPS} className="fixed inset-0 z-50">
          <ErrorView onRetry={handleRetry} onHome={handleRestart} />
        </MotionDiv>
      )}
    </AnimatePresence>
  );
}
