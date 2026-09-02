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
  onJumpToStep: (step: number) => void;
}

export function ReplayBar({
  events,
  step,
  playing,
  onStepBackward,
  onTogglePlaying,
  onStepForward,
  onJumpToStep,
}: ReplayBarProps) {
  const currentEvent = events[step];
  const progress = events.length > 0 ? ((step + 1) / events.length) * 100 : 0;

  return (
    <div
      className="ct-replay-bar absolute bottom-16 left-1/2 -translate-x-1/2 bg-[#111827] border border-[#1e293b] rounded px-4 py-3 shadow-2xl flex items-center gap-3 z-20"
      role="region"
      aria-label="Investigation replay controls"
    >
      <button
        type="button"
        onClick={onStepBackward}
        aria-label="Step backward through replay"
        title="Step backward"
        className="min-h-10 min-w-10 flex items-center justify-center rounded text-slate-400 hover:bg-[#1e293b] hover:text-white"
      >
        <SkipBack className="w-4 h-4" />
      </button>
      <button
        type="button"
        onClick={onTogglePlaying}
        aria-label={playing ? 'Pause replay' : 'Play replay'}
        title={playing ? 'Pause replay' : 'Play replay'}
        className="min-h-10 min-w-10 flex items-center justify-center rounded bg-blue-500/10 text-blue-400 hover:bg-blue-500/20 hover:text-blue-300"
      >
        {playing ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
      </button>
      <button
        type="button"
        onClick={onStepForward}
        aria-label="Step forward through replay"
        title="Step forward"
        className="min-h-10 min-w-10 flex items-center justify-center rounded text-slate-400 hover:bg-[#1e293b] hover:text-white"
      >
        <SkipForward className="w-4 h-4" />
      </button>
      <div
        className="w-40 h-1 bg-[#1e293b] rounded-full relative"
        role="progressbar"
        aria-label="Replay progress"
        aria-valuemin={0}
        aria-valuemax={events.length}
        aria-valuenow={step + 1}
      >
        <div
          className="h-full bg-blue-500 rounded-full transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>
      <span className="text-xs text-slate-400 font-mono" aria-live="polite">
        {step + 1}/{events.length}
      </span>
      <label className="sr-only" htmlFor="replay-event-select">Jump to replay event</label>
      <select
        id="replay-event-select"
        value={step}
        onChange={(event) => onJumpToStep(Number(event.target.value))}
        className="max-w-44 min-h-10 rounded border border-[#2a3548] bg-[#0a0e17] px-2 text-[10px] text-white outline-none focus:border-blue-500"
      >
        {events.map((event, index) => (
          <option key={`${event.title || 'event'}-${index}`} value={index}>
            {index + 1}. {event.title || 'Replay event'}
          </option>
        ))}
      </select>
      <div className="ml-1 max-w-xs hidden md:block">
        <div className="text-xs text-white font-medium truncate">{currentEvent?.title}</div>
        <div className="text-[10px] text-slate-500 truncate">{currentEvent?.description}</div>
      </div>
    </div>
  );
}
