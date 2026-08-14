'use client';

import React, { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, Clock, Globe, Mic, Phone, Shield } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useAgent, useSessionContext, useSessionMessages } from '@livekit/components-react';
import { AgentControlBar } from '@/components/agents-ui/agent-control-bar';
import { TileLayout } from '@/components/agents-ui/blocks/agent-session-view-01/components/tile-view';
import { PremiumChatTranscript } from '@/components/agents-ui/premium-chat-transcript';
import { cn } from '@/lib/shadcn/utils';

export interface SaathiSessionViewProps {
  preConnectMessage?: string;
  supportsChatInput?: boolean;
  supportsVideoInput?: boolean;
  supportsScreenShare?: boolean;
  isPreConnectBufferEnabled?: boolean;
  audioVisualizerType?: 'bar' | 'wave' | 'grid' | 'radial' | 'aura';
  audioVisualizerColor?: `#${string}`;
  audioVisualizerColorShift?: number;
  audioVisualizerBarCount?: number;
  audioVisualizerGridRowCount?: number;
  audioVisualizerGridColumnCount?: number;
  audioVisualizerRadialBarCount?: number;
  audioVisualizerRadialRadius?: number;
  audioVisualizerWaveLineWidth?: number;
  className?: string;
}

export function SaathiSessionView({
  preConnectMessage = 'Saathi is listening. How can I help you today?',
  supportsChatInput = true,
  supportsVideoInput = true,
  supportsScreenShare = true,
  isPreConnectBufferEnabled = true,
  audioVisualizerType,
  audioVisualizerColor,
  audioVisualizerColorShift,
  audioVisualizerBarCount,
  audioVisualizerGridRowCount,
  audioVisualizerGridColumnCount,
  audioVisualizerRadialBarCount,
  audioVisualizerRadialRadius,
  audioVisualizerWaveLineWidth,
  ref,
  className,
  ...props
}: React.ComponentProps<'section'> & SaathiSessionViewProps) {
  const session = useSessionContext();
  const { messages } = useSessionMessages(session);
  const { state: agentState } = useAgent();
  const [callDuration, setCallDuration] = useState(0);
  const [transcriptOpen, setTranscriptOpen] = useState(false);

  // Call Timer logic
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (session.isConnected) {
      interval = setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);
    } else {
      setCallDuration(0);
    }
    return () => clearInterval(interval);
  }, [session.isConnected]);

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60)
      .toString()
      .padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const controls = {
    leave: true,
    microphone: true,
    chat: supportsChatInput,
    camera: supportsVideoInput,
    screenShare: supportsScreenShare,
  };

  // Voice state configuration with proper treatments
  const getVoiceStateConfig = (state: string) => {
    const configs: Record<
      string,
      {
        color: string;
        label: string;
        dotColor: string;
        description: string;
      }
    > = {
      listening: {
        color: 'text-emerald-600',
        label: 'Listening',
        dotColor: 'bg-emerald-500',
        description: 'Speak naturally in your language',
      },
      thinking: {
        color: 'text-amber-600',
        label: 'Thinking',
        dotColor: 'bg-amber-500',
        description: 'Analyzing your symptoms...',
      },
      speaking: {
        color: 'text-teal-600',
        label: 'Speaking',
        dotColor: 'bg-teal-500',
        description: 'Saathi is responding...',
      },
      connecting: {
        color: 'text-slate-500',
        label: 'Connecting',
        dotColor: 'bg-slate-400',
        description: 'Setting up secure session...',
      },
    };
    return (
      configs[state] || {
        color: 'text-slate-400',
        label: 'Offline',
        dotColor: 'bg-slate-300',
        description: 'Session ended',
      }
    );
  };

  const currentState = getVoiceStateConfig(agentState);

  return (
    <section
      ref={ref}
      className={cn(
        'flex h-[100dvh] w-full flex-col overflow-hidden bg-slate-50 text-slate-800 selection:bg-teal-200 selection:text-teal-900',
        className
      )}
      {...props}
    >
      {/* Premium Header */}
      <header className="z-40 flex shrink-0 items-center justify-between border-b border-slate-100 bg-white px-4 py-3 shadow-sm sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-teal-500 to-teal-600 text-sm font-bold text-white shadow-md">
            S
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-bold text-slate-800 sm:text-base">Saathi</span>
            <span className="text-[10px] text-slate-400">Health Navigator</span>
          </div>
        </div>

        {/* Voice State Pill - Enhanced */}
        <div
          className={cn(
            'flex items-center gap-2.5 rounded-full border px-4 py-2 transition-all duration-300',
            agentState === 'listening' && 'border-emerald-200 bg-emerald-50',
            agentState === 'thinking' && 'border-amber-200 bg-amber-50',
            agentState === 'speaking' && 'border-teal-200 bg-teal-50',
            !['listening', 'thinking', 'speaking'].includes(agentState) &&
              'border-slate-200 bg-slate-50'
          )}
        >
          <span
            className={cn(
              'h-2.5 w-2.5 rounded-full transition-colors',
              currentState.dotColor,
              agentState === 'listening' && 'animate-pulse'
            )}
          />
          <span className={cn('text-xs font-semibold tracking-wide uppercase', currentState.color)}>
            {currentState.label}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Language Indicator */}
          <div className="hidden items-center gap-1.5 rounded-lg border border-slate-100 bg-slate-50 px-3 py-1.5 sm:flex">
            <Globe className="h-3.5 w-3.5 text-slate-400" />
            <span className="text-[10px] font-medium text-slate-500">EN/HI/GU</span>
          </div>

          {/* Session Timer */}
          <div className="flex items-center gap-1.5 rounded-lg border border-slate-100 bg-slate-50 px-3 py-1.5 font-mono text-xs font-semibold text-slate-600">
            <Clock className="h-3.5 w-3.5" />
            {formatDuration(callDuration)}
          </div>
        </div>
      </header>

      {/* Emergency Banner - Subtle but persistent */}
      <div className="w-full border-b border-rose-50 bg-gradient-to-r from-rose-50/50 via-rose-50 to-rose-50/50 py-2">
        <div className="flex items-center justify-center gap-2 text-xs text-rose-600">
          <Phone className="h-3 w-3" />
          <span>
            For emergencies, call <strong className="font-bold">112</strong> or{' '}
            <strong className="font-bold">108</strong>
          </span>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
        {/* Voice Visualization Area - Integrated into page */}
        <div className="relative flex flex-1 flex-col items-center justify-center gap-4 bg-gradient-to-b from-slate-50 via-white to-slate-50 p-4">
          {/* Voice Orb - Integrated visualization */}
          <div className="relative flex items-center justify-center">
            {/* Subtle decorative rings - NOT a black box */}
            <div className="absolute h-[280px] w-[280px] rounded-full border border-teal-100/60 sm:h-[360px] sm:w-[360px]" />
            <div className="absolute h-[240px] w-[240px] rounded-full border border-teal-100/40 sm:h-[320px] sm:w-[320px]" />

            {/* Tile Layout with Audio Visualizer - No black background */}
            <div className="relative z-10">
              <TileLayout
                chatOpen={false}
                audioVisualizerType={audioVisualizerType}
                audioVisualizerColor={audioVisualizerColor || '#0d9488'}
                audioVisualizerColorShift={audioVisualizerColorShift}
                audioVisualizerBarCount={audioVisualizerBarCount}
                audioVisualizerRadialBarCount={audioVisualizerRadialBarCount}
                audioVisualizerRadialRadius={audioVisualizerRadialRadius}
                audioVisualizerGridRowCount={audioVisualizerGridRowCount}
                audioVisualizerGridColumnCount={audioVisualizerGridColumnCount}
                audioVisualizerWaveLineWidth={audioVisualizerWaveLineWidth}
              />
            </div>
          </div>

          {/* Status Text - Enhanced */}
          <motion.div
            className="text-center"
            initial={false}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            <p className={cn('text-sm font-medium', currentState.color)}>
              {currentState.description}
            </p>
          </motion.div>

          {/* Pre-connect Prompt */}
          <AnimatePresence>
            {messages.length === 0 && isPreConnectBufferEnabled && (
              <motion.div
                initial={false}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="absolute bottom-6 left-1/2 -translate-x-1/2 rounded-2xl border border-slate-100 bg-white px-6 py-4 shadow-lg sm:bottom-10"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-teal-50">
                    <Mic className="h-5 w-5 text-teal-600" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">{preConnectMessage}</p>
                    <p className="mt-0.5 text-[10px] text-slate-400">Tap microphone to start</p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Premium Transcript Panel */}
        <div className="flex flex-col border-t border-slate-100 bg-white">
          {/* Transcript Toggle - Premium styling */}
          <button
            onClick={() => setTranscriptOpen(!transcriptOpen)}
            className="flex items-center justify-between border-b border-slate-100 px-5 py-3 transition-colors hover:bg-slate-50/50"
          >
            <div className="flex items-center gap-3">
              <span className="text-[11px] font-bold tracking-widest text-slate-400 uppercase">
                Conversation
              </span>
              {messages.length > 0 && (
                <span className="rounded-full bg-teal-50 px-2.5 py-0.5 text-[10px] font-bold text-teal-600">
                  {messages.length}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <Shield className="h-3 w-3 text-emerald-500" />
                <span className="text-[10px] font-medium text-emerald-600">Secure</span>
              </div>
              {transcriptOpen ? (
                <ChevronDown className="h-4 w-4 text-slate-300" />
              ) : (
                <ChevronUp className="h-4 w-4 text-slate-300" />
              )}
            </div>
          </button>

          {/* Transcript Content */}
          <AnimatePresence>
            {transcriptOpen && (
              <motion.div
                initial={false}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.3, ease: 'easeInOut' }}
                className="overflow-hidden"
              >
                <div className="h-[250px] sm:h-[320px]">
                  <PremiumChatTranscript agentState={agentState} messages={messages} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Control Bar - Premium pill design */}
        <div className="flex shrink-0 items-center justify-center border-t border-slate-100 bg-white px-4 py-3">
          <div
            className={cn(
              'border border-slate-200/80 shadow-sm transition-all duration-300',
              transcriptOpen
                ? 'w-full max-w-[580px] rounded-2xl bg-white px-3 py-2.5'
                : 'rounded-full bg-slate-50 px-3 py-2.5'
            )}
          >
            <AgentControlBar
              variant="livekit"
              controls={controls}
              isChatOpen={transcriptOpen}
              isConnected={session.isConnected}
              onDisconnect={session.end}
              onIsChatOpenChange={setTranscriptOpen}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
