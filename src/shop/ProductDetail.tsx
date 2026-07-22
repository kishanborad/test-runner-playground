import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { products } from './data';
import { useCart } from './CartContext';

export default function ProductDetail() {
  const { id } = useParams<{ id: string }>();
  const { addToCart } = useCart();
  const [quantity, setQuantity] = useState(1);

  const product = products.find((p) => p.id === Number(id));
  if (!product) {
    return <p className="text-shop-muted">Product not found.</p>;
  }

  const handleAdd = () => {
    for (let i = 0; i < quantity; i++) addToCart(product);
  };

  return (
    <div data-testid="product-detail" className="max-w-2xl mx-auto">
      <Link to="/" className="text-shop-accent hover:underline text-sm">&larr; Back to products</Link>
      <div className="mt-4 flex flex-col sm:flex-row gap-6">
        <div
          className="w-full sm:w-64 h-64 rounded-lg flex items-center justify-center text-white text-6xl font-bold shrink-0"
          style={{ backgroundColor: product.color }}>
          {product.name.charAt(0)}
        </div>
        <div>
          <h1 data-testid="product-detail-name" className="text-2xl font-bold text-shop-text">
            {product.name}
          </h1>
          <p data-testid="product-detail-price" className="text-xl text-shop-accent font-bold mt-2">
            ${product.price.toFixed(2)}
          </p>
          <p className="text-shop-muted mt-3">{product.description}</p>
          <p className="text-sm text-shop-muted mt-1">Category: {product.category}</p>
          <div className="flex items-center gap-3 mt-4">
            <label htmlFor="qty" className="text-sm text-shop-muted">Qty:</label>
            <select
              id="qty"
              data-testid="quantity-select"
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              className="border border-shop-border rounded px-2 py-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
          <button
            data-testid="detail-add-to-cart"
            onClick={handleAdd}
            className="mt-4 bg-shop-accent text-white px-6 py-2 rounded hover:bg-blue-600 transition-colors">
            Add to Cart
          </button>
        </div>
      </div>
    </div>
  );
}
