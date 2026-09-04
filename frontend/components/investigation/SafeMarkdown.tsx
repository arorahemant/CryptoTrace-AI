import type { ReactNode } from 'react';

function renderInline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index} className="font-semibold text-[var(--ct-ink)]">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={index} className="rounded bg-[var(--ct-surface-high)] px-1 font-mono text-[0.92em]">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

export function SafeMarkdown({ content }: { content: string }) {
  const lines = content.split(/\r?\n/);
  return (
    <div className="space-y-1.5 text-left text-xs leading-relaxed">
      {lines.map((line, index) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={index} className="h-1" aria-hidden="true" />;
        if (/^\*\*[^*]+\*\*$/.test(trimmed)) {
          return <div key={index} className="pt-1 text-[10px] font-bold uppercase tracking-wide text-[var(--ct-primary)]">{trimmed.slice(2, -2)}</div>;
        }
        if (/^(?:[-*]|•|→)\s+/.test(trimmed)) {
          const item = trimmed.replace(/^(?:[-*]|•|→)\s+/, '');
          return <div key={index} className="grid grid-cols-[0.6rem_1fr] gap-1.5"><span aria-hidden="true">•</span><span>{renderInline(item)}</span></div>;
        }
        return <p key={index}>{renderInline(trimmed)}</p>;
      })}
    </div>
  );
}
