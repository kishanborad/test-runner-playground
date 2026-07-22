import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '../index.css';

function ShopPlaceholder() {
  return (
    <div className="min-h-screen bg-shop-bg flex items-center justify-center">
      <h1 className="text-xl text-shop-text">Demo Shop</h1>
    </div>
  );
}

createRoot(document.getElementById('shop-root')!).render(
  <StrictMode>
    <ShopPlaceholder />
  </StrictMode>,
);
