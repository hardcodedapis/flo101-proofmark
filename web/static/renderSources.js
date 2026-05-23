function lessonPage(result, typeOrId) {
  const pages = result.lesson_graph?.pages || [];
  return pages.find((page) => page.type === typeOrId || page.id === typeOrId) || null;
}

function renderLearningMedia(result) {
  const mediaPage = lessonPage(result, "media_lesson");
  if (mediaPage?.source_cards?.length) {
    $("#videoGrid").innerHTML = mediaPage.source_cards.map((resource) => renderMediaCard(resource)).join("");
    return;
  }
  const sources = result.content_graph?.sources || [];
  const chunks = result.rag_pipeline?.retrieved_chunks || [];
  const resourceById = new Map();
  for (const source of sources) {
    if (!source.url && source.type !== "video") continue;
    resourceById.set(source.id, {
      title: source.title || source.url || "Source",
      type: source.type || "source",
      url: source.url || "",
      concepts: [],
      text: source.text || "",
    });
  }
  for (const chunk of chunks) {
    if (!chunk.url && !chunk.source_id) continue;
    const existing = resourceById.get(chunk.source_id) || {
      title: chunk.source_title || "Source",
      type: chunk.source_type || "source",
      url: chunk.url || "",
      concepts: [],
      text: chunk.text || "",
    };
    existing.concepts = [...new Set([...(existing.concepts || []), ...(chunk.concepts || [])])];
    if (!existing.text) existing.text = chunk.text || "";
    resourceById.set(chunk.source_id, existing);
  }
  const resources = [...resourceById.values()];
  if (!resources.length) {
    $("#videoGrid").innerHTML = `
      <article class="media-card empty">
        <strong>No external video or PDF link yet</strong>
        <p>Add a YouTube URL, source URL, PDF, Markdown notes, or transcript above and generate again.</p>
      </article>
    `;
    return;
  }
  $("#videoGrid").innerHTML = resources.map((resource) => renderMediaCard(resource)).join("");
}

function renderMediaCard(resource) {
  const embedUrl = youtubeEmbedUrl(resource.url);
  const rawType = resource.media_role || resource.type || "source";
  const sourceType = rawType === "pdf" || String(resource.url || "").toLowerCase().endsWith(".pdf")
    ? "pdf"
    : rawType;
  const tags = (resource.concepts || []).slice(0, 4).map((concept) => `<span>${escapeHtml(concept)}</span>`).join("");
  const bullets = (resource.bullets || []).slice(0, 3).map((bullet) => `<li>${escapeHtml(bullet)}</li>`).join("");
  const sections = (resource.sections || []).slice(0, 4).map((section) => `
    <li>
      <span>${escapeHtml([section.start, section.end].filter(Boolean).join("-") || section.source_chunk_id || "section")}</span>
      <strong>${escapeHtml(section.title || "Source section")}</strong>
      <p>${escapeHtml(section.summary || "")}</p>
    </li>
  `).join("");
  if (embedUrl) {
    return `
      <article class="media-card video-card">
        <div class="video-frame">
          <iframe src="${escapeHtml(embedUrl)}" title="${escapeHtml(resource.title)}" allowfullscreen loading="lazy"></iframe>
        </div>
        <div class="media-card-body">
          <span>${escapeHtml(sourceType)}</span>
          <strong>${escapeHtml(resource.title)}</strong>
          <p>${escapeHtml(resource.summary || resource.text || "Watch this section, then use the notes below to lock in the concept.")}</p>
          ${sections ? `<ul class="timeline-list">${sections}</ul>` : ""}
          ${bullets ? `<ul>${bullets}</ul>` : ""}
          <div class="tag-row">${tags}</div>
        </div>
      </article>
    `;
  }
  return `
    <article class="media-card source-link-card">
      <div class="source-icon">${sourceType === "pdf" ? "PDF" : "URL"}</div>
      <div class="media-card-body">
        <span>${escapeHtml(sourceType)}</span>
        <strong>${escapeHtml(resource.title)}</strong>
        <p>${escapeHtml(resource.summary || resource.text || "Open this source while studying the notes below.")}</p>
        ${resource.url ? `<a href="${escapeHtml(resource.url)}" target="_blank" rel="noopener noreferrer">Open source</a>` : ""}
        ${sections ? `<ul class="timeline-list">${sections}</ul>` : ""}
        ${bullets ? `<ul>${bullets}</ul>` : ""}
        <div class="tag-row">${tags}</div>
      </div>
    </article>
  `;
}

function renderLearningSource(resource, mode) {
  const embedUrl = youtubeEmbedUrl(resource.url);
  const sections = cleanSections(resource.sections || []);
  const bullets = cleanList(resource.bullets || []);
  const concepts = cleanList(resource.concepts || []).slice(0, 5);
  const summary = cleanText(resource.summary || resource.text || "");
  if (embedUrl && mode === "video") {
    return `
      <section class="learning-source video-source">
        <div class="video-frame">
          <iframe src="${escapeHtml(embedUrl)}" title="${escapeHtml(resource.title)}" allowfullscreen loading="lazy"></iframe>
        </div>
        <div>
          <p class="kicker">Video</p>
          <h2>${escapeHtml(cleanSourceTitle(resource.title || resource.url))}</h2>
          <p>${escapeHtml(summary || "Watch the segment once. Then use the check below before moving on.")}</p>
          ${renderSectionList(sections)}
          ${renderBulletList(bullets)}
          ${renderTags(concepts)}
        </div>
      </section>
    `;
  }
  return `
    <section class="learning-source">
      <div class="source-label">${escapeHtml(sourceLabel(resource))}</div>
      <div>
        <p class="kicker">${escapeHtml(sourceLabel(resource))}</p>
        <h2>${escapeHtml(cleanSourceTitle(resource.title || resource.url || "Source"))}</h2>
        <p>${escapeHtml(summary || "Use this source as reference material while reading the structured notes.")}</p>
        ${resource.url ? `<a href="${escapeHtml(resource.url)}" target="_blank" rel="noopener noreferrer">Open source</a>` : ""}
        ${renderSectionList(sections)}
        ${renderBulletList(bullets)}
        ${renderTags(concepts)}
      </div>
    </section>
  `;
}

function renderReadingBlock(note, index) {
  const body = cleanText(note.body || "");
  if (!body) return "";
  const label = index === 0 ? "Goal" : index === 1 ? "Core" : index === 2 ? "Trap" : "Note";
  return `
    <article>
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(note.title || "Learning note")}</strong>
      <p>${escapeHtml(body)}</p>
    </article>
  `;
}

function renderInlineCheck(check) {
  const prompt = check.prompt || "Explain the idea in one sentence.";
  return `
    <section class="inline-check" data-quiz-card data-check-type="typed_explanation" data-prompt="${escapeHtml(prompt)}">
      <span>Try this</span>
      <strong>${escapeHtml(prompt)}</strong>
      <textarea class="answer-box" rows="3" placeholder="Write a short answer in your own words."></textarea>
      <button type="button" class="ghost-button small" data-self-check>Mark done</button>
      <p class="quiz-feedback"></p>
      <small>This helps choose what to show next.</small>
    </section>
  `;
}

function renderSectionList(sections) {
  if (!sections.length) return "";
  return `
    <ol class="clean-list source-sections">
      ${sections.slice(0, 5).map((section) => `
        <li>
          <span>${escapeHtml([section.start, section.end].filter(Boolean).join("-") || section.source_chunk_id || "section")}</span>
          <strong>${escapeHtml(section.title || "Section")}</strong>
          <p>${escapeHtml(cleanText(section.summary || ""))}</p>
        </li>
      `).join("")}
    </ol>
  `;
}

function renderBulletList(bullets) {
  if (!bullets.length) return "";
  return `<ul class="bullet-list">${bullets.slice(0, 4).map((bullet) => `<li>${escapeHtml(cleanText(bullet))}</li>`).join("")}</ul>`;
}

function renderTags(items) {
  if (!items.length) return "";
  return `<div class="tag-row">${items.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>`;
}

function renderEmptyModule(message) {
  return `<section class="empty-module"><p>${escapeHtml(message)}</p></section>`;
}

function isVideoResource(resource) {
  const type = String(resource.media_role || resource.type || "").toLowerCase();
  const url = String(resource.url || "").toLowerCase();
  return type.includes("video") || type === "transcript" || url.includes("youtube.com") || url.includes("youtu.be");
}

function sourceLabel(resource) {
  const type = String(resource.media_role || resource.type || "source").toLowerCase();
  if (type.includes("pdf") || String(resource.url || "").toLowerCase().endsWith(".pdf")) return "PDF";
  if (type.includes("note")) return "Notes";
  if (type.includes("worksheet")) return "Practice";
  if (resource.url) return "URL";
  return "Source";
}

function cleanSourceTitle(title) {
  const text = String(title || "Source").trim();
  if (/^https?:\/\//i.test(text)) {
    try {
      const parsed = new URL(text);
      if (parsed.hostname.includes("youtube.com") || parsed.hostname.includes("youtu.be")) {
        return "YouTube lesson";
      }
      return parsed.hostname.replace(/^www\./, "");
    } catch (_error) {
      return "Source";
    }
  }
  return text.replace(/^www\./, "").slice(0, 96);
}

function cleanText(value, limit = 420) {
  const text = stripListArtifact(String(value || "").replace(/\\n/g, " ").replace(/\s+/g, " ").trim());
  if (!text || looksNoisy(text)) return "";
  return text.length > limit ? `${text.slice(0, limit).replace(/\s+\S*$/, "")}...` : text;
}

function cleanList(values) {
  const array = Array.isArray(values) ? values : [values].filter(Boolean);
  return [...new Set(array.flatMap(expandCleanListValue).map((item) => cleanText(item)).filter(Boolean))];
}

function expandCleanListValue(value) {
  if (value === null || value === undefined) return [];
  if (typeof value !== "string") return [value];
  const text = String(value).replace(/\\n/g, " ").replace(/\s+/g, " ").trim();
  if (!text) return [];
  const parsed = parsePackedStringList(text);
  if (parsed.length) return parsed;
  if (/["']\s*,\s*["']/.test(text)) {
    return text.split(/["']\s*,\s*["']/).map(stripListArtifact).filter(Boolean);
  }
  return [text];
}

function parsePackedStringList(value) {
  const text = value.trim();
  const candidates = [];
  if (text.startsWith("[") && text.endsWith("]")) candidates.push(text);
  if (/["']\s*,\s*["']/.test(text)) {
    const stripped = text.replace(/^["'\[]+|["'\]]+$/g, "");
    candidates.push(`["${stripped}"]`);
  }
  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate);
      if (Array.isArray(parsed)) return parsed.map(stripListArtifact).filter(Boolean);
    } catch (_error) {
      // Fall back to delimiter splitting below.
    }
  }
  return [];
}

function stripListArtifact(value) {
  return String(value || "")
    .replace(/^[\s"'`,\[]+/, "")
    .replace(/[\s"'`,\]]+$/, "")
    .replace(/\\"/g, '"')
    .trim();
}

function cleanSections(sections) {
  return (sections || [])
    .map((section) => ({
      ...section,
      title: cleanText(section.title || "Section"),
      summary: cleanText(section.summary || ""),
    }))
    .filter((section) => section.summary || section.title);
}

function looksNoisy(text) {
  const lower = String(text || "").toLowerCase();
  if (lower.startsWith("metadata only:")) return true;
  if (/(metadata only|url metadata only)/.test(lower) && /(youtube\.com\/watch|youtu\.be|https?:\/\/)/.test(lower)) {
    return true;
  }
  if (/^(https?:\/\/)?(www\.)?(youtube\.com\/watch|youtu\.be)\b/.test(lower)) return true;
  if (["/filter", "/flatedecode", "function()", "ytplayer", "client_canary_state", "xref", "endstream"].some((token) => lower.includes(token))) {
    return true;
  }
  const weird = [...String(text || "")].filter((char) => "{}<>/\\�".includes(char)).length;
  return weird / Math.max(1, String(text || "").length) > 0.16;
}

function uniqueBy(items, keyFn) {
  const seen = new Set();
  const result = [];
  for (const item of items || []) {
    const key = keyFn(item);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    result.push(item);
  }
  return result;
}

function youtubeEmbedUrl(url) {
  if (!url) return "";
  try {
    const parsed = new URL(url);
    let id = "";
    if (parsed.hostname.includes("youtube.com")) {
      id = parsed.searchParams.get("v") || "";
      if (!id && parsed.pathname.startsWith("/embed/")) id = parsed.pathname.split("/")[2] || "";
      if (!id && parsed.pathname.startsWith("/shorts/")) id = parsed.pathname.split("/")[2] || "";
    }
    if (parsed.hostname.includes("youtu.be")) {
      id = parsed.pathname.split("/").filter(Boolean)[0] || "";
    }
    return id ? `https://www.youtube.com/embed/${encodeURIComponent(id)}` : "";
  } catch (_error) {
    return "";
  }
}

function youtubeWatchUrlAt(url, start) {
  if (!url) return "";
  const seconds = timeToSeconds(start);
  if (!seconds) return url;
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes("youtube.com")) {
      parsed.searchParams.set("t", `${seconds}s`);
      return parsed.toString();
    }
    if (parsed.hostname.includes("youtu.be")) {
      parsed.searchParams.set("t", `${seconds}s`);
      return parsed.toString();
    }
  } catch (_error) {
    return url;
  }
  return url;
}

function timeToSeconds(value) {
  const text = String(value || "").trim();
  if (!text) return 0;
  const parts = text.split(":").map((part) => Number(part));
  if (parts.some((part) => Number.isNaN(part))) return 0;
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return parts[0] || 0;
}

function buildMemoryCards(graph, chunks) {
  const concepts = graph.concepts || [];
  const cards = concepts.slice(0, 5).map((concept) => ({
    type: "concept",
    title: concept.name,
    body: [
      concept.common_confusions?.length ? `Do not confuse with ${concept.common_confusions.slice(0, 2).join(", ")}.` : "",
      concept.prerequisites?.length ? `Prerequisite: ${concept.prerequisites.slice(0, 2).join(", ")}.` : "",
    ].filter(Boolean).join(" ") || "Use this concept in the final challenge.",
  }));
  const formulaSnippets = [];
  for (const chunk of chunks) {
    for (const match of String(chunk.text || "").matchAll(/(\$\$[^$]+\$\$|\$[^$\n]+\$|\\\([^)]+\\\)|\\\[[\s\S]+?\\\])/g)) {
      formulaSnippets.push(match[0]);
    }
  }
  for (const formula of [...new Set(formulaSnippets)].slice(0, 3)) {
    cards.push({
      type: "formula",
      title: formula,
      body: "Write what each symbol means before applying the equation.",
    });
  }
  return cards.slice(0, 8);
}
