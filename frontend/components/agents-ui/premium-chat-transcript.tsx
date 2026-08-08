'use client';

import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { type AgentState, type ReceivedMessage } from '@livekit/components-react';
import { cn } from '@/lib/shadcn/utils';

interface PremiumChatTranscriptProps {
  messages: ReceivedMessage[];
  agentState: AgentState;
  className?: string;
}

export function PremiumChatTranscript({
  messages,
  agentState,
  className,
}: PremiumChatTranscriptProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, agentState]);

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div
      ref={scrollRef}
      className={cn('w-full h-full overflow-y-auto px-4 py-6 scroll-smooth custom-scrollbar flex flex-col gap-6', className)}
    >
      <AnimatePresence initial={false}>
        {messages.map((msg, index) => {
          const isUser = msg.from?.isLocal;
          
          return (
            <motion.div
              key={msg.id || index}
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              className={cn(
                'flex w-full',
                isUser ? 'justify-end' : 'justify-start'
              )}
            >
              <div className={cn('flex gap-3 max-w-[85%]', isUser ? 'flex-row-reverse' : 'flex-row')}>
                {/* Avatar */}
                {!isUser ? (
                  <div className="w-8 h-8 shrink-0 rounded-full bg-teal-600 flex items-center justify-center shadow-md">
                    <span className="text-white font-bold text-sm">S</span>
                  </div>
                ) : (
                  <div className="w-8 h-8 shrink-0 rounded-full bg-slate-200 flex items-center justify-center shadow-sm border border-slate-300">
                    <span className="text-slate-500 font-bold text-sm">U</span>
                  </div>
                )}

                {/* Message Bubble */}
                <div className="flex flex-col gap-1 min-w-0">
                  <div className={cn(
                    'flex items-center gap-2',
                    isUser ? 'justify-end' : 'justify-start'
                  )}>
                    <span className="text-xs font-semibold text-slate-500">
                      {isUser ? 'You' : 'Saathi'}
                    </span>
                    <span className="text-[10px] text-slate-400 font-medium">
                      {msg.timestamp ? formatTime(msg.timestamp) : ''}
                    </span>
                  </div>

                  <div className={cn(
                    'px-4 py-3 shadow-sm text-sm leading-relaxed whitespace-pre-wrap break-words',
                    isUser
                      ? 'bg-teal-600 text-white rounded-2xl rounded-tr-sm'
                      : 'bg-white border border-slate-200 text-slate-800 rounded-2xl rounded-tl-sm'
                  )}>
                    {msg.message}
                  </div>
                </div>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>

      {/* Typing Indicator / Agent Thinking State */}
      <AnimatePresence>
        {(agentState === 'thinking' || agentState === 'speaking') && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="flex w-full justify-start mt-2"
          >
             <div className="flex gap-3 max-w-[85%] flex-row">
                <div className="w-8 h-8 shrink-0 rounded-full bg-teal-600 flex items-center justify-center shadow-md">
                  <span className="text-white font-bold text-sm">S</span>
                </div>
                <div className="px-4 py-3 bg-white border border-slate-200 rounded-2xl rounded-tl-sm flex items-center gap-1.5 shadow-sm h-11">
                  <motion.span
                    animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
                    transition={{ repeat: Infinity, duration: 1, delay: 0 }}
                    className="w-1.5 h-1.5 rounded-full bg-teal-400"
                  />
                  <motion.span
                    animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
                    transition={{ repeat: Infinity, duration: 1, delay: 0.2 }}
                    className="w-1.5 h-1.5 rounded-full bg-teal-400"
                  />
                  <motion.span
                    animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
                    transition={{ repeat: Infinity, duration: 1, delay: 0.4 }}
                    className="w-1.5 h-1.5 rounded-full bg-teal-400"
                  />
                </div>
             </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
