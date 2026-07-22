import { useEffect, useRef } from 'react';
import type { HighlightInfo } from '../engine/executor';

interface Props {
  cursorPos: { x: number; y: number } | null;
  highlight: HighlightInfo | null;
  visible: boolean;
}

export default function Overlay({ cursorPos, highlight, visible }: Props) {
  const cursorRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!cursorRef.current || !cursorPos) return;
    cursorRef.current.style.transform = `translate(${cursorPos.x}px, ${cursorPos.y}px)`;
  }, [cursorPos]);

  if (!visible) return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-50 overflow-hidden">
      {/* Cursor */}
      {cursorPos && (
        <div
          ref={cursorRef}
          className="absolute top-0 left-0 transition-transform ease-out"
          style={{ transitionDuration: '300ms' }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path
              d="M5 3l14 8-6 2-2 6z"
              fill="#3b82f6"
              stroke="#1e40af"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      )}

      {/* Highlight box */}
      {highlight && (
        <>
          <div
            className={`absolute border-2 rounded transition-all duration-200 ${
              highlight.success ? 'border-green-500 bg-green-500/10' : 'border-red-500 bg-red-500/10'
            }`}
            style={{
              top: highlight.rect.top,
              left: highlight.rect.left,
              width: highlight.rect.width,
              height: highlight.rect.height,
            }}
          />
          <div
            className={`absolute px-2 py-1 rounded text-xs text-white whitespace-nowrap ${
              highlight.success ? 'bg-green-600' : 'bg-red-600'
            }`}
            style={{
              top: highlight.rect.top - 28,
              left: highlight.rect.left,
            }}>
            {highlight.label}
          </div>
        </>
      )}
    </div>
  );
}
