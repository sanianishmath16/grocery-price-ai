/**
 * app.js — GroceryAI v3
 *
 * Professional grocery marketplace SPA
 * Features:
 *   - Home → Category → Brand → Product Comparison
 *   - Large catalog: 80+ products, multiple brands per category
 *   - Global search with autocomplete (brand, category, variant-aware)
 *   - Platform comparison with size variants + cheapest calculation
 *   - Filter by brand, sort by price/discount
 *   - Brand discovery page
 *   - Pincode-based availability
 *   - MRP / discount display with normalized price (₹/kg, ₹/L)
 *   - "Search on Platform" links (real URLs, clearly labelled)
 *   - My List / basket comparison
 *   - Price alerts (localStorage)
 *   - No Price History / No Quality Comparison / No Image Upload
 *
 * Data note: All platform prices are representative demo data (reference date 2025-07-15).
 * Buy Now buttons open the platform's legitimate search page for the product.
 */

"use strict";

// ─────────────────────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────────────────────
const API_BASE = window.__GROCERYAI_API || "";

const PLATFORM_META = {
  zepto:     { name: "Zepto",            emoji: "⚡", css: "zepto",     logoText: "Z" },
  blinkit:   { name: "Blinkit",          emoji: "💛", css: "blinkit",   logoText: "B" },
  instamart: { name: "Swiggy Instamart", emoji: "🟠", css: "instamart", logoText: "I" },
  flipkart:  { name: "Flipkart Minutes", emoji: "🔵", css: "flipkart",  logoText: "F" },
};

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────
const state = {
  pincode: localStorage.getItem("groceryai_pincode") || "",
  categories: [],
  products: [],
  brands: [],
  currentProduct: null,
  currentCategory: null,
  currentBrand: null,
  myList: JSON.parse(localStorage.getItem("groceryai_list") || "[]"),
  priceAlerts: JSON.parse(localStorage.getItem("groceryai_alerts") || "[]"),
  previousView: "home",
};

// ─────────────────────────────────────────────────────────────────────────────
// DOM helpers
// ─────────────────────────────────────────────────────────────────────────────
const $  = (id) => document.getElementById(id);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
};
function show(id)  { const e = $(id); if (e) e.classList.remove("hidden"); }
function hide(id)  { const e = $(id); if (e) e.classList.add("hidden"); }

// ─────────────────────────────────────────────────────────────────────────────
// View switching
// ─────────────────────────────────────────────────────────────────────────────
const VIEWS = ["view-home", "view-category", "view-search", "view-product", "view-mylist", "view-brands"];

function switchView(viewId) {
  VIEWS.forEach(v => {
    const e = $(v);
    if (e) e.classList.toggle("hidden", v !== viewId);
  });
  document.querySelectorAll(".bnav-btn").forEach(b => b.classList.remove("active"));
  const map = { "view-home": "bnav-home", "view-mylist": "bnav-list" };
  if (map[viewId]) $(map[viewId])?.classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showHome() { switchView("view-home"); hideSearchSuggestions(); }

function showCategoryView(catId) {
  state.currentCategory = catId;
  state.previousView = "home";
  const cat = state.categories.find(c => c.id === catId);
  if (cat) {
    $("cat-emoji").textContent = cat.emoji;
    $("cat-name").textContent = cat.name;
  }
  switchView("view-category");
  loadCategoryProducts(catId);
}

function showSearchView(query) {
  $("search-query-label").textContent = query;
  switchView("view-search");
  loadSearchResults(query);
}

function showProductView(productId, fromView) {
  state.previousView = fromView || "home";
  $("product-back-btn").onclick = () => {
    if (state.previousView === "category") showCategoryView(state.currentCategory);
    else if (state.previousView === "search") switchView("view-search");
    else if (state.previousView === "brands") showBrandsView();
    else if (state.previousView === "mylist") showMyList();
    else showHome();
  };
  switchView("view-product");
  loadProductComparison(productId);
}

function showMyList() { switchView("view-mylist"); renderMyList(); }

function showBrandsView() {
  switchView("view-brands");
  renderBrandsPage();
}

function showBrandProducts(brandName) {
  state.currentBrand = brandName;
  state.previousView = "brands";
  $("brand-products-title").textContent = brandName;
  $("brand-products-subtitle").textContent = "";
  switchView("view-category");
  // Reuse category view but load brand products
  $("cat-emoji").textContent = "🏷️";
  $("cat-name").textContent = brandName;
  loadBrandProducts(brandName);
}

// ─────────────────────────────────────────────────────────────────────────────
// Pincode
// ─────────────────────────────────────────────────────────────────────────────
function promptPincode() {
  $("modal-pincode").value = state.pincode;
  show("pincode-modal");
  setTimeout(() => $("modal-pincode").focus(), 100);
}
function closePincodeModal() { hide("pincode-modal"); }
function quickPin(pin) { $("modal-pincode").value = pin; applyPincode(); }

function applyPincode() {
  const val = $("modal-pincode").value.trim();
  if (!/^\d{6}$/.test(val)) { show("modal-pincode-error"); return; }
  hide("modal-pincode-error");
  state.pincode = val;
  localStorage.setItem("groceryai_pincode", val);
  closePincodeModal();
  updateLocationUI();
  if (!$("view-product").classList.contains("hidden") && state.currentProduct) {
    loadProductComparison(state.currentProduct.id);
  }
}

function updateLocationUI() {
  const pin = state.pincode;
  $("nav-location-text").textContent = pin ? `📍 ${pin}` : "Set Location";
}

$("pincode-modal").addEventListener("click", (e) => {
  if (e.target === $("pincode-modal")) closePincodeModal();
});
$("modal-pincode").addEventListener("keydown", (e) => {
  if (e.key === "Enter") applyPincode();
  if (e.key === "Escape") closePincodeModal();
});

// ─────────────────────────────────────────────────────────────────────────────
// API helpers
// ─────────────────────────────────────────────────────────────────────────────
async function apiFetch(path) {
  const r = await fetch(API_BASE + path);
  if (!r.ok) throw new Error(`API error ${r.status}: ${path}`);
  return r.json();
}

// ─────────────────────────────────────────────────────────────────────────────
// Init
// ─────────────────────────────────────────────────────────────────────────────
async function init() {
  updateLocationUI();
  updateCartCount();

  try {
    const [catData, prodData, brandData] = await Promise.all([
      apiFetch("/api/categories"),
      apiFetch("/api/products?limit=200"),
      apiFetch("/api/brands"),
    ]);
    state.categories = catData.categories || [];
    state.products   = prodData.products  || [];
    state.brands     = brandData.brands   || [];

    renderCategories();
    renderFeaturedProducts();
    renderBrandStrip();
    setupSearchAutocomplete();
  } catch (err) {
    console.error("Init failed:", err);
    renderCategoriesFallback();
    renderProductsFallback();
  }

  if (!state.pincode) {
    setTimeout(promptPincode, 1200);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Render Categories
// ─────────────────────────────────────────────────────────────────────────────
// Category background colors for visual distinction
const CAT_COLORS = {
  fruits_vegetables: { bg: "#f0fdf4", border: "#86efac", accent: "#16a34a" },
  dairy:             { bg: "#eff6ff", border: "#93c5fd", accent: "#2563eb" },
  staples:           { bg: "#fffbeb", border: "#fcd34d", accent: "#d97706" },
  dal_pulses:        { bg: "#fef3c7", border: "#fbbf24", accent: "#92400e" },
  oil_masala:        { bg: "#fef2f2", border: "#fca5a5", accent: "#dc2626" },
  snacks:            { bg: "#f5f3ff", border: "#c4b5fd", accent: "#7c3aed" },
  beverages:         { bg: "#ecfeff", border: "#67e8f9", accent: "#0891b2" },
  personal_care:     { bg: "#fdf2f8", border: "#f0abfc", accent: "#db2777" },
  household:         { bg: "#f0fdf4", border: "#6ee7b7", accent: "#059669" },
  baby_care:         { bg: "#fffbeb", border: "#fde68a", accent: "#f59e0b" },
  meat:              { bg: "#fff7ed", border: "#fdba74", accent: "#b45309" },
  bakery:            { bg: "#fef9c3", border: "#fde047", accent: "#a16207" },
  frozen:            { bg: "#eff6ff", border: "#bfdbfe", accent: "#1d4ed8" },
};

function renderCategories() {
  const container = $("categories-scroll");
  if (!container) return;
  container.innerHTML = "";
  state.categories.forEach(cat => {
    const colors = CAT_COLORS[cat.id] || { bg: "#f9fafb", border: "#e5e7eb", accent: "#374151" };
    const card = el("button", "category-card");
    card.setAttribute("type", "button");
    card.setAttribute("role", "listitem");
    card.setAttribute("aria-label", cat.name);
    card.style.cssText = `background:${colors.bg};border-color:${colors.border};`;
    card.innerHTML = `
      <span class="cat-emoji" aria-hidden="true" style="font-size:26px">${cat.emoji}</span>
      <span class="cat-name" style="color:${colors.accent}">${cat.name}</span>
    `;
    card.addEventListener("click", () => showCategoryView(cat.id));
    container.appendChild(card);
  });
}

function renderCategoriesFallback() {
  const CATS = [
    { id: "fruits_vegetables", name: "Fruits & Veg", emoji: "🥬" },
    { id: "dairy",             name: "Dairy",        emoji: "🥛" },
    { id: "staples",           name: "Staples",      emoji: "🌾" },
    { id: "snacks",            name: "Snacks",       emoji: "🍪" },
    { id: "beverages",         name: "Beverages",    emoji: "🥤" },
    { id: "personal_care",     name: "Personal",     emoji: "🧴" },
  ];
  state.categories = CATS;
  renderCategories();
}

// ─────────────────────────────────────────────────────────────────────────────
// Render Brand Strip
// ─────────────────────────────────────────────────────────────────────────────
function renderBrandStrip() {
  const container = $("brands-strip");
  if (!container) return;
  container.innerHTML = "";
  const topBrands = state.brands.slice(0, 18);
  topBrands.forEach(brand => {
    const chip = el("button", "brand-chip");
    chip.type = "button";
    chip.innerHTML = `${brand.name}<span class="brand-count">(${brand.count})</span>`;
    chip.addEventListener("click", () => showSearchView(brand.name));
    container.appendChild(chip);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Render Product Grid
// ─────────────────────────────────────────────────────────────────────────────
function renderProductGrid(products, containerId, fromView, sortBy) {
  const container = $(containerId);
  if (!container) return;
  container.innerHTML = "";

  if (products === null) {
    for (let i = 0; i < 8; i++) container.appendChild(el("div", "skel-product"));
    return;
  }

  // Apply sorting
  let sorted = [...products];
  if (sortBy === "price_asc") sorted.sort((a, b) => (a.base_price_inr || 0) - (b.base_price_inr || 0));
  else if (sortBy === "price_desc") sorted.sort((a, b) => (b.base_price_inr || 0) - (a.base_price_inr || 0));
  else if (sortBy === "rating") sorted.sort((a, b) => (b.rating || 0) - (a.rating || 0));

  if (!sorted.length) {
    if (containerId === "search-products") show("search-empty");
    return;
  }
  if (containerId === "search-products") hide("search-empty");

  sorted.forEach(product => {
    container.appendChild(buildProductCard(product, fromView));
  });
}

function buildProductCard(product, fromView) {
  const inList = state.myList.some(i => i.id === product.id);
  const card = el("article", "product-card", "");
  card.setAttribute("role", "listitem");
  card.setAttribute("aria-label", product.name);

  // Image — prefer real product photo, fall back gracefully (no cartoon emoji in main slot)
  let imgHtml;
  if (product.image_url) {
    imgHtml = `
      <img src="${product.image_url}" alt="${product.name}" class="product-card-img" loading="lazy"
        onerror="this.style.display='none';this.nextElementSibling.style.display='flex'" />
      <div class="product-img-placeholder" style="display:none">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/>
          <path d="M21 15l-5-5L5 21"/>
        </svg>
        <span>No Image Available</span>
      </div>`;
  } else {
    imgHtml = `
      <div class="product-img-placeholder">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8.5" cy="8.5" r="1.5"/>
          <path d="M21 15l-5-5L5 21"/>
        </svg>
        <span>No Image Available</span>
      </div>`;
  }

  // Price / MRP / discount
  const price = product.base_price_inr;
  const mrp   = product.mrp_inr || null;
  const discPct = (mrp && mrp > price) ? Math.round((1 - price / mrp) * 100) : 0;

  const priceHtml = `₹${price}`;
  const mrpHtml   = (mrp && discPct > 0) ? `<span class="product-card-mrp">₹${mrp}</span>` : "";
  const discHtml  = discPct > 0 ? `<span class="product-card-discount">${discPct}% off</span>` : "";
  const discBadge = discPct > 0 ? `<span class="product-discount-badge">${discPct}% OFF</span>` : "";

  // Quantity — first available size
  const qty = product.available_sizes?.[0] || "";

  // Delivery time chip — Blinkit-style "11 MINS" chip
  const deliveryChip = `
    <div class="product-card-delivery">
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" width="11" height="11" aria-hidden="true">
        <circle cx="8" cy="8" r="6.5"/>
        <path d="M8 4.5V8.5l2.5 1.5" stroke-linecap="round"/>
      </svg>
      <span>10-20 mins</span>
    </div>`;

  // Rating
  const ratingHtml = product.rating
    ? `<span class="product-card-rating">★ ${product.rating}</span>` : "";

  card.innerHTML = `
    ${inList ? '<span class="in-list-badge">✓ In List</span>' : ""}
    ${discBadge}
    <div class="product-img-wrap" aria-hidden="true">${imgHtml}</div>
    <div class="product-card-body">
      ${deliveryChip}
      ${product.brand ? `<p class="product-card-brand">${product.brand}</p>` : ""}
      <p class="product-card-name">${product.name}</p>
      ${qty ? `<span class="product-card-qty">${qty}</span>` : ""}
      <div class="product-card-price-row">
        <span class="product-card-price">${priceHtml}</span>
        ${mrpHtml}${discHtml}
        ${ratingHtml}
      </div>
      <div class="product-card-footer">
        <button type="button" class="compare-btn" aria-label="Compare prices for ${product.name}">
          Compare Prices
        </button>
      </div>
    </div>
  `;

  card.addEventListener("click", () => showProductView(product.id, fromView || "home"));
  return card;
}

function renderFeaturedProducts() {
  const featured = state.products.slice(0, 16);
  renderProductGrid(featured, "featured-products", "home");
}

function renderProductsFallback() {
  renderProductGrid([], "featured-products", "home");
}

// ─────────────────────────────────────────────────────────────────────────────
// Category Products
// ─────────────────────────────────────────────────────────────────────────────
async function loadCategoryProducts(catId) {
  renderProductGrid(null, "category-products", "category");
  try {
    const data = await apiFetch(`/api/products?category=${catId}&limit=100`);
    state._catProducts = data.products || [];
    renderProductGrid(state._catProducts, "category-products", "category");
  } catch (err) {
    const products = state.products.filter(p => p.category === catId);
    state._catProducts = products;
    renderProductGrid(products, "category-products", "category");
  }
}

async function loadBrandProducts(brandName) {
  renderProductGrid(null, "category-products", "category");
  try {
    const data = await apiFetch(`/api/products?brand=${encodeURIComponent(brandName)}&limit=100`);
    const products = data.products || [];
    renderProductGrid(products, "category-products", "brand");
    if (products.length === 0) {
      const container = $("category-products");
      container.innerHTML = `
        <div class="empty-state" style="grid-column:1/-1">
          <div class="empty-icon">🏷️</div>
          <p class="empty-title">No products for ${brandName}</p>
          <p class="empty-sub">Try searching or browse other brands.</p>
        </div>`;
    }
  } catch (err) {
    const products = state.products.filter(p =>
      (p.brand || "").toLowerCase().includes(brandName.toLowerCase())
    );
    renderProductGrid(products, "category-products", "brand");
  }
}

// Category filter / sort
function applyCategorySort(sortVal) {
  const products = state._catProducts || [];
  renderProductGrid(products, "category-products", "category", sortVal);
}

// ─────────────────────────────────────────────────────────────────────────────
// Search
// ─────────────────────────────────────────────────────────────────────────────
async function loadSearchResults(query) {
  hide("search-empty");
  renderProductGrid(null, "search-products", "search");

  try {
    const data = await apiFetch(`/api/products?q=${encodeURIComponent(query)}&limit=100`);
    const products = data.products || [];
    state._searchProducts = products;
    renderProductGrid(products, "search-products", "search");
    // Update search result count
    const countEl = $("search-result-count");
    if (countEl) countEl.textContent = `${products.length} products found`;
  } catch (err) {
    const q = query.toLowerCase();
    const products = state.products.filter(p =>
      p.name.toLowerCase().includes(q) ||
      p.id.includes(q) ||
      (p.tags || []).some(t => t.toLowerCase().includes(q)) ||
      (p.brand || "").toLowerCase().includes(q)
    );
    state._searchProducts = products;
    renderProductGrid(products, "search-products", "search");
  }
}

function setupSearchAutocomplete() {
  const inputs = [$("global-search"), $("hero-search")];
  inputs.forEach(input => {
    if (!input) return;
    let debounceTimer;
    input.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      const val = input.value.trim();
      if (input.id === "global-search") {
        val.length > 0 ? show("search-clear-btn") : hide("search-clear-btn");
      }
      if (val.length < 2) { hideSearchSuggestions(); return; }
      debounceTimer = setTimeout(() => showSearchSuggestions(val, input), 200);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const val = input.value.trim();
        if (val.length > 0) { hideSearchSuggestions(); showSearchView(val); }
      }
      if (e.key === "Escape") hideSearchSuggestions();
    });
  });

  $("search-clear-btn")?.addEventListener("click", () => {
    $("global-search").value = "";
    hide("search-clear-btn");
    hideSearchSuggestions();
    $("global-search").focus();
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".nav-search-wrap") && !e.target.closest(".hero-search-box")) {
      hideSearchSuggestions();
    }
  });
}

function showSearchSuggestions(query, inputEl) {
  const q = query.toLowerCase();
  const matches = state.products.filter(p =>
    p.name.toLowerCase().includes(q) ||
    (p.brand || "").toLowerCase().includes(q) ||
    (p.tags || []).some(t => t.toLowerCase().includes(q)) ||
    (p.subcategory || "").toLowerCase().includes(q)
  ).slice(0, 7);

  const container = $("search-suggestions");
  if (!container || !matches.length) { hideSearchSuggestions(); return; }

  container.innerHTML = "";
  matches.forEach(p => {
    const item = el("div", "suggestion-item", "");
    item.setAttribute("role", "option");
    item.setAttribute("tabindex", "0");
    const highlighted = p.name.replace(new RegExp(`(${escapeRe(query)})`, "gi"), "<strong>$1</strong>");
    const catLabel = (p.category || "").replace(/_/g, " ");
    const sizePills = (p.available_sizes || []).slice(0, 3)
      .map(s => `<span class="sugg-size-pill">${s}</span>`).join("");
    item.innerHTML = `
      <span class="suggestion-emoji" aria-hidden="true">${p.emoji || "🛒"}</span>
      <span class="suggestion-text-wrap">
        <span class="suggestion-text">${highlighted}</span>
        ${p.brand ? `<span style="font-size:11px;color:var(--muted)">${p.brand}</span>` : ""}
        ${sizePills ? `<span class="suggestion-sizes">${sizePills}</span>` : ""}
      </span>
      <span class="suggestion-cat">${catLabel}</span>
    `;
    item.addEventListener("click", () => { hideSearchSuggestions(); showProductView(p.id, "search"); });
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { hideSearchSuggestions(); showProductView(p.id, "search"); }
    });
    container.appendChild(item);
  });
  show("search-suggestions");
}

function hideSearchSuggestions() { hide("search-suggestions"); }

function focusNavSearch() { $("global-search")?.focus(); $("bnav-search")?.classList.add("active"); }

function focusHeroSearch() {
  const heroSearch = $("hero-search");
  const val = heroSearch?.value?.trim();
  if (val) showSearchView(val);
  else heroSearch?.focus();
}

function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

// ─────────────────────────────────────────────────────────────────────────────
// Brands Page
// ─────────────────────────────────────────────────────────────────────────────
function renderBrandsPage() {
  const container = $("brands-grid");
  if (!container) return;
  container.innerHTML = "";
  const brands = state.brands.length > 0 ? state.brands : extractBrandsFromProducts();
  brands.forEach(brand => {
    const chip = el("button", "brand-chip", "");
    chip.type = "button";
    chip.style.cssText = "min-width:120px; justify-content:space-between; padding: 12px 16px;";
    chip.innerHTML = `
      <span>${brand.name}</span>
      <span class="brand-count" style="font-size:11px;color:var(--muted)">${brand.count} products</span>
    `;
    chip.addEventListener("click", () => showBrandProducts(brand.name));
    container.appendChild(chip);
  });
}

function extractBrandsFromProducts() {
  const map = {};
  state.products.forEach(p => {
    const b = p.brand;
    if (!b) return;
    map[b] = (map[b] || 0) + 1;
  });
  return Object.entries(map)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({ name, count }));
}

// ─────────────────────────────────────────────────────────────────────────────
// Product Comparison Page
// ─────────────────────────────────────────────────────────────────────────────
async function loadProductComparison(productId) {
  state.currentProduct = { id: productId };

  $("platform-cards").innerHTML = `
    <div class="compare-loading">
      <div class="spinner"></div>
      <span>Comparing prices across platforms…</span>
    </div>
  `;
  hide("best-price-banner");

  const pincode = state.pincode || "560001";

  try {
    const [productData, compareData] = await Promise.all([
      apiFetch(`/api/product/${productId}`),
      apiFetch(`/api/product/${productId}/compare?pincode=${pincode}`),
    ]);

    const product = productData.product;
    state.currentProduct = product;
    state.currentCompareData = compareData;

    // Update product header
    const heroImgEl = $("product-hero-img");
    const heroEmojiEl = $("product-hero-emoji");
    if (product.image_url && heroImgEl) {
      heroImgEl.src = product.image_url;
      heroImgEl.alt = product.name;
      heroImgEl.classList.remove("hidden");
      heroEmojiEl.classList.add("hidden");
    } else {
      if (heroImgEl) heroImgEl.classList.add("hidden");
      heroEmojiEl.classList.remove("hidden");
      heroEmojiEl.textContent = product.emoji || "🛒";
    }
    $("product-hero-name").textContent = product.name;
    const brandPart = product.brand ? ` · ${product.brand}` : "";
    $("product-hero-meta").textContent = `${(product.category || "").replace(/_/g, " ")}${brandPart}`;
    $("product-pincode-display").textContent = pincode;

    renderSizeSelector(product, compareData);
    renderPlatformCards(compareData, product);
    renderProductDetails(product);
    renderAvailability(compareData);
    renderDataNote(compareData);

    const cheapest = getCheapestVariant(compareData);
    if (cheapest) {
      $("alert-price-input").placeholder = Math.floor(cheapest.price * 0.9);
    }

  } catch (err) {
    console.error("Product compare failed:", err);
    $("platform-cards").innerHTML = `
      <div class="empty-state" style="grid-column:1/-1">
        <div class="empty-icon">⚠️</div>
        <p class="empty-title">Could not load comparison</p>
        <p class="empty-sub">Please check your connection or try again.</p>
      </div>
    `;
  }
}

function getCheapestVariant(compareData) {
  const platforms = compareData.platforms || [];
  const bests = platforms.map(p => p.best_variant).filter(Boolean);
  if (!bests.length) return null;
  return bests.reduce((a, b) => (a.normalized_price || 9999) < (b.normalized_price || 9999) ? a : b);
}

// Per-card selected variant index
const _cardSelectedVariant = {};

function _renderVariantPrice(v, isCheapest, pid, meta, areaAvail) {
  if (!areaAvail) {
    return {
      priceHtml: `<span class="platform-price-big text-muted">—</span><span class="platform-price-norm text-muted">Not available in your area</span>`,
      buyBtnHtml: `<span class="buy-btn buy-btn-unavail">Not available in your area</span>`,
      stockHtml: `<span class="out-of-stock">❌ Not available in your area</span>`,
      qty: "—", brand: "—",
    };
  }
  if (!v) {
    return {
      priceHtml: `<span class="platform-price-big text-muted">—</span><span class="platform-price-norm text-muted">Not listed on this platform</span>`,
      buyBtnHtml: `<span class="buy-btn buy-btn-unavail">Not listed</span>`,
      stockHtml: `<span class="out-of-stock">❌ Not listed</span>`,
      qty: "—", brand: "—",
    };
  }

  const mrpHtml = v.mrp && v.mrp > v.price
    ? `<span class="platform-price-mrp">₹${v.mrp}</span>` : "";
  const discountHtml = v.mrp && v.mrp > v.price
    ? `<span class="platform-discount-tag">${Math.round((1 - v.price / v.mrp) * 100)}% off</span>` : "";

  const normLabel = v.normalized_price && v.normalized_unit
    ? `₹${v.normalized_price.toFixed(0)}/${v.normalized_unit}` : "";

  const priceHtml = `
    <span class="platform-price-big">₹${v.price}</span>${mrpHtml}${discountHtml}
    ${normLabel ? `<span class="platform-price-norm">${normLabel}</span>` : ""}
  `;

  const inStock = v.effective_available;
  const stockHtml = inStock
    ? `<span class="in-stock">✓ In Stock</span>`
    : `<span class="out-of-stock">❌ Out of Stock</span>`;

  const cheapestRibbon = isCheapest && inStock
    ? `<span class="cheapest-ribbon">CHEAPEST</span>` : "";

  const btnClass = `buy-btn buy-btn-${pid}`;
  // Search URLs open the platform's search for the product — labelled clearly
  const btnLabel = `Search on ${meta.name} ↗`;
  const buyBtnHtml = v.product_url
    ? `<a href="${v.product_url}" target="_blank" rel="noopener noreferrer" class="${btnClass}" title="Opens ${meta.name} — search page for this product">${btnLabel}</a>`
    : `<span class="buy-btn buy-btn-unavail">Not available</span>`;

  return {
    priceHtml, buyBtnHtml, stockHtml,
    qty: v.display_quantity || `${v.quantity}${v.unit}`,
    brand: v.brand || "—",
    cheapestRibbon,
  };
}

function renderPlatformCards(compareData, product) {
  const container = $("platform-cards");
  const cheapestId = compareData.cheapest_platform_id;

  // Update best price banner
  const cheapestPlatform = compareData.platforms?.find(p => p.platform?.id === cheapestId);
  if (cheapestPlatform?.best_variant) {
    const bv = cheapestPlatform.best_variant;
    const meta = PLATFORM_META[cheapestId] || {};
    $("best-platform-name").textContent = meta.name || cheapestId;
    $("best-price-val").textContent = `₹${bv.price}`;
    $("best-price-norm").textContent = bv.normalized_price
      ? `₹${bv.normalized_price.toFixed(0)}/${bv.normalized_unit || "unit"}` : "";
    show("best-price-banner");
  }

  container.innerHTML = "";
  const platforms = compareData.platforms || [];
  const availableSizes = product?.available_sizes || [];

  platforms.forEach(platData => {
    const platform = platData.platform;
    const pid = platform.id;
    const meta = PLATFORM_META[pid] || {};
    const variants = platData.variants || [];
    const isCheapest = pid === cheapestId;
    const areaAvail = platData.area_available;
    const bestVar = platData.best_variant;

    // Determine initial selected pill index — find the pill (size) that matches the best variant
    if (bestVar && availableSizes.length > 0) {
      const bestLabel = bestVar.display_quantity || `${bestVar.quantity}${bestVar.unit}`;
      const bestKey = _normSizeKey(bestLabel);
      const pillIdx = availableSizes.findIndex(s => _normSizeKey(s) === bestKey);
      _cardSelectedVariant[pid] = pillIdx >= 0 ? pillIdx : 0;
    } else if (bestVar) {
      _cardSelectedVariant[pid] = variants.indexOf(bestVar);
    } else {
      _cardSelectedVariant[pid] = 0;
    }

    const card = el("div", `platform-card${isCheapest ? " is-cheapest" : ""}${!areaAvail ? " is-unavailable" : ""}`);

    const cheapestRibbon = isCheapest && areaAvail && bestVar
      ? `<span class="cheapest-ribbon">CHEAPEST</span>` : "";

    card.innerHTML = `
      <div class="platform-card-header">
        <div class="platform-name-row">
          <div class="platform-logo ${meta.css}">${meta.logoText || pid[0].toUpperCase()}</div>
          <div>
            <div class="platform-card-name">${platform.name}</div>
            <div class="platform-delivery">🚚 ${platData.delivery_time || platform.delivery_promise}</div>
          </div>
        </div>
        ${cheapestRibbon}
      </div>
      <div class="platform-card-body" id="card-body-${pid}"></div>
    `;

    container.appendChild(card);
    _renderCardBody(card.querySelector(`#card-body-${pid}`), pid, variants, isCheapest, areaAvail, compareData, availableSizes);
  });
}

function renderSizeSelector(product, compareData) {
  const selectorEl = $("product-size-selector");
  if (!selectorEl) return;

  const sizes = product.available_sizes || [];
  if (sizes.length === 0) {
    selectorEl.classList.add("hidden");
    selectorEl.innerHTML = "";
    return;
  }

  // Determine the initially selected index from the best variant of any platform
  let initIdx = 0;
  const platforms = compareData.platforms || [];
  for (const platData of platforms) {
    const bv = platData.best_variant;
    if (bv) {
      const bestLabel = bv.display_quantity || `${bv.quantity}${bv.unit}`;
      const idx = sizes.findIndex(s => _normSizeKey(s) === _normSizeKey(bestLabel));
      if (idx >= 0) { initIdx = idx; break; }
    }
  }

  function updateHeroWeight(sizeLabel) {
    const brandPart = product.brand ? ` · ${product.brand}` : "";
    $("product-hero-meta").textContent =
      `${(product.category || "").replace(/_/g, " ")}${brandPart} · ${sizeLabel}`;
  }

  function selectSize(idx) {
    // Sync all platform cards to this size index
    platforms.forEach(platData => {
      _cardSelectedVariant[platData.platform.id] = idx;
    });

    // Re-render all platform card bodies
    const cheapestId = compareData.cheapest_platform_id;
    platforms.forEach(platData => {
      const pid = platData.platform.id;
      const bodyEl = document.getElementById(`card-body-${pid}`);
      if (bodyEl) {
        _renderCardBody(
          bodyEl, pid,
          platData.variants || [],
          pid === cheapestId,
          platData.area_available,
          compareData,
          sizes
        );
      }
    });

    // Update pills active state
    selectorEl.querySelectorAll(".size-selector-pill").forEach((pill, i) => {
      pill.classList.toggle("selected", i === idx);
    });

    updateHeroWeight(sizes[idx]);
  }

  selectorEl.innerHTML =
    `<span class="size-selector-label">Size:</span>` +
    sizes.map((s, i) =>
      `<button type="button" class="size-selector-pill${i === initIdx ? " selected" : ""}" data-idx="${i}">${s}</button>`
    ).join("");

  selectorEl.querySelectorAll(".size-selector-pill").forEach(pill => {
    pill.addEventListener("click", () => selectSize(parseInt(pill.dataset.idx, 10)));
  });

  selectorEl.classList.remove("hidden");
  updateHeroWeight(sizes[initIdx]);
}

// Normalise a size label like "1kg", "500g", "2L", "1000ml" to a canonical string
// so that "1kg" and "1000g" compare as equal.
function _normSizeKey(label) {
  const s = String(label).trim().toLowerCase().replace(/\s+/g, "");
  const m = s.match(/^([\d.]+)(g|gm|gms|gram|grams|kg|kgs|kilogram|ml|milliliter|millilitre|l|liter|litre|liters|litres|pcs|pc|piece|pieces|nos)$/);
  if (!m) return s;
  let qty = parseFloat(m[1]);
  const unit = m[2];
  if (unit === "g" || unit === "gm" || unit === "gms" || unit === "gram" || unit === "grams") {
    return `${qty}g`;
  }
  if (unit === "kg" || unit === "kgs" || unit === "kilogram") {
    return `${qty * 1000}g`;
  }
  if (unit === "ml" || unit === "milliliter" || unit === "millilitre") {
    return `${qty}ml`;
  }
  if (unit === "l" || unit === "liter" || unit === "litre" || unit === "liters" || unit === "litres") {
    return `${qty * 1000}ml`;
  }
  return s;
}

function _renderCardBody(bodyEl, pid, variants, isCheapest, areaAvail, compareData, availableSizes) {
  // Build a normalised-size→variant lookup for this platform
  const sizeToVariant = {};
  variants.forEach(v => {
    const label = v.display_quantity || `${v.quantity}${v.unit}`;
    sizeToVariant[_normSizeKey(label)] = v;
  });

  // Determine the pills to show: use availableSizes if present, otherwise fall back to variant list
  let pills = [];
  if (availableSizes && availableSizes.length > 0) {
    pills = availableSizes.map(size => ({
      label: size,
      variant: sizeToVariant[_normSizeKey(size)] || null,
    }));
  } else if (variants.length > 0) {
    pills = variants.map(v => ({
      label: v.display_quantity || `${v.quantity}${v.unit}`,
      variant: v,
    }));
  }

  // selPillIdx is always a pill-level index (stored by pill clicks and initial best-variant mapping)
  let selPillIdx = _cardSelectedVariant[pid] || 0;
  if (selPillIdx >= pills.length) selPillIdx = 0;

  const selPill = pills[selPillIdx] || null;
  const selVar = selPill ? selPill.variant : null;
  const info = _renderVariantPrice(selVar, isCheapest, pid, PLATFORM_META[pid] || {}, areaAvail);

  // Variant pills — always show available sizes, even for single-size products
  const pillsHtml = pills.length >= 1
    ? `<div class="platform-variant-pills" id="pills-${pid}">
        ${pills.map((p, i) => {
          const hasVariant = !!p.variant;
          const oos = hasVariant ? (!p.variant.in_stock || !areaAvail) : true;
          return `<button type="button"
            class="variant-pill ${i === selPillIdx ? "selected" : ""}${oos ? " out-of-stock" : ""}"
            data-pidx="${i}"
            aria-label="${p.label}${oos ? " (unavailable)" : ""}">
            ${p.label}
          </button>`;
        }).join("")}
      </div>` : "";

  bodyEl.innerHTML = `
    ${pillsHtml}
    <div id="price-area-${pid}">
      ${info.priceHtml}
    </div>
    <div class="plat-details">
      <div class="plat-detail-row">
        <span class="plat-detail-label">Quantity:</span>
        <span id="qty-${pid}">${info.qty}</span>
      </div>
      <div class="plat-detail-row">
        <span class="plat-detail-label">Brand:</span>
        <span>${info.brand}</span>
      </div>
      <div class="plat-detail-row">
        <span class="plat-detail-label">Stock:</span>
        <span>${info.stockHtml}</span>
      </div>
    </div>
    <div class="data-note-row">📊 Reference data · ${selVar?.last_updated || compareData.data_note?.split(".")[0] || "2025-07-15"}</div>
    ${info.buyBtnHtml}
    <button type="button" class="buy-btn" style="margin-top:6px;background:var(--green-light);color:var(--green-dark);border:1px solid var(--green-border);font-size:13px;"
      onclick="addToList('${pid}')">+ Add to List</button>
  `;

  // Wire up variant pill clicks
  if (pills.length >= 1) {
    bodyEl.querySelectorAll(".variant-pill").forEach(pill => {
      pill.addEventListener("click", () => {
        _cardSelectedVariant[pid] = parseInt(pill.dataset.pidx, 10);
        const cheapestId = compareData.cheapest_platform_id;
        _renderCardBody(bodyEl, pid, variants, pid === cheapestId, areaAvail, compareData, availableSizes);
      });
    });
  }
}

function renderProductDetails(product) {
  const body = $("detail-body");
  if (!body) return;
  const items = [
    ["Brand", product.brand],
    ["Category", (product.category || "").replace(/_/g, " ")],
    ["Subcategory", product.subcategory],
    ["Available Sizes", (product.available_sizes || []).join(", ")],
    ["Base Unit", product.base_unit],
  ].filter(([, v]) => v);

  if (product.nutrition) {
    const nutritionStr = Object.entries(product.nutrition)
      .map(([k, v]) => `${k}: ${v}`).join(" · ");
    items.push(["Nutrition", nutritionStr]);
  }

  body.innerHTML = `
    <p style="margin-bottom:10px;font-size:13.5px;color:var(--text-mid)">${product.description || ""}</p>
    <div class="detail-grid">
      ${items.map(([label, value]) => `
        <div>
          <div class="detail-item-label">${label}</div>
          <div class="detail-item-val">${value}</div>
        </div>`).join("")}
    </div>
  `;
}

function renderAvailability(compareData) {
  const content = $("avail-content");
  if (!content) return;
  const platforms = compareData.platforms || [];
  content.innerHTML = platforms.map(p => {
    const avail = p.area_available;
    const icon = avail ? "✅" : "❌";
    return `<div class="avail-platform-row">
      ${icon} <strong>${p.platform.name}</strong>
      <span style="margin-left:auto;font-size:12px;color:var(--muted)">${avail ? p.delivery_time || "Available" : "Not available"}</span>
    </div>`;
  }).join("");
}

function renderDataNote(compareData) {
  const noteEl = $("data-note-banner");
  if (!noteEl) return;
  const note = compareData.data_note || "Prices shown are representative reference data as of 2025-07-16. Actual prices on each platform may differ. Click 'Search on Platform' to verify current prices.";
  noteEl.innerHTML = `<strong>ℹ️ Data note:</strong> ${note}`;
  noteEl.classList.remove("hidden");
}

// ─────────────────────────────────────────────────────────────────────────────
// Product detail accordion
// ─────────────────────────────────────────────────────────────────────────────
function toggleProductDetail() {
  const btn = $("detail-toggle");
  const body = $("detail-body");
  if (!btn || !body) return;
  const expanded = btn.getAttribute("aria-expanded") === "true";
  btn.setAttribute("aria-expanded", String(!expanded));
  body.classList.toggle("hidden", expanded);
}

// ─────────────────────────────────────────────────────────────────────────────
// Availability check
// ─────────────────────────────────────────────────────────────────────────────
async function checkAvailability() {
  const pincode = $("avail-pincode-input")?.value.trim();
  if (!pincode || !/^\d{6}$/.test(pincode)) return;
  const resultEl = $("avail-result");
  resultEl.innerHTML = "Checking…";
  resultEl.classList.remove("hidden");
  try {
    const data = await apiFetch(`/api/check-availability?pincode=${pincode}`);
    const platforms = data.platforms || [];
    resultEl.innerHTML = platforms.map(p =>
      `<div class="avail-platform-row">
        ${p.available ? "✅" : "❌"} <strong>${p.name}</strong>
        <span style="margin-left:auto;font-size:12px;color:var(--muted)">${p.available ? p.delivery_promise : "Not available"}</span>
      </div>`
    ).join("");
  } catch (err) {
    resultEl.innerHTML = "Could not check availability. Try again.";
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Price Alert
// ─────────────────────────────────────────────────────────────────────────────
function setPriceAlert() {
  if (!state.currentProduct) return;
  const price = parseFloat($("alert-price-input").value);
  if (!price || isNaN(price)) return;
  const alert = { productId: state.currentProduct.id, name: state.currentProduct.name, targetPrice: price, createdAt: Date.now() };
  state.priceAlerts = state.priceAlerts.filter(a => a.productId !== alert.productId);
  state.priceAlerts.push(alert);
  localStorage.setItem("groceryai_alerts", JSON.stringify(state.priceAlerts));
  const msgEl = $("alert-set-msg");
  msgEl.textContent = `✅ Alert set for ₹${price}`;
  msgEl.style.cssText = "color:var(--green);font-size:13px;margin-top:6px;";
  msgEl.classList.remove("hidden");
  setTimeout(() => msgEl.classList.add("hidden"), 3000);
}

// ─────────────────────────────────────────────────────────────────────────────
// My List
// ─────────────────────────────────────────────────────────────────────────────
function addToList(pid) {
  if (!state.currentProduct) return;
  const product = state.currentProduct;
  if (state.myList.some(i => i.id === product.id)) return;

  // Capture best price per platform from the live comparison data
  const prices = {};
  (state.currentCompareData?.platforms || []).forEach(p => {
    if (p.best_variant && p.best_variant.price != null) {
      prices[p.platform.id] = p.best_variant.price;
    }
  });

  state.myList.push({
    id: product.id,
    name: product.name,
    brand: product.brand,
    emoji: product.emoji,
    image_url: product.image_url,
    prices,
  });
  localStorage.setItem("groceryai_list", JSON.stringify(state.myList));
  updateCartCount();
}

function removeFromList(productId) {
  state.myList = state.myList.filter(i => i.id !== productId);
  localStorage.setItem("groceryai_list", JSON.stringify(state.myList));
  updateCartCount();
  renderMyList();
}

function updateCartCount() {
  const count = state.myList.length;
  const el = $("cart-count");
  if (!el) return;
  el.textContent = count;
  count > 0 ? el.classList.remove("hidden") : el.classList.add("hidden");
}

function renderMyList() {
  const emptyEl = $("mylist-empty");
  const itemsEl = $("mylist-items");
  const basketEl = $("mylist-basket");

  if (state.myList.length === 0) {
    show("mylist-empty"); hide("mylist-items"); hide("mylist-basket"); return;
  }
  hide("mylist-empty"); show("mylist-items"); show("mylist-basket");

  const PLATFORMS = ["zepto", "blinkit", "instamart", "flipkart"];

  // ── Per-item rows ────────────────────────────────────────────────────
  itemsEl.innerHTML = state.myList.map(item => {
    const imgHtml = item.image_url
      ? `<img src="${item.image_url}" alt="${item.name}" class="mylist-item-img" loading="lazy" onerror="this.style.display='none'">`
      : `<div class="mylist-item-emoji">${item.emoji || "🛒"}</div>`;

    // Build per-platform price pills for this item
    const pricePills = PLATFORMS.map(pid => {
      const meta = PLATFORM_META[pid];
      const price = item.prices?.[pid];
      return price != null
        ? `<span class="item-price-pill item-price-pill-${meta.css}" title="${meta.name}">${meta.emoji} ₹${price}</span>`
        : `<span class="item-price-pill item-price-pill-na" title="${meta.name} — not listed">${meta.emoji} —</span>`;
    }).join("");

    return `
      <div class="mylist-item">
        ${imgHtml}
        <div class="mylist-item-info">
          <div class="mylist-item-name">${item.name}</div>
          ${item.brand ? `<div class="mylist-item-brand">${item.brand}</div>` : ""}
          <div class="mylist-item-prices">${pricePills}</div>
        </div>
        <div class="mylist-item-actions">
          <button type="button" class="mylist-compare-btn" onclick="showProductView('${item.id}', 'mylist')">Compare</button>
          <button type="button" class="mylist-remove-btn" onclick="removeFromList('${item.id}')">Remove</button>
        </div>
      </div>`;
  }).join("");

  // ── Basket totals table ──────────────────────────────────────────────
  const totalsEl = $("basket-platform-totals");
  if (!totalsEl) return;

  // Sum prices per platform (only items that have a price for that platform)
  const totals = {};
  const counts = {};
  PLATFORMS.forEach(pid => { totals[pid] = 0; counts[pid] = 0; });

  state.myList.forEach(item => {
    PLATFORMS.forEach(pid => {
      const price = item.prices?.[pid];
      if (price != null) {
        totals[pid] += price;
        counts[pid]++;
      }
    });
  });

  const totalItems = state.myList.length;
  const activePlatforms = PLATFORMS.filter(pid => counts[pid] > 0);

  if (activePlatforms.length === 0) {
    // No price data saved yet (items added before this update or no compare loaded)
    totalsEl.innerHTML = `
      <p class="basket-no-data">
        Open each product and tap <strong>"Compare Prices"</strong> then <strong>"+ Add to List"</strong> to capture live prices.
      </p>`;
    return;
  }

  // Find cheapest platform (most items covered + lowest total)
  const ranked = activePlatforms.slice().sort((a, b) => {
    if (counts[b] !== counts[a]) return counts[b] - counts[a]; // more coverage first
    return totals[a] - totals[b]; // then lower total
  });
  const cheapestPid = ranked[0];

  const rows = PLATFORMS.map(pid => {
    const meta = PLATFORM_META[pid];
    const covered = counts[pid];
    const total = totals[pid];
    const isCheapest = pid === cheapestPid;
    const coverageNote = covered < totalItems
      ? `<span class="basket-coverage">${covered}/${totalItems} items</span>` : "";
    const savings = isCheapest && ranked.length > 1
      ? "" : (isCheapest ? "" : `<span class="basket-savings">+₹${(total - totals[cheapestPid]).toFixed(0)} more</span>`);

    if (covered === 0) {
      return `
        <div class="basket-platform-row basket-row-na">
          <div class="basket-row-left">
            <div class="platform-logo ${meta.css}" style="width:28px;height:28px;font-size:11px;flex-shrink:0">${meta.logoText}</div>
            <span class="basket-plat-name">${meta.name}</span>
          </div>
          <span class="basket-plat-total basket-na">Not listed</span>
        </div>`;
    }

    return `
      <div class="basket-platform-row${isCheapest ? " basket-row-best" : ""}">
        <div class="basket-row-left">
          <div class="platform-logo ${meta.css}" style="width:28px;height:28px;font-size:11px;flex-shrink:0">${meta.logoText}</div>
          <span class="basket-plat-name">${meta.name}</span>
          ${coverageNote}
        </div>
        <div class="basket-row-right">
          ${savings}
          <span class="basket-plat-total">₹${total.toFixed(0)}</span>
          ${isCheapest ? `<span class="basket-cheapest-tag">🏆 Best</span>` : ""}
        </div>
      </div>`;
  }).join("");

  const savedAmount = ranked.length > 1
    ? (totals[ranked[ranked.length - 1]] - totals[cheapestPid]).toFixed(0)
    : null;

  totalsEl.innerHTML = `
    ${rows}
    ${savedAmount && Number(savedAmount) > 0 ? `
    <div class="basket-winner">
      🏆 Shop on <strong>${PLATFORM_META[cheapestPid].name}</strong> and save up to ₹${savedAmount} on this list!
    </div>` : ""}
  `;
}

// ─────────────────────────────────────────────────────────────────────────────
// Utility
// ─────────────────────────────────────────────────────────────────────────────
function showAllCategories() {
  showHome();
  setTimeout(() => {
    const sec = document.querySelector(".categories-scroll");
    if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 100);
}

// ─────────────────────────────────────────────────────────────────────────────
// INIT
// ─────────────────────────────────────────────────────────────────────────────
init();
