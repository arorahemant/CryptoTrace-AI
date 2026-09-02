'use client';

import { Pause, Play, SkipBack, SkipForward } from 'lucide-react';

interface ReplayBarEvent {
  title?: string;
  description?: string;
}

interface ReplayBarProps {
  events: readonly ReplayBarEvent[];
  step: number;
  playing: boolean;
  onStepBackward: () => void;
  onTogglePlaying: () => void;
  onStepForward: () => void;
}

export function ReplayBar({
  events,
  step,
  playing,
  onStepBackward,
  onTogglePlaying,
  onStepForward,
}: ReplayBarProps) {
  const currentEvent = events[step];
  const progress = events.length > 0 ? ((step + 1) / events.length) * 100 : 0;

  return (
    <div className="ct-replay-bar absolute bottom-16 left-1/2 -translate-x-1/2 bg-[#111827] border border-[#1e293b] rounded-xl px-5 py-3 shadow-2xl flex items-center gap-4 z-20">
      <button
        type="button"
        onClick={onStepBackward}
        aria-label="Step backward through replay"
        title="Step backward"
        className="text-slate-400 hover:text-white"
      >
        <SkipBack className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={onTogglePlaying}
        aria-label={playing ? 'Pause replay' : 'Play replay'}
        title={playing ? 'Pause replay' : 'Play replay'}
        className="text-blue-400 hover:text-blue-300"
      >
        {playing ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
      </button>
      <button
        type="button"
        onClick={onStepForward}
        aria-label="Step forward through replay"
        title="Step forward"
        className="text-slate-400 hover:text-white"
      >
        <SkipForward className="w-4 h-4" />
      </button>
      <div className="w-40 h-1 bg-[#1e293b] rounded-full relative" aria-hidden="true">
        <div
          className="h-full bg-blue-500 rounded-full transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>
      <span className="text-xs text-slate-400 font-mono" aria-live="polite">
        {step + 1}/{events.length}
      </span>
      <div className="ml-2 max-w-xs">
        <div className="text-xs text-white font-medium truncate">{currentEvent?.title}</div>
        <div className="text-[10px] text-slate-500 truncate">{currentEvent?.description}</div>
      </div>
    </div>
  );
}
