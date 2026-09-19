function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function isImageUrl(url: string): boolean {
  try {
    const path = new URL(url).pathname.toLowerCase();
    return /\.(jpg|jpeg|png|gif|webp|avif|bmp)$/.test(path);
  } catch {
    return false;
  }
}

export function renderRedditBody(text: string): string {
  const pattern = /\[([^\]]*)\]\((https?:\/\/[^)]+)\)|(?<!\]\()(?<!\()https?:\/\/[^\s)>\]]+/g;
  let result = '';
  let lastIndex = 0;

  for (const match of text.matchAll(pattern)) {
    result += escapeHtml(text.slice(lastIndex, match.index));

    if (match[1] !== undefined) {
      const linkText = escapeHtml(match[1]);
      const url = match[2];
      if (isImageUrl(url)) {
        result += `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${linkText}</a>`;
        result += `<img src="${escapeHtml(url)}" alt="" loading="lazy" />`;
      } else {
        result += `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${linkText}</a>`;
      }
    } else {
      const url = match[0];
      if (isImageUrl(url)) {
        result += `<img src="${escapeHtml(url)}" alt="" loading="lazy" />`;
      } else {
        const escaped = escapeHtml(url);
        result += `<a href="${escaped}" target="_blank" rel="noopener noreferrer">${escaped}</a>`;
      }
    }

    lastIndex = (match.index ?? 0) + match[0].length;
  }

  result += escapeHtml(text.slice(lastIndex));
  return result;
}
