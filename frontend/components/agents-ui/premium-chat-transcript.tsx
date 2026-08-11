'use client';

import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { type AgentState, type ReceivedMessage } from '@livekit/components-react';
import { Mic, CheckCircle, Loader2, User } from 'lucide-react';
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
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, agentState]);

  // Handle scroll position
  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
      setShowScrollButton(!isAtBottom);
    }
  };

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };

  // Detect tool activity messages
  const isToolActivity = (message: ReceivedMessage) => {
    const text = message.message?.toLowerCase() || '';
    return text.includes('finding') || text.includes('searching') || text.includes('looking up');
  };

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className={cn(
        'custom-scrollbar relative flex h-full w-full flex-col gap-1 overflow-y-auto scroll-smooth px-4 py-3',
        className
      )}
    >
      {/* Empty State */}
      {messages.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-slate-50">
            <Mic className="h-7 w-7 text-slate-300" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-500">
              Your conversation will appear here
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Speak naturally to begin
            </p>
          </div>
        </div>
      )}

      {/* Messages - Premium voice transcript style */}
      <AnimatePresence initial={false}>
        {messages.map((msg, index) => {
          const isUser = msg.from?.isLocal;
          const isTool = !isUser && isToolActivity(msg);

          return (
            <motion.div
              key={msg.id || index}
              initial={false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className={cn(
                'flex w-full py-2',
                isUser ? 'justify-end' : 'justify-start'
              )}
            >
              <div
                className={cn(
                  'flex max-w-[85%] gap-2.5',
                  isUser ? 'flex-row-reverse' : 'flex-row'
                )}
              >
                {/* Avatar */}
                {!isUser ? (
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-teal-500 to-teal-600 text-[10px] font-bold text-white shadow-sm">
                    S
                  </div>
                ) : (
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-[10px] font-bold text-slate-400">
                    <User className="h-3.5 w-3.5" />
                  </div>
                )}

                {/* Message Content */}
                <div className="flex min-w-0 flex-col gap-1">
                  {/* Speaker Label & Time */}
                  <div
                    className={cn(
                      'flex items-center gap-2',
                      isUser ? 'justify-end' : 'justify-start'
                    )}
                  >
                    <span className={cn(
                      'text-[10px] font-semibold',
                      isUser ? 'text-slate-400' : 'text-teal-600'
                    )}>
                      {isUser ? 'You' : 'Saathi'}
                    </span>
                    <span className="font-mono text-[9px] text-slate-300">
                      {msg.timestamp ? formatTime(msg.timestamp) : ''}
                    </span>
                  </div>

                  {/* Message Bubble - Premium style */}
                  {isTool ? (
                    // Tool Activity Message
                    <div className="flex items-center gap-2 rounded-xl border border-amber-100 bg-amber-50/50 px-3 py-2">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-amber-500" />
                      <span className="text-xs font-medium text-amber-700">{msg.message}</span>
                    </div>
                  ) : (
                    // Regular Message - Premium transcript style
                    <div
                      className={cn(
                        'px-3.5 py-2.5 text-sm leading-relaxed',
                        isUser
                          ? 'rounded-2xl rounded-tr-sm bg-gradient-to-br from-teal-500 to-teal-600 text-white shadow-sm'
                          : 'rounded-2xl rounded-tl-sm border border-slate-100 bg-white text-slate-700'
                      )}
                    >
                      {msg.message}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>

      {/* Typing Indicator */}
      <AnimatePresence>
        {(agentState === 'thinking' || agentState === 'speaking') && (
          <motion.div
            initial={false}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="flex w-full justify-start py-2"
          >
            <div className="flex gap-2.5">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-teal-500 to-teal-600 text-[10px] font-bold text-white shadow-sm">
                S
              </div>
              <div className="flex items-center gap-1.5 rounded-2xl rounded-tl-sm border border-slate-100 bg-white px-3.5 py-2.5">
                <motion.span
                  animate={{ scale: [1, 1.2, 1], opacity: [0.4, 1, 0.4] }}
                  transition={{ repeat: Infinity, duration: 1, delay: 0 }}
                  className="h-1.5 w-1.5 rounded-full bg-teal-400"
                />
                <motion.span
                  animate={{ scale: [1, 1.2, 1], opacity: [0.4, 1, 0.4] }}
                  transition={{ repeat: Infinity, duration: 1, delay: 0.2 }}
                  className="h-1.5 w-1.5 rounded-full bg-teal-400"
                />
                <motion.span
                  animate={{ scale: [1, 1.2, 1], opacity: [0.4, 1, 0.4] }}
                  transition={{ repeat: Infinity, duration: 1, delay: 0.4 }}
                  className="h-1.5 w-1.5 rounded-full bg-teal-400"
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Scroll to Bottom Button */}
      <AnimatePresence>
        {showScrollButton && (
          <motion.button
            initial={false}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            onClick={scrollToBottom}
            className="sticky bottom-2 left-1/2 -translate-x-1/2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-600 shadow-lg transition-colors hover:bg-slate-50"
          >
            New messages
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
