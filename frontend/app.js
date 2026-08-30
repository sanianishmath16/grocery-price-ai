/**
 * app.js — GroceryAI frontend logic (v3 — with image search)
 *
 * TEXT SEARCH API  (unchanged):
 *   POST /api/compare  { items: string[], pincode: string }
 *   → CompareResponse  { results: AppPrice[], savings_tip: string, query_items: GroceryItem[] }
 *
 * IMAGE SEARCH API  (new):
 *   POST /api/analyze-images  { images_b64: string[], pincode: string }
 *   → ImageAnalyzeResponse {
 *       vision_status: "ok"|"not_configured"|"no_products"|"error",
 *       detected: DetectedProduct[],
 *       compare_result: CompareResponse | null,
 *       error_message: string
 *     }
 */

"use strict";

// ─── Config ────────────────────────────────────────────────────────────────
// API_BASE is always same-origin ("") — nginx proxies /api/* to FastAPI
// in every environment: Docker local, VPS, Render, Fly.io, Railway.
// No backend URL is ever hardcoded or exposed in this file.
// The only time you would change this is if you serve the frontend from a
// completely separate domain; in that case set window.__GROCERYAI_API
// from an injected <script> tag in index.html (see deploy docs).
const API_BASE = window.__GROCERYAI_API || "";

const MAX_IMAGES = 10;
const MAX_IMAGE_PX = 1024;     // resize longest edge to this before upload
const JPEG_QUALITY = 0.82;     // canvas JPEG compression quality
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

const APP_CONFIG = {
  blinkit:   { icon: "⚡", label: "Blinkit" },
  zepto:     { icon: "🟣", label: "Zepto" },
  instamart: { icon: "🍊", label: "Instamart" },
  flipkart:  { icon: "🔵", label: "Flipkart Min." },
};

// ─── DOM refs — Text search ─────────────────────────────────────────────────
const itemsInput     = document.getElementById("items-input");
const pincodeInput   = document.getElementById("pincode-input");
const compareBtn     = document.getElementById("compare-btn");
const errorMsg       = document.getElementById("error-msg");
const pincodeError   = document.getElementById("pincode-error");
const loadingSection = document.getElementById("loading-section");
const formSection    = document.getElementById("form-section");
const resultsSection = document.getElementById("results-section");
const savingsTip     = document.getElementById("savings-tip");
const appCardsEl     = document.getElementById("app-cards");
const breakdownSec   = document.getElementById("breakdown-section");
const itemCount      = document.getElementById("item-count");
const clearBtn       = document.getElementById("clear-btn");

// ─── DOM refs — Image search ────────────────────────────────────────────────
const imgPincodeInput  = document.getElementById("img-pincode-input");
const imgPincodeError  = document.getElementById("img-pincode-error");
const analyseBtn       = document.getElementById("analyse-btn");
const imgErrorMsg      = document.getElementById("img-error-msg");
const imgUploadError   = document.getElementById("img-upload-error");
const imgLoadingSection = document.getElementById("img-loading-section");
const imgLoadingTitle  = document.getElementById("img-loading-title");
const imgLoadingSub    = document.getElementById("img-loading-sub");
const detectedSection  = document.getElementById("detected-section");
const detectedList     = document.getElementById("detected-list");
const imgResultsSec    = document.getElementById("img-results-section");
const imgSavingsTip    = document.getElementById("img-savings-tip");
const imgAppCardsEl    = document.getElementById("img-app-cards");
const imgBreakdownSec  = document.getElementById("img-breakdown-section");
const dropZone         = document.getElementById("drop-zone");
const fileInput        = document.getElementById("file-input");
const browseBtn        = document.getElementById("browse-btn");
const thumbGrid        = document.getElementById("thumb-grid");
const uploadCount      = document.getElementById("upload-count");
const clearImagesBtn   = document.getElementById("clear-images-btn");
const visionNotice     = document.getElementById("vision-notice");

// ─── Tab state ──────────────────────────────────────────────────────────────
function switchTab(tab) {
  const isText = tab === "text";
  document.getElementById("tab-text").classList.toggle("active", isText);
  document.getElementById("tab-image").classList.toggle("active", !isText);
  document.getElementById("tab-text").setAttribute("aria-selected", String(isText));
  document.getElementById("tab-image").setAttribute("aria-selected", String(!isText));
  document.getElementById("panel-text").classList.toggle("hidden", !isText);
  document.getElementById("panel-image").classList.toggle("hidden", isText);
}

// ─── Image state ────────────────────────────────────────────────────────────
/** @type {{ file: File, b64: string, objectUrl: string }[]} */
let uploadedImages = [];

// ─── Item counter (text search) ─────────────────────────────────────────────
function updateItemCount() {
  const n = getItems().length;
  itemCount.textContent = n === 0 ? "0 items" : n === 1 ? "1 item" : `${n} items`;
}

function getItems() {
  return itemsInput.value.split("\n").map(s => s.trim()).filter(Boolean);
}

itemsInput.addEventListener("input", updateItemCount);
clearBtn.addEventListener("click", () => { itemsInput.value = ""; updateItemCount(); itemsInput.focus(); });

// ─── Helpers ────────────────────────────────────────────────────────────────
function showError(el, msg) {
  el.textContent = msg;
  el.classList.remove("hidden");
}

function clearError(el) {
  el.textContent = "";
  el.classList.add("hidden");
}

function showPincodeErr(errEl, inputEl, show) {
  errEl.classList.toggle("hidden", !show);
  inputEl.classList.toggle("invalid", show);
}

function setTextLoading(on) {
  loadingSection.classList.toggle("hidden", !on);
  formSection.classList.toggle("hidden", on);
  compareBtn.disabled = on;
  compareBtn.querySelector(".btn-text").classList.toggle("hidden", on);
  compareBtn.querySelector(".btn-loading").classList.toggle("hidden", !on);
}

function setImageLoading(on) {
  imgLoadingSection.classList.toggle("hidden", !on);
  // hide the upload grid while loading; keep pincode card visible via loading section
  document.querySelector(".img-search-grid").classList.toggle("hidden", on);
  analyseBtn.disabled = on;
  analyseBtn.querySelector(".btn-text").classList.toggle("hidden", on);
  analyseBtn.querySelector(".btn-loading").classList.toggle("hidden", !on);
}

function updateLoadingStep(title, sub) {
  imgLoadingTitle.textContent = title;
  imgLoadingSub.textContent = sub;
}

function formatPrice(n)     { return "₹" + n.toFixed(0); }
function formatPriceFull(n) { return "₹" + n.toFixed(2); }

function confClass(s) {
  if (s === 0)  return "conf-none";
  if (s >= 0.7) return "conf-high";
  if (s >= 0.4) return "conf-mid";
  return "conf-low";
}

function confLabel(s) {
  if (s === 0)  return "Not found";
  if (s >= 0.7) return "Match";
  if (s >= 0.4) return "~Match";
  return "Low";
}

// ─── Image compression ───────────────────────────────────────────────────────
/**
 * Resize a File to ≤ MAX_IMAGE_PX on the longest side, then return base64 JPEG.
 * @param {File} file
 * @returns {Promise<string>} raw base64 (no data URI prefix)
 */
async function compressImage(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      let { width: w, height: h } = img;
      if (w > MAX_IMAGE_PX || h > MAX_IMAGE_PX) {
        const ratio = MAX_IMAGE_PX / Math.max(w, h);
        w = Math.round(w * ratio);
        h = Math.round(h * ratio);
      }
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      canvas.getContext("2d").drawImage(img, 0, 0, w, h);
      const dataUrl = canvas.toDataURL("image/jpeg", JPEG_QUALITY);
      // strip "data:image/jpeg;base64,"
      resolve(dataUrl.split(",")[1]);
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Could not load image")); };
    img.src = url;
  });
}

// ─── Image upload handling ───────────────────────────────────────────────────
async function addFiles(files) {
  clearError(imgUploadError);
  const incoming = Array.from(files);

  // Validate types
  const bad = incoming.filter(f => !ALLOWED_TYPES.has(f.type));
  if (bad.length) {
    showError(imgUploadError, `Please upload JPG, PNG, or WebP images only.`);
    return;
  }

  // Cap at 10
  const remaining = MAX_IMAGES - uploadedImages.length;
  if (remaining <= 0) {
    showError(imgUploadError, `Maximum ${MAX_IMAGES} images allowed. Remove some before adding more.`);
    return;
  }

  const toAdd = incoming.slice(0, remaining);
  if (incoming.length > remaining) {
    showError(imgUploadError, `Only added ${toAdd.length} image(s). Maximum is ${MAX_IMAGES} total.`);
  }

  // Compress and add
  for (const file of toAdd) {
    try {
      const b64 = await compressImage(file);
      const objectUrl = URL.createObjectURL(file);
      uploadedImages.push({ file, b64, objectUrl });
    } catch {
      showError(imgUploadError, `Could not process image: ${file.name}`);
    }
  }

  renderThumbs();
}

function removeImage(idx) {
  URL.revokeObjectURL(uploadedImages[idx].objectUrl);
  uploadedImages.splice(idx, 1);
  renderThumbs();
  clearError(imgUploadError);
}

function clearAllImages() {
  uploadedImages.forEach(img => URL.revokeObjectURL(img.objectUrl));
  uploadedImages = [];
  renderThumbs();
  clearError(imgUploadError);
}

function renderThumbs() {
  uploadCount.textContent = `${uploadedImages.length} / ${MAX_IMAGES} photos`;
  thumbGrid.innerHTML = "";

  uploadedImages.forEach((item, idx) => {
    const div = document.createElement("div");
    div.className = "thumb-item";

    const img = document.createElement("img");
    img.src = item.objectUrl;
    img.alt = `Grocery image ${idx + 1}: ${item.file.name}`;
    img.loading = "lazy";

    const btn = document.createElement("button");
    btn.className = "thumb-remove";
    btn.type = "button";
    btn.setAttribute("aria-label", `Remove image ${idx + 1}`);
    btn.innerHTML = "×";
    btn.addEventListener("click", (e) => { e.stopPropagation(); removeImage(idx); });

    div.appendChild(img);
    div.appendChild(btn);
    thumbGrid.appendChild(div);
  });
}

// ─── Drop zone events ────────────────────────────────────────────────────────
dropZone.addEventListener("click", (e) => {
  if (e.target === browseBtn || browseBtn.contains(e.target)) return;
  fileInput.click();
});

browseBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  fileInput.click();
});

dropZone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
});

fileInput.addEventListener("change", (e) => {
  if (e.target.files.length) addFiles(e.target.files);
  e.target.value = ""; // allow re-uploading same file
});

dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragleave", ()  => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
});

clearImagesBtn.addEventListener("click", clearAllImages);

// Pincode digit-only enforcement (both inputs)
[pincodeInput, imgPincodeInput].forEach(inp => {
  inp.addEventListener("input", () => {
    inp.value = inp.value.replace(/\D/g, "").slice(0, 6);
  });
});

pincodeInput.addEventListener("keydown", e => { if (e.key === "Enter") compareItems(); });
imgPincodeInput.addEventListener("keydown", e => { if (e.key === "Enter") analyseImages(); });

// ─── TEXT SEARCH ─────────────────────────────────────────────────────────────
async function compareItems() {
  clearError(errorMsg);
  showPincodeErr(pincodeError, pincodeInput, false);

  const rawItems = getItems();
  if (rawItems.length === 0) {
    showError(errorMsg, "Please enter at least one grocery item.");
    itemsInput.focus();
    return;
  }

  const pincode = pincodeInput.value.trim();
  if (!/^\d{6}$/.test(pincode)) {
    showPincodeErr(pincodeError, pincodeInput, true);
    pincodeInput.focus();
    return;
  }

  setTextLoading(true);
  resultsSection.classList.add("hidden");

  try {
    const resp = await fetch(`${API_BASE}/api/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: rawItems, pincode }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${resp.status}`);
    }

    const data = await resp.json();
    renderCompareResults(data, appCardsEl, breakdownSec, savingsTip, resultsSection);

  } catch (err) {
    setTextLoading(false);
    const msg = err.message.includes("fetch") || err.message.includes("NetworkError")
      ? "Could not connect to GroceryAI. Please check your connection and try again."
      : "Something went wrong while comparing prices. Please try again.";
    showError(errorMsg, msg);
  }
}

function renderCompareResults(data, cardsEl, bdSec, tipEl, resultsSec) {
  setTextLoading(false);

  if (data.savings_tip) {
    tipEl.innerHTML = `
      <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14" style="flex-shrink:0;color:var(--green-dark)" aria-hidden="true">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
      </svg>
      ${data.savings_tip}`;
    tipEl.classList.remove("hidden");
  } else {
    tipEl.classList.add("hidden");
  }

  cardsEl.innerHTML = "";
  data.results.forEach((app, idx) => cardsEl.appendChild(buildAppCard(app, idx)));

  bdSec.innerHTML = "";
  if (data.query_items && data.query_items.length > 0) {
    bdSec.appendChild(buildBreakdownSection(data));
  }

  resultsSec.classList.remove("hidden");
  resultsSec.scrollIntoView({ behavior: "smooth", block: "start" });
}

function buildAppCard(app, rank) {
  const isBest = rank === 0;
  const cfg    = APP_CONFIG[app.app_name] || { icon: "🛒", label: app.app_name };
  const rankEmoji = ["🥇", "🥈", "🥉", "4️⃣"][rank] || `${rank + 1}`;
  const totalItems = app.items_found + app.items_missing.length;

  const deliveryHtml = app.delivery_fee > 0
    ? `<span class="app-card-delivery">+${formatPrice(app.delivery_fee)} delivery</span>`
    : `<span class="app-card-delivery free">Free delivery</span>`;

  const savingsHtml = app.savings > 0
    ? `<div class="app-card-savings">Save ${formatPrice(app.savings)} vs costliest</div>`
    : "";

  const missingHtml = app.items_missing.length > 0
    ? `<div class="app-card-missing">⚠ Not found: ${app.items_missing.join(", ")}</div>`
    : "";

  const card = document.createElement("div");
  card.className = "app-card" + (isBest ? " best" : "");
  card.dataset.appName = app.app_name;

  card.innerHTML = `
    <div class="app-card-rank" aria-label="Rank ${rank + 1}">${rankEmoji}</div>
    <div class="app-card-icon" aria-hidden="true">${cfg.icon}</div>
    <div class="app-card-name">${cfg.label}</div>
    ${isBest ? '<div class="best-badge">Best Deal</div>' : ""}
    <div class="app-card-price" aria-label="Total ${formatPrice(app.total_price)}">${formatPrice(app.total_price)}</div>
    ${deliveryHtml}
    <div class="app-card-items">${app.items_found} of ${totalItems} items found</div>
    ${savingsHtml}
    ${missingHtml}
  `;
  return card;
}

function buildBreakdownSection(data) {
  const wrapper = document.createElement("div");
  wrapper.className = "breakdown-card";

  const toggle = document.createElement("button");
  toggle.className = "breakdown-toggle";
  toggle.setAttribute("aria-expanded", "false");
  toggle.innerHTML = `<span>Per-item Price Breakdown</span><span class="breakdown-toggle-icon" aria-hidden="true">▾</span>`;

  const tableWrap = document.createElement("div");
  tableWrap.className = "breakdown-table-wrap hidden";

  let open = false;
  toggle.addEventListener("click", () => {
    open = !open;
    toggle.classList.toggle("open", open);
    toggle.setAttribute("aria-expanded", String(open));
    tableWrap.classList.toggle("hidden", !open);
  });

  const appNames = data.results.map(a => APP_CONFIG[a.app_name]?.label || a.app_name);
  const table = document.createElement("table");
  table.className = "breakdown-table";

  const thead = document.createElement("thead");
  thead.innerHTML = `<tr><th scope="col">Item</th>${appNames.map(n => `<th scope="col">${n}</th>`).join("")}</tr>`;
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  data.query_items.forEach((item, itemIdx) => {
    const appMatches = data.results.map(app =>
      app.matches.find(m => m.query.toLowerCase().includes(item.name.toLowerCase()))
      || app.matches[itemIdx]
      || null
    );
    const prices  = appMatches.filter(m => m && m.found).map(m => m.price);
    const minPrice = prices.length ? Math.min(...prices) : null;

    const tr = document.createElement("tr");
    const tdItem = document.createElement("td");
    tdItem.innerHTML = `<strong>${item.raw}</strong>`;
    tr.appendChild(tdItem);

    appMatches.forEach(match => {
      const td = document.createElement("td");
      if (!match || !match.found) {
        td.innerHTML = `<span class="conf-pill conf-none">Not found</span>`;
      } else {
        if (minPrice !== null && Math.abs(match.price - minPrice) < 0.001) td.classList.add("cheapest-cell");
        td.innerHTML = `<span class="price-wrap">${formatPriceFull(match.price)}</span><br><span class="conf-pill ${confClass(match.confidence)}">${confLabel(match.confidence)}</span>`;
      }
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  tableWrap.appendChild(table);
  wrapper.appendChild(toggle);
  wrapper.appendChild(tableWrap);
  return wrapper;
}

// ─── TEXT SEARCH RESET ───────────────────────────────────────────────────────
function resetForm() {
  resultsSection.classList.add("hidden");
  formSection.classList.remove("hidden");
  clearError(errorMsg);
  showPincodeErr(pincodeError, pincodeInput, false);
  window.scrollTo({ top: 0, behavior: "smooth" });
  itemsInput.focus();
}

// ─── IMAGE SEARCH ─────────────────────────────────────────────────────────────
async function analyseImages() {
  clearError(imgErrorMsg);
  clearError(imgUploadError);
  showPincodeErr(imgPincodeError, imgPincodeInput, false);
  visionNotice.classList.add("hidden");

  if (uploadedImages.length === 0) {
    showError(imgUploadError, "Please upload at least one grocery image.");
    return;
  }

  const pincode = imgPincodeInput.value.trim();
  if (!/^\d{6}$/.test(pincode)) {
    showPincodeErr(imgPincodeError, imgPincodeInput, true);
    imgPincodeInput.focus();
    return;
  }

  // Hide previous results
  detectedSection.classList.add("hidden");
  imgResultsSec.classList.add("hidden");

  setImageLoading(true);
  updateLoadingStep("Analysing images…", `Processing ${uploadedImages.length} image(s)`);

  try {
    const images_b64 = uploadedImages.map(img => img.b64);

    updateLoadingStep("Detecting products…", "Identifying grocery items in your photos");

    const resp = await fetch(`${API_BASE}/api/analyze-images`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ images_b64, pincode }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${resp.status}`);
    }

    const data = await resp.json();
    setImageLoading(false);
    handleImageResponse(data, pincode);

  } catch (err) {
    setImageLoading(false);
    showError(imgErrorMsg, "Image analysis failed: " + err.message);
    document.querySelector(".img-search-grid").classList.remove("hidden");
  }
}

function handleImageResponse(data, pincode) {
  // Re-show the upload grid
  document.querySelector(".img-search-grid").classList.remove("hidden");

  const status = data.vision_status;

  // ── Not configured (no API key set) ──────────────────────────────────────
  if (status === "not_configured") {
    visionNotice.classList.remove("hidden");
    return;
  }

  // ── Quota exhausted (credits used up) ────────────────────────────────────
  if (status === "quota_exhausted") {
    showVisionUnavailable(
      "Image recognition is temporarily unavailable because the AI service has reached its usage limit.",
      "You can still use text search to compare grocery prices."
    );
    return;
  }

  // ── Transient rate limit ──────────────────────────────────────────────────
  if (status === "rate_limited") {
    showError(imgErrorMsg,
      "The AI service is currently busy. Please wait a moment and try again. Text search is still available."
    );
    return;
  }

  // ── Authentication / key problem ─────────────────────────────────────────
  if (status === "auth_error") {
    showError(imgErrorMsg,
      "Image recognition could not connect to the AI service. Please contact the site administrator."
    );
    return;
  }

  // ── Generic error or no products found ───────────────────────────────────
  if (status === "error" || status === "no_products") {
    const msg = data.error_message
      || "We couldn't identify any products. Try uploading a clearer image.";
    showError(imgErrorMsg, msg);
    return;
  }

  // ── OK — show detected products for review ───────────────────────────────
  if (data.detected && data.detected.length > 0) {
    renderDetectedProducts(data.detected);

    // If we already have compare results, show them immediately below
    if (data.compare_result) {
      renderImageCompareResults(data.compare_result);
    }
  } else {
    showError(imgErrorMsg, "No grocery products were identified in the uploaded images.");
  }
}

/**
 * Show the info notice (amber box) with custom headline and subtitle.
 * Used for quota_exhausted, not_configured, auth_error.
 */
function showVisionUnavailable(headline, sub) {
  const titleEl = document.getElementById("vision-notice-title");
  const subEl   = document.getElementById("vision-notice-sub");
  if (titleEl) titleEl.textContent = headline;
  if (subEl)   subEl.textContent   = sub;
  visionNotice.classList.remove("hidden");
}

function renderDetectedProducts(detected) {
  detectedList.innerHTML = "";
  detected.forEach((product, idx) => {
    const item = document.createElement("div");
    item.className = "detected-item";
    item.dataset.idx = idx;

    const check = document.createElement("span");
    check.className = "detected-check";
    check.setAttribute("aria-hidden", "true");
    check.textContent = "✓";

    const input = document.createElement("input");
    input.type = "text";
    input.value = product.name;
    input.setAttribute("aria-label", `Detected product ${idx + 1}: ${product.name}. Edit to change.`);

    const removeBtn = document.createElement("button");
    removeBtn.className = "detected-remove";
    removeBtn.type = "button";
    removeBtn.setAttribute("aria-label", `Remove ${product.name}`);
    removeBtn.innerHTML = `<svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>`;
    removeBtn.addEventListener("click", () => { item.remove(); });

    item.appendChild(check);
    item.appendChild(input);
    item.appendChild(removeBtn);
    detectedList.appendChild(item);
  });

  detectedSection.classList.remove("hidden");
  detectedSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function compareDetected() {
  // Collect current (possibly edited) product names from inputs
  const inputs = Array.from(detectedList.querySelectorAll("input[type='text']"));
  const items = inputs.map(i => i.value.trim()).filter(Boolean);

  if (items.length === 0) {
    showError(imgErrorMsg, "Please keep at least one detected product to compare.");
    return;
  }

  const pincode = imgPincodeInput.value.trim();
  if (!/^\d{6}$/.test(pincode)) {
    showPincodeErr(imgPincodeError, imgPincodeInput, true);
    imgPincodeInput.focus();
    return;
  }

  // Reuse compare-detected button as loading indicator
  const btn = document.getElementById("compare-detected-btn");
  btn.disabled = true;
  const origText = btn.innerHTML;
  btn.innerHTML = `<span class="btn-spinner" style="border:2px solid rgba(255,255,255,.35);border-top-color:#fff;width:15px;height:15px;border-radius:50%;animation:spin .7s linear infinite;display:inline-block;margin-right:6px"></span> Comparing…`;

  try {
    const resp = await fetch(`${API_BASE}/api/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items, pincode }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${resp.status}`);
    }

    const data = await resp.json();
    renderImageCompareResults(data);

  } catch (err) {
    showError(imgErrorMsg, "Could not compare prices: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = origText;
  }
}

function renderImageCompareResults(data) {
  if (data.savings_tip) {
    imgSavingsTip.innerHTML = `
      <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14" style="flex-shrink:0" aria-hidden="true">
        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
      </svg>
      ${data.savings_tip}`;
    imgSavingsTip.classList.remove("hidden");
  } else {
    imgSavingsTip.classList.add("hidden");
  }

  imgAppCardsEl.innerHTML = "";
  data.results.forEach((app, idx) => imgAppCardsEl.appendChild(buildAppCard(app, idx)));

  imgBreakdownSec.innerHTML = "";
  if (data.query_items && data.query_items.length > 0) {
    imgBreakdownSec.appendChild(buildBreakdownSection(data));
  }

  imgResultsSec.classList.remove("hidden");
  imgResultsSec.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ─── IMAGE SEARCH RESET ──────────────────────────────────────────────────────
function resetImageSearch() {
  imgResultsSec.classList.add("hidden");
  detectedSection.classList.add("hidden");
  imgLoadingSection.classList.add("hidden");
  document.querySelector(".img-search-grid").classList.remove("hidden");
  clearAllImages();
  clearError(imgErrorMsg);
  clearError(imgUploadError);
  showPincodeErr(imgPincodeError, imgPincodeInput, false);
  visionNotice.classList.add("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}
