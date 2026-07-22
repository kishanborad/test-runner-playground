import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useCart } from './CartContext';

export default function ShopNav() {
  const { itemCount } = useCart();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="bg-white border-b border-shop-border px-4 py-3 flex items-center justify-between">
      <Link to="/" className="text-lg font-bold text-shop-text">Demo Shop</Link>

      <button
        data-testid="nav-toggle"
        className="sm:hidden p-2 text-shop-muted"
        onClick={() => setMenuOpen(!menuOpen)}
        aria-label="Toggle menu">
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {menuOpen ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          )}
        </svg>
      </button>

      <div
        data-testid="nav-menu"
        className={`${menuOpen ? 'flex' : 'hidden'} sm:flex flex-col sm:flex-row absolute sm:static top-14 left-0 right-0 bg-white sm:bg-transparent border-b sm:border-0 border-shop-border items-center gap-4 p-4 sm:p-0 z-50`}>
        <Link to="/" className="text-shop-muted hover:text-shop-text">Products</Link>
        <Link to="/cart" className="relative text-shop-muted hover:text-shop-text">
          Cart
          {itemCount > 0 && (
            <span
              data-testid="cart-badge"
              className="absolute -top-2 -right-4 bg-shop-accent text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
              {itemCount}
            </span>
          )}
        </Link>
      </div>
    </nav>
  );
}
