import { HashRouter, Routes, Route } from 'react-router-dom';
import { CartProvider } from './CartContext';
import ShopNav from './ShopNav';
import ProductList from './ProductList';
import ProductDetail from './ProductDetail';
import Cart from './Cart';
import Checkout from './Checkout';

export default function ShopApp() {
  return (
    <HashRouter>
      <CartProvider>
        <div className="min-h-screen bg-shop-bg">
          <ShopNav />
          <main className="max-w-6xl mx-auto px-4 py-6">
            <Routes>
              <Route path="/" element={<ProductList />} />
              <Route path="/product/:id" element={<ProductDetail />} />
              <Route path="/cart" element={<Cart />} />
              <Route path="/checkout" element={<Checkout />} />
            </Routes>
          </main>
        </div>
      </CartProvider>
    </HashRouter>
  );
}
