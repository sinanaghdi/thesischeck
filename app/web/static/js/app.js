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
      container.append(make("li", "empty-state", emptyText));
      return;
    }
    items.forEach((item) => container.append(renderItem(item)));
  }

  function showError(message) {
    results.hidden = true;
    status.className = "upload-status is-error";
    status.textContent = message;
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
    results.hidden = false;
    status.className = "upload-status is-success";
    status.textContent = "استخراج اولیه انجام شد. این گزارش فقط خلاصه parser است و هنوز بررسی علمی یا قالب‌بندی نهایی انجام نمی‌دهد.";
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
    status.textContent = "فایل در حال اعتبارسنجی و استخراج ساختار است. متن کامل به این صفحه بازگردانده نمی‌شود.";
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
