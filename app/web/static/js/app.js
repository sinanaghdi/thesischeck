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
        const top = make("div", "finding-top");
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
    renderChecks(data.checks || { rules_checked: 0, rules_skipped: 0, findings: [], results: [] });
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
});
