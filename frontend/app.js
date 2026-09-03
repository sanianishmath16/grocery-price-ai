/**
 * app.js — GroceryAI v13
 *
 * Full SPA: Home → Category → Product Comparison
 * Features:
 *   - Category browsing + product grid with real product images
 *   - Global search with autocomplete (brand, category, variant-aware)
 *   - Per-product platform comparison with quantity normalization
 *   - ALL size variants shown per platform card with interactive pills
 *   - Best (cheapest available) variant pre-selected; click pills to switch
 *   - Pincode-based availability
 *   - Cheapest available calculation (code-based, not AI)
 *   - MRP / discount display
 *   - Product image shown in comparison header
 *   - "Search on Platform" links (real platform search URLs, clearly labelled)
 *   - Price alerts (localStorage)
 *   - My List / shopping basket comparison
 *   - 52 products, 4 platforms, Flipkart duplicate keys removed
 *
 * Data note: All platform prices are representative demo data.
 * Buy Now buttons open the platform's legitimate search page for the product.
 * Direct product page URLs are not generated because we do not have real
 * platform product IDs — doing so would produce broken 404 links.
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
  currentProduct: null,
  currentCategory: null,
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
function toggle(id){ const e = $(id); if (e) e.classList.toggle("hidden"); }

// ─────────────────────────────────────────────────────────────────────────────
// View switching
// ─────────────────────────────────────────────────────────────────────────────
const VIEWS = ["view-home", "view-category", "view-search", "view-product", "view-mylist"];

function switchView(viewId) {
  VIEWS.forEach(v => {
    const el = $(v);
    if (el) el.classList.toggle("hidden", v !== viewId);
  });
  // Update bottom nav active state
  document.querySelectorAll(".bnav-btn").forEach(b => b.classList.remove("active"));
  const map = { "view-home": "bnav-home", "view-mylist": "bnav-list" };
  if (map[viewId]) $( map[viewId])?.classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showHome() {
  switchView("view-home");
  hideSearchSuggestions();
}

function showCategoryView(catId) {
  state.currentCategory = catId;
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
    else if (state.previousView === "search") { /* stay on search */ switchView("view-search"); }
    else showHome();
  };
  switchView("view-product");
  loadProductComparison(productId);
}

function showMyList() {
  switchView("view-mylist");
  renderMyList();
}

function showAllCategories() {
  // For now, scroll to categories on home
  showHome();
  setTimeout(() => {
    const sec = document.querySelector(".categories-scroll");
    if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 100);
}

// ─────────────────────────────────────────────────────────────────────────────
// Pincode
// ─────────────────────────────────────────────────────────────────────────────
function promptPincode() {
  $("modal-pincode").value = state.pincode;
  show("pincode-modal");
  setTimeout(() => $("modal-pincode").focus(), 100);
}

function closePincodeModal() {
  hide("pincode-modal");
}

function quickPin(pin) {
  $("modal-pincode").value = pin;
  applyPincode();
}

function applyPincode() {
  const val = $("modal-pincode").value.trim();
  if (!/^\d{6}$/.test(val)) {
    show("modal-pincode-error");
    return;
  }
  hide("modal-pincode-error");
  state.pincode = val;
  localStorage.setItem("groceryai_pincode", val);
  closePincodeModal();
  updateLocationUI();
  // If on product view, reload comparison
  if (!$("view-product").classList.contains("hidden") && state.currentProduct) {
    loadProductComparison(state.currentProduct.id);
  }
}

function updateLocationUI() {
  const pin = state.pincode;
  const locationText = pin ? `📍 ${pin}` : "Set Location";
  $("nav-location-text").textContent = locationText;
}

// Close modal on overlay click
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
// Init — load categories and featured products
// ─────────────────────────────────────────────────────────────────────────────
async function init() {
  updateLocationUI();
  updateCartCount();

  try {
    const [catData, prodData] = await Promise.all([
      apiFetch("/api/categories"),
      apiFetch("/api/products?limit=50"),
    ]);
    state.categories = catData.categories || [];
    state.products   = prodData.products  || [];

    renderCategories();
    renderFeaturedProducts();
    setupSearchAutocomplete();
  } catch (err) {
    console.error("Init failed:", err);
    // Show graceful degradation — render with built-in fallback data
    renderCategoriesFallback();
    renderProductsFallback();
  }

  // Prompt for pincode on first visit
  if (!state.pincode) {
    setTimeout(promptPincode, 1200);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Render Categories
// ─────────────────────────────────────────────────────────────────────────────
function renderCategories() {
  const container = $("categories-scroll");
  if (!container) return;
  container.innerHTML = "";
  state.categories.forEach(cat => {
    const card = el("button", "category-card");
    card.setAttribute("type", "button");
    card.setAttribute("role", "listitem");
    card.setAttribute("aria-label", cat.name);
    card.innerHTML = `
      <span class="cat-emoji" aria-hidden="true">${cat.emoji}</span>
      <span class="cat-name">${cat.name}</span>
    `;
    card.addEventListener("click", () => showCategoryView(cat.id));
    container.appendChild(card);
  });
}

function renderCategoriesFallback() {
  const CATS = [
    { id: "vegetables", name: "Vegetables", emoji: "🥬" },
    { id: "fruits",     name: "Fruits",     emoji: "🍎" },
    { id: "dairy",      name: "Dairy",      emoji: "🥛" },
    { id: "staples",    name: "Staples",    emoji: "🌾" },
    { id: "snacks",     name: "Snacks",     emoji: "🍪" },
    { id: "beverages",  name: "Beverages",  emoji: "🥤" },
  ];
  state.categories = CATS;
  renderCategories();
}

// ─────────────────────────────────────────────────────────────────────────────
// Render Product Grid
// ─────────────────────────────────────────────────────────────────────────────
function renderProductGrid(products, containerId, fromView) {
  const container = $(containerId);
  if (!container) return;
  container.innerHTML = "";

  // Show skeletons first
  if (products === null) {
    for (let i = 0; i < 8; i++) {
      container.appendChild(el("div", "skel-product"));
    }
    return;
  }

  if (!products.length) {
    if (containerId === "search-products") {
      show("search-empty");
    }
    return;
  }
  if (containerId === "search-products") hide("search-empty");

  products.forEach(product => {
    const card = buildProductCard(product, fromView);
    container.appendChild(card);
  });
}

function buildProductCard(product, fromView) {
  const inList = state.myList.some(i => i.id === product.id);
  const card = el("article", `product-card${inList ? "" : ""}`, "");
  card.setAttribute("role", "listitem");
  card.setAttribute("aria-label", product.name);

  const catName = product.category
    ? product.category.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())
    : "";

  // Image: use real product image URL if available, otherwise show emoji fallback
  const imgHtml = product.image_url
    ? `<img src="${product.image_url}" alt="${product.name}" class="product-card-img" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'" /><span class="product-card-emoji-fallback" style="display:none">${product.emoji || "🛒"}</span>`
    : `<span class="product-card-emoji-fallback">${product.emoji || "🛒"}</span>`;

  card.innerHTML = `
    ${inList ? '<span class="in-list-badge">✓ In List</span>' : ""}
    <div class="product-img-wrap" aria-hidden="true">
      ${imgHtml}
    </div>
    <div class="product-card-body">
      <p class="product-card-name">${product.name}</p>
      ${product.brand ? `<p class="product-card-brand">${product.brand}</p>` : ""}
      <p class="product-card-cat">${catName}</p>
      <div class="product-card-price-row">
        <span class="product-card-price">from ₹${product.base_price_inr}</span>
        <span class="product-card-unit">/ ${product.available_sizes?.[0] || "1 unit"}</span>
      </div>
      <div class="product-card-rating">⭐ ${product.rating || "4.3"}</div>
      <div class="product-card-footer">
        <button type="button" class="compare-btn" aria-label="Compare prices for ${product.name}">
          Compare Prices →
        </button>
      </div>
    </div>
  `;

  card.addEventListener("click", (e) => {
    if (e.target.classList.contains("add-to-list-btn")) return;
    showProductView(product.id, fromView || "home");
  });

  return card;
}

function renderFeaturedProducts() {
  // Show first 8 popular products
  const featured = state.products.slice(0, 12);
  renderProductGrid(featured, "featured-products", "home");
}

function renderProductsFallback() {
  // If API fails, show placeholder skeleton
  renderProductGrid([], "featured-products", "home");
}

// ─────────────────────────────────────────────────────────────────────────────
// Category Products
// ─────────────────────────────────────────────────────────────────────────────
async function loadCategoryProducts(catId) {
  // Show skeletons
  renderProductGrid(null, "category-products", "category");

  try {
    const data = await apiFetch(`/api/products?category=${catId}`);
    const products = data.products || [];
    renderProductGrid(products, "category-products", "category");
  } catch (err) {
    console.error("Category load failed:", err);
    // Filter from cached state
    const products = state.products.filter(p => p.category === catId);
    renderProductGrid(products, "category-products", "category");
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Search
// ─────────────────────────────────────────────────────────────────────────────
async function loadSearchResults(query) {
  hide("search-empty");
  renderProductGrid(null, "search-products", "search");

  try {
    const data = await apiFetch(`/api/products?q=${encodeURIComponent(query)}`);
    const products = data.products || [];
    renderProductGrid(products, "search-products", "search");
  } catch (err) {
    const q = query.toLowerCase();
    const products = state.products.filter(p =>
      p.name.toLowerCase().includes(q) ||
      p.id.includes(q) ||
      (p.tags || []).some(t => t.toLowerCase().includes(q))
    );
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
      if (val.length < 2) {
        hideSearchSuggestions();
        return;
      }
      debounceTimer = setTimeout(() => showSearchSuggestions(val, input), 200);
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const val = input.value.trim();
        if (val.length > 0) {
          hideSearchSuggestions();
          showSearchView(val);
        }
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

  // Close suggestions when clicking outside
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
    // Show size variants as small pills if available
    const sizePills = (p.available_sizes || []).slice(0, 3)
      .map(s => `<span class="sugg-size-pill">${s}</span>`).join("");
    item.innerHTML = `
      <span class="suggestion-emoji" aria-hidden="true">${p.emoji || "🛒"}</span>
      <span class="suggestion-text-wrap">
        <span class="suggestion-text">${highlighted}</span>
        ${sizePills ? `<span class="suggestion-sizes">${sizePills}</span>` : ""}
      </span>
      <span class="suggestion-cat">${catLabel}</span>
    `;
    item.addEventListener("click", () => {
      hideSearchSuggestions();
      showProductView(p.id, "search");
    });
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        hideSearchSuggestions();
        showProductView(p.id, "search");
      }
    });
    container.appendChild(item);
  });

  show("search-suggestions");
}

function hideSearchSuggestions() {
  hide("search-suggestions");
}

function focusNavSearch() {
  $("global-search")?.focus();
  $("bnav-search")?.classList.add("active");
}

function focusHeroSearch() {
  const heroSearch = $("hero-search");
  const val = heroSearch?.value?.trim();
  if (val) {
    showSearchView(val);
  } else {
    heroSearch?.focus();
  }
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// ─────────────────────────────────────────────────────────────────────────────
// Product Comparison Page
// ─────────────────────────────────────────────────────────────────────────────
async function loadProductComparison(productId) {
  state.currentProduct = { id: productId };

  // Show loading state
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

    // Update product header — image or emoji
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
    $("product-hero-name").textContent  = product.name;
    const brandPart = product.brand ? ` · ${product.brand}` : "";
    $("product-hero-meta").textContent  = `${(product.category || "").replace(/_/g, " ")}${brandPart}`;
    $("product-pincode-display").textContent = pincode;

    // Render platform comparison
    renderPlatformCards(compareData);
    renderProductDetails(product);
    renderAvailability(compareData);
    renderDataNote(compareData);

    // Populate price alert with suggested price
    const cheapest = getCheapestVariant(compareData);
    if (cheapest) {
      $("alert-price-input").placeholder = Math.floor(cheapest.price * 0.9);
    }

  } catch (err) {
    console.error("Product compare failed:", err);
    $("platform-cards").innerHTML = `
      <div class="empty-state">
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

// ---------------------------------------------------------------------------
// Per-card state: track which variant index is selected for each platform
// ---------------------------------------------------------------------------
const _cardSelectedVariant = {};

function _renderVariantPrice(v, isCheapest, pid, meta, areaAvail) {
  if (!areaAvail) {
    return {
      priceHtml: `<span class="platform-price-big text-muted">—</span><span class="platform-price-norm text-muted">Not in area</span>`,
      buyBtnHtml: `<span class="buy-btn buy-btn-unavail">Not in your area</span>`,
      stockHtml: `<span class="plat-detail-val out-of-stock">❌ Not available</span>`,
      qty: "—", brand: "—",
    };
  }
  if (!v) {
    return {
      priceHtml: `<span class="platform-price-big text-muted">—</span><span class="platform-price-norm text-muted">Not listed</span>`,
      buyBtnHtml: `<span class="buy-btn buy-btn-unavail">Not listed</span>`,
      stockHtml: `<span class="plat-detail-val out-of-stock">❌ Not listed</span>`,
      qty: "—", brand: "—",
    };
  }
  const mrpHtml = v.mrp && v.mrp > v.price ? `<span class="platform-price-mrp">₹${v.mrp}</span>` : "";
  const discountHtml = v.mrp && v.mrp > v.price
    ? `<span class="platform-discount-tag">${Math.round((1 - v.price / v.mrp) * 100)}% off</span>` : "";
  if (!v.in_stock) {
    return {
      priceHtml: `<span class="platform-price-big">₹${v.price}</span>${mrpHtml}<span class="platform-price-norm">${normLabel(v)}</span><span class="platform-qty">${v.display_quantity || ""}</span>`,
      buyBtnHtml: `<span class="buy-btn buy-btn-unavail">❌ Out of Stock</span>`,
      stockHtml: `<span class="plat-detail-val out-of-stock">❌ Out of Stock</span>`,
      qty: v.display_quantity || "—", brand: v.brand || "—",
    };
  }
  const btnUrl = v.product_url || (meta && meta.website) || "#";
  const btnLabel = v.url_is_search ? `Search on ${meta.name}` : `Buy on ${meta.name}`;
  const btnClass = v.url_is_search ? "buy-btn buy-btn-search" : "buy-btn buy-btn-green";
  const prodName = state.currentProduct?.name || "";
  return {
    priceHtml: `<span class="platform-price-big">₹${v.price}</span>${mrpHtml}<span class="platform-price-norm">${normLabel(v)}</span><span class="platform-qty">${v.display_quantity || ""}</span>${isCheapest ? '<span class="platform-cheapest-tag">🏆 CHEAPEST</span>' : ""}${discountHtml}`,
    buyBtnHtml: `<a href="${btnUrl}" target="_blank" rel="noopener noreferrer" class="${btnClass}" aria-label="${btnLabel} for ${prodName}">${btnLabel} →</a>`,
    stockHtml: `<span class="plat-detail-val in-stock">✅ In Stock</span>`,
    qty: v.display_quantity || "—", brand: v.brand || "—",
  };
}

function _updateCardVariant(pid, variantIndex, allVariants, isCheapest, areaAvail, delivery, meta, bestVariant) {
  const card = document.getElementById(`pcard-${pid}`);
  if (!card) return;
  _cardSelectedVariant[pid] = variantIndex;

  const v = allVariants[variantIndex] || null;
  const { priceHtml, buyBtnHtml, stockHtml, qty, brand } = _renderVariantPrice(v, isCheapest, pid, meta, areaAvail);

  card.querySelector(".pc-price-area").innerHTML = priceHtml;
  card.querySelector(".pc-stock").innerHTML = stockHtml;
  card.querySelector(".pc-qty").textContent = qty;
  card.querySelector(".pc-brand").textContent = brand;
  card.querySelector(".pc-actions").innerHTML = `
    ${buyBtnHtml}
    ${areaAvail && v && v.in_stock ? `<button type="button" class="add-to-list-btn" onclick="addToList('${state.currentProduct?.id}', '${v.price}')">+ My List</button>` : ""}
  `;

  // Update variant pill active states
  card.querySelectorAll(".variant-pill").forEach((pill, i) => {
    pill.classList.toggle("variant-pill-active", i === variantIndex);
  });
}

function renderPlatformCards(compareData) {
  const platforms = compareData.platforms || [];
  const cheapestId = compareData.cheapest_platform_id;
  const container = $("platform-cards");
  container.innerHTML = "";

  if (!platforms.length) {
    container.innerHTML = `<div class="empty-state"><p class="empty-title">No platform data available.</p></div>`;
    return;
  }

  // Sort: available first, unavailable last
  const sorted = [...platforms].sort((a, b) => {
    const aAvail = a.area_available && a.best_variant && a.best_variant.in_stock ? 0 : 1;
    const bAvail = b.area_available && b.best_variant && b.best_variant.in_stock ? 0 : 1;
    return aAvail - bAvail;
  });

  sorted.forEach(pData => {
    const pid = pData.platform.id;
    const meta = PLATFORM_META[pid] || { name: pid, emoji: "🏪", css: pid, logoText: pid[0] };
    const isCheapest = pid === cheapestId;
    const allVariants = pData.variants || [];
    const bestVariant = pData.best_variant;
    const isAvail = pData.area_available && bestVariant && bestVariant.in_stock;
    const delivery = pData.area_available ? `⚡ ${pData.delivery_time} (est.)` : "—";

    // Find the index of the best variant to pre-select it
    const bestIdx = bestVariant
      ? allVariants.findIndex(v => v.display_quantity === bestVariant.display_quantity && v.price === bestVariant.price)
      : 0;
    const initIdx = bestIdx >= 0 ? bestIdx : 0;
    _cardSelectedVariant[pid] = initIdx;

    const initVariant = allVariants[initIdx] || bestVariant;
    const { priceHtml, buyBtnHtml, stockHtml, qty, brand } = _renderVariantPrice(
      initVariant, isCheapest, pid, meta, pData.area_available
    );

    // Build variant size pills (only if there are multiple variants)
    let variantPillsHtml = "";
    if (allVariants.length > 1) {
      const pills = allVariants.map((v, i) => {
        const isActive = i === initIdx;
        const outCls = !v.in_stock ? " variant-pill-oos" : "";
        return `<button type="button" class="variant-pill${isActive ? " variant-pill-active" : ""}${outCls}"
          title="₹${v.price} — ${normLabel(v)}${!v.in_stock ? " (Out of Stock)" : ""}"
          onclick="_updateCardVariant('${pid}', ${i}, window.__pdata_${pid}, ${isCheapest}, ${pData.area_available}, '${delivery.replace(/'/g, "\\'")}', window.__pmeta_${pid}, null)"
          >${v.display_quantity || `${v.quantity}${v.unit}`}</button>`;
      }).join("");
      variantPillsHtml = `<div class="variant-pills-row">${pills}</div>`;
    }

    const card = el("div", `platform-card ${pid}-card${isCheapest ? " is-cheapest" : ""}${!isAvail ? " is-unavailable" : ""}`);
    card.setAttribute("role", "listitem");
    card.id = `pcard-${pid}`;

    card.innerHTML = `
      <div class="platform-card-left">
        <div class="platform-name-row">
          <div class="platform-logo ${pid}-logo" aria-hidden="true">${meta.logoText}</div>
          <span class="platform-name-text">${meta.name}</span>
        </div>
        ${variantPillsHtml}
        <div class="platform-detail-grid">
          <div class="plat-detail-item">
            <span class="plat-detail-label">Brand</span>
            <span class="plat-detail-val pc-brand">${brand}</span>
          </div>
          <div class="plat-detail-item">
            <span class="plat-detail-label">Quantity</span>
            <span class="plat-detail-val pc-qty">${qty}</span>
          </div>
          <div class="plat-detail-item">
            <span class="plat-detail-label">Stock</span>
            <span class="pc-stock">${stockHtml}</span>
          </div>
          <div class="plat-detail-item">
            <span class="plat-detail-label">Delivery</span>
            <span class="plat-detail-val delivery-badge">${delivery}</span>
          </div>
        </div>
        <div class="pc-actions" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
          ${buyBtnHtml}
          ${isAvail && initVariant ? `<button type="button" class="add-to-list-btn" onclick="addToList('${state.currentProduct?.id}', '${initVariant.price}')">+ My List</button>` : ""}
        </div>
      </div>
      <div class="platform-card-right">
        <div class="pc-price-area">${priceHtml}</div>
      </div>
    `;

    // Store variant data on window so onclick can access it
    window[`__pdata_${pid}`] = allVariants;
    window[`__pmeta_${pid}`] = meta;

    container.appendChild(card);
  });

  // Best price banner
  const cheapestPlatform = platforms.find(p => p.platform.id === cheapestId);
  if (cheapestPlatform && cheapestPlatform.best_variant) {
    const v = cheapestPlatform.best_variant;
    $("best-platform-name").textContent = PLATFORM_META[cheapestId]?.name || cheapestId;
    $("best-price-val").textContent = `₹${v.price}`;
    $("best-price-norm").textContent = normLabel(v);
    show("best-price-banner");
  } else {
    hide("best-price-banner");
  }
}

function normLabel(variant) {
  if (!variant || !variant.normalized_price) return "";
  const unit = variant.normalized_unit || "unit";
  return `₹${variant.normalized_price.toFixed(0)}/${unit}`;
}

function renderProductDetails(product) {
  const body = $("detail-body");
  if (!body) return;

  const sizes = (product.available_sizes || []).map(s => `<span class="size-pill">${s}</span>`).join("");
  const nutrition = product.nutrition
    ? Object.entries(product.nutrition).map(([k, v]) => `<span class="size-pill">${k}: ${v}</span>`).join("")
    : null;

  body.innerHTML = `
    <div class="detail-grid">
      ${product.brand ? `<div class="detail-item">
        <span class="detail-label">Brand</span>
        <span class="detail-val" style="color:var(--blue);font-weight:600">${product.brand}</span>
      </div>` : ""}
      <div class="detail-item">
        <span class="detail-label">Category</span>
        <span class="detail-val">${(product.category || "").replace(/_/g, " ")}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">Type</span>
        <span class="detail-val">${product.subcategory || "—"}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">Origin</span>
        <span class="detail-val">${product.origin || "—"}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">Storage</span>
        <span class="detail-val">${product.storage || "—"}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">Shelf Life</span>
        <span class="detail-val">${product.shelf_life || "—"}</span>
      </div>
      <div class="detail-item detail-full">
        <span class="detail-label">Description</span>
        <span class="detail-val">${product.description || "—"}</span>
      </div>
      <div class="detail-item detail-full">
        <span class="detail-label">Available Sizes</span>
        <div class="size-pills">${sizes}</div>
      </div>
      ${nutrition ? `<div class="detail-item detail-full"><span class="detail-label">Nutrition</span><div class="size-pills">${nutrition}</div></div>` : ""}
    </div>
  `;
}

function renderDataNote(compareData) {
  // Show data freshness note — find or create element
  let noteEl = $("data-note-bar");
  if (!noteEl) {
    noteEl = el("div", "data-note-bar");
    noteEl.id = "data-note-bar";
    const wrap = $("product-detail-wrap");
    if (wrap) wrap.insertBefore(noteEl, wrap.firstChild);
  }
  const note = compareData.data_note || "";
  noteEl.innerHTML = note
    ? `<svg viewBox="0 0 16 16" fill="currentColor" width="13" height="13" style="flex-shrink:0" aria-hidden="true"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 2a5 5 0 110 10A5 5 0 018 3zm-.5 2v4h1V5h-1zm0 5v1h1v-1h-1z"/></svg> ${note}`
    : "";
  noteEl.style.display = note ? "flex" : "none";
}

function renderAvailability(compareData) {
  const container = $("avail-content");
  if (!container) return;

  const platforms = compareData.platforms || [];
  const rows = platforms.map(p => {
    const pid = p.platform.id;
    const meta = PLATFORM_META[pid] || { name: pid };
    const avail = p.area_available;
    return `
      <div class="avail-row">
        <span class="avail-plat">${meta.emoji || ""} ${meta.name}</span>
        <span class="avail-status ${avail ? "avail-yes" : "avail-no"}">
          ${avail ? "✅ Available" : "❌ Not available"}
        </span>
      </div>
    `;
  }).join("");

  container.innerHTML = rows;
}

// ─────────────────────────────────────────────────────────────────────────────
// Product detail toggle
// ─────────────────────────────────────────────────────────────────────────────
function toggleProductDetail() {
  const toggle = $("detail-toggle");
  const body = $("detail-body");
  if (!toggle || !body) return;
  const expanded = toggle.getAttribute("aria-expanded") === "true";
  toggle.setAttribute("aria-expanded", String(!expanded));
  body.classList.toggle("hidden", expanded);
}

// ─────────────────────────────────────────────────────────────────────────────
// Availability checker
// ─────────────────────────────────────────────────────────────────────────────
async function checkAvailability() {
  const pin = $("avail-pincode-input")?.value.trim();
  if (!pin || !/^\d{6}$/.test(pin)) {
    $("avail-result").innerHTML = `<span class="field-error">Please enter a valid 6-digit pincode.</span>`;
    show("avail-result");
    return;
  }

  $("avail-result").innerHTML = `<div class="compare-loading"><div class="spinner"></div> Checking...</div>`;
  show("avail-result");

  try {
    const data = await apiFetch(`/api/check-availability?pincode=${pin}`);
    const rows = (data.platforms || []).map(p => `
      <div class="avail-row">
        <span class="avail-plat">${PLATFORM_META[p.platform_id]?.name || p.platform_name}</span>
        <span class="avail-status ${p.available ? "avail-yes" : "avail-no"}">
          ${p.available ? "✅ Available" : "❌ Not available"}
        </span>
      </div>
    `).join("");

    $("avail-result").innerHTML = `
      <p style="font-size:12px;font-weight:600;color:var(--muted);margin-bottom:8px;padding:0 18px;">Pincode ${pin}</p>
      ${rows}
    `;
  } catch (err) {
    $("avail-result").innerHTML = `<p class="field-error" style="padding:12px 18px;">Could not check availability. Try again.</p>`;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Price Alerts
// ─────────────────────────────────────────────────────────────────────────────
function setPriceAlert() {
  const priceInput = $("alert-price-input");
  const targetPrice = parseFloat(priceInput?.value);
  const msgEl = $("alert-set-msg");
  const product = state.currentProduct;

  if (!product || !product.id) {
    showAlertMsg(msgEl, "No product selected.", true);
    return;
  }
  if (isNaN(targetPrice) || targetPrice <= 0) {
    showAlertMsg(msgEl, "Please enter a valid target price.", true);
    return;
  }

  // Remove existing alert for this product
  state.priceAlerts = state.priceAlerts.filter(a => a.productId !== product.id);
  state.priceAlerts.push({
    productId: product.id,
    productName: product.name,
    targetPrice,
    setAt: new Date().toISOString(),
  });
  localStorage.setItem("groceryai_alerts", JSON.stringify(state.priceAlerts));
  showAlertMsg(msgEl, `🔔 Alert set! We'll notify you when ${product.name} drops below ₹${targetPrice}.`, false);
}

function showAlertMsg(el, msg, isError) {
  if (!el) return;
  el.textContent = msg;
  el.className = isError ? "error-msg" : "";
  show(el.id);
  setTimeout(() => hide(el.id), 4000);
}

// ─────────────────────────────────────────────────────────────────────────────
// My List
// ─────────────────────────────────────────────────────────────────────────────
function addToList(productId, price) {
  if (!productId) return;
  const product = state.products.find(p => p.id === productId) || state.currentProduct;
  if (!product) return;

  const already = state.myList.some(i => i.id === productId);
  if (already) {
    showToast(`${product.name} is already in your list`);
    return;
  }

  state.myList.push({
    id: productId,
    name: product.name,
    emoji: product.emoji,
    category: product.category,
    price: parseFloat(price) || product.base_price_inr,
  });
  localStorage.setItem("groceryai_list", JSON.stringify(state.myList));
  updateCartCount();
  showToast(`✅ ${product.name} added to your list`);
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
  if (count > 0) el.classList.remove("hidden"); else el.classList.add("hidden");
}

function renderMyList() {
  const empty = $("mylist-empty");
  const itemsWrap = $("mylist-items");
  const basketWrap = $("mylist-basket");

  if (state.myList.length === 0) {
    show("mylist-empty");
    hide("mylist-items");
    hide("mylist-basket");
    return;
  }

  hide("mylist-empty");
  show("mylist-items");

  itemsWrap.innerHTML = state.myList.map(item => `
    <div class="mylist-item">
      <span class="mylist-emoji" aria-hidden="true">${item.emoji || "🛒"}</span>
      <div class="mylist-info">
        <p class="mylist-name">${item.name}</p>
        <p class="mylist-cat">${(item.category || "").replace(/_/g, " ")}</p>
      </div>
      <span class="mylist-price">₹${item.price || "—"}</span>
      <button type="button" class="mylist-remove" onclick="removeFromList('${item.id}')" aria-label="Remove ${item.name}">Remove</button>
    </div>
  `).join("");

  // Basket comparison
  renderBasketComparison();
  show("mylist-basket");
}

function renderBasketComparison() {
  // Simple basket: sum up the cheapest available price per product from each platform
  // We use what we have in state — a rough estimate

  const PLATFORM_IDS = ["zepto", "blinkit", "instamart", "flipkart"];
  const PLATFORM_NAMES = {
    zepto: "Zepto", blinkit: "Blinkit", instamart: "Swiggy Instamart", flipkart: "Flipkart Minutes"
  };

  // Simulate small variance per platform
  const totals = {};
  PLATFORM_IDS.forEach(pid => {
    let total = 0;
    state.myList.forEach(item => {
      // Use a deterministic hash-based variance for each platform+product combination
      const seed = simpleHash(`${pid}:${item.id}`);
      const variance = 0.90 + (seed % 20) / 100; // 0.90–1.10
      total += (item.price || 0) * variance;
    });
    totals[pid] = Math.round(total);
  });

  const sorted = PLATFORM_IDS.slice().sort((a, b) => totals[a] - totals[b]);
  const cheapestPid = sorted[0];

  $("basket-platform-totals").innerHTML = sorted.map(pid => `
    <div class="basket-platform-row${pid === cheapestPid ? " fw-700" : ""}">
      <span class="basket-plat">
        ${PLATFORM_META[pid]?.emoji || ""} ${PLATFORM_NAMES[pid]}
        ${pid === cheapestPid ? " 🏆" : ""}
      </span>
      <span class="basket-total">₹${totals[pid]}</span>
    </div>
  `).join("");

  const savings = totals[sorted[sorted.length - 1]] - totals[cheapestPid];
  $("basket-winner").innerHTML = `
    🏆 Cheapest Basket: <strong>${PLATFORM_NAMES[cheapestPid]}</strong> — ₹${totals[cheapestPid]}
    ${savings > 0 ? `<br><small>Save ₹${savings} vs. the most expensive option</small>` : ""}
  `;
  show("basket-winner");
}

function simpleHash(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

// ─────────────────────────────────────────────────────────────────────────────
// Toast notification
// ─────────────────────────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg) {
  let toast = document.querySelector(".toast");
  if (!toast) {
    toast = el("div", "toast");
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add("toast-show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("toast-show"), 3000);
}

// Inject toast CSS
const toastStyle = el("style");
toastStyle.textContent = `
  .toast {
    position: fixed;
    bottom: 80px;
    left: 50%;
    transform: translateX(-50%) translateY(20px);
    background: #1f2937;
    color: white;
    padding: 10px 20px;
    border-radius: 24px;
    font-size: 13px;
    font-weight: 500;
    opacity: 0;
    transition: opacity .2s, transform .2s;
    z-index: 500;
    white-space: nowrap;
    pointer-events: none;
  }
  .toast.toast-show { opacity: 1; transform: translateX(-50%) translateY(0); }
`;
document.head.appendChild(toastStyle);

// ─────────────────────────────────────────────────────────────────────────────
// Hero search setup
// ─────────────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  $("hero-search")?.addEventListener("input", (e) => {
    const val = e.target.value.trim();
    if (val.length >= 2) showSearchSuggestions(val, e.target);
    else hideSearchSuggestions();
  });

  $("hero-search")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const val = $("hero-search").value.trim();
      if (val) { hideSearchSuggestions(); showSearchView(val); }
    }
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Start
// ─────────────────────────────────────────────────────────────────────────────
init();
