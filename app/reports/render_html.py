"""Dependency-free HTML report renderer; untrusted thesis text is HTML-escaped."""

from __future__ import annotations

from html import escape

from app.reports.scoring import HealthReport, ScoreCategory


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _category_row(category: ScoreCategory) -> str:
    score = "در دسترس نیست" if category.score is None else f"{category.score:.1f}/100"
    normalized = f"{category.normalized_weight:.2f}%"
    status = "ارزیابی‌شده" if category.available else "خارج از امتیاز"
    return (
        "<tr>"
        f"<td>{_e(category.title_fa)}<small dir=\"ltr\">{_e(category.title_en)}</small></td>"
        f"<td>{_e(category.configured_weight)}%</td>"
        f"<td>{_e(normalized)}</td>"
        f"<td>{_e(score)}</td>"
        f"<td>{_e(category.finding_count)}</td>"
        f"<td>{_e(status)}</td>"
        "</tr>"
    )


def _finding_card(item, index: int) -> str:
    location_parts = [
        item.element_id or "",
        " ← ".join(item.heading_path or []),
        f"صفحه {item.page_number}" if item.page_number else "",
    ]
    location = " · ".join(part for part in location_parts if part)
    return (
        f"<article class=\"finding { _e(item.severity) }\">"
        f"<div class=\"meta\"><span>{_e(item.severity)}</span>"
        f"<code dir=\"ltr\">{_e(item.rule_id)}</code>"
        f"<span>اطمینان {round(item.confidence * 100)}٪</span></div>"
        f"<h3>{index}. {_e(item.title_fa)}</h3>"
        f"<p>{_e(item.message_fa)}</p>"
        + (f"<blockquote><b>شاهد از سند</b><p>{_e(item.snippet)}</p></blockquote>" if item.snippet else "")
        + (f"<p class=\"location\">{_e(location)}</p>" if location else "")
        + f"<p class=\"fix\">{_e(item.suggested_fix_fa)}</p></article>"
    )


def render_html_report(report: HealthReport, *, include_all_findings: bool = True) -> str:
    """Render a self-contained RTL HTML report suitable for download or Chromium PDF."""
    categories = "".join(_category_row(item) for item in report.categories)
    findings = report.checks.findings if include_all_findings else report.top_issues
    finding_html = "".join(_finding_card(item, index) for index, item in enumerate(findings, 1))
    if not finding_html:
        finding_html = "<p class=\"empty\">در قواعدی که اجرا شده‌اند، یافته‌ای برای بازبینی ثبت نشد.</p>"
    limitations = "".join(f"<li>{_e(item)}</li>" for item in report.limitations_fa)
    diagnostics = "".join(
        f"<li><code dir=\"ltr\">{_e(item.get('code', ''))}</code> — {_e(item.get('message', ''))}</li>"
        for item in report.parser_diagnostics
    )
    score = "—" if report.score is None else f"{report.score:.1f}"
    return f"""<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>گزارش سلامت پایان‌نامه — {_e(report.file_name)}</title>
<style>
:root{{font-family:Tahoma,"Noto Naskh Arabic","DejaVu Sans",sans-serif;color:#192b26;background:#f5f7f5;line-height:1.85}}
*{{box-sizing:border-box}}body{{margin:0}}.sheet{{max-width:1060px;margin:28px auto;background:#fff;border:1px solid #e0e8e2;border-radius:16px;padding:34px;box-shadow:0 18px 48px #143d2b0c}}
header{{border-bottom:2px solid #1b6a53;padding-bottom:20px;margin-bottom:22px}}.brand{{font:700 13px Arial,sans-serif;letter-spacing:.12em;color:#1b6a53}}h1{{font-size:28px;margin:6px 0}}.subtitle{{color:#718078;font-size:12px}}.meta-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:15px}}.meta-box,.score-card,.category-card{{border:1px solid #e3ebe6;border-radius:10px;padding:12px;background:#fcfdfc}}.meta-box small,.score-card small{{display:block;color:#77857e;font-size:10px}}.meta-box strong{{font-size:12px;overflow-wrap:anywhere}}.score-grid{{display:grid;grid-template-columns:1.1fr 2fr;gap:12px;margin:20px 0}}.score-card strong{{display:block;color:#176b55;font-size:42px;line-height:1.45}}.score-card p{{font-size:11px;color:#687970;margin:4px 0}}.coverage{{display:inline-block;background:#e8f2ec;color:#24654f;padding:2px 8px;border-radius:20px;font-size:10px}}h2{{font-size:17px;margin:25px 0 10px}}h3{{font-size:13px;margin:9px 0 4px}}p{{overflow-wrap:anywhere}}.summary{{font-size:12px}}.warning{{border-right:3px solid #bd8b36;background:#fffbf1;border-radius:7px;padding:11px 13px;font-size:11px}}table{{width:100%;border-collapse:collapse;font-size:10px}}th,td{{border:1px solid #e3eae5;text-align:right;padding:8px;vertical-align:top}}th{{background:#eff5f0}}td small{{display:block;color:#849189;direction:ltr;text-align:right}}.formula{{font-size:11px;border:1px dashed #d7e1da;border-radius:8px;padding:12px;direction:rtl}}.finding{{border:1px solid #e4ebe6;border-right:3px solid #9eafa5;border-radius:10px;padding:13px 15px;margin:10px 0;break-inside:avoid}}.finding.error{{border-right-color:#b24b46}}.finding.warning{{border-right-color:#c28a3d}}.finding.info{{border-right-color:#8ca69a}}.meta{{display:flex;align-items:center;gap:10px;color:#738078;font-size:9px;flex-wrap:wrap}}code{{font-family:Consolas,monospace;direction:ltr;unicode-bidi:isolate}}.finding p{{font-size:11px;line-height:1.9;margin:5px 0}}blockquote{{margin:10px 0;padding:8px 12px;background:#f7f9f7;border-radius:7px;font-size:10px;overflow-wrap:anywhere;unicode-bidi:plaintext}}blockquote p{{white-space:pre-wrap}}.location{{color:#819087;font-size:9px!important}}.fix{{background:#eef5f0;border-radius:7px;padding:8px 10px;color:#385c4b}}ul{{padding-inline-start:22px;font-size:11px}}li{{margin:4px 0}}.empty{{background:#f6f8f6;padding:14px;border-radius:8px;font-size:11px}}footer{{margin-top:28px;border-top:1px solid #e4ebe6;padding-top:14px;color:#89958e;font-size:9px}}.ltr{{direction:ltr;unicode-bidi:isolate}}.exec-page{{break-after:page}}@page{{size:A4;margin:15mm}}@media print{{body{{background:white}}.sheet{{max-width:none;margin:0;border:0;border-radius:0;box-shadow:none;padding:0}}.exec-page{{min-height:250mm;break-after:page}}h2{{break-after:avoid}}.finding{{break-inside:avoid}}}}
</style>
</head>
<body><main class="sheet">
<section class="exec-page">
<header><div class="brand">THESISCHECK / HEALTH REPORT</div><h1>گزارش سلامت پیش‌نویس پایان‌نامه</h1>
<div class="subtitle">ابزار بازبینی نگارش و قالب‌بندی · این گزارش نمره دانشگاهی نیست.</div>
<div class="meta-grid">
<div class="meta-box"><small>نام فایل</small><strong>{_e(report.file_name)}</strong></div>
<div class="meta-box"><small>قالب منبع</small><strong dir="ltr">{_e(report.source_format.upper())}</strong></div>
<div class="meta-box"><small>زمان تولید (UTC)</small><strong dir="ltr">{_e(report.generated_at.strftime("%Y-%m-%d %H:%M"))}</strong></div>
</div></header>
<div class="score-grid">
<div class="score-card"><small>{_e(report.score_label_fa)}</small><strong>{score}<span style="font-size:15px;color:#829087"> / 100</span></strong>
<p>{_e(report.summary_fa)}</p><span class="coverage">پوشش وزن‌های امتیازدهی: {_e(report.coverage_percent)}٪</span></div>
<div class="score-card"><small>خلاصه اجرایی</small><p class="summary">{_e(report.summary_fa)}</p>
<p>یافته‌ها: {_e(report.severity_counts.get("error",0))} مهم · {_e(report.severity_counts.get("warning",0))} نیازمند بازبینی · {_e(report.severity_counts.get("info",0))} اطلاع‌رسانی</p>
<p>قواعد اجراشده: {_e(report.checks.rules_checked)} · قواعد ردشده یا ناموجود: {_e(report.checks.rules_skipped)}</p>
<div class="warning">{_e(report.checks.disclaimer_fa)}</div></div></div>
<h2>۱۰ مورد اولویت‌دار برای بازبینی</h2>
{''.join(_finding_card(item,index) for index,item in enumerate(report.top_issues,1)) or '<p class="empty">هنوز یافته‌ای برای اولویت‌بندی ثبت نشده است.</p>'}
<h2>روش محاسبه امتیاز</h2><div class="formula">{_e(report.score_formula_fa)}</div>
</section>
<section><h2>جزئیات پوشش و امتیاز دسته‌ها</h2>
<p class="subtitle">وزن پیکربندی‌شده در کنار وزن نرمال‌شده نشان داده شده است. دسته‌های ارزیابی‌نشده امتیاز ندارند و در مخرج امتیاز کل وارد نشده‌اند.</p>
<table><thead><tr><th>دسته</th><th>وزن</th><th>وزن در امتیاز کل</th><th>امتیاز دسته</th><th>یافته‌ها</th><th>وضعیت</th></tr></thead><tbody>{categories}</tbody></table>
<h2>همه یافته‌ها</h2>{finding_html}
<h2>محدودیت‌های تحلیل</h2><ul>{limitations}</ul>
{('<h2>تشخیص‌های استخراج فایل</h2><ul>'+diagnostics+'</ul>') if diagnostics else ''}
<footer>ThesisCheck · گزارش تولیدشده به‌صورت محلی · مجموعه قوانین: {_e(report.ruleset_name)} · نسخه: {_e(report.ruleset_version)} · وضعیت تأیید رسمی: {'تأییدنشده' if not report.ruleset_verified else 'تأییدشده'}<br>این ابزار منبع واقعی راستی‌آزمایی نمی‌کند، داده علمی تولید نمی‌کند و متن اصلی را تغییر نمی‌دهد. یافته‌ها را با سند اصلی بررسی کنید.</footer>
</section></main></body></html>"""
