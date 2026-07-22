export interface Product {
  id: number;
  name: string;
  price: number;
  description: string;
  category: string;
  color: string;
}

export const products: Product[] = [
  { id: 1, name: 'Wireless Headphones', price: 79.99, description: 'Premium noise-canceling wireless headphones with 30-hour battery life.', category: 'Audio', color: '#6366f1' },
  { id: 2, name: 'Mechanical Keyboard', price: 129.99, description: 'Cherry MX switches with RGB backlighting and aluminum frame.', category: 'Input', color: '#ec4899' },
  { id: 3, name: 'USB-C Hub', price: 49.99, description: '7-in-1 hub with HDMI, USB-A, SD card reader, and ethernet.', category: 'Accessories', color: '#14b8a6' },
  { id: 4, name: 'Laptop Stand', price: 39.99, description: 'Ergonomic aluminum stand with adjustable height and angle.', category: 'Accessories', color: '#f59e0b' },
  { id: 5, name: 'Webcam HD', price: 69.99, description: '1080p webcam with autofocus, noise-canceling mic, and privacy shutter.', category: 'Video', color: '#8b5cf6' },
  { id: 6, name: 'Mouse Pad XL', price: 24.99, description: 'Extended desk pad with stitched edges and non-slip rubber base.', category: 'Input', color: '#06b6d4' },
  { id: 7, name: 'Monitor Light Bar', price: 54.99, description: 'LED screen light bar with adjustable color temperature.', category: 'Lighting', color: '#84cc16' },
  { id: 8, name: 'Desk Organizer', price: 34.99, description: 'Bamboo desktop organizer with phone stand and pen holder.', category: 'Accessories', color: '#d97706' },
  { id: 9, name: 'Cable Management Kit', price: 19.99, description: 'Silicone cable clips, velcro ties, and under-desk tray.', category: 'Accessories', color: '#64748b' },
  { id: 10, name: 'Portable SSD 1TB', price: 89.99, description: 'USB 3.2 Gen 2 portable SSD with read speeds up to 1050 MB/s.', category: 'Storage', color: '#e11d48' },
];
