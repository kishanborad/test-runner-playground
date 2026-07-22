import { useState, type FormEvent } from 'react';
import { useCart } from './CartContext';

interface FormData {
  name: string;
  email: string;
  address: string;
  city: string;
  zip: string;
}

const emptyForm: FormData = { name: '', email: '', address: '', city: '', zip: '' };

export default function Checkout() {
  const { items, total, clearCart } = useCart();
  const [form, setForm] = useState<FormData>(emptyForm);
  const [errors, setErrors] = useState<Partial<FormData>>({});
  const [submitted, setSubmitted] = useState(false);

  const validate = (): Partial<FormData> => {
    const errs: Partial<FormData> = {};
    if (!form.name.trim()) errs.name = 'Name is required';
    if (!form.email.trim()) errs.email = 'Email is required';
    if (!form.address.trim()) errs.address = 'Address is required';
    if (!form.city.trim()) errs.city = 'City is required';
    if (!form.zip.trim()) errs.zip = 'Zip code is required';
    return errs;
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;
    clearCart();
    setSubmitted(true);
  };

  const handleChange = (field: keyof FormData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  if (submitted) {
    return (
      <div data-testid="order-confirmation" className="max-w-md mx-auto text-center py-12">
        <div className="text-5xl mb-4">&#10003;</div>
        <h1 className="text-2xl font-bold text-shop-text">Order Confirmed!</h1>
        <p className="text-shop-muted mt-2">Thank you for your purchase, {form.name}.</p>
      </div>
    );
  }

  if (items.length === 0) {
    return <p className="text-shop-muted text-center py-12">Your cart is empty.</p>;
  }

  const fields: { key: keyof FormData; label: string; type: string }[] = [
    { key: 'name', label: 'Full Name', type: 'text' },
    { key: 'email', label: 'Email', type: 'email' },
    { key: 'address', label: 'Address', type: 'text' },
    { key: 'city', label: 'City', type: 'text' },
    { key: 'zip', label: 'Zip Code', type: 'text' },
  ];

  return (
    <div className="max-w-md mx-auto">
      <h1 className="text-2xl font-bold text-shop-text mb-6">Checkout</h1>
      <form data-testid="checkout-form" onSubmit={handleSubmit} noValidate className="space-y-4">
        {fields.map(({ key, label, type }) => (
          <div key={key}>
            <label htmlFor={key} className="block text-sm font-medium text-shop-text mb-1">
              {label}
            </label>
            <input
              id={key}
              data-testid={`field-${key}`}
              type={type}
              value={form[key]}
              onChange={(e) => handleChange(key, e.target.value)}
              className={`w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-shop-accent ${
                errors[key] ? 'border-shop-error' : 'border-shop-border'
              }`}
            />
            {errors[key] && (
              <p data-testid="error-message" className="text-shop-error text-sm mt-1">
                {errors[key]}
              </p>
            )}
          </div>
        ))}
        <div className="border-t border-shop-border pt-4 mt-6">
          <p className="text-lg font-bold text-shop-text">Total: ${total.toFixed(2)}</p>
        </div>
        <button
          type="submit"
          data-testid="submit-order"
          className="w-full bg-shop-accent text-white py-3 rounded-lg hover:bg-blue-600 transition-colors font-medium">
          Place Order
        </button>
      </form>
    </div>
  );
}
