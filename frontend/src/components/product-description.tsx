import type { ReactNode } from "react";

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={`${keyPrefix}-${index}`}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

export function ProductDescription({ text, className = "" }: { text: string; className?: string }) {
  const blocks: ReactNode[] = [];
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  let paragraph: string[] = [];
  let list: { type: "ul" | "ol"; items: Array<{ number: number; text: string }> } | null = null;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const isHeading = paragraph.length === 1 && /^\*\*[^*]+\*\*$/.test(paragraph[0].trim());
    blocks.push(
      <p key={`p-${blocks.length}`} className={isHeading ? "text-base font-semibold text-ink" : undefined}>
        {paragraph.map((line, index) => <span key={index}>{index ? <br /> : null}{renderInline(line, `p-${blocks.length}-${index}`)}</span>)}
      </p>,
    );
    paragraph = [];
  };

  const flushList = () => {
    if (!list) return;
    const items = list.items.map((item, index) => <li key={`${list?.type}-${index}`}>{renderInline(item.text, `li-${blocks.length}-${index}`)}</li>);
    blocks.push(list.type === "ul"
      ? <ul key={`ul-${blocks.length}`} className="list-disc space-y-1 pl-5">{items}</ul>
      : <ol key={`ol-${blocks.length}`} start={list.items[0]?.number ?? 1} className="list-decimal space-y-1 pl-5">{items}</ol>);
    list = null;
  };

  for (const line of lines) {
    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const numbered = /^\s*(\d+)\.\s+(.*)$/.exec(line);
    if (bullet || numbered) {
      flushParagraph();
      const type = bullet ? "ul" : "ol";
      if (list && list.type !== type) flushList();
      if (!list) list = { type, items: [] };
      list.items.push({ number: numbered ? Number(numbered[1]) : list.items.length + 1, text: bullet ? bullet[1] : numbered![2] });
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushList();

  return blocks.length ? <div className={`space-y-3 whitespace-normal ${className}`}>{blocks}</div> : null;
}
