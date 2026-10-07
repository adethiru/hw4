// Remembers the Products page query string (?q=&cat=&size=&sort=) so "Back" from a product page
// returns to the same filtered list (Problem 9).
let lastProductsSearch = "";

export const rememberProductsSearch = (search: string) => {
  lastProductsSearch = search;
};

export const productsUrl = () => `/products${lastProductsSearch}`;
