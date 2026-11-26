"use client";

import { useRef } from "react";

import { ProductDescription } from "@/components/product-description";

type Props = { value: string; onChange: (value: string) => void; label?: string; id?: string };

export function ProductDescriptionField({ value, onChange, label = "Product description (optional)", id = "product-description" }: Props) {
  const textarea = useRef<HTMLTextAreaElement>(null);
  const updateValue = (next: string) => onChange(next.slice(0, 50000));

  function insertSyntax(kind: "bold" | "bullet" | "numbered") {
    const input = textarea.current;
    if (!input) return;
    const start = input.selectionStart;
    const end = input.selectionEnd;
    const selected = value.slice(start, end);
    let before = "";
    let replacement = "";
    let selectionStart = start;
    let selectionEnd = start;

    if (kind === "bold") {
      const content = selected || "text";
      replacement = `**${content}**`;
      selectionStart = start + 2;
      selectionEnd = selectionStart + content.length;
    } else {
      before = value.slice(0, start);
      const lineStart = before.lastIndexOf("\n") + 1;
      const lineEndAt = value.indexOf("\n", end);
      const lineEnd = lineEndAt < 0 ? value.length : lineEndAt;
      const selectedWithLines = value.slice(lineStart, lineEnd);
      replacement = selectedWithLines.split("\n").map((line, index) =>
        `${kind === "bullet" ? "- " : `${index + 1}. `}${line}`
      ).join("\n");
      selectionStart = lineStart;
      selectionEnd = lineStart + replacement.length;
      updateValue(`${value.slice(0, lineStart)}${replacement}${value.slice(lineEnd)}`);
      requestAnimationFrame(() => {
        input.focus();
        input.setSelectionRange(selectionStart, selectionEnd);
      });
      return;
    }

    updateValue(`${value.slice(0, start)}${replacement}${value.slice(end)}`);
    requestAnimationFrame(() => {
      input.focus();
      input.setSelectionRange(selectionStart, selectionEnd);
    });
  }

  return <div className="block text-sm">
    <label htmlFor={id}>{label}</label>
    <div className="mt-1 flex flex-wrap gap-2" role="toolbar" aria-label="Description formatting">
      <button type="button" onClick={() => insertSyntax("bold")} className="border border-line px-3 py-1.5 text-xs font-semibold">Bold</button>
      <button type="button" onClick={() => insertSyntax("bullet")} className="border border-line px-3 py-1.5 text-xs">Bullet list</button>
      <button type="button" onClick={() => insertSyntax("numbered")} className="border border-line px-3 py-1.5 text-xs">Numbered list</button>
    </div>
    <textarea id={id} ref={textarea} maxLength={50000} rows={5} value={value} onChange={(event) => updateValue(event.target.value)} placeholder="Details, fit, fabric, condition, or other notes" className="mt-2 block w-full border border-line px-3 py-2" />
    <span className="mt-1 block text-xs text-stone">{value.length}</span>
    <div className="mt-3 border border-line bg-white p-3">
      <p className="mb-2 text-xs font-semibold text-ink-muted">Customer preview</p>
      {value.trim() ? <ProductDescription text={value} className="text-sm leading-7 text-ink-muted" /> : <p className="text-sm text-stone">No description</p>}
    </div>
  </div>;
}
