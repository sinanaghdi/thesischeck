"use strict";

document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector("[data-language-toggle]");
  const englishPanel = document.querySelector("[data-english-panel]");
  if (toggle && englishPanel) {
    toggle.addEventListener("click", () => {
      const showing = englishPanel.hidden;
      englishPanel.hidden = !showing;
      toggle.setAttribute("aria-expanded", String(showing));
      toggle.textContent = showing ? "EN / FA" : "FA / EN";
    });
  }

  const form = document.querySelector("#inspect-form");
  if (!form) return;
  setupFindingFilters();
  const fileInput = document.querySelector("#thesis-file");
  const submit = document.querySelector("#inspect-submit");
  const status = document.querySelector("#upload-status");
  const results = document.querySelector("#inspection-results");
  const maxBytes = Number(form.dataset.maxUploadMb || 30) * 1024 * 1024;

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }

  function fillList(container, items, emptyText, renderItem) {
    container.replaceChildren();
    if (!items || items.length === 0) {
      container.append(make("p", "empty-state", emptyText));
      return;
    }
    items.forEach((item) => container.append(renderItem(item)));
  }

  function showError(message) {
    results.hidden = true;
    status.className = "upload-status is-error";
    status.textContent = message;
  }

  function renderScore(report) {
    const value = document.querySelector("#score-value");
    value.textContent = report.score === null ? "—" : Number(report.score).toFixed(1);
    document.querySelector("#score-label").textContent = report.score_label_fa || "امتیاز موقت";
    document.querySelector("#score-coverage").textContent =
      "پوشش وزن‌ها: " + Number(report.coverage_percent).toFixed(1) + "%";
    document.querySelector("#score-summary").textContent = report.summary_fa || "";
    document.querySelector("#score-formula").textContent = report.score_formula_fa || "";
    document.querySelector("#score-weight-note").textContent =
      "وزن ارزیابی‌شده: " + report.assessed_weight_total + " از " + report.configured_weight_total +
      ". وزن‌های مربوط به قابلیت‌های پیاده‌سازی‌نشده یا قواعد ردشده در مخرج نرمال‌شده لحاظ نمی‌شوند.";
    const container = document.querySelector("#score-categories");
    container.replaceChildren();
    (report.categories || []).forEach((category) => {
      const card = make("article", "score-category " + (category.available ? "is-assessed" : "is-unavailable"));
      const heading = make("div", "score-category-heading");
      heading.append(make("strong", "", category.title_fa));
      heading.append(make("span", "", category.score === null ? "خارج از امتیاز" : Number(category.score).toFixed(1) + "/100"));
      const weight = make("p", "score-category-meta",
        "وزن " + category.configured_weight + "% · سهم نرمال‌شده " +
        Number(category.normalized_weight || 0).toFixed(2) + "% · " + category.finding_count + " یافته");
      const progress = make("div", "score-progress");
      const bar = make("span", "");
      bar.style.width = category.score === null ? "0%" : Math.max(0, Math.min(100, Number(category.score))) + "%";
      progress.append(bar);
      const note = make("p", "score-category-note", category.explanation_fa);
      card.append(heading, weight, progress, note);
      container.append(card);
    });
  }

  function categoryLabel(category) {
    const labels = {
      references: "منابع و ارجاعات",
      terminology: "اصطلاحات",
      abstracts: "چکیده‌ها",
      figures_tables: "شکل‌ها و جدول‌ها",
      structure: "ساختار",
      formatting: "قالب‌بندی",
      writing_quality: "کیفیت نگارش",
    };
    return labels[category] || "سایر";
  }

  function applyFindingFilters() {
    const container = document.querySelector("#finding-list");
    const search = document.querySelector("#finding-search-live");
    const severity = document.querySelector("#finding-severity-live");
    const category = document.querySelector("#finding-category-live");
    const count = document.querySelector("#finding-filter-count");
    const noMatches = document.querySelector("#finding-no-filter-matches");
    if (!container || !search || !severity || !category) return;
    const cards = Array.from(container.querySelectorAll(".finding-card"));
    const query = search.value.trim().toLocaleLowerCase();
    const selectedSeverity = severity.value;
    const selectedCategory = category.value;
    let visible = 0;
    cards.forEach((card) => {
      const searchText = (card.dataset.search || card.textContent).toLocaleLowerCase();
      const matchesSearch = !query || searchText.includes(query);
      const matchesSeverity = selectedSeverity === "all" || card.dataset.severity === selectedSeverity;
      const matchesCategory = selectedCategory === "all" || card.dataset.category === selectedCategory;
      const show = matchesSearch && matchesSeverity && matchesCategory;
      card.hidden = !show;
      if (show) visible += 1;
    });
    if (count) count.textContent = visible + " از " + cards.length + " یافته";
    if (noMatches) noMatches.hidden = cards.length === 0 || visible > 0;
  }

  function setupFindingFilters() {
    const search = document.querySelector("#finding-search-live");
    const severity = document.querySelector("#finding-severity-live");
    const category = document.querySelector("#finding-category-live");
    const clear = document.querySelector("#clear-finding-filters");
    [search, severity, category].forEach((control) => {
      if (!control) return;
      control.addEventListener(control === search ? "input" : "change", applyFindingFilters);
    });
    if (clear) {
      clear.addEventListener("click", () => {
        if (search) search.value = "";
        if (severity) severity.value = "all";
        if (category) category.value = "all";
        applyFindingFilters();
      });
    }
  }

  function renderChecks(report) {
    const coverage = document.querySelector("#check-coverage");
    coverage.textContent = report.rules_checked + " اجرا / " + report.rules_skipped + " ردشده";
    document.querySelector("#checks-disclaimer").textContent =
      (report.disclaimer_fa || "") + " · امتیاز سلامت هنوز پیاده‌سازی نشده است؛ این موارد نتیجه‌های بازبینی هستند، نه حکم قطعی.";
    const counters = document.querySelector("#check-counters");
    counters.replaceChildren();
    const severityCount = { error: 0, warning: 0, info: 0 };
    (report.findings || []).forEach((item) => {
      if (Object.prototype.hasOwnProperty.call(severityCount, item.severity)) severityCount[item.severity] += 1;
    });
    [
      ["موارد مهم", severityCount.error, "error"],
      ["نیازمند بازبینی", severityCount.warning, "warning"],
      ["اطلاعات", severityCount.info, "info"],
    ].forEach(([title, count, severity]) => {
      const card = make("div", "check-counter counter-" + severity);
      card.append(make("small", "", title), make("strong", "", count));
      counters.append(card);
    });

    fillList(
      document.querySelector("#finding-list"),
      report.findings || [],
      "در قواعد فعال، موردی برای بازبینی شناسایی نشد. این نتیجه به معنی تأیید علمی یا قالب رسمی نیست.",
      (item) => {
        const card = make("article", "finding-card finding-" + item.severity);
        card.dataset.severity = item.severity || "info";
        card.dataset.category = item.category || "other";
        card.dataset.search = [
          item.rule_id, item.title_fa, item.title_en, item.message_fa, item.message_en,
          item.snippet, item.element_id, (item.heading_path || []).join(" "),
        ].filter(Boolean).join(" ").toLocaleLowerCase();
        const top = make("div", "finding-top");
        top.append(make("span", "finding-category", categoryLabel(item.category)));
        top.append(
          make("span", "finding-severity", item.severity === "error" ? "مهم" : item.severity === "warning" ? "بازبینی" : "اطلاعات"),
          make("code", "finding-rule", item.rule_id),
          make("span", "finding-confidence", "اطمینان " + Math.round(item.confidence * 100) + "%"),
        );
        const title = make("h3", "", item.title_fa);
        const message = make("p", "finding-message", item.message_fa);
        card.append(top, title, message);
        if (item.snippet) {
          const quote = make("blockquote", "finding-snippet");
          quote.append(make("small", "", "شاهد از سند"), make("p", "", item.snippet));
          card.append(quote);
        }
        const place = [item.element_id, (item.heading_path || []).join(" ← "), item.page_number ? "صفحه " + item.page_number : ""].filter(Boolean).join(" · ");
        if (place) card.append(make("p", "finding-location", place));
        card.append(make("p", "finding-fix", item.suggested_fix_fa));
        return card;
      },
    );

    applyFindingFilters();

    fillList(
      document.querySelector("#rule-results"),
      report.results || [],
      "وضعیت قواعد موجود نیست.",
      (item) => {
        const row = make("div", "rule-result rule-" + item.status);
        const title = make("strong", "", item.title_fa);
        const badge = make("span", "rule-status", item.status === "passed" ? "بدون مورد" : item.status === "issues_found" ? "یافته دارد" : "رد شد");
        row.append(title, badge, make("p", "", item.note_fa));
        return row;
      },
    );
  }

  function renderSummary(data) {
    document.querySelector("#result-file-name").textContent = data.file_name;
    document.querySelector("#result-format").textContent = data.source_format.toUpperCase();

    const metrics = document.querySelector("#result-metrics");
    metrics.replaceChildren();
    const metricItems = [
      ["عناصر استخراج‌شده", data.element_count],
      ["عنوان‌ها", data.element_counts.heading || 0],
      ["پاراگراف‌ها", data.element_counts.paragraph || 0],
      ["جدول‌ها", data.element_counts.table || 0],
      ["صفحات", data.page_count === null ? "نامشخص" : data.page_count],
    ];
    metricItems.forEach(([label, value]) => {
      const card = make("div", "result-metric");
      card.append(make("small", "", label), make("strong", "", value));
      metrics.append(card);
    });

    fillList(
      document.querySelector("#result-headings"),
      data.headings,
      "عنوان مشخصی تشخیص داده نشد؛ فهرست عنوان‌ها را در فایل اصلی بررسی کنید.",
      (item) => {
        const li = make("li", "");
        li.append(
          make("strong", "", item.title),
          make("small", "", item.element_id + " · عنصر " + item.source_index),
        );
        return li;
      },
    );

    fillList(
      document.querySelector("#result-previews"),
      data.preview_paragraphs,
      "متن قابل پیش‌نمایش شناسایی نشد.",
      (item) => {
        const card = make("article", "preview-excerpt");
        const location = item.element_id + (item.page_number ? " · صفحه " + item.page_number : "");
        card.append(make("p", "", item.text), make("small", "", location));
        return card;
      },
    );

    fillList(
      document.querySelector("#result-diagnostics-list"),
      data.diagnostics,
      "هشداری از سوی parser ثبت نشد؛ این به معنی تأیید صحت پایان‌نامه نیست.",
      (item) => {
        const li = make("li", "diagnostic diagnostic-" + item.severity);
        li.append(make("strong", "", item.code), make("p", "", item.message));
        return li;
      },
    );
    document.querySelector("#result-privacy").textContent = data.privacy_note;
    const parserDiagnostics = data.diagnostics || [];
    const parserWarnings = parserDiagnostics.filter((item) => item.severity === "warning" || item.severity === "error").length;
    const parserStatus = document.querySelector("#parser-status-pill");
    parserStatus.textContent = data.parsing_complete ? "استخراج اولیه انجام شد" : "استخراج ناقص";
    parserStatus.className = "coverage-status " + (data.parsing_complete ? "is-ready" : "is-warning");
    document.querySelector("#parser-coverage-note").textContent =
      "این بخش کیفیت استخراج را توصیف می‌کند، نه کیفیت علمی پایان‌نامه. موارد مبهم یا پشتیبانی‌نشده باید در فایل اصلی بازبینی شوند.";
    const coverageCards = document.querySelector("#parser-coverage-cards");
    coverageCards.replaceChildren();
    [
      ["عناصر ساختاریافته", data.element_count || 0],
      ["عنوان‌های تشخیص‌داده‌شده", (data.headings || []).length],
      ["هشدارهای استخراج", parserWarnings],
      ["محدودیت‌های اعلام‌شده", parserDiagnostics.length],
    ].forEach(([label, value]) => {
      const card = make("div", "parser-coverage-card");
      card.append(make("small", "", label), make("strong", "", value));
      coverageCards.append(card);
    });
    const parserDetails = document.querySelector("#parser-coverage-diagnostics");
    parserDetails.replaceChildren();
    if (parserDiagnostics.length) {
      parserDetails.append(make("strong", "", "محدودیت‌های مهم در استخراج"));
      const list = make("ul", "");
      parserDiagnostics.slice(0, 4).forEach((item) => {
        const row = make("li", "");
        row.append(make("span", "parser-diagnostic-code", item.code), document.createTextNode(" " + item.message));
        list.append(row);
      });
      parserDetails.append(list);
    } else {
      parserDetails.append(make("p", "", "هشدار خاصی از سوی parser ثبت نشده است؛ این به معنی تأیید همه اجزای سند نیست."));
    }
    renderScore(data.health_report || {});
    renderChecks((data.health_report && data.health_report.checks) || { rules_checked: 0, rules_skipped: 0, findings: [], results: [] });
    results.hidden = false;
    status.className = "upload-status is-success";
    status.textContent = "استخراج و بررسی‌های قطعی انجام شد. یافته‌ها ابتکاری‌اند و باید با سند اصلی بازبینی شوند؛ AI و امتیازدهی هنوز فعال نیستند.";
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = fileInput.files && fileInput.files[0];
    if (!file) {
      showError("ابتدا یک فایل DOCX یا PDF انتخاب کنید.");
      return;
    }
    if (file.size > maxBytes) {
      showError("حجم فایل از حد " + Math.round(maxBytes / (1024 * 1024)) + " مگابایت بیشتر است.");
      return;
    }
    const suffix = file.name.toLowerCase().split(".").pop();
    if (["docx", "pdf"].indexOf(suffix) < 0) {
      showError("فقط فایل‌های DOCX و PDF پذیرفته می‌شوند؛ DOCM قابل قبول نیست.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file, file.name);
    submit.disabled = true;
    submit.textContent = "در حال بررسی…";
    status.className = "upload-status";
    status.textContent = "فایل در حال اعتبارسنجی، استخراج ساختار و اجرای قواعد قطعی است.";
    results.hidden = true;
    try {
      const response = await fetch("/api/v1/inspect", { method: "POST", body: formData });
      const payload = await response.json();
      if (!response.ok) {
        const detail = payload.detail;
        showError(typeof detail === "string" ? detail : (detail && detail.message) || "پردازش فایل ناموفق بود. ساختار یا قالب فایل را بررسی کنید.");
        return;
      }
      renderSummary(payload);
      results.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (_error) {
      showError("ارتباط با سرور برقرار نشد. برنامه را بررسی کنید و دوباره تلاش کنید.");
    } finally {
      submit.disabled = false;
      submit.textContent = "بررسی ساختار فایل";
    }
  });
  document.querySelectorAll("[data-export-format]").forEach((button) => {
    button.addEventListener("click", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) {
        document.querySelector("#export-status").textContent = "برای خروجی گرفتن، ابتدا فایل را دوباره انتخاب کنید.";
        return;
      }
      const outputFormat = button.dataset.exportFormat;
      const status = document.querySelector("#export-status");
      const formData = new FormData();
      formData.append("file", file, file.name);
      document.querySelectorAll("[data-export-format]").forEach((item) => { item.disabled = true; });
      status.textContent = "در حال تولید خروجی " + outputFormat.toUpperCase() + "…";
      try {
        const response = await fetch("/api/v1/report?format=" + encodeURIComponent(outputFormat), {
          method: "POST",
          body: formData,
        });
        if (!response.ok) {
          let message = "ساخت خروجی ناموفق بود.";
          try {
            const payload = await response.json();
            if (payload.detail) message = typeof payload.detail === "string" ? payload.detail : (payload.detail.message || message);
          } catch (_error) { /* keep the safe fallback message */ }
          status.textContent = message;
          return;
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "thesischeck-report." + outputFormat;
        document.body.append(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        status.textContent = "خروجی " + outputFormat.toUpperCase() + " آماده شد.";
      } catch (_error) {
        status.textContent = "ارتباط با سرور برقرار نشد؛ دوباره تلاش کنید.";
      } finally {
        document.querySelectorAll("[data-export-format]").forEach((item) => { item.disabled = false; });
      }
    });
  });

});
