const TIME_RE = /\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?/;
const HINT_TEXT = '좌표를 클릭하면 해당 좌표의 스크린샷을 확인할 수 있습니다.';
const HINT_HTML = `<p class="timeline-hint">${HINT_TEXT}</p>`;

export function enhanceTimelineHtml(html: string) {
  return decorateSummaries(insertTimelineHint(html));
}

function insertTimelineHint(html: string) {
  if (html.includes('class="timeline-hint"')) return html;

  const detailsIdx = html.search(/<details\b/i);
  if (detailsIdx === -1) return html;

  const before = html.slice(0, detailsIdx);
  const headings = [...before.matchAll(/<h2\b[^>]*>[\s\S]*?<\/h2>/gi)];
  const heading = headings.at(-1);
  if (!heading || heading.index == null) return html;
  if (!/좌표|타임라인/.test(heading[0])) return html;

  const insertAt = heading.index + heading[0].length;
  return `${html.slice(0, insertAt)}\n${HINT_HTML}${html.slice(insertAt)}`;
}

function decorateSummaries(html: string) {
  return html.replace(/<details\b[^>]*>[\s\S]*?<\/details>/gi, (block) => {
    if (block.includes('class="timeline-time"') || block.includes("class='timeline-time'")) {
      return block;
    }

    const summaryMatch = block.match(/<summary\b([^>]*)>([\s\S]*?)<\/summary>/i);
    if (!summaryMatch) return block;

    const afterSummary = block.slice((summaryMatch.index ?? 0) + summaryMatch[0].length);
    const timeMatch = afterSummary.match(TIME_RE);
    if (!timeMatch) return block;

    const attrs = summaryMatch[1];
    const title = summaryMatch[2].trim();
    const stamped = `<summary${attrs}><span class="timeline-title">${title}</span><span class="timeline-time">좌표 ${timeMatch[1]}</span></summary>`;
    return block.replace(summaryMatch[0], stamped);
  });
}
