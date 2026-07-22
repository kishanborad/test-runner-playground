import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import ShopApp from './ShopApp';
import '../index.css';

createRoot(document.getElementById('shop-root')!).render(
  <StrictMode>
    <ShopApp />
  </StrictMode>,
);
