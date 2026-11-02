"use strict";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));
let state = null;
let csrfToken = "";
let currentView = "overview";
let activeAlert = null;
let busy = false;
let toastTimer;
const titles = {
  overview: ["Security overview", "A clear view of the signals, decisions, and evidence that matter."],
  detections: ["Detection queue", "From a suspicious signal to a documented, measured response."],
  fraud: ["Fraud intelligence", "Understand the reasons behind every synthetic risk decision."],
  controls: ["Control assurance", "A precise account of what runs, what is simulated, and what comes next."],
  audit: ["Audit ledger", "A locally verified chain of decisions and response actions."],
  runbooks: ["Response playbooks", "Clear ownership. Controlled containment. Evidence-led recovery."],
};

function el(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined && content !== null) node.textContent = String(content);
  return node;
}
function append(parent, ...children) {
  children.forEach((child) => parent.append(child));
  return parent;
}
function display(value) {
  if (typeof value === "object" && value !== null) return JSON.stringify(value);
  return String(value ?? "—");
}
function normalized(value, allowed, fallback) {
  return allowed.includes(value) ? value : fallback;
}
function severityBadge(value) {
  const severity = normalized(value, ["critical", "high", "medium", "low"], "low");
  return el("span", `severity ${severity}`, severity);
}
function statusBadge(value) {
  const status = normalized(value, ["open", "investigating", "contained", "resolved"], "open");
  return el("span", `status-pill ${status}`, status);
}
function timeLabel(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return display(timestamp);
  return date.toLocaleTimeString("en-GB", {timeZone: "Europe/Zurich", hour: "2-digit", minute: "2-digit"}) + " ZRH";
}
function toast(message, error = false) {
  const node = $("#toast");
  node.textContent = message;
  node.className = error ? "toast error" : "toast";
  node.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { node.hidden = true; }, error ? 8500 : 5500);
}
async function request(path, body) {
  const options = {headers: {Accept: "application/json"}, cache: "no-store"};
  if (body !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.headers["X-CSRF-Token"] = csrfToken;
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}
function setConnection(connected) {
  const connection = $("#connection");
  connection.classList.toggle("offline", !connected);
  connection.replaceChildren(el("span", "status-dot"), document.createTextNode(connected ? "Local service connected" : "Service unavailable"));
}
async function refresh(silent = false) {
  try {
    const session = await request("/api/session");
    csrfToken = session.csrf_token;
    state = await request("/api/state");
    setConnection(true);
    $("#load-error").hidden = true;
    render();
    if (!silent) toast("Local evidence refreshed.");
  } catch (error) {
    setConnection(false);
    $("#load-error").textContent = `${error.message}. Start the local Portbug service and refresh this page.`;
    $("#load-error").hidden = false;
    if (!silent) toast(error.message, true);
  }
}
function view(name) {
  if (!(name in titles)) return;
  currentView = name;
  $$(".view-panel").forEach((panel) => { panel.hidden = panel.id !== `view-${name}`; });
  $$("[data-view]").forEach((button) => {
    const active = button.dataset.view === name;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  $("#page-title").replaceChildren(document.createTextNode(titles[name][0]), el("span", "heading-dot", "."));
  $("#page-description").textContent = titles[name][1];
  document.title = `${titles[name][0]} · Portbug Bank`;
}
function table(headers, rows) {
  const element = el("table");
  const head = el("thead");
  const headerRow = el("tr");
  headers.forEach((text) => {
    const th = el("th", "", text);
    th.scope = "col";
    headerRow.append(th);
  });
  head.append(headerRow);
  const body = el("tbody");
  rows.forEach((row) => body.append(row));
  append(element, head, body);
  return element;
}
function renderMetrics() {
  const glyphs = ["⌁", "◇", "▧", "≋"];
  $("#metrics").replaceChildren(...(state.metrics || []).map((metric, i) => {
    const card = el("div", "metric");
    const label = append(el("div", "metric-label"), el("span", "", metric.label), el("span", "metric-glyph", glyphs[i % glyphs.length]));
    const tone = ["warning", "warn", "critical", "amber"].includes(metric.tone) ? "warn" : ["info", "blue", "cyan"].includes(metric.tone) ? "info" : "";
    append(card, label, el("strong", "metric-value", metric.value), el("div", `metric-detail ${tone}`, metric.detail));
    return card;
  }));
}
function svgNode(tag, attributes = {}, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attributes).forEach(([name, value]) => node.setAttribute(name, value));
  if (text !== undefined) node.textContent = String(text);
  return node;
}
function renderChart() {
  const data = state.trend || [];
  const target = $("#activity-chart");
  if (!data.length) { target.replaceChildren(el("div", "empty-state", "Run a scenario to create activity.")); return; }
  const svg = svgNode("svg", {viewBox: "0 0 640 180", role: "img", "aria-label": "Illustrative history of flagged observations and baseline checks"});
  const defs = svgNode("defs");
  const gradient = svgNode("linearGradient", {id: "activity-fill", x1: "0", x2: "0", y1: "0", y2: "1"});
  append(gradient, svgNode("stop", {offset: "0%", "stop-color": "#70dbc0", "stop-opacity": ".18"}), svgNode("stop", {offset: "100%", "stop-color": "#70dbc0", "stop-opacity": "0"}));
  defs.append(gradient);
  svg.append(defs);
  const maximum = Math.max(4, ...data.map((d) => Math.max(Number(d.blocked) || 0, Number(d.reviewed) || 0)));
  const upper = Math.ceil(maximum / 4) * 4;
  [0, 1, 2, 3, 4].forEach((step) => {
    const y = 145 - step * 32;
    append(svg, svgNode("line", {x1: "31", x2: "630", y1: y, y2: y, class: "chart-grid"}), svgNode("text", {x: "23", y: y + 3, class: "chart-label", "text-anchor": "end"}, Math.round(upper * step / 4)));
  });
  const point = (item, index, key) => [35 + index * 588 / Math.max(1, data.length - 1), 145 - (Number(item[key]) || 0) / upper * 128];
  const primary = data.map((item, index) => point(item, index, "blocked"));
  const secondary = data.map((item, index) => point(item, index, "reviewed"));
  const path = (points) => points.map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  svg.append(svgNode("path", {d: `${path(primary)} L${primary.at(-1)[0]},145 L${primary[0][0]},145 Z`, class: "chart-area"}));
  append(svg, svgNode("path", {d: path(secondary), class: "chart-series chart-secondary"}), svgNode("path", {d: path(primary), class: "chart-series"}));
  data.forEach((item, index) => {
    if (data.length <= 9 || index % 2 === 0 || index === data.length - 1) {
      svg.append(svgNode("text", {x: primary[index][0], y: "171", class: "chart-label", "text-anchor": "middle"}, item.label));
    }
    const circle = svgNode("circle", {cx: primary[index][0], cy: primary[index][1], r: "3", fill: "#70dbc0", stroke: "#101d28", "stroke-width": "2"});
    circle.append(svgNode("title", {}, `${item.label}: ${item.blocked} flagged; ${item.reviewed} baseline checks`));
    svg.append(circle);
  });
  target.replaceChildren(svg);
}
function renderPosture() {
  const controls = state.controls || [];
  const labels = {implemented: "Implemented in this lab", simulated: "Simulated banking controls", planned: "Production requirements"};
  $("#posture").replaceChildren(...Object.entries(labels).map(([status, label]) => append(el("div", "posture-item"), el("span", `posture-indicator ${status}`), el("span", "", label), el("strong", "", controls.filter((c) => c.status === status).length))));
  $("#control-summary").replaceChildren(...Object.entries(labels).map(([status, label]) => append(el("div", `card control-count ${status}`), el("strong", "", controls.filter((c) => c.status === status).length), el("span", "", label))));
  const rows = controls.map((control) => append(el("tr"), append(el("td"), el("span", "cell-title", control.name), el("span", "cell-subtitle", control.id)), el("td", "", control.category), append(el("td"), el("span", `control-status ${normalized(control.status, Object.keys(labels), "planned")}`, control.status)), el("td", "control-evidence", control.evidence)));
  $("#control-table").replaceChildren(table(["CONTROL", "DOMAIN", "IMPLEMENTATION", "EVIDENCE / BOUNDARY"], rows));
}
function alertTable(alerts, container) {
  if (!alerts.length) { container.replaceChildren(el("div", "empty-state", "No detections match this view. Run a scenario to exercise a rule.")); return; }
  const rows = alerts.map((alert) => {
    const row = el("tr", "alert-row");
    row.tabIndex = 0;
    row.dataset.alertId = alert.id;
    row.setAttribute("aria-label", `Investigate ${alert.title}`);
    row.addEventListener("click", () => openAlert(alert.id));
    row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openAlert(alert.id); } });
    append(row, append(el("td"), severityBadge(alert.severity)), append(el("td"), el("span", "cell-title", alert.title), el("span", "cell-subtitle", `${alert.id} · ${alert.source}`)), el("td", "hash-cell", alert.technique), append(el("td"), statusBadge(alert.status)), el("td", "", timeLabel(alert.time)), el("td", "table-arrow", "→"));
    return row;
  });
  container.replaceChildren(table(["SEVERITY", "DETECTION", "ATT&CK", "RESPONSE", "OBSERVED", ""], rows));
}
function renderAlerts() {
  const alerts = state.alerts || [];
  $("#nav-alert-count").textContent = String(alerts.filter((a) => a.status !== "resolved").length);
  const order = {critical: 0, high: 1, medium: 2, low: 3};
  const prioritized = [...alerts].sort((a, b) => (a.status === "resolved") - (b.status === "resolved") || (order[a.severity] ?? 4) - (order[b.severity] ?? 4));
  alertTable(prioritized.slice(0, 4), $("#overview-alerts"));
  const query = $("#alert-search").value.trim().toLowerCase();
  const severity = $("#severity-filter").value;
  const filtered = prioritized.filter((a) => (severity === "all" || a.severity === severity) && [a.title, a.id, a.source, a.technique, a.detail].some((value) => display(value).toLowerCase().includes(query)));
  alertTable(filtered, $("#all-alerts"));
}
function renderZones() {
  const names = {dmz: "Edge & ingress", app: "Application layer", data: "Protected data", mgmt: "Security management"};
  $("#zones").replaceChildren(...Object.entries(names).map(([zone, label], index) => {
    const assets = (state.assets || []).filter((asset) => display(asset.zone).toLowerCase() === zone);
    return append(el("div", "zone"), el("span", "zone-number", `0${index + 1} / ZONE`), el("h3", "", zone), el("p", "", assets.length ? assets.map((asset) => asset.name).join(" · ") : label));
  }));
}
function renderIncidents() {
  const incidents = (state.incidents || []).slice(0, 3);
  if (!incidents.length) { $("#incident-preview").replaceChildren(el("div", "empty-state", "Run a scenario to create a local incident.")); return; }
  $("#incident-preview").replaceChildren(...incidents.map((incident, index) => append(el("div", "incident-item"), el("span", "incident-index", String(index + 1).padStart(2, "0")), append(el("div", "incident-copy"), el("strong", "", incident.title), el("p", "", `${incident.owner} · ${incident.status}`)), severityBadge(incident.severity))));
}
function renderFraud() {
  const transactions = state.fraud || [];
  if (!transactions.length) { $("#fraud-cards").replaceChildren(el("div", "card empty-state", "Run the payment-change scenario to evaluate a synthetic transaction.")); return; }
  $("#fraud-cards").replaceChildren(...transactions.map((transaction) => {
    const card = el("article", "card fraud-card");
    const amount = new Intl.NumberFormat("en-CH", {style: "currency", currency: "CHF", maximumFractionDigits: 0}).format(Number(transaction.amount_chf) || 0);
    const top = append(el("div", "fraud-top"), append(el("div"), el("p", "eyebrow", transaction.id), el("h2", "", amount)), el("span", `severity ${transaction.decision === "review" ? "high" : "low"}`, transaction.decision === "review" ? "Manual review" : "Allow signal"));
    const score = Math.min(100, Math.max(0, Number(transaction.score) || 0));
    const track = el("div", "score-track");
    const fill = el("span", "score-fill");
    // A numeric-only presentation property cannot introduce markup or external URLs.
    fill.style.setProperty("--score", `${score}%`);
    track.append(fill);
    const reasons = el("ul", "reason-list");
    (transaction.reasons || []).forEach((reason) => reasons.append(el("li", "", reason)));
    if (!(transaction.reasons || []).length) reasons.append(el("li", "", "No configured risk signals triggered."));
    append(card, top, el("p", "fraud-account", transaction.account), append(el("div", "score-row"), el("span", "", "EXPLAINABLE RISK SCORE"), append(el("span", "score-value"), document.createTextNode(score), el("span", "cell-subtitle", "/ 100"))), track, reasons);
    return card;
  }));
}
function renderAudit() {
  const audit = state.audit || {valid: false, count: 0, entries: []};
  const integrity = $("#audit-integrity");
  integrity.classList.toggle("invalid", !audit.valid);
  integrity.replaceChildren(el("div", "integrity-icon", audit.valid ? "✓" : "!"), append(el("div"), el("h2", "", audit.valid ? "Audit chain verified." : "Audit verification failed."), el("p", "", "HMAC-linked local entries · verify before relying on evidence"), el("code", "", `HEAD ${display(audit.head).slice(0, 48)}…`)), append(el("div", "integrity-count"), el("strong", "", audit.count), el("span", "", "recorded actions")));
  const entries = [...(audit.entries || [])].sort((a, b) => Number(b.sequence) - Number(a.sequence));
  const rows = entries.map((entry) => append(el("tr"), el("td", "hash-cell", `#${entry.sequence}`), el("td", "", timeLabel(entry.timestamp)), el("td", "cell-title", entry.action), el("td", "audit-detail", display(entry.detail)), el("td", "hash-cell", display(entry.hash).slice(0, 18) + "…")));
  $("#audit-table").replaceChildren(rows.length ? table(["SEQ", "TIME", "ACTION", "CONTEXT", "CHAIN HASH"], rows) : el("div", "empty-state", "No audit entries yet."));
}
function render() {
  if (!state) return;
  renderMetrics(); renderChart(); renderPosture(); renderAlerts(); renderZones(); renderIncidents(); renderFraud(); renderAudit();
  $("#last-updated").textContent = `State as of ${timeLabel(state.as_of)}`;
}
function openAlert(id, focusAction = false) {
  const alert = (state?.alerts || []).find((entry) => entry.id === id);
  if (!alert) return;
  activeAlert = id;
  const body = $("#detail-body");
  const heading = el("h2", "", alert.title);
  heading.id = "detail-title";
  heading.tabIndex = -1;
  const metadata = append(el("div", "detail-meta"), severityBadge(alert.severity), statusBadge(alert.status), el("span", "", alert.id));
  const grid = el("dl", "detail-grid");
  [["MITRE ATT&CK", alert.technique], ["Signal source", alert.source], ["Observed", timeLabel(alert.time)], ["Scope", "Synthetic local identities only"]].forEach(([label, value]) => grid.append(append(el("div"), el("dt", "", label), el("dd", "", value))));
  const transitions = {open: ["triage", "Begin investigation", "Review the fixture and record an investigation decision."], investigating: ["contain", "Simulate containment", "Move this local incident into the contained state."], contained: ["resolve", "Resolve incident", "Record resolution after reviewing the simulated response."]};
  const action = el("div", "detail-action");
  if (transitions[alert.status]) {
    const [name, label, explanation] = transitions[alert.status];
    const button = el("button", "button button-primary", label);
    button.disabled = busy;
    button.addEventListener("click", () => mutate("/api/respond", {alert_id: alert.id, action: name}, button));
    append(action, el("p", "", explanation), button);
  } else action.append(el("p", "", "This simulated incident is resolved. Its decision trail remains in the audit ledger."));
  body.replaceChildren(metadata, heading, el("p", "detail-description", alert.detail), grid, action, el("p", "detail-note", "Demo response actions update local records only. No account at a real bank or external identity provider is changed."));
  const dialog = $("#alert-dialog");
  if (!dialog.open) dialog.showModal();
  if (focusAction) (body.querySelector(".detail-action button") || heading).focus();
}
async function mutate(path, body, button) {
  if (busy) return;
  busy = true;
  if (button) button.disabled = true;
  $("#run-scenario").disabled = true;
  try {
    const payload = await request(path, body);
    state = payload.state;
    render();
    setConnection(true);
    const result = payload.result || {};
    toast(result.summary || result.title || "Local action recorded in the audit ledger.");
    if ($("#alert-dialog").open && activeAlert) openAlert(activeAlert);
  } catch (error) {
    toast(error.message, true);
  } finally {
    busy = false;
    if (button) button.disabled = false;
    $("#run-scenario").disabled = false;
    if ($("#alert-dialog").open && activeAlert) openAlert(activeAlert, true);
  }
}
function exportEvidence() {
  if (!state) { toast("Load local evidence before exporting.", true); return; }
  const payload = {project: "Portbug Bank Cyber Defense Center",made_by: "Vaibhav Thakur",disclaimer: "Fictional bank. Synthetic local simulation. Not production control or compliance evidence.",exported_at: new Date().toISOString(),state};
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"}));
  const link = el("a");
  link.href = url; link.download = `portbug-evidence-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  toast("Synthetic evidence exported. No session token or audit key is included.");
}
const playbooks = [
  {id: "IR-01 / IDENTITY",title: "Credential compromise",intro: "Treat repeated authentication failures and unusual sign-ins as signals requiring context, not proof of compromise.",steps: ["Correlate the affected synthetic identity, time window, and authentication events.","Triage the detection and establish the scope of the exercise.","Simulate containment; document the intended session-revocation and account-review decision.","Review recovery criteria and resolve only after retaining the evidence trail."],owner: "Identity response lead"},
  {id: "IR-02 / PAYMENTS",title: "Payment instruction anomaly",intro: "An unusual instruction change demands a controlled review with clear separation of duties.",steps: ["Inspect the synthetic transaction and the explainable fraud reasons.","Compare beneficiary-change, velocity, amount, and geography signals.","Simulate a hold decision and record an independent verification requirement.","Resolve the local incident with a documented review outcome; never execute a real payment."],owner: "Fraud operations lead"},
  {id: "IR-03 / DATA",title: "Unusual data movement",intro: "Focus on provenance, data classification, and the boundary crossed by the modeled export.",steps: ["Review the generated export event and expected access context.","Preserve the correlated detection and verify the audit chain.","Simulate scoped containment; avoid broad action without confirming the affected identity.","Record recovery steps and follow-up access-policy improvements."],owner: "Security operations lead"},
  {id: "IR-04 / PRIVILEGE",title: "Unexpected privilege change",intro: "A role change should be explainable, approved, and attributable to a specific operator.",steps: ["Correlate the synthetic role-change event with its intended approval context.","Assess whether the role grants payment, identity, or security-administration authority.","Simulate containment and record the intended rollback and access-review steps.","Resolve with documented ownership and a follow-up least-privilege review."],owner: "Privileged access lead"},
  {id: "IR-05 / RESILIENCE",title: "Service disruption tabletop",intro: "Prepare recovery decisions before a failure, including who can authorize a restore.",steps: ["Declare a local tabletop, identify the affected service, and preserve current evidence.","Define a synthetic recovery point and confirm that recovery keys remain available.","Restore only into an isolated test target and validate record integrity before use.","Record measured recovery time and unmet targets; production resilience remains a design requirement."],owner: "Resilience coordinator"},
  {id: "IR-06 / AWARENESS",title: "Phishing report triage",intro: "Use invented reports to practice safe escalation without delivering phishing messages or contacting real targets.",steps: ["Record the fictional report without opening attachments or following external links.","Identify the modeled identity, service, and potential access exposure.","Document intended identity safeguards and provide a safe reporting reminder.","Close the exercise with lessons learned and an update to the awareness material."],owner: "Security awareness lead"},
];
function renderRunbooks() {
  $("#runbook-cards").replaceChildren(...playbooks.map((book) => {
    const list = el("ol");
    book.steps.forEach((step) => list.append(el("li", "", step)));
    return append(el("article", "card runbook-card"), el("p", "eyebrow", book.id), el("h2", "", book.title), el("p", "", book.intro), list, el("div", "runbook-foot", `OWNER · ${book.owner.toUpperCase()} / TABLETOP GUIDANCE`));
  }));
}
$$("[data-view]").forEach((button) => button.addEventListener("click", () => view(button.dataset.view)));
$$("[data-goto]").forEach((button) => button.addEventListener("click", () => view(button.dataset.goto)));
$("#notice-controls").addEventListener("click", (event) => { event.preventDefault(); view("controls"); });
$("#refresh").addEventListener("click", () => refresh());
$("#export").addEventListener("click", exportEvidence);
$("#run-scenario").addEventListener("click", (event) => mutate("/api/scenarios", {scenario: $("#scenario-select").value}, event.currentTarget));
$("#alert-search").addEventListener("input", () => { if (state) renderAlerts(); });
$("#severity-filter").addEventListener("change", () => { if (state) renderAlerts(); });
$("#close-dialog").addEventListener("click", () => $("#alert-dialog").close());
$("#alert-dialog").addEventListener("click", (event) => { if (event.target === $("#alert-dialog")) $("#alert-dialog").close(); });
$("#alert-dialog").addEventListener("close", () => {
  const row = $$(".alert-row").find((entry) => entry.dataset.alertId === activeAlert && entry.offsetParent !== null);
  if (row) row.focus();
  else $("#workspace").focus();
});
function updateClock() { $("#clock").textContent = new Date().toLocaleTimeString("en-GB", {timeZone: "Europe/Zurich",hour: "2-digit",minute: "2-digit",second: "2-digit"}) + " ZRH"; }
updateClock(); setInterval(updateClock, 1000); renderRunbooks();
(async () => {
  try {
    const session = await request("/api/session");
    csrfToken = session.csrf_token;
    await refresh(true);
  } catch (error) {
    setConnection(false);
    $("#load-error").textContent = `${error.message}. Open the dashboard through the running local Python server.`;
    $("#load-error").hidden = false;
  }
})();
setInterval(() => { if (!busy && !$("#alert-dialog").open) refresh(true); }, 30000);
