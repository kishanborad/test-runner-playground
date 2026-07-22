import { useState } from 'react';
import { Link } from 'react-router-dom';
import { products } from './data';
import { useCart } from './CartContext';

export default function ProductList() {
  const [search, setSearch] = useState('');
  const { addToCart } = useCart();

  const filtered = products.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div>
      <input
        data-testid="search-input"
        type="text"
        placeholder="Search products..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full mb-6 px-4 py-2 border border-shop-border rounded-lg focus:outline-none focus:ring-2 focus:ring-shop-accent"
      />
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
        {filtered.map((product) => (
          <div
            key={product.id}
            data-testid="product-card"
            className="bg-shop-card rounded-lg border border-shop-border overflow-hidden hover:shadow-md transition-shadow">
            <Link to={`/product/${product.id}`}>
              <div
                className="h-40 flex items-center justify-center text-white text-3xl font-bold"
                style={{ backgroundColor: product.color }}>
                {product.name.charAt(0)}
              </div>
            </Link>
            <div className="p-3">
              <Link to={`/product/${product.id}`}>
                <h3 data-testid="product-name" className="font-medium text-shop-text text-sm">
                  {product.name}
                </h3>
              </Link>
              <p data-testid="product-price" className="text-shop-accent font-bold mt-1">
                ${product.price.toFixed(2)}
              </p>
              <button
                data-testid="add-to-cart"
                onClick={() => addToCart(product)}
                className="mt-2 w-full bg-shop-accent text-white text-sm py-1.5 rounded hover:bg-blue-600 transition-colors">
                Add to Cart
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
