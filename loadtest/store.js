import http from 'k6/http';
import { check, group } from 'k6';

const API = (__ENV.BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');
const PRODUCT_SLUG = __ENV.PRODUCT_SLUG || 'sample-product';
const EMAIL = __ENV.TEST_EMAIL || '';
const PASSWORD = __ENV.TEST_PASSWORD || '';
const ADDRESS_ID = __ENV.ADDRESS_ID || '';

export const options = {
  stages: [
    { duration: '1m', target: 10 },
    { duration: '2m', target: 10 },
    { duration: '1m', target: 25 },
    { duration: '2m', target: 25 },
    { duration: '1m', target: 50 },
    { duration: '2m', target: 50 },
    { duration: '1m', target: 0 },
  ],
};

const params = { headers: { Accept: 'application/json' } };
function expectOk(response, name) {
  check(response, { [`${name}: status < 500`]: (r) => r.status < 500 });
}

export default function () {
  // Approximate request mix by iteration: 70% browsing, 20% product views,
  // 7% login + cart, 3% checkout. Point BASE_URL only at local/staging.
  const roll = Math.random();
  if (roll < 0.70) {
    group('browse', () => {
      expectOk(http.get(`${API.replace('/api/v1', '')}/`), 'home');
      expectOk(http.get(`${API}/products?page_size=12`, params), 'shop');
    });
  } else if (roll < 0.90) {
    group('product', () => expectOk(http.get(`${API}/products/${PRODUCT_SLUG}`, params), 'product'));
  } else if (roll < 0.97) {
    group('login and cart', () => {
      if (!EMAIL || !PASSWORD) return;
      const login = http.post(`${API}/auth/login`, JSON.stringify({ email: EMAIL, password: PASSWORD }), {
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      });
      expectOk(login, 'login');
      if (login.status === 200) expectOk(http.get(`${API}/cart`, params), 'cart');
    });
  } else {
    group('checkout', () => {
      // Use a dedicated disposable local test account and address. Checkout
      // creates orders, so the script must never target production.
      if (!EMAIL || !PASSWORD || !ADDRESS_ID) return;
      const login = http.post(`${API}/auth/login`, JSON.stringify({ email: EMAIL, password: PASSWORD }), {
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      });
      if (login.status !== 200) return;
      const cart = http.get(`${API}/cart`, params);
      if (cart.status !== 200 || !cart.json('items')?.length) return;
      expectOk(http.post(`${API}/checkout`, JSON.stringify({
        address_id: ADDRESS_ID,
        payment_method: 'COD',
        delivery_method: 'STANDARD',
      }), { headers: { 'Content-Type': 'application/json', Accept: 'application/json' } }), 'checkout');
    });
  }
}
