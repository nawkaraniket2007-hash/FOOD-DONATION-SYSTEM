const $ = (id) => document.getElementById(id);
const messageBox = $("message");
let messageTimer;

function showMessage(text, type = "success") {
  clearTimeout(messageTimer);
  messageBox.textContent = text;
  messageBox.className = `message show ${type}`;
  messageTimer = setTimeout(() => messageBox.classList.remove("show"), 5000);
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || "Request failed.");
  return body;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function badge(status) {
  return `<span class="badge ${esc(status).toLowerCase()}">${esc(status)}</span>`;
}

function donationCard(d, mode = "manage") {
  const actions = mode === "manage"
    ? `${d.status === "Available" ? `<button class="button secondary" data-action="edit" data-id="${d.id}">Edit</button>` : ""}
       <button class="button secondary" data-action="details" data-id="${d.id}">Details</button>`
    : `<button class="button primary" data-action="request" data-id="${d.id}" data-name="${esc(d.food_name)}">Request donation</button>
       <button class="button secondary" data-action="details" data-id="${d.id}">Details</button>`;

  return `<article class="donation-card">
    <div class="card-top"><div><h3>${esc(d.food_name)}</h3><p class="muted">${esc(d.category)}</p></div>${badge(d.status)}</div>
    <div class="card-details">
      <div class="detail">Quantity<strong>${esc(d.quantity)} ${esc(d.unit)}</strong></div>
      <div class="detail">Pickup location<strong>${esc(d.pickup_location)}</strong></div>
      <div class="detail">Expiry<strong>${esc(formatDate(d.expiry_datetime))}</strong></div>
      <div class="detail">Donor<strong>${esc(d.donor_name)}</strong></div>
    </div>
    <div class="card-actions">${actions}</div>
  </article>`;
}

function emptyCard(text) {
  return `<div class="empty">${esc(text)}</div>`;
}

async function loadDonations() {
  const donations = await api("/api/donations");
  $("manage-donations").innerHTML = donations.length
    ? donations.map(d => donationCard(d, "manage")).join("")
    : emptyCard("No donations have been added yet.");
  await loadCategories();
}

async function loadAvailable() {
  const params = new URLSearchParams({ status: "Available" });
  const search = $("search-input").value.trim();
  const category = $("category-filter").value;
  if (search) params.set("search", search);
  if (category) params.set("category", category);
  const donations = await api(`/api/donations?${params}`);
  $("available-donations").innerHTML = donations.length
    ? donations.map(d => donationCard(d, "discover")).join("")
    : emptyCard("No matching available donations were found.");
}

async function loadCategories() {
  const categories = await api("/api/categories");
  const select = $("category-filter");
  const current = select.value;
  select.innerHTML = '<option value="">All categories</option>' +
    categories.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
  if (categories.includes(current)) select.value = current;
}

async function loadRequests() {
  const requests = await api("/api/requests");
  $("requests-list").innerHTML = requests.length ? requests.map(r => {
    let actions = "";
    if (r.status === "Pending") {
      actions = `<button class="button primary" data-action="approve" data-id="${r.id}">Approve</button>
                 <button class="button danger" data-action="reject" data-id="${r.id}">Reject</button>`;
    } else if (r.status === "Approved") {
      actions = `<button class="button primary" data-action="complete" data-id="${r.id}">Mark completed</button>`;
    }
    return `<article class="request-card">
      <div class="card-top"><div><h3>${esc(r.food_name)}</h3><p class="muted">Request #${r.id} · Donation #${r.donation_id}</p></div>${badge(r.status)}</div>
      <div class="card-details">
        <div class="detail">Recipient<strong>${esc(r.recipient_name)}</strong></div>
        <div class="detail">Contact<strong>${esc(r.recipient_contact)}</strong></div>
        <div class="detail">Pickup location<strong>${esc(r.pickup_location || "—")}</strong></div>
        <div class="detail">Donation status<strong>${esc(r.donation_status)}</strong></div>
      </div>
      <div class="card-actions">${actions || '<span class="muted">No further actions available.</span>'}</div>
    </article>`;
  }).join("") : emptyCard("No donation requests have been submitted.");
}

function switchTab(panelId) {
  document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.tab === panelId));
  document.querySelectorAll(".panel").forEach(panel => panel.classList.toggle("hidden", panel.id !== panelId));
  if (panelId === "discover-panel") loadAvailable().catch(err => showMessage(err.message, "error"));
  if (panelId === "requests-panel") loadRequests().catch(err => showMessage(err.message, "error"));
}

document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => switchTab(tab.dataset.tab)));

function formData() {
  return {
    food_name: $("food-name").value.trim(),
    category: $("category").value,
    quantity: $("quantity").value,
    unit: $("unit").value,
    expiry_datetime: $("expiry-datetime").value,
    pickup_location: $("pickup-location").value.trim(),
    donor_name: $("donor-name").value.trim(),
    donor_contact: $("donor-contact").value.trim(),
    notes: $("notes").value.trim()
  };
}

function resetDonationForm() {
  $("donation-form").reset();
  $("donation-id").value = "";
  $("donation-form-title").textContent = "Add a food donation";
  $("save-donation-button").textContent = "Save donation";
  $("cancel-edit-button").classList.add("hidden");
}

$("donation-form").addEventListener("submit", async event => {
  event.preventDefault();
  const id = $("donation-id").value;
  try {
    const result = await api(id ? `/api/donations/${id}` : "/api/donations", {
      method: id ? "PUT" : "POST",
      body: JSON.stringify(formData())
    });
    showMessage(result.message);
    resetDonationForm();
    await loadDonations();
    await loadAvailable();
  } catch (error) {
    showMessage(error.message, "error");
  }
});

$("cancel-edit-button").addEventListener("click", resetDonationForm);
$("refresh-donations").addEventListener("click", () => loadDonations().catch(e => showMessage(e.message, "error")));
$("refresh-requests").addEventListener("click", () => loadRequests().catch(e => showMessage(e.message, "error")));
$("search-button").addEventListener("click", () => loadAvailable().catch(e => showMessage(e.message, "error")));
$("category-filter").addEventListener("change", () => loadAvailable().catch(e => showMessage(e.message, "error")));
$("search-input").addEventListener("keydown", event => {
  if (event.key === "Enter") {
    event.preventDefault();
    loadAvailable().catch(e => showMessage(e.message, "error"));
  }
});
$("clear-search-button").addEventListener("click", () => {
  $("search-input").value = "";
  $("category-filter").value = "";
  loadAvailable().catch(e => showMessage(e.message, "error"));
});

document.addEventListener("click", async event => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const action = button.dataset.action;
  const id = button.dataset.id;

  try {
    if (action === "edit") {
      const d = await api(`/api/donations/${id}`);
      if (d.status !== "Available") throw new Error("Only Available donations can be edited.");
      $("donation-id").value = d.id;
      $("food-name").value = d.food_name;
      $("category").value = d.category;
      $("quantity").value = d.quantity;
      $("unit").value = d.unit;
      $("expiry-datetime").value = d.expiry_datetime.slice(0, 16);
      $("pickup-location").value = d.pickup_location;
      $("donor-name").value = d.donor_name;
      $("donor-contact").value = d.donor_contact;
      $("notes").value = d.notes || "";
      $("donation-form-title").textContent = `Edit donation #${d.id}`;
      $("save-donation-button").textContent = "Save changes";
      $("cancel-edit-button").classList.remove("hidden");
      window.scrollTo({ top: 0, behavior: "smooth" });
    } else if (action === "details") {
      const d = await api(`/api/donations/${id}`);
      showMessage(`${d.food_name}: ${d.quantity} ${d.unit}; expiry ${formatDate(d.expiry_datetime)}; donor ${d.donor_name}; contact ${d.donor_contact}. Notes: ${d.notes || "None"}`);
    } else if (action === "request") {
      $("request-donation-id").value = id;
      $("request-food-title").textContent = `Requesting: ${button.dataset.name}`;
      $("request-form").reset();
      $("request-donation-id").value = id;
      $("request-dialog").showModal();
    } else if (["approve", "reject", "complete"].includes(action)) {
      const result = await api(`/api/requests/${id}/decision`, {
        method: "PATCH",
        body: JSON.stringify({ action })
      });
      showMessage(result.message);
      await loadRequests();
      await loadDonations();
      await loadAvailable();
    }
  } catch (error) {
    showMessage(error.message, "error");
  }
});

$("request-form").addEventListener("submit", async event => {
  event.preventDefault();
  const id = $("request-donation-id").value;
  try {
    const result = await api(`/api/donations/${id}/requests`, {
      method: "POST",
      body: JSON.stringify({
        recipient_name: $("recipient-name").value.trim(),
        recipient_contact: $("recipient-contact").value.trim()
      })
    });
    $("request-dialog").close();
    showMessage(result.message);
    await loadAvailable();
    await loadDonations();
    await loadRequests();
  } catch (error) {
    showMessage(error.message, "error");
  }
});

$("close-dialog").addEventListener("click", () => $("request-dialog").close());
$("cancel-request").addEventListener("click", () => $("request-dialog").close());

Promise.all([loadDonations(), loadAvailable(), loadRequests()])
  .catch(error => showMessage(error.message, "error"));
