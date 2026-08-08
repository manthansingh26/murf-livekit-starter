'use client';

import { useState, useEffect } from 'react';
import { useTheme } from 'next-themes';
import { AnimatePresence, motion } from 'motion/react';
import { useSessionContext } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { SaathiSessionView } from '@/components/app/saathi-session-view';
import { WelcomeView } from '@/components/app/welcome-view';
import { Button } from '@/components/ui/button';

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
  transition: { duration: 0.5, ease: 'linear' },
};

// --- Custom Views for Day 3 ---
const ConnectingView = () => (
  <div className="fixed inset-0 min-h-screen w-full bg-slate-50 flex flex-col items-center justify-center text-slate-800">
    <div className="flex items-center gap-3 mb-8">
      <div className="w-10 h-10 rounded-xl bg-teal-600 flex items-center justify-center text-white font-extrabold text-lg shadow-sm">
        S
      </div>
      <span className="font-bold text-lg text-slate-800">Saathi Swasthya</span>
    </div>
    <div className="w-12 h-12 rounded-full border-4 border-teal-200 border-t-teal-600 animate-spin mb-6"></div>
    <h2 className="text-xl font-bold text-slate-800">Connecting to Saathi...</h2>
    <p className="text-slate-500 mt-2 text-sm">Setting up your secure voice session</p>
  </div>
);

const CallEndedView = ({ onRestart }: { onRestart: () => void }) => (
  <div className="fixed inset-0 min-h-screen w-full bg-slate-50 flex flex-col items-center justify-center text-slate-800 px-6">
    <div className="flex items-center gap-3 mb-8">
      <div className="w-10 h-10 rounded-xl bg-teal-600 flex items-center justify-center text-white font-extrabold text-lg shadow-sm">
        S
      </div>
      <span className="font-bold text-lg text-slate-800">Saathi Swasthya</span>
    </div>
    <div className="w-16 h-16 rounded-full bg-slate-200 flex items-center justify-center mb-6">
      <span className="text-2xl">👋</span>
    </div>
    <h2 className="text-2xl font-bold mb-2">Conversation ended</h2>
    <p className="text-slate-500 mb-8 max-w-sm text-center text-sm">
      Thank you for using Saathi Swasthya. Your health is our priority.
    </p>
    <Button
      size="lg"
      onClick={onRestart}
      className="bg-teal-600 hover:bg-teal-700 text-white font-semibold rounded-xl px-8 h-12 shadow-sm transition-all duration-150 active:scale-[0.98]"
    >
      🎙️ Start again
    </Button>
    <p className="text-xs text-slate-400 mt-4">
      For emergencies, call <strong className="text-slate-600">112</strong> or <strong className="text-slate-600">108</strong>
    </p>
  </div>
);
// ------------------------------

interface ViewControllerProps {
  appConfig: AppConfig;
}

export function ViewController({ appConfig }: ViewControllerProps) {
  const { isConnected, start } = useSessionContext();
  const { resolvedTheme } = useTheme();

  type AppState = 'ready' | 'connecting' | 'connected' | 'ended';
  const [appState, setAppState] = useState<AppState>('ready');
  const [micError, setMicError] = useState<string | undefined>();

  // Sync LiveKit's isConnected with our state machine to handle the ENDED state
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
      // Explicitly request microphone first to handle NotAllowedError cleanly
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Stop the tracks immediately, we just needed to verify permission
      stream.getTracks().forEach(track => track.stop());

      await start();
    } catch (err: any) {
      setAppState('ready');
      if (err.name === 'NotAllowedError' || err.message?.toLowerCase().includes('permission denied')) {
        setMicError("Microphone access is blocked. Please allow microphone access in your browser settings and try again.");
      } else {
        setMicError(`Unable to start voice session. ${err.message || 'Unknown device error.'}`);
      }
    }
  };

  const handleRestart = () => {
    setAppState('ready');
    setMicError(undefined);
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
    </AnimatePresence>
  );
}
