import { HashRouter, Routes, Route } from 'react-router-dom';
import { CartProvider } from './CartContext';
import ShopNav from './ShopNav';

function Placeholder({ name }: { name: string }) {
  return <div className="p-8 text-shop-muted">{name} — coming in Task 3</div>;
}

export default function ShopApp() {
  return (
    <HashRouter>
      <CartProvider>
        <div className="min-h-screen bg-shop-bg">
          <ShopNav />
          <main className="max-w-6xl mx-auto px-4 py-6">
            <Routes>
              <Route path="/" element={<Placeholder name="Product List" />} />
              <Route path="/product/:id" element={<Placeholder name="Product Detail" />} />
              <Route path="/cart" element={<Placeholder name="Cart" />} />
              <Route path="/checkout" element={<Placeholder name="Checkout" />} />
            </Routes>
          </main>
        </div>
      </CartProvider>
    </HashRouter>
  );
}
