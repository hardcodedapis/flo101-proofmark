function renderVideoModule(cards, page, result) {
  const cleanCards = (cards || []).filter(Boolean);
  const study = normalizeStudentLesson(
    page.student_video_lesson || result.ai_source_analysis?.student_video_lesson || {},
    result.model_generation?.assets?.student_study_pack || {},
    page.video_learning_plan || result.ai_source_analysis?.video_learning_plan || {},
  );
  const videoCard = cleanCards.find((card) => youtubeEmbedUrl(card.url)) || cleanCards[0] || {};
  return `
    <section class="video-breakdown-hero">
      <div class="study-summary">
        <p class="kicker">What the video teaches</p>
        <h2>${escapeHtml(study.friendly_title || "Video lesson")}</h2>
        <p>${escapeHtml(study.one_minute_summary || "Use this as the clean version of the video: summary first, then formulas, diagrams, and a short check.")}</p>
      </div>
      ${renderVoiceOverview(study)}
    </section>
    ${renderFormulaCards(study.formula_cards)}
    ${renderFactSection("Important points", study.key_facts)}
    ${renderAiVisualArtifact(result.model_generation?.assets?.visual_artifact, result.model_generation?.status)}
    ${renderMindMap(study.mindmap)}
    ${renderSimpleCards("Shortcuts", study.shortcuts)}
    ${renderSimpleCards("Remember this", study.things_to_remember)}
    ${renderSimpleCards("Tips and tricks", study.tips_and_tricks)}
    ${renderTimestampGuide(study.timestamp_guide, videoCard.url)}
    ${renderStudentVideoSource(videoCard, study)}
    ${renderDiagramPrompts(study.diagram_prompts)}
    ${renderSimpleCards("Common mistakes", study.common_mistakes)}
    ${renderDrawingEvidence(result.model_generation?.assets?.visual_artifact, study)}
    ${renderInlineCheck(page.completion_check || {
      prompt: study.tiny_check?.prompt || "What is the one idea this video is trying to teach?",
      evidence_collected: ["source_grounding", "confidence"],
    })}
  `;
}

function renderProviderNotice(result) {
  const notices = result?.provider_notices || [];
  if (!notices.length) return "";
  const rateLimited = notices.some((notice) => notice.kind === "rate_limit" || Number(notice.status_code) === 429);
  const title = rateLimited ? "AI provider limit hit" : "AI provider fallback";
  const copy = rateLimited
    ? "The provider rate-limited the request after retry. This run shows the local fallback and keeps the provider status visible."
    : "The provider did not return the expected structured output. This run shows the local source-grounded fallback and keeps the provider status visible.";
  return `
    <section class="provider-notice" role="status">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(copy)}</p>
      <ul>
        ${notices.map((notice) => `
          <li>
            <b>${escapeHtml(notice.stage || "AI call")}</b>
            <span>${escapeHtml(notice.provider || "provider")}${notice.status_code ? ` · HTTP ${escapeHtml(notice.status_code)}` : ""}</span>
            <small>${escapeHtml(cleanText(notice.message || ""))}</small>
            ${notice.fallback ? `<small>${escapeHtml(cleanText(notice.fallback))}</small>` : ""}
          </li>
        `).join("")}
      </ul>
    </section>
  `;
}

function normalizeStudentLesson(lesson, modelPack, videoPlan) {
  const merged = { ...(lesson || {}) };
  if (modelPack?.one_minute_summary) merged.one_minute_summary = modelPack.one_minute_summary;
  if (modelPack?.key_facts?.length) {
    merged.key_facts = modelPack.key_facts.map((fact) => ({ fact, why_it_matters: "Use this in the next question." }));
  }
  if (modelPack?.formula_cards?.length) merged.formula_cards = modelPack.formula_cards;
  if (modelPack?.things_to_remember?.length) merged.things_to_remember = modelPack.things_to_remember;
  if (modelPack?.tips_and_tricks?.length) merged.tips_and_tricks = modelPack.tips_and_tricks;
  if (modelPack?.shortcuts?.length) merged.shortcuts = modelPack.shortcuts;
  if (modelPack?.voice_over_script) merged.audio_overview_script = modelPack.voice_over_script;
  if (!merged.timestamp_guide?.length && videoPlan?.segments?.length) {
    merged.timestamp_guide = videoPlan.segments.slice(0, 6).map((segment) => ({
      start: segment.start || "",
      end: segment.end || "",
      title: segment.title || "Video part",
      what_happens: segment.watch_goal || "",
      watch_for: segment.signals_to_notice || [],
    }));
  }
  return merged;
}

function renderVoiceOverview(study) {
  const script = cleanText(study.audio_overview_script || buildVoiceScript(study));
  if (!script) return "";
  return `
    <aside class="voice-overview">
      <p class="kicker">Audio option</p>
      <h3>Listen to the explanation</h3>
      <p>This turns the extracted video ideas into a short spoken overview. Full live conversation would need a streaming speech layer; this demo keeps it to narrated learning.</p>
      <button type="button" class="small" id="voiceSummaryButton" data-voice-script="${escapeHtml(script)}">Generate voice summary</button>
      <audio id="voiceSummaryAudio" controls class="hidden"></audio>
      <small id="voiceSummaryStatus">Uses the configured backend demo voice. Deepgram-style live conversation is documented as future scope.</small>
    </aside>
  `;
}

function buildVoiceScript(study) {
  const facts = cleanList((study.key_facts || []).map((item) => typeof item === "string" ? item : item.fact));
  const formula = (study.formula_cards || [])[0];
  return [
    study.one_minute_summary,
    facts.slice(0, 3).join(" "),
    formula ? `The key formula is ${formula.latex}. ${formula.meaning}` : "",
    "Remember: understand the meaning first, then choose the formula, then check the common trap.",
  ].filter(Boolean).join(" ");
}

function renderFormulaCards(cards) {
  const formulas = (cards || [])
    .filter((card) => card && (card.latex || card.meaning || card.label))
    .slice(0, 5);
  if (!formulas.length) return "";
  return `
    <section class="module-section formula-section">
      <h2>Formulas</h2>
      <div class="formula-grid">
        ${formulas.map((card) => `
          <article>
            <span>${escapeHtml(card.label || "Formula")}</span>
            ${renderFormulaLatex(card.latex || "")}
            <p>${escapeHtml(cleanText(card.meaning || ""))}</p>
            ${card.when_to_use ? `<small>${escapeHtml(cleanText(card.when_to_use))}</small>` : ""}
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderFormulaLatex(value) {
  const latex = normalizeLatex(value);
  if (!latex) return "";
  return `<div class="formula-latex">\\[${escapeHtml(latex)}\\]</div>`;
}

function normalizeLatex(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\\\\(?=(?:frac|text|sqrt|sin|cos|tan|log|ln|left|right|theta|alpha|beta|gamma|delta|Delta|lambda|mu|cdot|times|rightarrow|le|ge|pm|infty|vec|hat|circ)\b)/g, "\\")
    .replace(/\\n/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function renderStudentVideoSource(card, study) {
  const embedUrl = youtubeEmbedUrl(card.url);
  if (embedUrl) {
    return `
      <section class="module-section">
        <h2>Original video source</h2>
        <p class="section-help">Use this only if you want to inspect the original explanation. The important ideas are already extracted above.</p>
        <div class="student-video-frame compact-video">
          <iframe src="${escapeHtml(embedUrl)}" title="${escapeHtml(study.friendly_title || card.title || "Video lesson")}" allowfullscreen loading="lazy"></iframe>
        </div>
      </section>
    `;
  }
  return `
    <section class="module-section">
      <h2>Original source</h2>
      <div class="student-video-placeholder">
        <strong>${escapeHtml(study.friendly_title || cleanSourceTitle(card.title || card.url || "Video lesson"))}</strong>
        <p>${escapeHtml(card.url ? "Open the source only if you want to inspect the original material." : "No playable video URL was supplied, so this page uses the transcript and notes.")}</p>
        ${card.url ? `<a href="${escapeHtml(card.url)}" target="_blank" rel="noopener noreferrer">Open source</a>` : ""}
      </div>
    </section>
  `;
}

function renderFactSection(title, facts) {
  const cleanFacts = normalizeFactCards(facts).slice(0, 6);
  if (!cleanFacts.length) return "";
  return `
    <section class="module-section">
      <h2>${escapeHtml(title)}</h2>
      <div class="fact-grid">
        ${cleanFacts.map((item) => `
          <article>
            ${renderTextCard(item.fact, item.why_it_matters)}
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderSimpleCards(title, items) {
  const values = cleanStudyItems(items || []);
  if (!values.length) return "";
  return `
    <section class="module-section">
      <h2>${escapeHtml(title)}</h2>
      <div class="simple-card-list">
        ${values.slice(0, 6).map((item) => `<article>${renderTextCard(item)}</article>`).join("")}
      </div>
    </section>
  `;
}

function normalizeFactCards(facts) {
  const rows = [];
  for (const item of facts || []) {
    if (typeof item === "string") {
      cleanStudyItems([item]).forEach((fact) => rows.push({ fact, why_it_matters: "" }));
      continue;
    }
    const factValues = cleanStudyItems([item?.fact || item?.title || ""]);
    const why = cleanSupportText(item?.why_it_matters || item?.why || "");
    factValues.forEach((fact) => rows.push({ fact, why_it_matters: why }));
  }
  return rows.filter((item) => item.fact);
}

function cleanStudyItems(items, limit = 220) {
  return cleanList(items)
    .flatMap(splitLongStudyItem)
    .map((item) => cleanText(item, limit))
    .filter(Boolean);
}

function splitLongStudyItem(value) {
  const text = cleanText(value, 640);
  if (!text) return [];
  if (text.length > 230 && text.split(";").length >= 3) {
    return text.split(/;\s+/).map((part) => part.trim()).filter((part) => part.length > 18);
  }
  return [text];
}

function cleanSupportText(value) {
  const text = cleanText(value, 180);
  if (/^use this in the next (question|practice question)\.?$/i.test(text)) return "";
  return text;
}

function renderTextCard(value, support = "") {
  const text = cleanText(value, 260);
  const help = cleanSupportText(support);
  if (!text) return "";
  const parts = splitTitleBody(text);
  return `
    <strong>${escapeHtml(parts.title)}</strong>
    ${parts.body ? `<p>${escapeHtml(parts.body)}</p>` : ""}
    ${help ? `<small>${escapeHtml(help)}</small>` : ""}
  `;
}

function splitTitleBody(value) {
  const text = cleanText(value, 260);
  const colonIndex = text.indexOf(":");
  if (colonIndex > 4 && colonIndex < 58) {
    return {
      title: text.slice(0, colonIndex).trim(),
      body: text.slice(colonIndex + 1).trim(),
    };
  }
  return { title: text, body: "" };
}

function renderTimestampGuide(items, url) {
  const rows = (items || []).filter((item) => item && (item.title || item.what_happens || item.start));
  if (!rows.length) return "";
  return `
    <section class="module-section">
      <h2>Useful timestamps</h2>
      <div class="timestamp-guide">
        ${rows.slice(0, 6).map((item) => {
          const label = [item.start, item.end].filter(Boolean).join("-") || "Source";
          const timedUrl = youtubeWatchUrlAt(url, item.start);
          return `
            <article>
              <a href="${escapeHtml(timedUrl || url || "#")}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>
              <div>
                <strong>${escapeHtml(item.title || "Video part")}</strong>
                <p>${escapeHtml(cleanText(item.what_happens || ""))}</p>
                ${renderMiniList("Look for", item.watch_for)}
              </div>
            </article>
          `;
        }).join("")}
      </div>
    </section>
  `;
}

function renderMindMap(map) {
  if (!map || !map.branches?.length) return "";
  const branches = normalizeMindMapBranches(map.branches).slice(0, 6);
  if (!branches.length) return "";
  return `
    <section class="module-section">
      <h2>Mind map</h2>
      <div class="mindmap-panel">
        <div class="mindmap-center">${escapeHtml(map.center || "Main idea")}</div>
        <div class="mindmap-branches">
          ${branches.map((branch) => `
            <article>
              <strong>${escapeHtml(branch.label || "Branch")}</strong>
              <ul>${branch.points.slice(0, 4).map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ul>
            </article>
          `).join("")}
        </div>
      </div>
    </section>
  `;
}

function normalizeMindMapBranches(branches) {
  return (branches || [])
    .map((branch) => ({
      label: cleanText(branch?.label || "Branch", 42),
      points: cleanStudyItems(branch?.points || [], 180),
    }))
    .filter((branch) => branch.label && branch.points.length);
}

function renderLearnerDiagramSection(study) {
  const center = study?.mindmap?.center || "Main idea";
  const branches = Array.isArray(study?.mindmap?.branches) ? study.mindmap.branches : [];
  const pathNodes = diagramPathNodes(center, branches).filter((node) => cleanDiagramText(node.body));
  const trap = extractTrapConcept(study, center);
  if (!pathNodes.length && !trap) return "";
  return `
    <section class="module-section">
      <h2>Diagram</h2>
      <div class="learner-diagrams">
        <article class="concept-map-diagram">
          <div class="diagram-caption">
            <span>Concept picture</span>
            <strong>Read from the center outward</strong>
          </div>
          <div class="concept-map-canvas">
            <div class="concept-center">
              <span>Main idea</span>
              <strong>${escapeHtml(center)}</strong>
            </div>
            ${pathNodes.map((node, index) => `
              <div class="concept-orbit orbit-${index + 1}">
                <span>${escapeHtml(node.label)}</span>
                <strong>${escapeHtml(node.title)}</strong>
                <p>${escapeHtml(cleanDiagramText(node.body))}</p>
              </div>
            `).join("")}
          </div>
        </article>
        <article class="trap-diagram">
          <div class="diagram-caption">
            <span>Trap check</span>
            <strong>Do not mix these two ideas</strong>
          </div>
          <div class="trap-columns">
            <div>
              <span>Main idea</span>
              <strong>${escapeHtml(center)}</strong>
              <p>${escapeHtml(firstBranchPoint(branches, "Meaning") || "Explain this in your own words before solving.")}</p>
            </div>
            <div>
              <span>Common mix-up</span>
              <strong>${escapeHtml(trap || "Similar idea")}</strong>
              <p>${escapeHtml(firstMistake(study) || "Check how it is different before choosing a formula.")}</p>
            </div>
          </div>
        </article>
      </div>
    </section>
  `;
}

function renderAiVisualArtifact(artifact, generationStatus) {
  if (!artifact || artifact.kind === "ai_unavailable") {
    return `
      <section class="module-section ai-visual-unavailable">
        <h2>AI diagram</h2>
        <p>The diagram is intentionally not faked. It appears only after the model returns a renderable visual artifact. This run hit a provider limit, so retry after the limit clears or use a cached successful response.</p>
      </section>
    `;
  }
  const normalizedArtifact = normalizeVisualArtifact(artifact);
  const nodes = Array.isArray(normalizedArtifact.nodes) ? normalizedArtifact.nodes : [];
  const edges = Array.isArray(normalizedArtifact.edges) ? normalizedArtifact.edges : [];
  const rays = Array.isArray(normalizedArtifact.rays) ? normalizedArtifact.rays : [];
  const annotations = Array.isArray(normalizedArtifact.annotations) ? normalizedArtifact.annotations : [];
  if (!nodes.length && !edges.length && !rays.length && !annotations.length) {
    return `
      <section class="module-section ai-visual-unavailable">
        <h2>AI diagram</h2>
        <p>The model responded, but it did not return enough visual primitives to draw. Retry generation or use a richer source/video input.</p>
      </section>
    `;
  }
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const labelPolicy = diagramLabelPolicy(normalizedArtifact);
  const isModelGenerated = generationStatus === "model_generated";
  return `
    <section class="module-section ai-visual-section">
      <div class="section-title-row">
        <div>
          <p class="kicker">${isModelGenerated ? "AI generated diagram" : "Local source-grounded diagram"}</p>
          <h2>${escapeHtml(normalizedArtifact.title || "Concept diagram")}</h2>
        </div>
        <span>${escapeHtml(normalizedArtifact.kind || "visual")}</span>
      </div>
      <div class="ai-visual-layout">
        <svg class="ai-diagram-svg" viewBox="0 0 720 360" role="img" aria-label="${escapeHtml(normalizedArtifact.title || "AI diagram")}">
          <defs>
            <marker id="arrow-green" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L9,3 z" fill="currentColor"></path>
            </marker>
            <marker id="arrow-gold" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L0,6 L9,3 z" fill="currentColor"></path>
            </marker>
          </defs>
          <line class="axis-line" x1="40" y1="180" x2="680" y2="180"></line>
          ${rays.map((ray) => renderSvgRay(ray, labelPolicy)).join("")}
          ${edges.map((edge) => renderSvgEdge(edge, nodeMap, labelPolicy)).join("")}
          ${nodes.map((node) => renderSvgNode(node, labelPolicy)).join("")}
          ${annotations.map((annotation) => renderSvgAnnotation(annotation, labelPolicy)).join("")}
        </svg>
        <div class="ai-visual-notes">
          <strong>${escapeHtml(normalizedArtifact.concept || "Concept")}</strong>
          <p>${escapeHtml(normalizedArtifact.learner_goal || "Use the diagram to explain the idea before solving.")}</p>
          ${renderMiniList("How to read it", normalizedArtifact.instructions || [])}
          ${renderMiniList("Diagram labels", diagramLegendItems(normalizedArtifact))}
        </div>
      </div>
    </section>
  `;
}

function normalizeVisualArtifact(artifact) {
  const copy = { ...(artifact || {}) };
  const nodes = Array.isArray(copy.nodes) ? copy.nodes.map((node) => ({ ...node })) : [];
  const rays = Array.isArray(copy.rays) ? copy.rays.map((ray) => ({ ...ray })) : [];
  const annotations = Array.isArray(copy.annotations) ? copy.annotations.map((annotation) => ({ ...annotation })) : [];
  const points = [
    ...nodes.map((node) => ({ x: Number(node.x), y: Number(node.y) })),
    ...rays.flatMap((ray) => [
      { x: Number(ray.from_x), y: Number(ray.from_y) },
      { x: Number(ray.to_x), y: Number(ray.to_y) },
    ]),
    ...annotations.map((annotation) => ({ x: Number(annotation.x), y: Number(annotation.y) })),
  ].filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  const bounds = diagramBounds(points);
  const mapper = diagramCoordinateMapper(bounds);
  for (const node of nodes) {
    const point = mapper(Number(node.x), Number(node.y));
    node.x = point.x;
    node.y = point.y;
  }
  for (const ray of rays) {
    const from = mapper(Number(ray.from_x), Number(ray.from_y));
    const to = mapper(Number(ray.to_x), Number(ray.to_y));
    ray.from_x = from.x;
    ray.from_y = from.y;
    ray.to_x = to.x;
    ray.to_y = to.y;
  }
  for (const annotation of annotations) {
    const point = mapper(Number(annotation.x), Number(annotation.y));
    annotation.x = point.x;
    annotation.y = point.y;
  }
  return { ...copy, nodes, rays, annotations };
}

function diagramBounds(points) {
  if (!points.length) return { minX: 0, maxX: 720, minY: 0, maxY: 360 };
  return {
    minX: Math.min(...points.map((point) => point.x)),
    maxX: Math.max(...points.map((point) => point.x)),
    minY: Math.min(...points.map((point) => point.y)),
    maxY: Math.max(...points.map((point) => point.y)),
  };
}

function diagramCoordinateMapper(bounds) {
  const padX = 52;
  const padY = 36;
  const spanX = Math.max(1, bounds.maxX - bounds.minX);
  const spanY = Math.max(1, bounds.maxY - bounds.minY);
  const normalized01 = bounds.minX >= -0.05 && bounds.maxX <= 1.5 && bounds.minY >= -0.05 && bounds.maxY <= 1.5;
  const normalized100 = bounds.minX >= -1 && bounds.maxX <= 110 && bounds.minY >= -1 && bounds.maxY <= 110;
  const outOfCanvas = bounds.minX < 0 || bounds.maxX > 720 || bounds.minY < 0 || bounds.maxY > 360;
  return (x, y) => {
    let mappedX = Number.isFinite(x) ? x : 360;
    let mappedY = Number.isFinite(y) ? y : 180;
    if (normalized01) {
      mappedX = padX + mappedX * (720 - padX * 2);
      mappedY = padY + mappedY * (360 - padY * 2);
    } else if (normalized100) {
      mappedX = padX + (mappedX / 100) * (720 - padX * 2);
      mappedY = padY + (mappedY / 100) * (360 - padY * 2);
    } else if (outOfCanvas) {
      mappedX = padX + ((mappedX - bounds.minX) / spanX) * (720 - padX * 2);
      mappedY = padY + ((mappedY - bounds.minY) / spanY) * (360 - padY * 2);
    }
    return {
      x: clampDiagramX(mappedX),
      y: clampDiagramY(mappedY),
    };
  };
}

function diagramLabelPolicy(artifact) {
  const rayDiagram = isRayDiagram(artifact);
  return {
    rayDiagram,
    showRayLabels: !rayDiagram,
    showEdgeLabels: !rayDiagram,
    showAnnotations: !rayDiagram,
    showNodeLabels: true,
    maxNodeLabelLength: rayDiagram ? 16 : 26,
  };
}

function isRayDiagram(artifact) {
  const text = `${artifact?.kind || ""} ${artifact?.title || ""} ${artifact?.concept || ""}`.toLowerCase();
  return text.includes("ray")
    || text.includes("lens")
    || text.includes("optics")
    || (Array.isArray(artifact?.rays) && artifact.rays.length >= 2);
}

function renderSvgRay(ray, labelPolicy = {}) {
  const labelPoint = labelBetween(ray.from_x, ray.from_y, ray.to_x, ray.to_y, -12);
  return `
    <g class="svg-ray ${escapeHtml(ray.style || "main")}">
      <line x1="${num(ray.from_x)}" y1="${num(ray.from_y)}" x2="${num(ray.to_x)}" y2="${num(ray.to_y)}"></line>
      ${labelPolicy.showRayLabels && ray.label ? `<text x="${numX(labelPoint.x)}" y="${numY(labelPoint.y)}">${escapeHtml(shortDiagramLabel(ray.label, 34))}</text>` : ""}
    </g>
  `;
}

function renderSvgEdge(edge, nodeMap, labelPolicy = {}) {
  const from = nodeMap.get(edge.from);
  const to = nodeMap.get(edge.to);
  if (!from || !to) return "";
  const labelPoint = labelBetween(from.x, from.y, to.x, to.y, -10);
  return `
    <g class="svg-edge ${escapeHtml(edge.kind || "edge")}">
      <line x1="${num(from.x)}" y1="${num(from.y)}" x2="${num(to.x)}" y2="${num(to.y)}"></line>
      ${labelPolicy.showEdgeLabels && edge.label ? `<text x="${numX(labelPoint.x)}" y="${numY(labelPoint.y)}">${escapeHtml(shortDiagramLabel(edge.label, 28))}</text>` : ""}
    </g>
  `;
}

function renderSvgNode(node, labelPolicy = {}) {
  const role = String(node.role || "node").toLowerCase();
  const isLens = role.includes("lens") || role.includes("center");
  const label = nodeLabelPosition(node, isLens);
  const nodeLabel = diagramNodeLabel(node, labelPolicy);
  const showLabel = nodeLabel && shouldShowNodeLabel(node, labelPolicy);
  return `
    <g class="svg-node ${escapeHtml(role)}">
      ${isLens
        ? `<line x1="${numX(node.x)}" y1="${numY(Number(node.y) - 95)}" x2="${numX(node.x)}" y2="${numY(Number(node.y) + 95)}"></line>`
        : `<circle cx="${numX(node.x)}" cy="${numY(node.y)}" r="8"></circle>`}
      ${showLabel ? `<text text-anchor="${escapeHtml(label.anchor)}" x="${numX(label.x)}" y="${numY(label.y)}">${escapeHtml(nodeLabel)}</text>` : ""}
    </g>
  `;
}

function renderSvgAnnotation(annotation, labelPolicy = {}) {
  if (!labelPolicy.showAnnotations) return "";
  return `<text class="svg-annotation" x="${numX(annotation.x)}" y="${numY(annotation.y)}">${escapeHtml(shortDiagramLabel(annotation.text || "", 58))}</text>`;
}

function shouldShowNodeLabel(node, labelPolicy = {}) {
  if (!labelPolicy.showNodeLabels) return false;
  if (!labelPolicy.rayDiagram) return true;
  const text = `${node.role || ""} ${node.label || ""} ${node.id || ""}`.toLowerCase();
  if (/\b(ray|incident|refracted|through|from|mark|tip)\b/.test(text)) return false;
  return /\b(lens|center|object|image|focus|principal|optical|f1|f2|2f1|2f2|o)\b/.test(text)
    || /(^|\s)2f/.test(text)
    || /(^|\s)f[12]?($|\s)/.test(text);
}

function diagramLegendItems(artifact) {
  const labelPolicy = diagramLabelPolicy(artifact);
  const items = [];
  for (const node of artifact.nodes || []) {
    if (!shouldShowNodeLabel(node, labelPolicy)) continue;
    const text = diagramNodeLabel(node, { ...labelPolicy, maxNodeLabelLength: 36 });
    if (text) items.push(text);
  }
  for (const annotation of artifact.annotations || []) {
    const text = shortDiagramLabel(annotation.text || "", 54);
    if (text) items.push(text);
  }
  return [...new Set(items)].slice(0, 6);
}

function diagramNodeLabel(node, labelPolicy = {}) {
  const label = cleanText(node.label || "");
  if (label) return shortDiagramLabel(label, labelPolicy.maxNodeLabelLength || 26);
  const id = cleanText(node.id || "");
  if (/^(o|f1|f2|2f1|2f2)$/i.test(id)) return id.toUpperCase();
  return "";
}

function num(value) {
  return numX(value);
}

function numX(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? String(clampDiagramX(parsed)) : "360";
}

function numY(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? String(clampDiagramY(parsed)) : "180";
}

function clampDiagramX(value) {
  return Math.max(24, Math.min(696, Number(value)));
}

function clampDiagramY(value) {
  return Math.max(24, Math.min(336, Number(value)));
}

function mid(a, b) {
  return (Number(a) + Number(b)) / 2;
}

function labelBetween(x1, y1, x2, y2, offset) {
  return {
    x: mid(x1, x2),
    y: mid(y1, y2) + offset,
  };
}

function nodeLabelPosition(node, isLens) {
  const role = String(node.role || "").toLowerCase();
  const x = Number(node.x);
  const y = Number(node.y);
  if (isLens) return { x, y: y - 108, anchor: "middle" };
  if (role.includes("focus") || role === "f" || role.includes("2f")) return { x, y: y + 24, anchor: "middle" };
  if (role.includes("image")) return { x: x + 14, y: y + 24, anchor: "start" };
  if (role.includes("object")) return { x: x + 14, y: y - 18, anchor: "start" };
  if (x > 620) return { x: x - 14, y: y - 14, anchor: "end" };
  return { x: x + 14, y: y - 14, anchor: "start" };
}

function shortDiagramLabel(value, limit = 28) {
  const text = cleanText(value);
  if (text.length <= limit) return text;
  return `${text.slice(0, limit).replace(/\s+\S*$/, "")}...`;
}

function renderDrawingEvidence(artifact, study) {
  const prompt = artifact?.draw_question || study?.tiny_check?.prompt || "Draw the concept and label the main idea, rule, and trap.";
  const expected = cleanList(artifact?.expected_features || ["main idea", "rule or formula", "common trap"]);
  const concept = artifact?.concept || study?.mindmap?.center || "";
  return `
    <section class="drawing-check" data-quiz-card data-drawing-check data-check-type="visual_map" data-concept="${escapeHtml(concept)}" data-prompt="${escapeHtml(prompt)}">
      <span>Draw check</span>
      <strong>${escapeHtml(prompt)}</strong>
      <p>Upload a photo or screenshot of the drawing. Add notes only if the image needs extra explanation.</p>
      <div class="drawing-evidence-grid">
        <div class="drawing-response">
          <label class="drawing-image-drop">
            <input type="file" accept="image/*" data-drawing-image>
            <span>Attach drawing image</span>
            <small>PNG, JPG, or WebP. The browser compresses it before sending evidence.</small>
          </label>
          <div class="drawing-image-preview hidden" data-drawing-image-preview></div>
          <textarea class="answer-box" rows="4" placeholder="Optional notes: labels, arrows/rays, formula links, or what you are unsure about."></textarea>
        </div>
        <div class="feature-checks">
          ${expected.slice(0, 6).map((feature, index) => `
            <label>
              <input type="checkbox" data-drawing-feature value="${escapeHtml(feature)}">
              <span>${escapeHtml(feature)}</span>
            </label>
          `).join("")}
          ${expected.length ? "" : `<small>No expected features were returned by the model.</small>`}
        </div>
      </div>
      <button type="button" class="ghost-button small" data-self-check>Save drawing evidence</button>
      <p class="quiz-feedback"></p>
      <small>Captures visual interpretation, concept edges, missing labels, and confidence before the adaptive test.</small>
    </section>
  `;
}

function diagramPathNodes(center, branches) {
  const branchMap = new Map((branches || []).map((branch) => [String(branch.label || "").toLowerCase(), branch]));
  const meaning = firstBranchPoint(branches, "Meaning") || firstBranchPoint(branches, "Definition") || `Say what ${center} means.`;
  const formula = firstBranchPoint(branches, "Formula") || firstBranchPoint(branches, "Formula or rule") || "Choose the rule only after the meaning is clear.";
  const trap = firstBranchPoint(branches, "Trap") || "Compare with the idea learners usually confuse it with.";
  const practice = firstBranchPoint(branches, "Use") || firstBranchPoint(branches, "Use in questions") || "Apply it to one changed question.";
  const prereq = cleanList(branchMap.get("prerequisite")?.points || [])[0] || "Start from the related idea.";
  return [
    { label: "Start", title: "Related idea", body: prereq },
    { label: "1", title: center, body: meaning },
    { label: "2", title: "Rule", body: formula },
    { label: "3", title: "Trap check", body: trap },
    { label: "4", title: "Question", body: practice },
  ].filter((node) => node.title || node.body);
}

function firstBranchPoint(branches, label) {
  const target = String(label || "").toLowerCase();
  const branch = (branches || []).find((item) => String(item.label || "").toLowerCase().includes(target));
  return cleanList(branch?.points || []).map(cleanDiagramText).filter(Boolean)[0] || "";
}

function cleanDiagramText(value) {
  const text = cleanText(value);
  if (!text) return "";
  if (/https?:\/\//i.test(text) || /\byoutube\.com\b/i.test(text)) return "";
  return text.length > 120 ? `${text.slice(0, 120).replace(/\s+\S*$/, "")}...` : text;
}

function extractTrapConcept(study, center) {
  const prompts = study?.diagram_prompts || [];
  for (const prompt of prompts) {
    const text = `${prompt.description || ""} ${prompt.title || ""}`;
    const match = text.match(/compare\s+(.+?)\s+with\s+(.+?)(?:\s+so|\s+to|\.|$)/i);
    if (match) {
      const left = cleanText(match[1]);
      const right = cleanText(match[2]);
      if (left && left.toLowerCase() !== String(center).toLowerCase()) return left;
      if (right && right.toLowerCase() !== String(center).toLowerCase()) return right;
    }
  }
  const mistake = firstMistake(study);
  const match = mistake.match(/(?:with|and)\s+([A-Z][A-Za-z ]+?)(?:\s+as|\s+are|\s+is|\.|$)/);
  return match ? cleanText(match[1]) : "";
}

function firstMistake(study) {
  return cleanList(study?.common_mistakes || [])[0] || "";
}

function renderDiagramPrompts(prompts) {
  const rows = (prompts || []).filter((item) => item && (item.title || item.description));
  if (!rows.length) return "";
  return `
    <section class="module-section">
      <h2>Try drawing it yourself</h2>
      <div class="diagram-ideas">
        ${rows.slice(0, 4).map((item) => `
          <article>
            <strong>${escapeHtml(item.title || "Diagram")}</strong>
            <p>${escapeHtml(cleanText(item.description || ""))}</p>
            ${item.steps?.length ? `<ol>${item.steps.slice(0, 5).map((step) => `<li>${escapeHtml(cleanText(step))}</li>`).join("")}</ol>` : ""}
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderVideoLearningPlan(plan) {
  if (!plan || (!plan.pre_watch?.length && !plan.segments?.length && !plan.after_watch?.length)) {
    return "";
  }
  return `
    <section class="module-section">
      <h2>How to learn from this video</h2>
      <div class="video-plan-grid">
        ${(plan.pre_watch || []).map((item) => `
          <article>
            <span>${escapeHtml(item.label || "before")}</span>
            <strong>${escapeHtml(item.prompt || "")}</strong>
            <p>${escapeHtml(item.why || "")}</p>
          </article>
        `).join("")}
      </div>
    </section>
    <section class="module-section">
      <h2>Guided watch path</h2>
      <div class="watch-segment-list">
        ${(plan.segments || []).slice(0, 6).map((segment, index) => `
          <article>
            <div class="watch-index">${index + 1}</div>
            <div>
              <span>${escapeHtml([segment.start, segment.end].filter(Boolean).join("-") || "segment")}</span>
              <strong>${escapeHtml(segment.title || "Video segment")}</strong>
              <p>${escapeHtml(segment.watch_goal || "")}</p>
              ${renderMiniList("Notice", segment.signals_to_notice)}
              ${renderMiniList("Ignore", segment.noise_to_ignore)}
              <div class="prompt-triplet">
                <p><b>Pause</b>${escapeHtml(segment.pause_prompt || "")}</p>
                <p><b>Explain</b>${escapeHtml(segment.self_explanation_prompt || "")}</p>
                <p><b>Check</b>${escapeHtml(segment.retrieval_check || "")}</p>
              </div>
              ${renderTags(segment.expected_evidence || [])}
            </div>
          </article>
        `).join("")}
      </div>
    </section>
    <section class="module-section">
      <h2>After watching</h2>
      <div class="video-plan-grid">
        ${(plan.after_watch || []).map((item) => `
          <article>
            <span>${escapeHtml(item.label || "after")}</span>
            <strong>${escapeHtml(item.task || "")}</strong>
            ${renderTags(item.evidence || [])}
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderMiniList(label, values) {
  const items = cleanList(values || []);
  if (!items.length) return "";
  return `
    <div class="mini-list">
      <b>${escapeHtml(label)}</b>
      <ul>${items.slice(0, 4).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </div>
  `;
}

function renderSourceNotesModule(sourceCards, sourcePage, mediaPage, result) {
  const notes = sourcePage.notes_below || mediaPage.notes_below || [];
  const memoryCards = sourcePage.memory_cards || mediaPage.memory_cards || [];
  return `
    <section class="module-section">
      <h2>Source notes</h2>
      <div class="module-stack">
        ${sourceCards.length ? sourceCards.map((card) => renderLearningSource(card, "source")).join("") : renderEmptyModule("No PDF, notes, or web source was supplied.")}
      </div>
    </section>
    <section class="module-section">
      <h2>Study notes</h2>
      <div class="reading-stack">
        ${notes.map((note, index) => renderReadingBlock(note, index)).join("")}
      </div>
    </section>
    <section class="module-section">
      <h2>Remember these</h2>
      <div class="memory-list">
        ${memoryCards.map((card) => `
          <article>
            <span>${escapeHtml(card.type || "fact")}</span>
            <strong>${escapeHtml(card.title)}</strong>
            <p>${escapeHtml(cleanText(card.body))}</p>
          </article>
        `).join("")}
      </div>
    </section>
    ${renderInlineCheck(sourcePage.completion_check || {
      prompt: "Write one definition, one trap, and one example from the sources.",
      evidence_collected: ["text_comprehension", "source_grounding"],
    })}
  `;
}

function renderCheckpointModule(page, result) {
  const questions = page.questions || result.curated_learning_bundle?.checkpoint_questions || [];
  return `
    <section class="module-section">
      <h2>Quick checks</h2>
      <div class="quiz-list compact-quiz">
        ${questions.slice(0, 4).map((question, index) => renderQuizCard(question, index)).join("")}
      </div>
    </section>
  `;
}

function renderVisualModule(page, result) {
  const nodes = page.mind_map_nodes || [];
  const flowSteps = page.flow_steps || [];
  const cues = page.visual_cues || [];
  const diagrams = page.concept_diagrams || [];
  const flowcharts = page.flowcharts || [];
  return `
    ${renderAiVisualArtifact(result?.model_generation?.assets?.visual_artifact, result?.model_generation?.status)}
    <section class="module-section">
      <h2>Mind map</h2>
      ${diagrams.length ? `<div class="diagram-grid">${diagrams.map(renderConceptDiagram).join("")}</div>` : renderEmptyModule("No diagram spec was returned. Generate with source analysis enabled or add more concept-rich notes.")}
    </section>
    <section class="module-section">
      <h2>Step-by-step path</h2>
      ${flowcharts.length ? `<div class="flowchart-grid">${flowcharts.map(renderGeneratedFlowchart).join("")}</div>` : ""}
    </section>
    <section class="module-section">
      <h2>Concepts to connect</h2>
      <div class="map-list">
        ${nodes.map((node) => `
          <article>
            <strong>${escapeHtml(node.label || node.name)}</strong>
            <p>${escapeHtml((node.prerequisites || []).slice(0, 3).join(", ") || "No prerequisite detected")}</p>
            <small>${escapeHtml((node.common_confusions || []).slice(0, 3).join(" | ") || "No common trap detected")}</small>
          </article>
        `).join("")}
      </div>
    </section>
    <section class="module-section">
      <h2>Learning flow</h2>
      <ol class="clean-list">
        ${flowSteps.map((step) => `
          <li>
            <span>${escapeHtml(step.step || "")}</span>
            <strong>${escapeHtml(step.label || "Step")}</strong>
            <p>${escapeHtml(cleanText(step.body))}</p>
          </li>
        `).join("")}
      </ol>
    </section>
    <section class="module-section">
      <h2>Look for this</h2>
      <div class="memory-list">
        ${cues.map((cue) => `
          <article>
            <span>${escapeHtml(cue.best_after || "cue")}</span>
            <strong>${escapeHtml(cue.cue || cue)}</strong>
            <p>${escapeHtml(cue.target_gap || "Use this cue to separate similar concepts.")}</p>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderPracticeCaseModule(practicePage, casePage, result) {
  const dynamicCase = result.dynamic_case || {};
  const requiredOutput = casePage.required_output || dynamicCase.required_output || {};
  const questions = practicePage.questions || [];
  const retestPlan = practicePage.retest_quiz_plan || [];
  const reteachBeforeRetry = practicePage.reteach_before_retry || [];
  const rubric = casePage.rubric || dynamicCase.rubric || [];
  const casePrompt = dynamicCase.scenario || casePage.scenario || casePage.title || dynamicCase.title || "Final practice case";
  return `
    <section class="module-section">
      <h2>Practice questions</h2>
      <p class="section-help">${escapeHtml(practicePage.mix_rule || "Answer these first. Your responses update the next relearn and retest path.")}</p>
      <div class="quiz-list compact-quiz">
        ${questions.slice(0, 3).map((question, index) => renderQuizCard(question, index)).join("")}
      </div>
    </section>
    <section class="module-section">
      <h2>Retest questions</h2>
      <p class="section-help">These are answerable checks. Submit them and the backend updates the learner state before the next relearn page.</p>
      <div class="quiz-plan-list">
        ${retestPlan.length ? retestPlan.map((item, index) => renderRetestCard(item, index)).join("") : renderEmptyModule("No retest plan was generated.")}
      </div>
    </section>
    <section class="module-section">
      <h2>Review before retry</h2>
      ${renderReteachPlan(reteachBeforeRetry)}
    </section>
    <section class="module-section">
      <h2>${escapeHtml(casePage.title || dynamicCase.title || "Final case")}</h2>
      <p>${escapeHtml(dynamicCase.scenario || casePage.scenario || "")}</p>
      <div class="output-spec" data-quiz-card data-check-type="dynamic_case" data-requires-answer="true" data-concept="${escapeHtml(requiredOutput.concept || dynamicCase.concept || "")}" data-prompt="${escapeHtml(casePrompt)}">
        <strong>${escapeHtml(requiredOutput.format || "written_response")}</strong>
        <ul>${(requiredOutput.components || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        <textarea class="answer-box" rows="8" placeholder="Write the answer, reasoning, source used, confidence, and what should be revised."></textarea>
        <button type="button" class="ghost-button small" data-self-check>Submit final answer</button>
        <p class="quiz-feedback"></p>
      </div>
    </section>
    <section class="module-section">
      <h2>What a good answer includes</h2>
      <div class="rubric-list">
        ${rubric.map((item) => `
          <article>
            <strong>${escapeHtml(item.name)}</strong>
            <p>${escapeHtml((item.checks || []).join(" "))}</p>
            <span>${Math.round(Number(item.weight || 0) * 100)}%</span>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderRevisionModule(page, result) {
  const profile = result.learner_model || {};
  const variants = result.dynamic_case?.personalized_variants?.variants || {};
  const curves = page.forgetting_curve || [];
  const nextRetake = page.next_retake || {};
  const practicePage = lessonPage(result, "practice") || {};
  const progression = buildAdaptiveProgression(page, practicePage, result);
  return `
    <section class="revision-hero">
      <div>
        <p class="kicker">Next best action</p>
        <h2>${escapeHtml(nextRetake.concept || "Relearn the weakest idea")}</h2>
        <p>${escapeHtml(nextRetake.action || "Reteach, then generate the next mixed retest.")}</p>
      </div>
      <div class="next-retake">
        <span>${escapeHtml(nextRetake.review_in_days ? `${nextRetake.review_in_days}d` : "now")}</span>
        <div>
          <strong>${escapeHtml(nextRetake.review_date || "After checkpoint")}</strong>
          <p>${escapeHtml(nextRetake.risk ? `Risk: ${nextRetake.risk}` : "First revision is scheduled from current evidence.")}</p>
        </div>
      </div>
    </section>
    ${renderAdaptiveStateOverview(progression)}
    <section class="module-section">
      <h2>When to revise</h2>
      ${curves.length ? `<div class="curve-grid">${curves.map(renderForgettingCurve).join("")}</div>` : renderEmptyModule("No review schedule exists yet.")}
    </section>
    <section class="module-section">
      <h2>Review this first</h2>
      ${renderReteachPlan(page.reteaching_plan || [])}
    </section>
    <section class="module-section">
      <div class="section-title-row">
        <h2>Review progression</h2>
        <span>${escapeHtml(progression.evidenceStatus)}</span>
      </div>
      ${renderAdaptiveProgressGraph(progression)}
    </section>
    <section class="module-section">
      <h2>How your path adapts</h2>
      <p>${escapeHtml(profile.profile_available ? `Active route: ${profile.dominant_anchor}` : "No learner evidence yet. The first run collects evidence, then selects a route.")}</p>
      <div class="route-list">
        ${Object.entries(variants).map(([key, variant]) => `
          <article>
            <span>${escapeHtml(key.replaceAll("_", " "))}</span>
            <strong>${escapeHtml(variant.profile?.label || key)}</strong>
            <p>${escapeHtml(variant.profile?.description || "")}</p>
          </article>
        `).join("")}
      </div>
    </section>
    <section class="module-section">
      <h2>Continue adaptive practice</h2>
      <p class="section-help">Open the next relearn page, answer retests, and use the spaced schedule to come back on later days.</p>
      <button type="button" class="small" id="adaptiveSeriesButton">Open relearn and retest path</button>
    </section>
  `;
}

function renderAdaptiveSeriesPage(result) {
  const page = lessonPage(result, "revision") || {};
  const practicePage = lessonPage(result, "practice") || {};
  const retests = practicePage.retest_quiz_plan || [];
  const reteach = page.reteaching_plan || practicePage.reteach_before_retry || [];
  const simulation = buildAdaptiveSeriesSimulation(result);
  const progression = buildAdaptiveProgression(page, practicePage, result);
  $("#moduleStepLabel").textContent = "Adaptive loop";
  $("#moduleTitle").textContent = "Relearn and retest";
  $("#moduleRail").classList.add("hidden");
  $("#moduleBody").innerHTML = `
    <div class="adaptive-loop-page" data-adaptive-loop-page="true">
      <header class="module-header adaptive-loop-header">
        <p class="kicker">Adaptive relearn loop</p>
        <h1>Relearn, then retest</h1>
        <p>Your answers update the learner state, then the graph shows when each concept should be relearned and retested.</p>
      </header>
      ${renderAdaptiveStateOverview(progression)}
      <section class="module-section">
        <div class="section-title-row">
          <h2>Progression graph</h2>
          <span>${escapeHtml(progression.nextReviewLabel)}</span>
        </div>
        ${renderAdaptiveProgressGraph(progression)}
      </section>
      ${renderAdaptiveActionPanels(reteach.slice(0, 4), retests.slice(0, 4), progression)}
      <section class="module-section">
        <div class="section-title-row">
          <h2>How the path changes</h2>
          <span>after next answer</span>
        </div>
        <div class="adaptive-series-page">
          ${simulation.map(renderAdaptiveScenario).join("")}
        </div>
      </section>
      <section class="module-section">
        <button type="button" class="ghost-button small" id="backToReviewButton">Back to review plan</button>
      </section>
    </div>
  `;
  $("#prevModuleButton").disabled = true;
  $("#nextModuleButton").disabled = false;
  $("#nextModuleButton").textContent = "Finish";
  $("#backToReviewButton").addEventListener("click", () => {
    $("#moduleRail").classList.remove("hidden");
    $("#nextModuleButton").disabled = false;
    renderActiveModule();
    renderModuleRail();
  });
  setupQuizInteractions();
  if (typeof applyStoredDemoAnswersToCurrentModule === "function") {
    applyStoredDemoAnswersToCurrentModule();
  }
  renderMath($("#moduleBody"));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function buildAdaptiveSeriesSimulation(result) {
  const page = lessonPage(result, "revision") || {};
  const practicePage = lessonPage(result, "practice") || {};
  const weakConcept = page.next_retake?.concept || practicePage.retest_quiz_plan?.[0]?.concept || "target concept";
  const reteach = page.reteaching_plan || practicePage.reteach_before_retry || [];
  return [
    {
      state: "Improved",
      signal: "Move to harder transfer",
      page: `Use ${weakConcept} in one harder transfer question with fewer hints.`,
      testMix: "20% repeat-style, 80% fresh variants",
      next: "Increase spacing and reduce hints.",
    },
    {
      state: "Stayed Flat",
      signal: "Change teaching mode",
      page: `Reteach ${weakConcept} with a diagram, a worked example, and one typed explanation.`,
      testMix: "50% repeat-style variants, 50% fresh equivalents",
      next: "Keep spacing short and change teaching mode.",
    },
    {
      state: "Went Down",
      signal: "Back up one step",
      page: `Back up to the prerequisite before ${weakConcept} with a side-by-side visual comparison and a short formula reminder.`,
      testMix: "60% repaired repeats, 40% very small fresh checks",
      next: "Schedule earlier review and add scaffolded hints.",
    },
  ].map((scenario) => ({
    ...scenario,
    reteach: reteach.slice(0, 2),
  }));
}

function renderAdaptiveScenario(scenario) {
  return `
    <article class="adaptive-scenario">
      <div class="scenario-head">
        <span>${escapeHtml(scenario.state)}</span>
        <strong>${escapeHtml(scenario.signal)}</strong>
      </div>
      <div class="scenario-grid">
        <section>
          <h3>Next relearn page</h3>
          <p>${escapeHtml(scenario.page)}</p>
          ${scenario.reteach.length ? renderReteachPlan(scenario.reteach) : ""}
        </section>
        <section>
          <h3>Next test mix</h3>
          <p>${escapeHtml(scenario.testMix)}</p>
          <small>${escapeHtml(scenario.next)}</small>
        </section>
      </div>
    </article>
  `;
}

function renderAdaptiveStateOverview(progression) {
  return `
    <section class="module-section adaptive-state-section">
      <div class="section-title-row">
        <h2>Current learner state</h2>
        <span>${escapeHtml(progression.evidenceStatus)}</span>
      </div>
      <div class="adaptive-state-grid">
        ${renderStateMetric("Last answer", progression.latestScoreLabel, progression.latestScoreBody, "score")}
        ${renderStateMetric("Weakest next", progression.nextConcept, progression.nextActionBody, "focus")}
        ${renderStateMetric("Learning route", progression.routeLabel, progression.routeBody, "route")}
        ${renderStateMetric("Next review", progression.nextReviewLabel, progression.nextReviewBody, "review")}
      </div>
    </section>
  `;
}

function renderStateMetric(label, value, body, modifier = "") {
  return `
    <article class="adaptive-state-card ${escapeHtml(modifier)}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <p>${escapeHtml(body)}</p>
    </article>
  `;
}

function renderAdaptiveProgressGraph(progression) {
  if (!progression.nodes.length) return renderEmptyModule("Answer a checkpoint first, then the progression graph becomes personalized.");
  const width = 920;
  const height = 270;
  const padX = 58;
  const padY = 34;
  const maxDay = Math.max(...progression.graphPoints.map((point) => point.day), 15);
  const xFor = (day) => padX + (Number(day || 0) / maxDay) * (width - padX * 2);
  const yFor = (retention) => padY + (1 - clampNumber(retention, 0.05, 0.98)) * (height - padY * 2);
  const polyline = progression.graphPoints
    .map((point) => `${xFor(point.day).toFixed(1)},${yFor(point.retention).toFixed(1)}`)
    .join(" ");
  const guideLines = [0.25, 0.5, 0.75].map((retention) => {
    const y = yFor(retention).toFixed(1);
    return `
      <line class="progress-guide" x1="${padX}" y1="${y}" x2="${width - padX}" y2="${y}"></line>
      <text class="progress-axis-label" x="12" y="${Number(y) + 4}">${Math.round(retention * 100)}%</text>
    `;
  }).join("");
  const dayTicks = progression.graphPoints.map((point) => {
    const x = xFor(point.day).toFixed(1);
    return `
      <line class="progress-tick" x1="${x}" y1="${height - padY}" x2="${x}" y2="${height - padY + 7}"></line>
      <text class="progress-day-label" x="${x}" y="${height - 8}">D${escapeHtml(point.day)}</text>
    `;
  }).join("");
  const points = progression.graphPoints.map((point) => {
    const node = progression.nodes.find((item) => item.day === point.day) || {};
    const x = xFor(point.day).toFixed(1);
    const y = yFor(point.retention).toFixed(1);
    const cssClass = node.status === "next" ? "next" : point.day === 0 ? "current" : "";
    return `
      <circle class="progress-dot ${cssClass}" cx="${x}" cy="${y}" r="${node.status === "next" ? 7 : 5}"></circle>
      <text class="progress-point-label" x="${x}" y="${Number(y) - 12}">${Math.round(point.retention * 100)}%</text>
    `;
  }).join("");
  return `
    <div class="adaptive-progress-graph">
      <div class="progress-graph-main">
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Projected retention over scheduled relearn and retest days">
          ${guideLines}
          <line class="progress-axis" x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}"></line>
          <line class="progress-axis" x1="${padX}" y1="${padY}" x2="${padX}" y2="${height - padY}"></line>
          ${dayTicks}
          <polyline class="progress-retention-line" points="${polyline}"></polyline>
          ${points}
        </svg>
        <div class="progress-graph-caption">
          <strong>${escapeHtml(progression.graphTitle)}</strong>
          <p>${escapeHtml(progression.graphCaption)}</p>
        </div>
      </div>
      <div class="progress-node-list">
        ${progression.nodes.filter((node) => node.day > 0).map(renderProgressionNode).join("")}
      </div>
    </div>
  `;
}

function renderProgressionNode(node) {
  return `
    <article class="progress-node ${escapeHtml(node.status)}">
      <span>${escapeHtml(node.label)}</span>
      <strong>${escapeHtml(node.concept)}</strong>
      <p>${escapeHtml(node.task)}</p>
      <small>${escapeHtml(node.retentionLabel)} projected retention · ${escapeHtml(node.masteryLabel)} mastery</small>
    </article>
  `;
}

function renderAdaptiveActionPanels(reteach, retests, progression) {
  return `
    <section class="module-section adaptive-action-section">
      <div class="section-title-row">
        <h2>Do next</h2>
        <span>${escapeHtml(progression.nextActionLabel)}</span>
      </div>
      <div class="adaptive-action-grid">
        <section class="adaptive-action-column">
          <p class="kicker">Relearn now</p>
          <h3>${escapeHtml(progression.nextConcept)}</h3>
          <p>${escapeHtml(progression.relearnBody)}</p>
          ${renderReteachPlan(reteach)}
        </section>
        <section class="adaptive-action-column">
          <p class="kicker">Retest now</p>
          <h3>Answer, then update the graph</h3>
          <p>Submitting a retest sends the answer evidence to the backend, refreshes the learner state, and changes the next review path.</p>
          <div class="quiz-plan-list">
            ${retests.length ? retests.map((item, index) => renderRetestCard(item, index)).join("") : renderEmptyModule("No retest questions were generated yet. Answer a checkpoint first.")}
          </div>
        </section>
      </div>
    </section>
  `;
}

function buildAdaptiveProgression(page, practicePage, result) {
  const update = result.adaptive_update || {};
  const profile = result.learner_model || {};
  const roadmap = result.adaptive_roadmap || {};
  const reviewRows = page.review_schedule || roadmap.review_schedule || [];
  const curves = page.forgetting_curve || [];
  const retests = practicePage.retest_quiz_plan || [];
  const calendar = buildRetestCalendar(page);
  const nextReview = update.next_review || page.next_retake || reviewRows[0] || {};
  const nextRetake = page.next_retake || nextReview || {};
  const latestScore = numberOrNull(update.latest_server_score);
  const eventCount = Number(update.accepted_event_count || (result.learner_events || []).length || 0);
  const nextDay = positiveNumber(nextReview.review_in_days)
    || positiveNumber(nextRetake.review_in_days)
    || positiveNumber(calendar[0]?.day)
    || 1;
  const concepts = uniqueText([
    nextRetake.concept,
    nextReview.concept,
    ...(reviewRows || []).map((row) => row.concept),
    ...(curves || []).map((row) => row.concept),
    ...(retests || []).map((row) => row.concept),
  ]);
  const nextConcept = nextRetake.concept || nextReview.concept || concepts[0] || "weakest idea";
  const days = uniqueNumbers([0, 1, 3, 7, 11, 15, nextDay]).sort((a, b) => a - b);
  const nodes = days.map((day, index) => {
    const row = day === 0 ? {} : reviewRows.find((item) => Number(item.review_in_days) === day)
      || calendar.find((item) => Number(item.day) === day)
      || reviewRows[(Math.max(0, index - 1)) % Math.max(1, reviewRows.length)]
      || {};
    const concept = day === 0
      ? nextConcept
      : row.concept || row.title || concepts[(Math.max(0, index - 1)) % Math.max(1, concepts.length)] || nextConcept;
    const curve = curves.find((item) => item.concept === concept) || curves[(Math.max(0, index - 1)) % Math.max(1, curves.length)] || {};
    const mastery = numberOrNull(row.mastery_estimate) ?? numberOrNull(curve.mastery_estimate)
      ?? numberOrNull(profile.concept_mastery?.[concept])
      ?? 0.5;
    const retention = day === 0 && latestScore !== null
      ? clampNumber(0.42 + normalizeScore(latestScore) * 0.52, 0.2, 0.96)
      : retentionAtDay(curve, day, mastery);
    return {
      day,
      concept,
      label: day === 0 ? "Now" : `Day ${day}`,
      task: day === 0 ? currentEvidenceTask(eventCount) : reviewTask(row, day, nextDay),
      retention,
      mastery,
      status: progressionNodeStatus(day, nextDay),
      retentionLabel: formatPercent(retention),
      masteryLabel: formatPercent(mastery),
    };
  });
  const graphPoints = days.map((day) => {
    const curveValues = curves.map((curve) => retentionAtDay(curve, day, numberOrNull(curve.mastery_estimate) ?? 0.5));
    const nodeValue = nodes.find((node) => node.day === day)?.retention;
    return {
      day,
      retention: curveValues.length ? averageNumber(curveValues) : nodeValue || 0.5,
    };
  });
  const route = update.dominant_anchor || profile.dominant_anchor || "balanced";
  const nextMode = update.next_mode || roadmap.next_mode || "collect_more_evidence";
  const latestScoreLabel = latestScore === null ? "waiting" : formatPercent(normalizeScore(latestScore));
  return {
    nodes,
    graphPoints,
    nextConcept,
    nextReviewLabel: `Day ${nextDay}`,
    nextReviewBody: nextReview.review_date
      ? `${nextConcept} is scheduled for ${nextReview.review_date}.`
      : `${nextConcept} is the next spaced check.`,
    nextActionLabel: `relearn ${nextConcept}`,
    nextActionBody: nextRetake.action || "Reteach the weakest concept, then use a mixed repeat and fresh retest.",
    relearnBody: "Start by changing the explanation mode for the weakest concept, then immediately ask for retrieval in a changed form.",
    latestScoreLabel,
    latestScoreBody: eventCount
      ? `Accepted ${eventCount} answer event${eventCount === 1 ? "" : "s"} and refreshed the next plan.`
      : "No live answer has been submitted yet; the path is using first-pass evidence.",
    routeLabel: labelize(route),
    routeBody: `Next teaching mode: ${labelize(nextMode)}.`,
    evidenceStatus: eventCount ? "answer evidence fed back" : "first pass plan",
    graphTitle: eventCount ? "Updated from submitted answer evidence" : "Projected from first-pass learner evidence",
    graphCaption: "The line estimates retention over time. Each node is a scheduled relearn or retest point; weak answers pull the next node earlier and add more support.",
  };
}

function currentEvidenceTask(eventCount) {
  return eventCount
    ? "Latest submitted answer updated the route, score, and next review."
    : "First pass evidence sets the initial route until the learner submits a retest.";
}

function reviewTask(row, day, nextDay) {
  const reviewType = String(row.review_type || row.mix || "").replaceAll("_", " ");
  if (row.body) return cleanLearnerPolicyText(row.body);
  if (row.reason) return cleanLearnerPolicyText(row.reason);
  if (reviewType.includes("fresh")) return day === nextDay ? "Fresh retest is due next." : "Fresh variant retest after spacing.";
  if (reviewType.includes("repair")) return "Reteach first, then repeat-style retrieval.";
  return day <= 1 ? "Relearn + repeat-style check." : day < 11 ? "Repeat-style + fresh variant." : "Mostly fresh transfer.";
}

function progressionNodeStatus(day, nextDay) {
  if (day === 0) return "current";
  if (day === nextDay) return "next";
  if (day < nextDay) return "support";
  return "scheduled";
}

function retentionAtDay(curve, day, fallbackMastery = 0.5) {
  const points = curve?.points || [];
  const exact = points.find((point) => Number(point.day) === Number(day));
  if (exact) return clampNumber(Number(exact.retention), 0.05, 0.99);
  const sorted = points
    .map((point) => ({ day: Number(point.day), retention: Number(point.retention) }))
    .filter((point) => Number.isFinite(point.day) && Number.isFinite(point.retention))
    .sort((a, b) => a.day - b.day);
  const before = [...sorted].reverse().find((point) => point.day <= day);
  const after = sorted.find((point) => point.day >= day);
  if (before && after && before.day !== after.day) {
    const ratio = (day - before.day) / (after.day - before.day);
    return clampNumber(before.retention + (after.retention - before.retention) * ratio, 0.05, 0.99);
  }
  if (before) return clampNumber(before.retention, 0.05, 0.99);
  if (after) return clampNumber(after.retention, 0.05, 0.99);
  const mastery = clampNumber(fallbackMastery, 0, 1);
  const start = clampNumber(0.56 + mastery * 0.42, 0.58, 0.97);
  const stability = 1.5 + mastery * 7;
  return clampNumber(start * Math.pow(2, -Math.max(0, day) / stability), 0.08, 0.97);
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function positiveNumber(value) {
  const number = numberOrNull(value);
  return number && number > 0 ? Math.round(number) : null;
}

function normalizeScore(value) {
  const number = numberOrNull(value);
  if (number === null) return 0;
  return clampNumber(number > 1 ? number / 100 : number, 0, 1);
}

function formatPercent(value) {
  const number = normalizeScore(value);
  return `${Math.round(number * 100)}%`;
}

function averageNumber(values) {
  const clean = values.map(Number).filter(Number.isFinite);
  if (!clean.length) return 0.5;
  return clean.reduce((sum, value) => sum + value, 0) / clean.length;
}

function clampNumber(value, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) return min;
  return Math.min(max, Math.max(min, number));
}

function uniqueText(values) {
  return [...new Set(values.map((value) => String(value || "").trim()).filter(Boolean))];
}

function uniqueNumbers(values) {
  return [...new Set(values.map(Number).filter((value) => Number.isFinite(value) && value >= 0))];
}

function labelize(value) {
  return String(value || "").replaceAll("_", " ").trim() || "balanced";
}

function renderConceptDiagram(diagram) {
  const nodes = (diagram.nodes || []).map((node, index) => typeof node === "string"
    ? { id: `node-${index + 1}`, label: node, kind: "node" }
    : node);
  const edges = diagram.edges || [];
  return `
    <article class="diagram-card">
      <div class="diagram-title">
        <span>${escapeHtml(diagram.concept || "diagram")}</span>
        <strong>${escapeHtml(diagram.title || "Concept diagram")}</strong>
      </div>
      <div class="diagram-nodes">
        ${nodes.map((node) => `
          <div class="diagram-node">
            <small>${escapeHtml(node.kind || "node")}</small>
            <b>${escapeHtml(node.label || node.id || "node")}</b>
          </div>
        `).join("")}
      </div>
      <div class="diagram-edges">
        ${edges.map((edge) => typeof edge === "string" ? `
          <p>${escapeHtml(edge)}</p>
        ` : `
          <p><b>${escapeHtml(edge.from)}</b> → <b>${escapeHtml(edge.to)}</b> <span>${escapeHtml(edge.label || "")}</span></p>
        `).join("")}
      </div>
      <p>${escapeHtml(diagram.takeaway || "")}</p>
    </article>
  `;
}

function renderGeneratedFlowchart(flowchart) {
  const steps = (flowchart.steps || []).map((step) => typeof step === "string"
    ? { label: step, action: "", check: "" }
    : step);
  return `
    <article class="flowchart-card">
      <span>${escapeHtml(flowchart.concept || "flowchart")}</span>
      <strong>${escapeHtml(flowchart.title || "Reasoning flow")}</strong>
      <ol>
        ${steps.map((step, index) => `
          <li>
            <i>${index + 1}</i>
            <div>
              <b>${escapeHtml(step.label || "Step")}</b>
              <p>${escapeHtml(step.action || "")}</p>
              ${step.check ? `<small>${escapeHtml(step.check)}</small>` : ""}
            </div>
          </li>
        `).join("")}
      </ol>
      ${flowchart.misconception_fixed ? `<p class="repair-note">${escapeHtml(flowchart.misconception_fixed)}</p>` : ""}
    </article>
  `;
}

function renderRetestCard(item, index = 0) {
  const prompt = item.prompt || `Answer a changed question for ${item.concept || "this concept"}.`;
  return `
    <article class="retest-card" data-quiz-card data-check-type="adaptive_retest" data-requires-answer="true" data-concept="${escapeHtml(item.concept || "target concept")}" data-prompt="${escapeHtml(prompt)}">
      <span>${escapeHtml(retestVariantLabel(item.variant_type, index))}</span>
      <strong>${escapeHtml(prompt)}</strong>
      <p>${escapeHtml(retestHelpText(item))}</p>
      <textarea class="answer-box" rows="4" placeholder="Solve it here. Include the reason, not only the final answer."></textarea>
      <button type="button" class="ghost-button small" data-self-check>Submit answer</button>
      <p class="quiz-feedback"></p>
    </article>
  `;
}

function retestVariantLabel(value, index) {
  const label = String(value || "").replaceAll("_", " ").trim();
  if (label) return label;
  return index % 2 === 0 ? "repeat-style" : "fresh variant";
}

function retestHelpText(item) {
  const parts = [];
  if (item.concept) parts.push(`Focus: ${item.concept}.`);
  if (item.reason) parts.push(cleanLearnerPolicyText(item.reason));
  if (!parts.length && item.mix) parts.push(cleanLearnerPolicyText(item.mix));
  return parts.join(" ");
}

function renderReteachPlan(plan) {
  if (!plan.length) return renderEmptyModule("Reteaching will be generated after the first missed checkpoint.");
  return `
    <div class="reteach-list">
      ${plan.map((item) => `
        <article>
          <span>${escapeHtml(relearnPriorityLabel(item.priority))}</span>
          <strong>${escapeHtml(item.concept || "target concept")}</strong>
          <p>${escapeHtml(cleanLearnerPolicyText(item.explanation || item.trigger || ""))}</p>
          ${item.next_check ? `<small>${escapeHtml(`Then: ${cleanLearnerPolicyText(item.next_check)}`)}</small>` : ""}
        </article>
      `).join("")}
    </div>
  `;
}

function relearnPriorityLabel(value) {
  const label = String(value || "review").toLowerCase();
  if (label.includes("high")) return "review first";
  if (label.includes("medium")) return "review next";
  return "quick review";
}

function cleanLearnerPolicyText(value) {
  return cleanText(String(value || "")
    .replaceAll("_", " ")
    .replace(/\bLLM\b/g, "lesson")
    .replace(/\bRAG\b/g, "source")
    .replace(/\bvisual contrast\b/gi, "visual comparison")
    .replace(/\bworked example\b/gi, "worked example"), 240);
}

function renderRetestCalendar(page) {
  const schedule = buildRetestCalendar(page);
  if (!schedule.length) return renderEmptyModule("Answer a checkpoint first, then this schedule becomes personalized.");
  return `
    <div class="retest-calendar">
      ${schedule.map((item) => `
        <article>
          <span>Day ${escapeHtml(item.day)}</span>
          <strong>${escapeHtml(item.title)}</strong>
          <p>${escapeHtml(item.body)}</p>
        </article>
      `).join("")}
    </div>
  `;
}

function buildRetestCalendar(page) {
  const concepts = [
    page.next_retake?.concept,
    ...(page.review_schedule || []).map((row) => row.concept),
    ...(page.forgetting_curve || []).map((row) => row.concept),
  ].filter(Boolean);
  const uniqueConcepts = [...new Set(concepts)];
  const cadence = [1, 3, 7, 11, 15];
  return cadence.map((day, index) => {
    const concept = uniqueConcepts[index % Math.max(1, uniqueConcepts.length)] || "weakest idea";
    const mix = index === 0 ? "relearn + repeat-style check" : index < 3 ? "repeat-style + fresh variant" : "mostly fresh transfer";
    return {
      day,
      title: concept,
      body: `${mix}. If the answer is weak, the next page reteaches this concept before testing again.`,
    };
  });
}

function renderForgettingCurve(curve) {
  const points = curve.points || [];
  const svg = renderCurveSvg(points);
  return `
    <article class="curve-card">
      <div class="curve-head">
        <div>
          <span>${escapeHtml(curve.risk || "risk")}</span>
          <strong>${escapeHtml(curve.concept || "concept")}</strong>
        </div>
        <b>${escapeHtml(curve.review_in_days)}d</b>
      </div>
      ${svg}
      <div class="curve-meta">
        <p>Predicted retention at review: ${Math.round(Number(curve.predicted_retention_at_review || 0) * 100)}%</p>
        <p>Personalized stability: ${escapeHtml(curve.personalized_stability_days || "?")} days</p>
        <p>Retest mix: ${escapeHtml(curve.retest_mix || "mixed")}</p>
      </div>
    </article>
  `;
}

function renderCurveSvg(points) {
  if (!points.length) return "";
  const width = 360;
  const height = 150;
  const pad = 18;
  const maxDay = Math.max(...points.map((point) => Number(point.day || 0)), 1);
  const coords = points.map((point) => {
    const x = pad + (Number(point.day || 0) / maxDay) * (width - pad * 2);
    const y = pad + (1 - Number(point.retention || 0)) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `
    <svg class="curve-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="forgetting curve">
      <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}"></line>
      <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}"></line>
      <polyline points="${coords}"></polyline>
      ${points.map((point) => {
        const x = pad + (Number(point.day || 0) / maxDay) * (width - pad * 2);
        const y = pad + (1 - Number(point.retention || 0)) * (height - pad * 2);
        return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3"></circle>`;
      }).join("")}
    </svg>
  `;
}

function renderMath(root) {
  if (!root || typeof renderMathInElement !== "function") return;
  renderMathInElement(root, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "\\[", right: "\\]", display: true },
      { left: "\\(", right: "\\)", display: false },
      { left: "$", right: "$", display: false },
    ],
    ignoredTags: ["script", "noscript", "style", "textarea", "pre", "code", "option"],
    throwOnError: false,
  });
}
