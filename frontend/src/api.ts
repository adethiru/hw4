// Thin client for the FastAPI backend (backend/main.py). Paths are proxied by Vite in dev.

export interface ProductSummary {
  product_id: string;
  name: string;
  garment_type: string;
  category: string;
  price: number;
  short_description: string;
  description: string;
  colors: string[];
  image_url: string;
  in_stock: boolean;
  sizes_in_stock: string[];
}

export interface SizeStock {
  size: string;
  quantity: number;
  in_stock: boolean;
}

export interface ProductDetail {
  product_id: string;
  name: string;
  garment_type: string;
  description: string;
  colors: string[];
  tags: string[];
  price: number;
  image_url: string;
  sizes: SizeStock[];
  total_stock: number;
}

export interface ProductCard {
  product_id: string;
  name: string;
  price: number;
  category: string;
  image_url: string;
}

/** One product in chat-driven page results (mirrors models.ProductMatchCard). */
export interface ProductMatchCard {
  product_id: string;
  name: string;
  category: string;
  price: number;
  image_url: string;
  short_description: string;
  colors: string[];
  sizes_in_stock: string[];
}

/** Structured product matches the Products page renders (mirrors models.PageResults). */
export interface PageResults {
  source: "chat_search";
  heading: string;
  query: string;
  filters: Record<string, string | number>;
  total_matches: number;
  products: ProductMatchCard[];
}

export interface ChatReply {
  reply: string;
  products: ProductCard[];
  page_results: PageResults | null;
  suggestions: string[]; // quick-reply chips (Problem 9)
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface SavedChatMessage extends ChatTurn {
  products: ProductCard[];
  created_at: string;
}

export interface User {
  id: number;
  first_name: string | null;
  last_name: string | null;
  name: string;
  email: string;
}

export interface RegisterInput {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  confirm_password: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "same-origin", // send the HttpOnly session cookie
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let message = res.status === 404 ? "Not found" : `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message);
  }
  return res.json() as Promise<T>;
}

export const getProducts = () => request<ProductSummary[]>("/api/products");
export const getProduct = (id: string) =>
  request<ProductDetail>(`/api/products/${encodeURIComponent(id)}`);
/** What the shopper is looking at (mirrors models.PageContext). */
export interface PageContext {
  path: string;
  product_id: string | null;
  results_heading: string | null;
}

export const sendChat = (message: string, page: PageContext, history: ChatTurn[]) =>
  request<ChatReply>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message, page, history: history.slice(-20) }),
  });
export const getChatHistory = () =>
  request<{ logged_in: boolean; messages: SavedChatMessage[] }>("/api/chat/history");
export const clearChatHistory = () => request<{ deleted: number }>("/api/chat/history", { method: "DELETE" });

export const register = (input: RegisterInput) =>
  request<{ user: User }>("/api/auth/register", { method: "POST", body: JSON.stringify(input) });
export const login = (email: string, password: string) =>
  request<{ user: User }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
export const logout = () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" });
export const getMe = () => request<{ user: User | null }>("/api/auth/me");

export const formatPrice = (p: number) => `$${p.toFixed(2)}`;
