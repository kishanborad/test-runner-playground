import { Link } from 'react-router-dom';
import { useCart } from './CartContext';

export default function Cart() {
  const { items, removeFromCart, updateQuantity, total } = useCart();

  if (items.length === 0) {
    return (
      <div data-testid="empty-cart" className="text-center py-12">
        <p className="text-shop-muted text-lg">Your cart is empty.</p>
        <Link to="/" className="text-shop-accent hover:underline mt-2 inline-block">Continue shopping</Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-shop-text mb-6">Shopping Cart</h1>
      <div className="space-y-4">
        {items.map((item) => (
          <div
            key={item.product.id}
            data-testid="cart-item"
            className="flex items-center gap-4 bg-shop-card border border-shop-border rounded-lg p-4">
            <div
              className="w-16 h-16 rounded flex items-center justify-center text-white font-bold text-xl shrink-0"
              style={{ backgroundColor: item.product.color }}>
              {item.product.name.charAt(0)}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-medium text-shop-text truncate">{item.product.name}</h3>
              <p className="text-shop-muted text-sm">${item.product.price.toFixed(2)} each</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                data-testid="quantity-minus"
                onClick={() => updateQuantity(item.product.id, item.quantity - 1)}
                disabled={item.quantity <= 1}
                className="w-8 h-8 rounded border border-shop-border flex items-center justify-center disabled:opacity-30">
                −
              </button>
              <span data-testid="quantity" className="w-8 text-center text-shop-text">
                {item.quantity}
              </span>
              <button
                data-testid="quantity-plus"
                onClick={() => updateQuantity(item.product.id, item.quantity + 1)}
                className="w-8 h-8 rounded border border-shop-border flex items-center justify-center">
                +
              </button>
            </div>
            <p className="font-bold text-shop-text w-20 text-right">
              ${(item.product.price * item.quantity).toFixed(2)}
            </p>
            <button
              data-testid="remove-item"
              onClick={() => removeFromCart(item.product.id)}
              className="text-shop-error hover:text-red-700 text-sm">
              Remove
            </button>
          </div>
        ))}
      </div>
      <div className="mt-6 flex items-center justify-between border-t border-shop-border pt-4">
        <span className="text-lg font-bold text-shop-text">Total:</span>
        <span data-testid="cart-total" className="text-xl font-bold text-shop-accent">
          ${total.toFixed(2)}
        </span>
      </div>
      <Link
        to="/checkout"
        data-testid="checkout-btn"
        className="mt-4 block text-center bg-shop-accent text-white py-3 rounded-lg hover:bg-blue-600 transition-colors font-medium">
        Proceed to Checkout
      </Link>
    </div>
  );
}
