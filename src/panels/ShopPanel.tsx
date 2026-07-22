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
      <div className="relative h-full bg-white">
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
    );
  },
);

ShopPanel.displayName = 'ShopPanel';
export default ShopPanel;
