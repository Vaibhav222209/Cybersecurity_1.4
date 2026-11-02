"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
let session = null;
let state = null;
let csrf = "";
let activeView = "overview";
let activeOps = "approvals";
let pendingPayment = null;
let busy = false;
let toastTimer;
let dialogTrigger;
const francs = new Intl.NumberFormat("en-CH", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const readable = {pending_review: "Awaiting review", settled: "Settled", rejected: "Rejected", active: "Active", admin: "Administrator", operator: "Security operator", customer: "Banking customer"};

function el(tag, className = "", text = "") {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}
function append(parent, ...children) { children.filter(Boolean).forEach((child) => parent.append(child)); return parent; }
function money(cents, currency = true) { return (currency ? "CHF " : "") + francs.format(Number(cents || 0) / 100); }
function date(value, detail = false) {
  if (!value || Number.isNaN(new Date(value).getTime())) return "—";
  return new Date(value).toLocaleString("en-GB", {timeZone: "Europe/Zurich", day: "2-digit", month: "short", ...(detail ? {hour: "2-digit", minute: "2-digit"} : {year: "numeric"})});
}
function badge(value, label) {
  const safe = ["pending_review", "settled", "rejected", "active", "high", "critical", "medium", "info", "neutral", "warning", "error"].includes(value) ? value : "neutral";
  return el("span", "badge " + safe, label || readable[value] || value);
}
function toast(message, error = false) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.toggle("error", error);
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, error ? 9000 : 6000);
}
function connection(online) {
  $("#connection").classList.toggle("offline", !online);
  $("#connection").replaceChildren(el("i"), document.createTextNode(online ? "Secure local session" : "Connection interrupted"));
}
async function api(path, body) {
  const options = {credentials: "same-origin", headers: {Accept: "application/json"}};
  if (body !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.headers["X-CSRF-Token"] = csrf;
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({error: "The server returned an unreadable response"}));
  if (!response.ok) {
    const error = new Error(payload.error || `Request could not be completed (${response.status})`);
    error.status = response.status;
    if (response.status === 401 && path !== "/api/login" && path !== "/api/setup") await signedOut("Your session has ended. Please sign in again.");
    throw error;
  }
  return payload;
}
async function loadSession() {
  session = await api("/api/session");
  csrf = session.csrf_token;
  return session;
}
function authScreen(message = "") {
  $("#app-shell").hidden = true;
  $("#auth-screen").hidden = false;
  $("#auth-loading").hidden = true;
  $("#auth-form").hidden = false;
  const setup = Boolean(session?.setup_required);
  $("#setup-name-wrap").hidden = !setup;
  $("#display-name").required = setup;
  $("#otp-wrap").hidden = setup;
  $("#password").minLength = setup ? 12 : 1;
  $("#password").autocomplete = setup ? "new-password" : "current-password";
  $("#auth-title").textContent = setup ? "A new standard. Your workspace." : "Your private banking, securely connected.";
  $("#auth-eyebrow").textContent = setup ? "CREATE YOUR LOCAL BANK" : "WELCOME BACK TO PORTBUG";
  $("#auth-description").textContent = setup ? "Create the first administrator account. Choose a unique local password of at least 12 characters. Synthetic accounts are prepared for you." : "Sign in to your local banking workspace. Use your authenticator code if two-step verification is enabled.";
  $("#auth-submit").replaceChildren(document.createTextNode(setup ? "Create secure workspace" : "Sign in securely"), el("span", "", "→"));
  $("#auth-error").textContent = message;
  $("#auth-error").hidden = !message;
}
async function signedOut(message = "") {
  state = null;
  pendingPayment = null;
  csrf = "";
  $("#password").value = "";
  $("#otp").value = "";
  $("#mfa-secret").value = "";
  $("#mfa-code").value = "";
  $("#mfa-enrollment").hidden = true;
  $("#user-form").reset();
  $("#payment-form").reset();
  $("#rules-form").reset();
  $("#payment-result").hidden = true;
  for (const id of ["portfolio-accounts", "account-cards", "recent-activity", "flow-chart", "activity-table", "approval-queue", "approval-summary", "event-timeline", "audit-summary", "users-list", "payment-result", "backtest-result", "session-detail", "security-checks", "detail-dialog-content", "payment-dialog-content"]) $("#" + id).replaceChildren();
  $("#profile-name").textContent = "";
  $("#total-balance").textContent = "—";
  for (const dialog of $$("dialog[open]")) dialog.close();
  try { await loadSession(); } catch (_) { session = {setup_required: false, user: null}; }
  authScreen(message);
}
function isOperator() { return ["admin", "operator"].includes(session?.user?.role); }
function ownAccounts() { return (state?.accounts || []).filter((account) => account.owner_id === session.user.id); }
function ownTransfers() {
  const ids = new Set(ownAccounts().map((account) => account.id));
  return (state?.transfers || []).filter((payment) => ids.has(payment.from_account) || ids.has(payment.to_account)).sort((a, b) => b.created_at.localeCompare(a.created_at));
}
async function refresh(options = {}) {
  if (!session?.user) return;
  try {
    state = await api("/api/state");
    render();
    connection(true);
    if (!options.silent) toast("Balances, decisions and security evidence refreshed.");
  } catch (error) {
    connection(false);
    if (error.status !== 401) toast(error.message, true);
  }
}
async function enterWorkspace() {
  await loadSession();
  if (!session.user) { authScreen(); return; }
  state = await api("/api/state");
  $("#auth-screen").hidden = true;
  $("#app-shell").hidden = false;
  $("#profile-name").textContent = session.user.display_name;
  $("#profile-role").textContent = readable[session.user.role];
  $("#avatar").textContent = session.user.display_name.split(/\s+/).slice(0, 2).map((name) => name[0]).join("").toUpperCase();
  $("#operations-nav").hidden = !isOperator();
  $("#users-tab").hidden = session.user.role !== "admin";
  $("#save-rules").hidden = session.user.role !== "admin";
  $("#rules-permission").textContent = session.user.role === "admin" ? "Applying a policy changes future evaluations only. Existing held transfers still require an independent decision." : "Operators can test candidate policies. Only an administrator can apply a policy.";
  activeOps = "approvals";
  opsView("approvals");
  render();
  view(session.user.role === "operator" ? "operations" : "overview", false);
  if (session.user.role === "admin") await loadUsers();
}
function view(name, focus = true) {
  if (name === "operations" && !isOperator()) return;
  if (!["overview", "payments", "activity", "security", "operations"].includes(name)) return;
  activeView = name;
  $$(".view").forEach((node) => { node.hidden = node.id !== "view-" + name; });
  $$("[data-view]").forEach((node) => {
    node.classList.toggle("active", node.dataset.view === name);
    if (node.dataset.view === name) node.setAttribute("aria-current", "page"); else node.removeAttribute("aria-current");
  });
  if (focus) { $("#main").focus({preventScroll: true}); window.scrollTo({top: 0, behavior: "instant"}); }
}
function opsView(name) {
  if (name === "users" && session.user.role !== "admin") return;
  activeOps = name;
  $$(".ops-panel").forEach((node) => { node.hidden = node.id !== "ops-" + name; });
  $$("[data-ops]").forEach((node) => node.setAttribute("aria-selected", String(node.dataset.ops === name)));
}
function empty(title, description, icon = "◇") { return append(el("div", "empty-state"), el("span", "", icon), el("h3", "", title), el("p", "", description)); }
function detailList(pairs) {
  const list = el("dl", "detail-list");
  pairs.forEach(([key, value]) => list.append(append(el("div"), el("dt", "", key), el("dd", "", value))));
  return list;
}
function showDialog(id, trigger) {
  dialogTrigger = trigger || document.activeElement;
  const dialog = $("#" + id);
  if (!dialog.open) dialog.showModal();
  const heading = dialog.querySelector("h2");
  if (heading) { heading.tabIndex = -1; heading.focus(); }
}
function showAccount(account, trigger) {
  const heading = el("h2", "dialog-heading", account.label);
  heading.id = "detail-dialog-title";
  $("#detail-dialog-content").replaceChildren(el("p", "dialog-eyebrow", "YOUR ACCOUNT / CHF"), heading, el("div", "dialog-amount", money(account.balance_cents)), detailList([["Account identifier", account.identifier], ["Account type", account.kind], ["Status", readable[account.status] || account.status], ["Ownership", "Your authenticated identity"]]), el("p", "dialog-note", "This is a non-routable synthetic account. Available balance excludes funds already reserved for held payments."));
  showDialog("detail-dialog", trigger);
}
function renderAccounts() {
  const accounts = ownAccounts();
  $("#welcome").textContent = `Welcome, ${session.user.display_name.split(/\s+/)[0]}.`;
  $("#total-balance").textContent = money(accounts.reduce((total, account) => total + account.balance_cents, 0), false);
  $("#account-count").textContent = `${accounts.length} ${accounts.length === 1 ? "ACCOUNT" : "ACCOUNTS"}`;
  $("#portfolio-accounts").replaceChildren(...accounts.map((account) => append(el("div", "portfolio-account"), el("span", "", account.label), el("strong", "", money(account.balance_cents)))));
  $("#security-checks").replaceChildren(...[["Authenticated session", "Verified"], ["Account ownership", "Enforced"], ["Authenticator protection", session.user.mfa_enabled ? "Enabled" : "Not enrolled"]].map(([label, value]) => append(el("div", "security-check-row"), el("strong", "", label), el("span", "", value))));
  const cards = accounts.map((account) => {
    const more = el("button", "text-button", "Account details →");
    more.addEventListener("click", () => showAccount(account, more));
    return append(el("article", "account-card"), append(el("div", "account-top"), append(el("div"), el("p", "account-type", account.kind === "current" ? "EVERYDAY PRIVATE BANKING" : "YOUR LONGER VIEW"), el("h3", "account-name", account.label), el("p", "account-identifier", account.identifier)), el("span", "account-mark", account.kind === "current" ? "P" : "R")), append(el("div", "account-money"), document.createTextNode(money(account.balance_cents, false)), el("small", "", "CHF")), append(el("div", "account-card-foot"), badge(account.status), more));
  });
  $("#account-cards").replaceChildren(...(cards.length ? cards : [empty("Your operator workspace.", "This identity reviews payments and security events; it does not own customer accounts.")]));
  const from = $("#from-account");
  const selected = from.value;
  from.replaceChildren(...accounts.map((account) => {
    const option = el("option", "", `${account.label} · ${money(account.balance_cents)}`);
    option.value = account.id;
    return option;
  }));
  if (accounts.some((account) => account.id === selected)) from.value = selected;
  const canPay = accounts.length > 0 && session.user.role !== "operator";
  $("#payment-form").hidden = !canPay;
  $("#payment-access").replaceChildren(...(canPay ? [] : [el("p", "hidden-access", "Payments require a banking identity with an owned account. This operator identity is intended for independent decisions.")]));
  const beneficiary = $("#beneficiary");
  const previousBeneficiary = beneficiary.value;
  beneficiary.replaceChildren(...(state.beneficiaries || []).map((item) => {
    const option = el("option", "", item.name + (item.trusted ? " · established" : " · new beneficiary"));
    option.value = item.id;
    return option;
  }));
  if ((state.beneficiaries || []).some((item) => item.id === previousBeneficiary)) beneficiary.value = previousBeneficiary;
  beneficiaryHint();
}
function beneficiaryHint() {
  const beneficiary = state?.beneficiaries?.find((item) => item.id === $("#beneficiary").value);
  $("#beneficiary-detail").textContent = beneficiary ? `${beneficiary.account_id} / ${beneficiary.country} / ${beneficiary.trusted ? "Established synthetic recipient" : "New synthetic recipient · review controls apply"}` : "";
}
function renderRecent() {
  const payments = ownTransfers().slice(0, 4);
  $("#recent-activity").replaceChildren(...(payments.length ? payments.map((payment) => {
    const row = el("div", "activity-item");
    const own = new Set(ownAccounts().map((item) => item.id));
    const outgoing = own.has(payment.from_account);
    return append(row, el("span", "movement-icon", outgoing ? "→" : "←"), append(el("div", "activity-item-main"), el("strong", "", payment.beneficiary_name), el("small", "", date(payment.created_at) + " / " + payment.reference)), append(el("div", "activity-item-right"), el("strong", "", (outgoing ? "− " : "+ ") + money(payment.amount_cents)), badge(payment.status)));
  }) : [empty("Your next move starts here.", "Make a synthetic payment to see the complete review and ledger journey.", "→")]));
}
function svg(tag, attributes = {}, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
  if (text !== undefined) node.textContent = text;
  return node;
}
function renderFlow() {
  const owned = new Set(ownAccounts().map((account) => account.id));
  const entries = (state.ledger || []).filter((entry) => owned.has(entry.account_id));
  if (!entries.length) { $("#flow-chart").replaceChildren(empty("A ledger with a clear beginning.", "Posted movements appear here after your first payment.", "⌁")); return; }
  const credits = entries.filter((entry) => entry.amount_cents > 0).reduce((sum, entry) => sum + entry.amount_cents, 0);
  const debits = entries.filter((entry) => entry.amount_cents < 0).reduce((sum, entry) => sum - entry.amount_cents, 0);
  const summary = append(el("div", "flow-summary"), append(el("div"), el("span", "", "MONEY IN"), el("strong", "", money(credits))), append(el("div"), el("span", "", "MONEY OUT"), el("strong", "", money(debits))));
  const grouped = new Map();
  entries.forEach((entry) => { const day = entry.posted_at.slice(0, 10); const item = grouped.get(day) || {in: 0, out: 0}; item[entry.amount_cents > 0 ? "in" : "out"] += Math.abs(entry.amount_cents); grouped.set(day, item); });
  const points = [...grouped.entries()].sort(([a], [b]) => a.localeCompare(b)).slice(-5);
  const chart = svg("svg", {viewBox: "0 0 340 130", class: "flow-chart", role: "img", "aria-label": "Posted credits and debits grouped by date"});
  chart.append(svg("line", {x1: 0, y1: 105, x2: 340, y2: 105, class: "chart-axis"}));
  const peak = Math.max(...points.flatMap(([, item]) => [item.in, item.out]), 1);
  const width = 300 / points.length;
  points.forEach(([day, item], index) => {
    const x = 20 + index * width;
    ["in", "out"].forEach((kind, offset) => {
      const height = item[kind] / peak * 82;
      const rect = svg("rect", {x: x + offset * 18, y: 104 - height, width: 13, height, rx: 1, class: "chart-bar" + (kind === "out" ? " out" : "")});
      rect.append(svg("title", {}, `${day} · ${kind === "in" ? "Credits" : "Debits"}: ${money(item[kind])}`)); chart.append(rect);
    });
    chart.append(svg("text", {x: x + 14, y: 124, "text-anchor": "middle", class: "chart-label"}, date(day).slice(0, 6)));
  });
  $("#flow-chart").replaceChildren(summary, chart);
}
function table(headings, rows) {
  const node = el("table");
  node.append(append(el("thead"), append(el("tr"), ...headings.map((name) => el("th", "", name)))));
  node.append(append(el("tbody"), ...rows));
  return node;
}
function paymentDetail(payment, trigger) {
  const heading = el("h2", "dialog-heading", payment.beneficiary_name);
  heading.id = "detail-dialog-title";
  const content = [el("p", "dialog-eyebrow", payment.id + " / PAYMENT DETAIL"), heading, badge(payment.status), el("div", "dialog-amount", money(payment.amount_cents)), detailList([["From account", payment.from_account], ["Recipient account", payment.to_account], ["Reference", payment.reference], ["Created", date(payment.created_at, true)], ["Risk score", `${payment.risk_score}/100`], ["Reviewed by", payment.approved_by ? `Local operator #${payment.approved_by}` : "No independent decision"]])];
  const reasons = el("div", "approval-reasons");
  reasons.append(append(el("ul"), ...(payment.reasons || []).map((reason) => el("li", "", reason))));
  content.push(reasons);
  if (payment.review_note) content.push(el("p", "dialog-note", "Review decision: " + payment.review_note));
  const incident = (state.cases || []).find((item) => item.transfer_id === payment.id);
  if (incident) content.push(caseTimeline(incident));
  $("#detail-dialog-content").replaceChildren(...content);
  showDialog("detail-dialog", trigger);
}
function renderActivity() {
  const filter = $("#activity-filter").value;
  const payments = ownTransfers().filter((payment) => filter === "all" || payment.status === filter);
  if (!payments.length) { $("#activity-table").replaceChildren(empty("Nothing in this view yet.", "Your payments and independent review decisions will appear here.")); return; }
  const rows = payments.map((payment) => {
    const row = el("tr", "clickable-row"); row.tabIndex = 0;
    row.setAttribute("aria-label", `Details for ${payment.id}, ${payment.beneficiary_name}, ${money(payment.amount_cents)}`);
    row.append(append(el("td"), el("strong", "", payment.beneficiary_name), el("small", "", payment.id)), append(el("td"), document.createTextNode(date(payment.created_at)), el("small", "", payment.reference)), el("td", "table-money", money(payment.amount_cents)), append(el("td"), badge(payment.status)), el("td", "row-arrow", "→"));
    row.addEventListener("click", () => paymentDetail(payment, row));
    row.addEventListener("keydown", (event) => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); paymentDetail(payment, row); } });
    return row;
  });
  $("#activity-table").replaceChildren(table(["BENEFICIARY", "DATE / REFERENCE", "AMOUNT", "STATUS", ""], rows));
}
function renderSecurity() {
  const user = session.user;
  $("#mfa-status").replaceWith(Object.assign(badge(user.mfa_enabled ? "active" : "warning", user.mfa_enabled ? "Enabled" : "Not enrolled"), {id: "mfa-status"}));
  $("#mfa-enroll").hidden = user.mfa_enabled;
  if (user.mfa_enabled) { $("#mfa-enrollment").hidden = true; $("#mfa-secret").value = ""; }
  $("#session-detail").replaceChildren(detailList([["Signed in as", user.username], ["Account role", readable[user.role]], ["Password protection", "scrypt password hashing"], ["Session", "Server-managed · HttpOnly cookie"], ["Write protection", "Session-bound CSRF validation"], ["Authenticator", user.mfa_enabled ? "Time-based verification enabled" : "Not enrolled"]]));
}
function caseTimeline(incident) {
  const timeline = el("div", "case-timeline");
  (incident.timeline || []).forEach((step) => timeline.append(append(el("div", "case-step"), el("strong", "", step.action), el("small", "", `${date(step.at, true)} · identity #${step.by}`), el("p", "", step.detail))));
  return timeline;
}
function renderApprovals() {
  const pending = (state.transfers || []).filter((payment) => payment.status === "pending_review").sort((a, b) => b.created_at.localeCompare(a.created_at));
  const all = state.transfers || [];
  $("#pending-count").textContent = pending.length;
  $("#approval-tab-count").textContent = pending.length;
  $("#approval-summary").replaceChildren(...[["AWAITING REVIEW", pending.length], ["FUNDS RESERVED", money(pending.reduce((total, payment) => total + payment.amount_cents, 0))], ["INDEPENDENT DECISIONS", all.filter((payment) => payment.approved_by).length]].map(([label, value]) => append(el("div", "mini-stat"), el("span", "", label), el("strong", "", value))));
  $("#approval-queue").replaceChildren(...(pending.length ? pending.map((payment) => {
    const card = el("article", "approval-card");
    const title = append(el("div"), el("h3", "", payment.beneficiary_name), el("small", "", payment.id));
    card.append(append(el("div", "approval-card-header"), title, el("div", "approval-amount", money(payment.amount_cents))), append(el("div", "approval-meta"), el("span", "", `Created by identity #${payment.created_by}`), el("span", "", date(payment.created_at, true)), el("span", "", `Risk ${payment.risk_score}/100`)), append(el("div", "approval-reasons"), append(el("ul"), ...(payment.reasons || []).map((reason) => el("li", "", reason)))));
    if (payment.created_by === session.user.id) card.append(el("p", "self-approval-note", "Independent review required. You created this payment and cannot approve or reject it yourself. Sign in as a different operator to make the decision."));
    else {
      const actions = el("form", "approval-actions");
      const label = el("label", "", "Decision rationale");
      const note = el("textarea"); note.required = true; note.minLength = 3; note.maxLength = 500; note.id = "decision-" + payment.id; label.htmlFor = note.id; note.placeholder = "Record the independent checks supporting your decision";
      const approve = el("button", "button primary", "Approve payment"); approve.type = "submit";
      const reject = el("button", "button secondary", "Reject & return funds"); reject.type = "button";
      const decide = async (decision, button) => {
        if (!actions.reportValidity()) return;
        button.disabled = true; approve.disabled = true; reject.disabled = true;
        try { const payload = await api("/api/decision", {transfer_id: payment.id, decision, note: note.value.trim()}); state = payload.state; render(); toast(payload.result?.summary || "Independent decision recorded."); }
        catch (error) { toast(error.message, true); button.disabled = false; approve.disabled = false; reject.disabled = false; }
      };
      actions.addEventListener("submit", (event) => { event.preventDefault(); decide("approve", approve); });
      reject.addEventListener("click", () => decide("reject", reject));
      actions.append(label, note, append(el("div", "button-row"), approve, reject)); card.append(actions);
    }
    const incident = (state.cases || []).find((item) => item.transfer_id === payment.id);
    if (incident) {
      const details = el("details"); details.append(el("summary", "timeline-toggle", "Inspect case timeline"), caseTimeline(incident)); card.append(details);
    }
    return card;
  }) : [append(el("section", "section"), empty("Nothing awaiting your decision.", "A high-value, new-beneficiary or high-velocity payment will enter this independent review queue."))]));
}
function renderEvents() {
  const search = $("#event-search").value.toLowerCase();
  const events = (state.events || []).filter((event) => `${event.title} ${event.detail} ${event.type} ${event.technique}`.toLowerCase().includes(search)).sort((a, b) => b.time.localeCompare(a.time));
  $("#event-timeline").replaceChildren(...(events.length ? events.map((event) => append(el("article", "event-item"), el("time", "", date(event.time, true)), append(el("div"), el("h3", "", event.title), el("p", "", event.detail), el("small", "", `${event.type} / ${event.technique || "Local control event"}`)), badge(event.severity))) : [empty("No matching observations.", "Sign-ins, payment evaluations, decisions and policy updates generate local security events.")]));
  const audit = state.audit || {};
  $("#audit-status").replaceWith(Object.assign(badge(audit.valid ? "active" : "error", audit.valid ? "Chain verified" : "Verification failed"), {id: "audit-status"}));
  $("#audit-summary").replaceChildren(append(el("dl", "audit-summary-grid"), append(el("div"), el("dt", "", "COMMITTED AUDIT ENTRIES"), el("dd", "", audit.count ?? "—")), append(el("div"), el("dt", "", "LATEST CHAIN HEAD"), el("dd", "", audit.head || "—"))), el("p", "subtle", "Each accepted operation binds a state digest into a keyed audit chain. The local host controls both database and key; this is integrity checking, not immutable off-host evidence."));
}
async function loadUsers() {
  if (session?.user?.role !== "admin") return;
  try {
    const payload = await api("/api/users");
    $("#users-list").replaceChildren(...payload.users.map((user) => append(el("div", "user-item"), el("span", "avatar", user.display_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()), append(el("div"), el("strong", "", user.display_name), el("small", "", `${user.username} · identity #${user.id} · ${user.mfa_enabled ? "MFA enabled" : "MFA not enrolled"}`)), badge("neutral", readable[user.role] || user.role))));
  } catch (error) { toast(error.message, true); }
}
function render() {
  if (!state || !session?.user) return;
  renderAccounts(); renderRecent(); renderFlow(); renderActivity(); renderSecurity();
  if (isOperator()) { renderApprovals(); renderEvents(); }
  if (document.activeElement !== $("#high-value")) $("#high-value").value = (state.rules.high_value_cents / 100).toFixed(2);
  if (document.activeElement !== $("#velocity-limit")) $("#velocity-limit").value = state.rules.velocity_limit;
  $("#session-label").textContent = `Signed in as ${session.user.username}`;
}
function candidateRules() { return {high_value_chf: $("#high-value").value.trim(), velocity_limit: Number($("#velocity-limit").value)}; }
function renderBacktest(result) {
  const matrix = el("div", "confusion-grid");
  [["True positives", result.tp, false], ["False positives", result.fp, true], ["True negatives", result.tn, false], ["Missed cases", result.fn, true]].forEach(([label, value, bad]) => matrix.append(append(el("div", "confusion-cell" + (bad ? " bad" : "")), el("span", "", label), el("strong", "", value))));
  const metrics = append(el("div", "evaluation-metrics"), append(el("span"), document.createTextNode("Precision"), el("strong", "", `${Math.round(result.precision * 100)}%`)), append(el("span"), document.createTextNode("Recall"), el("strong", "", `${Math.round(result.recall * 100)}%`)));
  const cases = (result.cases || []).map((item) => append(el("div", "test-case"), append(el("div"), el("strong", "", item.name), badge(item.flagged === item.expected ? "active" : "warning", item.flagged ? "Review" : "Pass")), el("p", "", `Expected: ${item.expected ? "review" : "pass"}. ${(item.reasons || []).join(" · ")}`)));
  $("#backtest-result").replaceChildren(matrix, metrics, ...cases, el("p", "dialog-note", "Results describe labeled synthetic fixtures, not measured production fraud or AML effectiveness."));
}
function invalidatePayment() { pendingPayment = null; }
function reviewPayment() {
  const account = ownAccounts().find((item) => item.id === $("#from-account").value);
  const beneficiary = state.beneficiaries.find((item) => item.id === $("#beneficiary").value);
  if (!account || !beneficiary) { toast("Select an owned account and a valid beneficiary.", true); return; }
  const payload = {from_account: account.id, beneficiary_id: beneficiary.id, amount: $("#amount").value.trim(), reference: $("#reference").value.trim()};
  if (!pendingPayment || ["from_account", "beneficiary_id", "amount", "reference"].some((key) => pendingPayment[key] !== payload[key])) pendingPayment = {...payload, idempotency_key: crypto.randomUUID()};
  const heading = el("h2", "dialog-heading", "A moment to review."); heading.id = "payment-dialog-title";
  const amount = append(el("div", "dialog-amount"), el("small", "", "CHF"), document.createTextNode(payload.amount));
  const confirm = el("button", "button primary", "Confirm payment →"); confirm.id = "confirm-payment";
  const cancel = el("button", "button secondary", "Back to details"); cancel.addEventListener("click", () => $("#payment-dialog").close());
  confirm.addEventListener("click", async () => {
    if (busy || !pendingPayment) return;
    busy = true; confirm.disabled = true; cancel.disabled = true;
    try {
      const response = await api("/api/transfer", pendingPayment);
      state = response.state;
      const payment = response.result.transfer || state.transfers.find((item) => item.id === response.result.transfer_id);
      render();
      pendingPayment = null;
      $("#amount").value = ""; $("#reference").value = "";
      $("#payment-dialog").close();
      const panel = $("#payment-result");
      const activity = el("button", "text-button", "View payment history →"); activity.addEventListener("click", () => view("activity"));
      panel.replaceChildren(badge(payment.status), el("h3", "", response.result.title || "Payment recorded"), el("p", "", `${payment.id} · ${money(payment.amount_cents)} to ${payment.beneficiary_name}. ${response.result.summary || ""}`), append(el("ul"), ...(payment.reasons || []).map((reason) => el("li", "", reason))), activity); panel.hidden = false;
      panel.scrollIntoView({block: "nearest", behavior: "smooth"});
      toast(response.result.title || "Payment recorded.");
    } catch (error) { toast(error.message, true); }
    finally { busy = false; confirm.disabled = false; cancel.disabled = false; }
  });
  $("#payment-dialog-content").replaceChildren(el("p", "dialog-eyebrow", "02 / VERIFY AND CONFIRM"), heading, amount, detailList([["From", account.label], ["To", beneficiary.name], ["Recipient", beneficiary.account_id], ["Reference", payload.reference]]), el("p", "dialog-note", "Confirming evaluates the payment policy and either posts the synthetic transfer or reserves funds for an independent review. Repeated submission of this same request cannot debit twice."), append(el("div", "dialog-actions"), cancel, confirm));
  showDialog("payment-dialog", $("#review-payment"));
}

$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#auth-submit"); button.disabled = true; $("#auth-error").hidden = true;
  const setup = session?.setup_required;
  const payload = {username: $("#username").value.trim(), password: $("#password").value};
  if (setup) payload.display_name = $("#display-name").value.trim();
  else if ($("#otp").value.trim()) payload.otp = $("#otp").value.trim();
  try { await api(setup ? "/api/setup" : "/api/login", payload); $("#password").value = ""; $("#otp").value = ""; await enterWorkspace(); }
  catch (error) { $("#auth-error").textContent = error.message; $("#auth-error").hidden = false; }
  finally { button.disabled = false; }
});
async function logout() {
  try { await api("/api/logout", {}); await signedOut(); }
  catch (error) { toast(error.message, true); }
}
$("#logout").addEventListener("click", logout);
$$("[data-view]").forEach((button) => button.addEventListener("click", () => view(button.dataset.view)));
$$("[data-goto]").forEach((button) => button.addEventListener("click", () => view(button.dataset.goto)));
$$("[data-ops]").forEach((button) => button.addEventListener("click", () => opsView(button.dataset.ops)));
$("#refresh").addEventListener("click", async () => { try { await loadSession(); if (session.user) await refresh(); else await signedOut(); } catch (error) { toast(error.message, true); } });
$("#payment-form").addEventListener("submit", (event) => { event.preventDefault(); reviewPayment(); });
$("#payment-form").addEventListener("input", invalidatePayment);
$("#beneficiary").addEventListener("change", () => { invalidatePayment(); beneficiaryHint(); });
$("#activity-filter").addEventListener("change", renderActivity);
$("#event-search").addEventListener("input", renderEvents);
$("#mfa-enroll").addEventListener("click", async (event) => {
  event.currentTarget.disabled = true;
  try { const payload = await api("/api/mfa/enroll", {}); $("#mfa-secret").value = payload.secret; $("#mfa-enrollment").hidden = false; $("#mfa-code").focus(); }
  catch (error) { toast(error.message, true); }
  finally { $("#mfa-enroll").disabled = false; }
});
$("#mfa-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const button = event.currentTarget.querySelector("button"); button.disabled = true;
  try { await api("/api/mfa/confirm", {code: $("#mfa-code").value}); await loadSession(); render(); $("#mfa-code").value = ""; toast("Authenticator verification enabled. Use the next code from your authenticator for a new sign-in."); }
  catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
});
$("#rules-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const button = event.currentTarget.querySelector("[type=submit]"); button.disabled = true;
  try { const payload = await api("/api/backtest", candidateRules()); renderBacktest(payload.result); }
  catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
});
$("#save-rules").addEventListener("click", async (event) => {
  if (!$("#rules-form").reportValidity()) return;
  event.currentTarget.disabled = true;
  try { const payload = await api("/api/rules", candidateRules()); state = payload.state; render(); toast(payload.result?.summary || "Payment policy applied."); }
  catch (error) { toast(error.message, true); }
  finally { $("#save-rules").disabled = false; }
});
$("#user-form").addEventListener("submit", async (event) => {
  event.preventDefault(); const button = event.currentTarget.querySelector("button"); button.disabled = true;
  try { await api("/api/users", {username: $("#new-user").value.trim(), display_name: $("#new-name").value.trim(), password: $("#new-password").value, role: $("#new-role").value}); $("#user-form").reset(); await loadUsers(); await refresh({silent: true}); toast("Local identity created. Use a separate sign-in for independent decisions."); }
  catch (error) { toast(error.message, true); }
  finally { button.disabled = false; }
});
$("#export-evidence").addEventListener("click", async (event) => {
  event.currentTarget.disabled = true;
  try {
    const response = await fetch("/api/evidence", {credentials: "same-origin"});
    if (!response.ok) { const payload = await response.json(); throw new Error(payload.error || "Export failed"); }
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = el("a"); link.href = url; link.download = "portbug-banking-evidence.json"; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1500); toast("Synthetic banking evidence exported. Keep operational exports private.");
  } catch (error) { toast(error.message, true); }
  finally { $("#export-evidence").disabled = false; }
});
$$("[data-close]").forEach((button) => button.addEventListener("click", () => $("#" + button.dataset.close).close()));
$$("dialog").forEach((dialog) => {
  dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener("close", () => { if (dialogTrigger?.isConnected) dialogTrigger.focus({preventScroll: true}); });
});
const mobileLogout = el("button", "top-logout", "Sign out"); mobileLogout.setAttribute("aria-label", "Sign out"); mobileLogout.addEventListener("click", logout); $(".topbar-right").append(mobileLogout);
function clock() {
  $("#clock").textContent = new Date().toLocaleTimeString("en-GB", {timeZone: "Europe/Zurich", hour: "2-digit", minute: "2-digit"}) + " ZRH";
  $("#today").textContent = new Date().toLocaleDateString("en-GB", {timeZone: "Europe/Zurich", day: "numeric", month: "long", year: "numeric"});
}
clock(); setInterval(clock, 30000);
setInterval(() => { if (session?.user && !busy && !$$("dialog[open]").length && document.visibilityState === "visible") refresh({silent: true}); }, 60000);
(async () => {
  try { await loadSession(); if (session.user) await enterWorkspace(); else authScreen(); }
  catch (error) { $("#auth-description").textContent = "The local banking service is unavailable."; $("#auth-loading").textContent = `${error.message}. Start the server with py -m portbug, then reload this page.`; }
})();
