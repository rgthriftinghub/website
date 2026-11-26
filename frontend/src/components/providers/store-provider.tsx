"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import * as commerce from "@/lib/api/commerce";
import { getCurrentUser, logout } from "@/lib/api/catalog";
import { ApiClientError } from "@/lib/api/client";
import type { Cart, User } from "@/lib/api/types";

/**
 * Shared session, bag, and wishlist state.
 *
 * These all depend on the HTTP-only session cookie, which only the browser can
 * send, so they are loaded client-side once and shared through context instead
 * of being refetched by every component that needs a count.
 */
interface StoreState {
  user: User | null;
  isAuthenticated: boolean;
  /** True until the first session check resolves, so UI can avoid flashing. */
  isLoading: boolean;
  cart: Cart | null;
  cartCount: number;
  wishlistIds: Set<string>;
  wishlistCount: number;
  refreshSession: () => Promise<void>;
  refreshCart: () => Promise<void>;
  addToCart: (variantId: string, quantity?: number) => Promise<void>;
  updateCartItem: (itemId: string, quantity: number) => Promise<void>;
  removeCartItem: (itemId: string) => Promise<void>;
  toggleWishlist: (productId: string) => Promise<boolean>;
  isWishlisted: (productId: string) => boolean;
  signOut: () => Promise<void>;
}

const StoreContext = createContext<StoreState | null>(null);
const GUEST_WISHLIST_KEY = "rgthriftinghub-guest-wishlist";

function guestWishlistIds(): Set<string> {
  try {
    const value = localStorage.getItem(GUEST_WISHLIST_KEY);
    const parsed: unknown = value ? JSON.parse(value) : [];
    return new Set(Array.isArray(parsed) ? parsed.filter((id): id is string => typeof id === "string").slice(0, 50) : []);
  } catch {
    return new Set();
  }
}

export function useStore(): StoreState {
  const context = useContext(StoreContext);
  if (context === null) {
    throw new Error("useStore must be used inside StoreProvider");
  }
  return context;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [cart, setCart] = useState<Cart | null>(null);
  const [wishlistIds, setWishlistIds] = useState<Set<string>>(new Set());

  const loadCustomerData = useCallback(async () => {
    const [cartResult, wishlistResult] = await Promise.allSettled([
      commerce.getCart(),
      commerce.getWishlistIds(),
    ]);
    setCart(cartResult.status === "fulfilled" ? cartResult.value : null);
    setWishlistIds(
      wishlistResult.status === "fulfilled" ? new Set(wishlistResult.value) : new Set()
    );
  }, []);

  const refreshSession = useCallback(async () => {
    try {
      const signedIn = await getCurrentUser();
      setUser(signedIn);
      const guests = guestWishlistIds();
      const failed = (await Promise.all([...guests].map(async (id) =>
        (await commerce.addToWishlist(id).then(() => false).catch(() => true)) ? id : null
      ))).filter((id): id is string => id !== null);
      if (failed.length) localStorage.setItem(GUEST_WISHLIST_KEY, JSON.stringify(failed));
      else localStorage.removeItem(GUEST_WISHLIST_KEY);
      await loadCustomerData();
    } catch {
      // Keep anonymous wishlist selections in browser storage.
      setUser(null);
      setCart(null);
      setWishlistIds(guestWishlistIds());
    } finally {
      setIsLoading(false);
    }
  }, [loadCustomerData]);

  // The initial load runs as a guarded promise chain rather than calling the
  // async `refreshSession` directly, so no state is set after unmount and the
  // effect never appears to set state synchronously.
  useEffect(() => {
    let cancelled = false;
    getCurrentUser()
      .then(async (signedIn) => {
        if (cancelled) return;
        setUser(signedIn);
        const guests = guestWishlistIds();
        const failed = (await Promise.all([...guests].map(async (id) =>
          (await commerce.addToWishlist(id).then(() => false).catch(() => true)) ? id : null
        ))).filter((id): id is string => id !== null);
        if (failed.length) localStorage.setItem(GUEST_WISHLIST_KEY, JSON.stringify(failed));
        else localStorage.removeItem(GUEST_WISHLIST_KEY);
        await loadCustomerData();
      })
      .catch(() => {
        if (cancelled) return;
        setUser(null);
        setCart(null);
        setWishlistIds(guestWishlistIds());
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadCustomerData]);

  const refreshCart = useCallback(async () => {
    try {
      setCart(await commerce.getCart());
    } catch {
      setCart(null);
    }
  }, []);

  // Cart mutations return the whole updated cart, so state stays in step with
  // the backend without a follow-up request.
  const addToCart = useCallback(async (variantId: string, quantity = 1) => {
    setCart(await commerce.addToCart(variantId, quantity));
  }, []);

  const updateCartItem = useCallback(async (itemId: string, quantity: number) => {
    setCart(await commerce.updateCartItem(itemId, quantity));
  }, []);

  const removeCartItem = useCallback(async (itemId: string) => {
    setCart(await commerce.removeCartItem(itemId));
  }, []);

  const toggleWishlist = useCallback(
    async (productId: string): Promise<boolean> => {
      const saved = wishlistIds.has(productId);
      if (!user) {
        const next = new Set(wishlistIds);
        if (saved) next.delete(productId);
        else if (next.size < 50) next.add(productId);
        localStorage.setItem(GUEST_WISHLIST_KEY, JSON.stringify([...next]));
        setWishlistIds(next);
        return !saved;
      }
      if (saved) {
        await commerce.removeFromWishlist(productId);
      } else {
        await commerce.addToWishlist(productId);
      }
      setWishlistIds((current) => {
        const next = new Set(current);
        if (saved) next.delete(productId);
        else next.add(productId);
        return next;
      });
      return !saved;
    },
    [user, wishlistIds]
  );

  const isWishlisted = useCallback(
    (productId: string) => wishlistIds.has(productId),
    [wishlistIds]
  );

  const signOut = useCallback(async () => {
    // Clear local state regardless of the response: the cookie is gone either
    // way, so the UI must not keep showing a signed-in bag.
    await logout().catch(() => undefined);
    localStorage.setItem(GUEST_WISHLIST_KEY, JSON.stringify([...wishlistIds].slice(0, 50)));
    setUser(null);
    setCart(null);
    setWishlistIds(new Set(wishlistIds));
  }, [wishlistIds]);

  const value = useMemo<StoreState>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isLoading,
      cart,
      cartCount: cart?.item_count ?? 0,
      wishlistIds,
      wishlistCount: wishlistIds.size,
      refreshSession,
      refreshCart,
      addToCart,
      updateCartItem,
      removeCartItem,
      toggleWishlist,
      isWishlisted,
      signOut,
    }),
    [
      user,
      isLoading,
      cart,
      wishlistIds,
      refreshSession,
      refreshCart,
      addToCart,
      updateCartItem,
      removeCartItem,
      toggleWishlist,
      isWishlisted,
      signOut,
    ]
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

/** Human-readable message from an API failure, for inline form errors. */
export function errorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (error instanceof ApiClientError) return error.message;
  return fallback;
}
