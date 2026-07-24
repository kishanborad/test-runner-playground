import { forwardRef } from 'react';
import Overlay from '../overlay/Overlay';
import type { HighlightInfo } from '../engine/executor';

interface Props {
  shopUrl: string;
  cursorPos: { x: number; y: number } | null;
  highlight: HighlightInfo | null;
  overlayVisible: boolean;
}

const ShopPanel = forwardRef<HTMLIFrameElement, Props>(
  ({ shopUrl, cursorPos, highlight, overlayVisible }, ref) => {
    return (
      <div className="relative h-full bg-panel-bg flex flex-col">
        <div className="flex-1 relative overflow-hidden border-2 border-panel-border rounded-lg m-2 shadow-glass">
          <iframe
            ref={ref}
            src={shopUrl}
            className="w-full h-full border-0"
            title="Demo Shop"
          />
          <Overlay
            cursorPos={cursorPos}
            highlight={highlight}
            visible={overlayVisible}
          />
        </div>
      </div>
    );
  },
);

ShopPanel.displayName = 'ShopPanel';
export default ShopPanel;
