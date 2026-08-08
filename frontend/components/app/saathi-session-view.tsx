'use client';

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useAgent, useSessionContext, useSessionMessages } from '@livekit/components-react';
import { PremiumChatTranscript } from '@/components/agents-ui/premium-chat-transcript';
import { AgentControlBar } from '@/components/agents-ui/agent-control-bar';
import { TileLayout } from '@/components/agents-ui/blocks/agent-session-view-01/components/tile-view';
import { cn } from '@/lib/shadcn/utils';
import { WarningCircle, Clock, Translate } from '@phosphor-icons/react/dist/ssr';

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
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
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

  return (
    <section
      ref={ref}
      className={cn('bg-slate-50 text-slate-800 flex flex-col h-screen w-full overflow-hidden selection:bg-teal-200 selection:text-teal-900', className)}
      {...props}
    >
      
      {/* Top Clinical Header */}
      <header className="flex justify-between items-center px-6 py-4 bg-white border-b border-slate-100 z-40 shadow-sm shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-teal-600 flex items-center justify-center text-white font-extrabold text-lg shadow-sm">
            S
          </div>
          <div>
            <h1 className="text-base sm:text-lg font-bold text-slate-900 leading-tight">Saathi Consultation</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
              </span>
              <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider">Voice AI Triage Assistant</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Call Timer */}
          <div className="flex items-center gap-1.5 px-3 py-1 bg-slate-100 rounded-lg text-slate-600 font-mono text-xs font-semibold border border-slate-200/50">
            <Clock weight="bold" /> {formatDuration(callDuration)}
          </div>
          {/* Language Indicator */}
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 bg-teal-50 text-teal-700 text-xs font-bold rounded-lg border border-teal-100/50">
            <Translate weight="bold" /> Multi-language Activated
          </div>
        </div>
      </header>

      {/* Main Split Layout */}
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden min-h-0">
        
        {/* Top/Left Side: Premium Conversation History */}
        <div className="flex flex-col h-[40%] md:h-auto md:w-[380px] lg:w-[440px] border-b md:border-b-0 md:border-r border-slate-200 bg-white relative z-20 shrink-0 order-2 md:order-1">
          <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
            <h2 className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">Medical Transcript</h2>
            <div className="text-[9px] text-teal-600 font-semibold bg-teal-50 border border-teal-100/50 px-2 py-0.5 rounded-full">Secure Session</div>
          </div>
          <div className="flex-1 overflow-hidden relative">
            <PremiumChatTranscript
              agentState={agentState}
              messages={messages}
            />
          </div>
        </div>

        {/* Bottom/Right Side: High-End Health Visualization Panel */}
        <div className="flex-1 relative flex flex-col justify-between bg-slate-50 overflow-hidden p-4 md:p-6 gap-4 md:gap-6 min-w-0 order-1 md:order-2">
          
          {/* Soft Professional Warning Banner instead of Red Anxiety-inducing strip */}
          <div className="w-full bg-rose-50 border border-rose-100 rounded-2xl p-4 flex gap-3 shadow-sm shrink-0 items-start">
            <WarningCircle weight="fill" className="size-5 text-rose-500 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <h4 className="text-xs font-bold text-rose-800 uppercase tracking-wide">Emergency Warning Advisory</h4>
              <p className="text-xs text-rose-700/90 leading-relaxed font-medium">
                For severe symptoms, stroke, heart complications, or breathing difficulties, call <strong className="text-rose-900 font-bold underline">112 or 108</strong> immediately. Saathi is an AI screening tool, not a doctor.
              </p>
            </div>
          </div>

          {/* Central Workspace Card for Audio Representation */}
          <div className="flex-1 w-full bg-white border border-slate-200/80 rounded-3xl shadow-sm flex flex-col items-center justify-center p-8 relative overflow-hidden">
            
            {/* Dynamic Interactive Listening Status Indicator */}
            <div className="absolute top-6 flex items-center gap-2 bg-slate-50 border border-slate-200 px-5 py-2 rounded-full shadow-inner z-20">
              <span className={cn(
                "w-2.5 h-2.5 rounded-full transition-all duration-300",
                agentState === 'listening' ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' :
                agentState === 'thinking' ? 'bg-amber-500 animate-pulse' :
                agentState === 'speaking' ? 'bg-teal-500 shadow-[0_0_8px_#0d9488]' : 'bg-slate-300'
              )} />
              <span className="text-xs font-bold text-slate-600 uppercase tracking-widest">
                {agentState === 'listening' ? 'Saathi is Listening' :
                 agentState === 'thinking' ? 'Analyzing Symptoms' :
                 agentState === 'speaking' ? 'Speaking' : 'Offline'}
              </span>
            </div>

            {/* Visualizer Frame */}
            <div className="w-full flex items-center justify-center relative">
              <div className="absolute w-[240px] h-[240px] rounded-full border border-teal-500/10 animate-[spin_12s_linear_infinite] z-0"></div>
              <div className="absolute w-[320px] h-[320px] rounded-full border border-teal-500/5 animate-[spin_20s_linear_infinite_reverse] z-0"></div>
              
              <div className="relative z-10 flex items-center justify-center">
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

            {/* Preconnect Prompt */}
            <AnimatePresence>
              {messages.length === 0 && isPreConnectBufferEnabled && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="absolute bottom-6 px-6 py-3.5 bg-slate-900 border border-slate-800 text-white rounded-2xl shadow-lg text-xs font-semibold tracking-wide text-center max-w-sm pointer-events-none"
                >
                  {preConnectMessage}
                </motion.div>
              )}
            </AnimatePresence>
            
          </div>

          {/* Call Controls Container */}
          <div className="w-full bg-white border border-slate-200/80 rounded-2xl p-3 shadow-sm flex items-center justify-center shrink-0">
            <div className="bg-slate-50 border border-slate-100 rounded-full px-4 py-2.5 shadow-inner">
              <AgentControlBar
                variant="livekit"
                controls={controls}
                isChatOpen={false}
                isConnected={session.isConnected}
                onDisconnect={session.end}
                onIsChatOpenChange={() => {}}
              />
            </div>
          </div>

        </div>

      </div>

    </section>
  );
}
