let loadedSample = null;
let lastResult = null;
let lastPayload = null;
let sessionLearnerEvents = [];
let currentModules = [];
let activeModuleIndex = 0;
let learnerEventCounter = 0;
let demoAnswerBank = {};

window.PROOFLOOP_BUILD_ID = "track-b-upload-v14";

const MAX_FILE_BYTES = 8 * 1024 * 1024;
const MAX_TOTAL_FILE_BYTES = 14 * 1024 * 1024;
const MAX_REQUEST_BODY_BYTES = 22 * 1024 * 1024;
const GENERATION_TIMEOUT_MS = 600000;
const BUILD_PROGRESS_MESSAGES = [
  "reading sources",
  "building RAG context",
  "asking Gemini to inspect source material",
  "asking the selected generation model to build this learning bundle",
  "still waiting on live providers; this is usually generation, source-analysis, or vector-RAG latency",
  "waiting through provider retry/backoff if needed",
  "if a provider times out, the app will return the bundle with a visible provider notice",
  "rendering learner pages",
];


function setStatus(text) {
  $("#appStatus").textContent = text;
}

function startBuildProgress() {
  let index = 0;
  setStatus(BUILD_PROGRESS_MESSAGES[index]);
  const interval = setInterval(() => {
    index = Math.min(index + 1, BUILD_PROGRESS_MESSAGES.length - 1);
    setStatus(BUILD_PROGRESS_MESSAGES[index]);
  }, 8000);
  return () => clearInterval(interval);
}

function showError(message) {
  $("#errorState").textContent = message;
  $("#errorState").classList.remove("hidden");
}

function showNotice(message) {
  $("#errorState").textContent = message;
  $("#errorState").classList.remove("hidden");
}

function clearError() {
  $("#errorState").classList.add("hidden");
  $("#errorState").textContent = "";
}

function resetGeneratedLessonState(statusText = "") {
  lastResult = null;
  lastPayload = null;
  sessionLearnerEvents = [];
  currentModules = [];
  activeModuleIndex = 0;
  learnerEventCounter = 0;
  demoAnswerBank = {};
  document.body.classList.remove("lesson-mode");
  $("#resultShell").classList.add("hidden");
  $("#inputHero").classList.remove("hidden");
  $("#inputScreen").classList.remove("hidden");
  $("#moduleBody").innerHTML = "";
  $("#moduleRail").innerHTML = "";
  if (statusText) setStatus(statusText);
}

async function loadSample(kind = "evidence") {
  clearError();
  resetGeneratedLessonState();
  setStatus("loading sample");
  const endpoints = {
    cold: "/api/track-b/sample-cold",
    physics: "/api/track-b/sample-physics",
    chemistry: "/api/track-b/sample-chemistry",
    evidence: "/api/track-b/sample",
  };
  const endpoint = endpoints[kind] || endpoints.evidence;
  const response = await fetch(endpoint);
  loadedSample = await response.json();
  $("#objectiveInput").value = loadedSample.learning_objective;
  fillContentFields(loadedSample.content_set || []);
  $("#includeEvidence").checked = Boolean(loadedSample.learner_events?.length);
  const labels = {
    cold: "cold-start sample loaded",
    physics: "physics diagram seed loaded",
    chemistry: "chemistry seed loaded",
    evidence: "evidence sample loaded",
  };
  setStatus(labels[kind] || labels.evidence);
}

function fillContentFields(contentSet) {
  const urls = [];
  const notes = [];
  const transcriptLines = [];
  for (const item of contentSet) {
    if (item.url) urls.push(item.url);
    if (item.segments?.length) {
      for (const segment of item.segments) {
        const location = [segment.start, segment.end].filter(Boolean).join("-");
        transcriptLines.push(`${location} | ${segment.text || segment.summary || ""}`.trim());
      }
      continue;
    }
    if (item.text || item.notes || item.body) {
      notes.push(`${item.title || "Source"}\n${item.text || item.notes || item.body}`);
    }
  }
  $("#urlInput").value = urls.join("\n");
  $("#notesInput").value = notes.join("\n\n");
  $("#transcriptInput").value = transcriptLines.join("\n");
  $("#fileInput").value = "";
  renderFileList();
  $("#sourceFinder").classList.add("hidden");
  $("#sourceFinder").innerHTML = "";
}

function invalidateLoadedSampleEvidence() {
  if (!loadedSample) return;
  loadedSample = null;
  $("#includeEvidence").checked = false;
  setStatus("custom input");
}

function parseTranscriptSegments(raw) {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [rangePart, ...textParts] = line.split("|");
      const text = textParts.length ? textParts.join("|").trim() : rangePart.trim();
      const range = textParts.length ? rangePart.trim() : "";
      const [start, end] = range.includes("-") ? range.split("-", 2).map((value) => value.trim()) : ["", ""];
      return {
        start,
        end,
        text,
        id: `segment-${index + 1}`,
      };
    });
}

function inferMimeType(file) {
  if (file.type) return file.type;
  const name = file.name.toLowerCase();
  if (name.endsWith(".pdf")) return "application/pdf";
  if (name.endsWith(".md") || name.endsWith(".markdown")) return "text/markdown";
  if (name.endsWith(".tex") || name.endsWith(".latex")) return "text/x-tex";
  return "text/plain";
}

function suggestedSourcesForObjective(objective) {
  const lower = objective.toLowerCase();
  if (lower.includes("electric potential") || lower.includes("electrostatic")) {
    return [
      {
        title: "YouTube lesson: electrostatic potential and capacitance",
        url: "https://www.youtube.com/watch?v=sGb3VLDvNRU",
        type: "video",
      },
      {
        title: "MIT OCW concept video: electric potential",
        url: "https://ocw.mit.edu/courses/res-tll-004-stem-concept-videos-fall-2013/resources/electric-potential/",
        type: "video/resource",
      },
      {
        title: "Khan Academy worked example: electric potential and work",
        url: "https://www.khanacademy.org/science/ka-physics-grade-12/xf5c71951dad171dd%3Ain-in-electrostatic-potential-and-capacitance/xf5c71951dad171dd%3Aelectric-potential-conceptual-problems/v/worked-example-electric-potential-and-work-done",
        type: "lesson",
      },
      {
        title: "NPTEL electromagnetic fields PDF reference",
        url: "https://archive.nptel.ac.in/content/syllabus_pdf/108106073.pdf",
        type: "pdf",
      },
      {
        title: "SATHEE JEE electrostatic potential and capacitance",
        url: "https://sathee.iitk.ac.in/sathee-jee/jee-tutorial-sessions/physics/physics12/electrostatic-potential-and-capacitance/",
        type: "lesson",
      },
    ];
  }
  const query = encodeURIComponent(objective || "target concept");
  return [
    { title: "YouTube lecture search", url: `https://www.youtube.com/results?search_query=${query}+lecture`, type: "search" },
    { title: "PDF notes search", url: `https://www.google.com/search?q=${query}+filetype%3Apdf+notes`, type: "search" },
    { title: "SATHEE / IITK search", url: `https://sathee.iitk.ac.in/?s=${query}`, type: "search" },
  ];
}

function suggestSources() {
  const objective = $("#objectiveInput").value.trim();
  const suggestions = suggestedSourcesForObjective(objective);
  const existing = new Set($("#urlInput").value.split("\n").map((line) => line.trim()).filter(Boolean));
  for (const source of suggestions) {
    existing.add(source.url);
  }
  $("#urlInput").value = [...existing].join("\n");
  $("#sourceFinder").classList.remove("hidden");
  $("#sourceFinder").innerHTML = suggestions.map((source) => `
    <a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">
      <span>${escapeHtml(source.type)}</span>
      <strong>${escapeHtml(source.title)}</strong>
    </a>
  `).join("");
  setStatus("source links added");
}

async function parseUploadedFiles() {
  const files = Array.from($("#fileInput").files || []);
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  if (totalBytes > MAX_TOTAL_FILE_BYTES) {
    throw new Error("Uploaded files are too large. Keep the total under 14 MB.");
  }
  return Promise.all(files.map(async (file, index) => {
    if (file.size > MAX_FILE_BYTES) {
      throw new Error(`${file.name} is too large. Keep each file under 8 MB.`);
    }
    return {
      id: `uploaded-file-${index + 1}`,
      type: "document",
      title: file.name,
      filename: file.name,
      mime_type: inferMimeType(file),
      size_bytes: file.size,
      data_url: await readFileAsDataUrl(file),
    };
  }));
}

async function parseContentSet() {
  const urls = $("#urlInput").value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const notes = $("#notesInput").value.trim();
  const transcript = $("#transcriptInput").value.trim();
  const contentSet = [];

  urls.forEach((url, index) => {
    let title = `Source URL ${index + 1}`;
    try {
      const parsed = new URL(url);
      title = parsed.hostname.replace(/^www\./, "") + parsed.pathname;
    } catch (_error) {
      title = url.slice(0, 72);
    }
    contentSet.push({
      id: `url-${index + 1}`,
      type: "url",
      title,
      url,
    });
  });

  if (notes) {
    contentSet.push({
      id: "pasted-docs-notes",
      type: "notes",
      title: "Pasted docs and notes",
      text: notes,
    });
  }

  if (transcript) {
    contentSet.push({
      id: "video-transcript",
      type: "video_transcript",
      title: "Pasted video transcript",
      segments: parseTranscriptSegments(transcript),
    });
  }

  contentSet.push(...await parseUploadedFiles());
  return contentSet;
}

async function generatePlan(event) {
  event.preventDefault();
  clearError();
  setStatus("reading sources");
  const submitButton = $("#planForm button[type='submit']");
  submitButton.disabled = true;
  submitButton.textContent = "Reading sources...";
  let contentSet = [];
  try {
    contentSet = await parseContentSet();
  } catch (error) {
    showError(error.message || "Could not read uploaded files.");
    setStatus("file error");
    submitButton.disabled = false;
    submitButton.textContent = "Build learning bundle";
    return;
  }
  const payload = {
    learning_objective: $("#objectiveInput").value.trim(),
    content_set: contentSet,
    constraints: {
      time_budget_minutes: Number($("#timeBudgetInput").value || 28),
      available_modes: [
        "structured_notes",
        "mind_map",
        "video_or_source_sections",
        "visual_cue",
        "hint_ladder",
        "micro_quiz",
        "typed_explanation",
        "voice_demo",
        "roleplay",
        "worked_example",
        "dynamic_case",
        "adaptive_retest",
      ],
    },
  };
  payload.session_id = buildPayloadSessionId(payload);

  if (!payload.content_set.length) {
    showError("Add at least one URL, uploaded file, note excerpt, or transcript segment.");
    setStatus("waiting for content");
    submitButton.disabled = false;
    submitButton.textContent = "Build learning bundle";
    return;
  }

  if ($("#includeEvidence").checked && loadedSample?.learner_events) {
    payload.learner_events = loadedSample.learner_events;
  }

  const requestBytes = jsonPayloadBytes(payload);
  if (requestBytes > MAX_REQUEST_BODY_BYTES) {
    showError(`This upload becomes ${Math.ceil(requestBytes / 1024 / 1024)} MB after browser encoding. Keep the total under ${Math.floor(MAX_REQUEST_BODY_BYTES / 1024 / 1024)} MB or use fewer PDFs at once.`);
    setStatus("upload too large");
    submitButton.disabled = false;
    submitButton.textContent = "Build learning bundle";
    return;
  }

  const stopBuildProgress = startBuildProgress();
  submitButton.textContent = "Calling models...";
  try {
    const result = await postJsonWithTimeout("/api/track-b/generate", payload, GENERATION_TIMEOUT_MS);
    lastResult = result;
    lastPayload = structuredCloneSafe(payload);
    sessionLearnerEvents = Array.isArray(payload.learner_events) ? [...payload.learner_events] : [];
    demoAnswerBank = {};
    renderResult(result);
    setStatus(result.mode === "cold_start" ? "cold start generated" : "personalized plan generated");
  } catch (error) {
    showError(error.message || "Could not generate the Track B plan.");
    setStatus("error");
  } finally {
    stopBuildProgress();
    submitButton.disabled = false;
    submitButton.textContent = "Build learning bundle";
  }
}

function renderResult(result) {
  document.body.classList.add("lesson-mode");
  $("#inputHero").classList.add("hidden");
  $("#inputScreen").classList.add("hidden");
  $("#resultShell").classList.remove("hidden");
  $("#moduleRail").classList.remove("hidden");
  $("#nextModuleButton").disabled = false;
  currentModules = buildDisplayModules(result);
  activeModuleIndex = 0;
  renderModuleRail();
  renderActiveModule();
  renderRag(result);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function buildDisplayModules(result) {
  const mediaPage = lessonPage(result, "media_lesson") || {};
  const sourceNotesPage = lessonPage(result, "source_notes") || {};
  const checkpointPage = lessonPage(result, "checkpoint") || {};
  const visualPage = lessonPage(result, "visual_repair") || {};
  const practicePage = lessonPage(result, "practice") || {};
  const casePage = lessonPage(result, "dynamic_case") || {};
  const revisionPage = lessonPage(result, "revision") || {};
  const sourceCards = mediaPage.source_cards || [];
  const videoCards = sourceCards.filter(isVideoResource);
  const nonVideoCards = [
    ...(sourceNotesPage.source_cards || []),
    ...sourceCards.filter((card) => !isVideoResource(card)),
  ];
  const uniqueNonVideo = uniqueBy(nonVideoCards, (card) => card.source_id || card.url || card.title);
  return [
    {
      id: "video",
      eyebrow: "Step 1",
      title: "Video breakdown",
      subtitle: "Use the video as source material. Start with the extracted ideas, formulas, diagrams, and audio summary.",
      render: () => renderVideoModule(videoCards.length ? videoCards : sourceCards, mediaPage, result),
    },
    {
      id: "sources",
      eyebrow: "Step 2",
      title: "Notes",
      subtitle: "Read the clean version of the source material.",
      render: () => renderSourceNotesModule(uniqueNonVideo, sourceNotesPage, mediaPage, result),
    },
    {
      id: "checkpoint",
      eyebrow: "Step 3",
      title: "Quick check",
      subtitle: "Answer a few small questions to see what is clear and what needs repair.",
      render: () => renderCheckpointModule(checkpointPage, result),
    },
    {
      id: "visual",
      eyebrow: "Step 4",
      title: "Mind map",
      subtitle: "Turn the idea into a picture, a flow, and a trap chart.",
      render: () => renderVisualModule(visualPage, result),
    },
    {
      id: "case",
      eyebrow: "Step 5",
      title: "Practice",
      subtitle: "Try questions that mix familiar traps with fresh versions.",
      render: () => renderPracticeCaseModule(practicePage, casePage, result),
    },
    {
      id: "revision",
      eyebrow: "Step 6",
      title: "Review plan",
      subtitle: "See when to revise and what to practice next.",
      render: () => renderRevisionModule(revisionPage, result),
    },
  ];
}

function renderModuleRail() {
  $("#moduleRail").innerHTML = currentModules.map((module, index) => `
    <button type="button" class="${index === activeModuleIndex ? "active" : ""}" data-module-index="${index}">
      <span>${escapeHtml(module.eyebrow)}</span>
      <strong>${escapeHtml(module.title)}</strong>
    </button>
  `).join("");
  document.querySelectorAll("[data-module-index]").forEach((button) => {
    button.addEventListener("click", () => {
      activeModuleIndex = Number(button.dataset.moduleIndex || 0);
      renderActiveModule();
      renderModuleRail();
    });
  });
}

function renderActiveModule() {
  const module = currentModules[activeModuleIndex] || currentModules[0];
  if (!module) return;
  $("#moduleStepLabel").textContent = `${module.eyebrow} of ${currentModules.length}`;
  $("#moduleTitle").textContent = module.title;
  $("#moduleBody").innerHTML = `
    <header class="module-header">
      <p class="kicker">${escapeHtml(module.eyebrow)}</p>
      <h1>${escapeHtml(module.title)}</h1>
      <p>${escapeHtml(module.subtitle)}</p>
    </header>
    ${module.render()}
  `;
  $("#prevModuleButton").disabled = activeModuleIndex === 0;
  $("#nextModuleButton").textContent = activeModuleIndex === currentModules.length - 1 ? "Finish" : "Next";
  setupQuizInteractions();
  setupVoiceControls();
  setupAdaptiveSeriesControls();
  applyStoredDemoAnswersToCurrentModule();
  renderMath($("#moduleBody"));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function fillDemoAnswersInCurrentModule() {
  if (lastResult) {
    demoAnswerBank = buildDemoAnswerBank(lastResult);
  }
  applyStoredDemoAnswersToCurrentModule(true);
}

function applyStoredDemoAnswersToCurrentModule(forceStatus = false) {
  const cards = Array.from(document.querySelectorAll("#moduleBody [data-quiz-card]"));
  if (!cards.length) {
    if (forceStatus) setStatus("no questions on this page");
    return;
  }
  cards.forEach((card, index) => {
    const key = demoAnswerKeyForCard(card);
    const answer = demoAnswerBank[key] || demoAnswerBank[demoPromptOnlyKey(card?.dataset.prompt)] || (forceStatus ? demoAnswerForCard(card, index) : "");
    if (answer) applyDemoAnswerToCard(card, answer);
  });
  if (forceStatus) {
    setStatus(`demo answers prepared for ${Object.keys(demoAnswerBank).length || cards.length} checks`);
  }
}

function applyDemoAnswerToCard(card, answer) {
  card.dataset.demoAnswer = answer;
  card.querySelectorAll("[data-drawing-feature]").forEach((input, featureIndex) => {
    input.checked = featureIndex < 3;
  });
  const textarea = card.querySelector("textarea");
  if (textarea) {
    textarea.value = answer;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }
  const correctChoice = card.querySelector(".choice-list button[data-correct='true']");
  if (correctChoice) {
    card.querySelectorAll(".choice-list button").forEach((choice) => choice.classList.remove("selected", "correct", "wrong"));
    correctChoice.classList.add("selected", "correct");
  }
  const feedback = card.querySelector(".quiz-feedback");
  if (feedback) {
    feedback.textContent = "Demo answer filled. Submit it to update the adaptive path, or press Finish to seed a demo profile.";
  }
}

function buildDemoAnswerBank(result) {
  const bank = {};
  const pages = result.lesson_graph?.pages || [];
  const concepts = currentConceptNames();
  const add = (type, prompt, concept, index = 0) => {
    const fallbackConcept = concept || concepts[index % Math.max(1, concepts.length)] || "";
    const answer = demoAnswerForPrompt(type, prompt, fallbackConcept, index);
    bank[demoAnswerKey(type, prompt, fallbackConcept)] = answer;
    bank[demoPromptOnlyKey(prompt)] = answer;
  };
  pages.forEach((page) => {
    const completion = page.completion_check || {};
    if (completion.prompt) add("typed_explanation", completion.prompt, concepts[0], 0);
    (page.questions || []).forEach((question, index) => {
      add(question.type || "typed_explanation", question.prompt, question.concept, index);
    });
    (page.retest_quiz_plan || []).forEach((item, index) => {
      add("adaptive_retest", item.prompt, item.concept, index);
    });
    if (page.type === "dynamic_case") {
      add("dynamic_case", page.scenario || page.title, page.required_output?.concept || concepts[0], 0);
    }
  });
  const visualArtifact = result.model_generation?.assets?.visual_artifact || {};
  if (visualArtifact.draw_question) {
    add("visual_map", visualArtifact.draw_question, visualArtifact.concept || concepts[0], 0);
  }
  return bank;
}

function demoAnswerForCard(card, index = 0) {
  const concept = inferCardConcept(card) || currentConceptNames()[index % Math.max(1, currentConceptNames().length)] || "the target concept";
  const prompt = shortDemoText(card?.dataset.prompt || card?.querySelector("strong")?.textContent || "", 120);
  const type = card?.dataset.drawingCheck !== undefined ? "visual_map" : String(card?.dataset.checkType || "typed");
  return demoAnswerForPrompt(type, prompt, concept, index);
}

function demoAnswerForPrompt(type, prompt, concept, index = 0) {
  const domain = demoAnswerDomain();
  const cleanPrompt = shortDemoText(prompt, 150);
  const target = concept || "the target concept";
  if (domain === "ray_optics") {
    if (String(type).includes("visual")) {
      return `Physics demo answer: I would draw the principal axis, convex lens, optical center O, F1/F2 and 2F marks, then place the object and trace two principal rays: parallel ray through focus and ray through O undeviated. The image position and nature are checked against the lens formula. Prompt focus: ${cleanPrompt}`;
    }
    if (String(type).includes("dynamic") || /formula|numerical|case|solve/i.test(cleanPrompt)) {
      return `Physics demo answer: For a convex lens, first predict with the ray diagram, then use 1/f = 1/v - 1/u. With a real object, u is negative and f is positive for a convex lens. For the common f=10 cm, u=-30 cm case, 1/v = 1/10 - 1/30 = 1/15, so v=+15 cm and m=v/u=-0.5: real, inverted, diminished, between F and 2F. Prompt focus: ${cleanPrompt}`;
    }
    return `Physics demo answer: ${target} is read from the ray-optics source. A convex lens converges rays; the principal axis is the reference line; a ray parallel to the axis refracts through the focus, and a ray through the optical center goes straight. I would cite the source and check the trap against concave lens/sign convention. Prompt focus: ${cleanPrompt}`;
  }
  if (domain === "electrostatics") {
    return `Physics demo answer: ${target} should be explained as electrostatic potential reasoning. Electric potential is work done per unit positive test charge, V = W/q, and for a point charge V = kQ/r. It is scalar, so potentials add algebraically with signs, unlike electric field which adds as a vector. Prompt focus: ${cleanPrompt}`;
  }
  if (domain === "electrochemistry") {
    return `Chemistry demo answer: ${target} should be tied to the galvanic-cell source. Oxidation occurs at the anode, reduction at the cathode, electrons flow through the external wire from anode to cathode, and the salt bridge maintains charge balance. Use Ecell = Ecathode - Eanode; when concentrations change, use the Nernst equation. Prompt focus: ${cleanPrompt}`;
  }
  if (String(type).includes("dynamic")) {
    return `Demo final answer: define ${target} from the supplied source, solve the case step by step, cite the source section used, report medium confidence, and review the weakest step if the result is wrong. Prompt focus: ${cleanPrompt}`;
  }
  return `Demo answer: ${target} means the source-backed idea being tested here. I would separate it from the nearest trap, explain the reasoning link, cite the source, and then try one changed version. Prompt focus: ${cleanPrompt}`;
}

function demoAnswerDomain() {
  const text = [
    lastResult?.content_graph?.learning_objective,
    ...(lastResult?.content_graph?.concepts || []).map((concept) => concept.name),
    ...(lastPayload?.content_set || []).map((source) => `${source.title || ""} ${source.text || ""}`),
  ].join(" ").toLowerCase();
  if (/convex lens|ray optics|lens formula|principal axis|focal|optical center/.test(text)) return "ray_optics";
  if (/electric potential|electrostatic|point charge|equipotential|work per unit charge/.test(text)) return "electrostatics";
  if (/galvanic|nernst|electrochem|anode|cathode|salt bridge|cell potential/.test(text)) return "electrochemistry";
  return "generic";
}

function demoAnswerKeyForCard(card) {
  return demoAnswerKey(card?.dataset.checkType || "typed", card?.dataset.prompt || card?.querySelector("strong")?.textContent || "", inferCardConcept(card));
}

function demoAnswerKey(type, prompt, concept = "") {
  return [type, concept, prompt].map(normalizeDemoKeyPart).join("::");
}

function demoPromptOnlyKey(prompt) {
  return ["prompt", normalizeDemoKeyPart(prompt)].join("::");
}

function normalizeDemoKeyPart(value) {
  return String(value || "").toLowerCase().replace(/\s+/g, " ").trim().slice(0, 220);
}

function finishLessonAndSeedProfile() {
  if (!lastPayload || !lastResult) {
    setStatus("nothing to finish");
    return;
  }
  const generatedEvents = buildDemoLearnerEvents(lastResult);
  const seededEvents = dedupeLearnerEvents([...sessionLearnerEvents, ...generatedEvents]);
  sessionLearnerEvents = seededEvents;
  const seededPayload = structuredCloneSafe(lastPayload);
  seededPayload.learner_events = seededEvents;
  loadedSample = seededPayload;
  lastPayload = structuredCloneSafe(seededPayload);
  $("#objectiveInput").value = seededPayload.learning_objective || "";
  fillContentFields(seededPayload.content_set || []);
  $("#includeEvidence").checked = true;
  document.body.classList.remove("lesson-mode");
  $("#resultShell").classList.add("hidden");
  $("#inputHero").classList.remove("hidden");
  $("#inputScreen").classList.remove("hidden");
  showNotice(`Demo learner profile seed is ready with ${seededEvents.length} evidence events. Keep "Use sample first-attempt answers" checked for a personalized run, or uncheck it for cold start.`);
  setStatus("profile seed ready");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function buildDemoLearnerEvents(result) {
  const concepts = currentConceptNames();
  const pages = result.lesson_graph?.pages || [];
  const events = [];
  const pushEvent = (stage, type, prompt, concept, score) => {
    if (!prompt) return;
    const eventIndex = events.length + 1;
    const eventConcept = concept || concepts[(eventIndex - 1) % Math.max(1, concepts.length)] || "";
    const responseText = demoAnswerForPrompt(type, prompt, eventConcept, eventIndex - 1);
    events.push({
      identity: {
        event_id: `demo-finish-${Date.now()}-${eventIndex}`,
        session_id: currentSessionId(),
        learner_id: "demo-learner",
        timestamp: new Date().toISOString(),
      },
      learning_context: {
        objective: result.content_graph?.learning_objective || lastPayload?.learning_objective || "",
        domain: lastPayload?.constraints?.exam_context || "",
        topic: stage,
        concepts: [eventConcept].filter(Boolean),
        difficulty: 0.56,
        bloom_level: type === "dynamic_case" ? "apply" : "understand",
      },
      activity: {
        stage,
        mode: type === "visual_map" ? "visual" : "typed",
        activity_type: type,
        prompt_variant: prompt,
        expected_output: type === "mcq" ? "selected choice" : "short explanation",
        support_level: "demo_seed",
      },
      response_quality: {
        raw_response: responseText,
        score,
        correctness: score >= 0.72 ? "correct" : "partial",
        answer_completeness: score,
        precision: Math.max(0.45, score - 0.08),
        uses_required_terms: true,
      },
      reasoning_signals: {
        error_type: score >= 0.72 ? "none" : "partial_relation",
        misconception: score >= 0.72 ? "" : `needs clearer distinction for ${concept || "the concept"}`,
        reasoning_depth: score,
        step_order_quality: Math.max(0.45, score - 0.05),
        causal_link_quality: Math.max(0.42, score - 0.08),
        transfer_quality: Math.max(0.38, score - 0.12),
      },
      metacognition: {
        self_reported_confidence: Math.min(0.85, score + 0.12),
        calibration_label: "demo_seed",
      },
      temporal_behavior: {
        total_response_time_seconds: 54 + eventIndex * 8,
        idle_time_seconds: eventIndex % 2 ? 4 : 10,
        revision_count: eventIndex % 3 === 0 ? 1 : 0,
      },
      hint_behavior: {
        hint_requested: score < 0.72,
        hint_count: score < 0.72 ? 1 : 0,
        max_hint_level: score < 0.72 ? "contrast_hint" : "none",
        improvement_after_hint: score < 0.72 ? 0.1 : 0,
      },
      modality_signals: {
        text_comprehension: Math.max(0.45, score - 0.03),
        visual_interpretation: type === "visual_map" ? score : 0.58,
        typed_explanation: type === "typed_explanation" || type === "dynamic_case" ? score : 0.56,
        symbolic_reasoning: type === "dynamic_case" ? Math.max(0.46, score - 0.08) : 0.52,
      },
      affective_behavior: {
        persistence: 0.72,
        dropoff_risk: score < 0.65 ? 0.28 : 0.16,
      },
      intervention_trace: {
        selected_next_mode: score < 0.72 ? "visual_contrast" : "fresh_variant",
        did_improve_after_hint: score < 0.72,
      },
      memory_state: {
        encoding_strength: Math.max(0.35, score - 0.14),
        retrieval_success: score >= 0.72,
        exposures: eventIndex,
        next_review_in_days: score >= 0.72 ? 3 : 1,
      },
    });
  };

  for (const page of pages) {
    const stage = page.id || page.type || "lesson_page";
    (page.questions || []).slice(0, 4).forEach((question, index) => {
      pushEvent(stage, question.type || "typed_explanation", question.prompt, concepts[index % Math.max(1, concepts.length)], 0.62 + (index % 3) * 0.08);
    });
    (page.retest_quiz_plan || []).slice(0, 4).forEach((item, index) => {
      pushEvent(stage, "adaptive_retest", item.prompt, item.concept, 0.58 + (index % 3) * 0.09);
    });
    if (page.type === "dynamic_case") {
      pushEvent(stage, "dynamic_case", page.scenario || page.title, concepts[0], 0.7);
    }
  }
  if (!events.length) {
    pushEvent("lesson_finish", "typed_explanation", "Explain the main idea and cite the source.", concepts[0], 0.68);
  }
  return events.slice(0, 14);
}

function dedupeLearnerEvents(events) {
  const seen = new Set();
  const kept = [];
  for (const event of events) {
    const activity = event.activity || {};
    const context = event.learning_context || {};
    const key = [
      activity.stage,
      activity.activity_type,
      activity.prompt_variant,
      (context.concepts || []).join("|"),
    ].join("::");
    if (seen.has(key)) continue;
    seen.add(key);
    kept.push(event);
  }
  return kept;
}

function currentSessionId() {
  if (lastPayload?.session_id) return lastPayload.session_id;
  if (lastPayload) return buildPayloadSessionId(lastPayload);
  return "browser-demo-session";
}

function buildPayloadSessionId(payload) {
  const fingerprint = JSON.stringify({
    objective: payload?.learning_objective || "",
    sources: (payload?.content_set || []).map((source) => ({
      id: source.id || "",
      type: source.type || "",
      title: source.title || "",
      url: source.url || "",
      text: shortSessionText(source.text || source.notes || source.body || ""),
      segments: (source.segments || []).map((segment) => shortSessionText(segment.text || segment.summary || "")).slice(0, 12),
    })),
  });
  let hash = 2166136261;
  for (let index = 0; index < fingerprint.length; index += 1) {
    hash ^= fingerprint.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `browser-${(hash >>> 0).toString(36)}`;
}

function shortSessionText(value) {
  return String(value || "").replace(/\s+/g, " ").trim().slice(0, 1600);
}

function currentConceptNames() {
  return (lastResult?.content_graph?.concepts || []).map((concept) => concept.name).filter(Boolean);
}

function shortDemoText(value, limit = 140) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= limit) return text || "answer the source-backed prompt";
  return `${text.slice(0, limit).replace(/\s+\S*$/, "")}...`;
}


function renderSnapshot(result) {
  const profile = result.learner_model;
  const graph = result.content_graph;
  const sourceStatus = result.ai_source_analysis?.status === "model_generated" ? "AI analyzed" : "local analysis";
  $("#modeValue").textContent = result.mode === "cold_start" ? "First lesson" : "Personalized";
  $("#sourceCountValue").textContent = `${graph.source_count} sources`;
  $("#chunkCountValue").textContent = `${graph.chunk_count} chunks`;
  $("#profileValue").textContent = profile.profile_available
    ? `${profile.dominant_anchor.replaceAll("_", " ")} route`
    : sourceStatus;
}


function renderBundle(result) {
  const bundle = result.curated_learning_bundle;
  const graph = result.content_graph;
  const mediaPage = lessonPage(result, "media_lesson");
  const visualPage = lessonPage(result, "visual_repair");
  $("#bundleObjective").textContent = result.lesson_graph?.learning_objective || bundle.objective;
  renderLearningMedia(result);

  $("#sourceRationale").innerHTML = bundle.selected_sources.map((source) => `
    <article class="mini-card">
      <div class="mini-card-top">
        <strong>${escapeHtml(source.title)}</strong>
        <span>${escapeHtml(source.type)}</span>
      </div>
      <p>${escapeHtml(source.why_chosen?.[0] || "Selected for objective coverage.")}</p>
      <div class="tag-row">${(source.concepts || []).slice(0, 5).map((concept) => `<span>${escapeHtml(concept)}</span>`).join("")}</div>
    </article>
  `).join("");

  const nodes = visualPage?.mind_map_nodes || bundle.concept_map.nodes || [];
  $("#conceptMap").innerHTML = nodes.map((node) => `
    <article class="map-node">
      <strong>${escapeHtml(node.label || node.name)}</strong>
      <small>${escapeHtml(node.bloom_level)} · difficulty ${escapeHtml(node.difficulty)}</small>
      <p>${escapeHtml((node.prerequisites || []).slice(0, 2).join(", ") || "No explicit prerequisite detected")}</p>
    </article>
  `).join("");

  const notes = mediaPage?.notes_below || bundle.guided_notes.sections || [];
  $("#lessonNotes").innerHTML = notes.map((section) => `
    <article class="note-card">
      <strong>${escapeHtml(section.title)}</strong>
      ${section.body ? `<p>${escapeHtml(section.body)}</p>` : ""}
      ${section.anchors ? `<ul>${section.anchors.map((anchor) => `
        <li><b>${escapeHtml(anchor.concept)}</b>: ${escapeHtml(anchor.definition_or_rule)}</li>
      `).join("")}</ul>` : ""}
    </article>
  `).join("");

  const cards = mediaPage?.memory_cards || buildMemoryCards(graph, result.rag_pipeline?.retrieved_chunks || []);
  $("#factsGrid").innerHTML = cards.map((card) => `
    <article class="memory-card">
      <span>${escapeHtml(card.type)}</span>
      <strong>${escapeHtml(card.title)}</strong>
      <p>${escapeHtml(card.body)}</p>
    </article>
  `).join("");

  const flowSteps = visualPage?.flow_steps || bundle.embedded_evidence_sequence || [];
  $("#flowChart").innerHTML = flowSteps.map((stage, index) => `
    <article class="flow-step">
      <span>${escapeHtml(stage.step || index + 1)}</span>
      <div>
        <strong>${escapeHtml((stage.label || stage.stage || "step").replaceAll("_", " "))}</strong>
        <p>${escapeHtml(stage.body || stage.learner_action)}</p>
        <small>${escapeHtml((stage.evidence || stage.signals_collected || []).join(" · "))}</small>
      </div>
    </article>
  `).join("");
}

function renderCase(result) {
  const dynamicCase = result.dynamic_case;
  const checkpointPage = lessonPage(result, "checkpoint");
  const practicePage = lessonPage(result, "practice");
  const casePage = lessonPage(result, "dynamic_case");
  $("#caseTitle").textContent = dynamicCase.title;
  $("#caseScenario").textContent = dynamicCase.scenario;
  const questions = checkpointPage?.questions || practicePage?.questions || lastResult?.curated_learning_bundle?.checkpoint_questions || [];
  $("#quizList").innerHTML = questions.map((question, index) => renderQuizCard(question, index)).join("");
  const requiredOutput = casePage?.required_output || dynamicCase.required_output;
  $("#requiredOutput").innerHTML = `
    <strong>${escapeHtml(requiredOutput.format)}</strong>
    <ul>${(requiredOutput.components || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    <p>${escapeHtml(requiredOutput.minimum_evidence)}</p>
    <textarea class="answer-box" rows="7" placeholder="Write the final answer, reasoning, source used, confidence, and what you would revise."></textarea>
  `;
  $("#rubricList").innerHTML = (casePage?.rubric || dynamicCase.rubric).map((item) => `
    <article class="rubric-row">
      <div>
        <strong>${escapeHtml(item.name)}</strong>
        <p>${escapeHtml((item.checks || []).join(" "))}</p>
      </div>
      <span>${Math.round(Number(item.weight) * 100)}%</span>
    </article>
  `).join("");
}

function renderQuizCard(question, index) {
  const type = String(question.type || "check").replaceAll("_", " ");
  const prompt = question.prompt || "";
  const concept = (question.captures || []).find((item) => typeof item === "string" && item.length > 3) || "";
  if (question.type === "mcq") {
    return `
      <article class="quiz-card" data-quiz-card data-check-type="mcq" data-concept="${escapeHtml(concept)}" data-prompt="${escapeHtml(prompt)}">
        <span>Check ${index + 1} · ${escapeHtml(type)}</span>
        <strong>${escapeHtml(prompt)}</strong>
        <div class="choice-list">
          <button type="button" data-correct="true">Separate the target concept from the trap and cite a source.</button>
          <button type="button">Treat both concepts as interchangeable.</button>
          <button type="button">Skip reasoning and memorize only the final formula.</button>
        </div>
        <p class="quiz-feedback"></p>
      </article>
    `;
  }
  if (question.type === "typed_explanation" || question.type === "voice_or_roleplay") {
    return `
      <article class="quiz-card" data-quiz-card data-check-type="${escapeHtml(question.type)}" data-concept="${escapeHtml(concept)}" data-prompt="${escapeHtml(prompt)}">
        <span>Check ${index + 1} · ${escapeHtml(type)}</span>
        <strong>${escapeHtml(prompt)}</strong>
        <textarea class="answer-box" rows="4" placeholder="Answer here. Keep it short but show the reasoning."></textarea>
        <button type="button" class="ghost-button small" data-self-check>Mark done</button>
        <p class="quiz-feedback"></p>
      </article>
    `;
  }
  return `
    <article class="quiz-card" data-quiz-card data-check-type="${escapeHtml(question.type || "check")}" data-concept="${escapeHtml(concept)}" data-prompt="${escapeHtml(prompt)}">
      <span>Check ${index + 1} · ${escapeHtml(type)}</span>
      <strong>${escapeHtml(prompt)}</strong>
      <p>${escapeHtml((question.captures || []).join(" · "))}</p>
      <button type="button" class="ghost-button small" data-self-check>Mark done</button>
      <p class="quiz-feedback"></p>
    </article>
  `;
}

function renderPersonalization(result) {
  const profile = result.learner_model;
  const personalization = result.dynamic_case.personalized_variants;
  $("#personalizationSummary").textContent = profile.profile_available
    ? `Evidence exists, so the active route is ${profile.dominant_anchor.replaceAll("_", " ")}.`
    : "No learner evidence yet, so the system previews all variants and waits for embedded checks.";

  const variants = personalization.variants || {};
  $("#variantGrid").innerHTML = Object.entries(variants).map(([key, variant]) => {
    const active = personalization.active_variant === key;
    return `
      <article class="variant-card ${active ? "active" : ""}">
        <span>${active ? "active route" : "variant"}</span>
        <h3>${escapeHtml(variant.profile.label)}</h3>
        <p>${escapeHtml(variant.profile.description)}</p>
        <dl>
          <dt>Notes</dt><dd>${escapeHtml(variant.notes)}</dd>
          <dt>Mind map</dt><dd>${escapeHtml(variant.mind_map)}</dd>
          <dt>Voice / roleplay</dt><dd>${escapeHtml(variant.voice_or_roleplay)}</dd>
          <dt>Hints</dt><dd>${escapeHtml((variant.hints || []).join(" -> "))}</dd>
          <dt>Practice</dt><dd>${escapeHtml(variant.practice)}</dd>
        </dl>
      </article>
    `;
  }).join("");

  const routeCards = Object.entries(profile.anchor_mix || {}).map(([key, value]) => `
    <div>
      <span>${escapeHtml(key.replaceAll("_", " "))}</span>
      <meter min="0" max="1" value="${Number(value)}"></meter>
      <small>${Math.round(Number(value) * 100)}%</small>
    </div>
  `).join("");
  $("#personalizationSummary").innerHTML += `
    <div class="state-bars compact">${routeCards}</div>
    <div class="tag-row">${(profile.weakest_signals || []).map((item) => `<span>${escapeHtml(item.replaceAll("_", " "))}</span>`).join("")}</div>
  `;
}

function renderRoadmap(result) {
  const roadmap = result.adaptive_roadmap || {};
  const revisionPage = lessonPage(result, "revision");
  const lessonPages = result.lesson_graph?.pages || [];
  const methods = lessonPages.length ? lessonPages : (roadmap.next_learning_methods || roadmap.first_pass_sequence || []);
  $("#methodList").innerHTML = methods.map((method, index) => `
    <article class="sequence-row">
      <span>${index + 1}</span>
      <div>
        <strong>${escapeHtml((method.title || method.mode || method.stage || "method").replaceAll("_", " "))}</strong>
        <p>${escapeHtml(method.intent || method.task || method.learner_action || method.adaptive_use)}</p>
      </div>
    </article>
  `).join("");
  $("#reviewSchedule").innerHTML = (revisionPage?.review_schedule || roadmap.review_schedule || []).map((row) => `
    <article class="review-row">
      <div>
        <strong>${escapeHtml(row.concept)}</strong>
        <p>${escapeHtml(row.reason)}</p>
      </div>
      <span>${escapeHtml(row.review_in_days)}d</span>
    </article>
  `).join("");
}

function renderRag(result) {
  const rag = result.rag_pipeline || {};
  const analysis = result.ai_source_analysis || {};
  const ragDetails = [
    rag.vector_rag_requested ? "vector requested" : "lexical default",
    rag.embedding_model ? `embedding ${rag.embedding_model}` : "",
    rag.pinecone_namespace ? `namespace ${rag.pinecone_namespace}` : "",
  ].filter(Boolean).join(" · ");
  $("#ragChunks").innerHTML = `
    <article class="mini-card">
      <div class="mini-card-top">
        <strong>${escapeHtml(rag.type || "local_lexical_tfidf")}</strong>
        <span>${rag.pinecone_enabled ? "pinecone configured" : "local/fallback"}</span>
      </div>
      ${ragDetails ? `<small>${escapeHtml(ragDetails)}</small>` : ""}
      <p>${escapeHtml(rag.fallback_reason || rag.retrieval_role || "Retrieved source chunks for generation.")}</p>
    </article>
    ${(rag.retrieved_chunks || []).map((chunk) => `
    <article class="mini-card">
      <div class="mini-card-top">
        <strong>${escapeHtml(chunk.source_title)}</strong>
        <span>${escapeHtml(chunk.start && chunk.end ? `${chunk.start}-${chunk.end}` : chunk.id)}</span>
      </div>
      <p>${escapeHtml(chunk.selected_because)}</p>
      <blockquote>${escapeHtml(chunk.text.slice(0, 360))}${chunk.text.length > 360 ? "..." : ""}</blockquote>
    </article>
  `).join("")}`;
  $("#llmPacket").textContent = JSON.stringify({
    lesson_graph: result.lesson_graph,
    ai_source_analysis: result.ai_source_analysis,
    llm_generation_packet: result.llm_generation_packet,
  }, null, 2);
  const generation = result.model_generation || {};
  const assets = generation.assets || {};
  $("#modelGeneration").innerHTML = `
    <article class="mini-card">
      <div class="mini-card-top">
        <strong>${escapeHtml(analysis.status || "source analysis")}</strong>
        <span>${escapeHtml(analysis.provider || "local")}</span>
      </div>
      <p>${escapeHtml(analysis.reason || analysis.summary || "Source analysis produced the staged lesson graph.")}</p>
      <div class="tag-row">${(analysis.page_sequence || []).slice(0, 5).map((page) => `<span>${escapeHtml(page.title || page.id || page.page_type)}</span>`).join("")}</div>
    </article>
    <article class="mini-card">
      <div class="mini-card-top">
        <strong>${escapeHtml(generation.status || "not available")}</strong>
        <span>${escapeHtml(generation.provider || "local")}</span>
      </div>
      <p>${escapeHtml(generation.reason || "No model generation result was returned.")}</p>
    </article>
    <article class="mini-card">
      <strong>Generated next plan</strong>
      <ul>${(assets.next_learning_plan || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </article>
    <article class="mini-card">
      <strong>Generated hints and assessment</strong>
      <p>${escapeHtml((assets.hint_ladder || []).join(" -> "))}</p>
      <ul>${(assets.micro_assessment || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </article>
  `;
}



function setupTabs() {
  document.querySelectorAll("[data-panel-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.panelTarget;
      document.querySelectorAll("[data-panel-target]").forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll(".result-panel").forEach((panel) => panel.classList.toggle("active", panel.id === target));
    });
  });
}

function renderFileList() {
  const files = Array.from($("#fileInput").files || []);
  if (!files.length) {
    $("#fileList").textContent = "No files selected";
    return;
  }
  $("#fileList").innerHTML = files.map((file) => `
    <span>${escapeHtml(file.name)} · ${Math.ceil(file.size / 1024)} KB</span>
  `).join("");
}

$("#planForm").addEventListener("submit", generatePlan);
$("#samplePhysicsButton").addEventListener("click", () => loadSample("physics"));
$("#sampleChemistryButton").addEventListener("click", () => loadSample("chemistry"));
$("#sampleEvidenceButton").addEventListener("click", () => loadSample("evidence"));
$("#sourceSuggestButton").addEventListener("click", suggestSources);
["objectiveInput", "urlInput", "notesInput", "transcriptInput"].forEach((id) => {
  $(`#${id}`).addEventListener("input", invalidateLoadedSampleEvidence);
});
$("#fileInput").addEventListener("change", () => {
  renderFileList();
  invalidateLoadedSampleEvidence();
});
$("#backToInputButton").addEventListener("click", () => {
  resetGeneratedLessonState("ready");
  window.scrollTo({ top: 0, behavior: "smooth" });
});
$("#prevModuleButton").addEventListener("click", () => {
  activeModuleIndex = Math.max(0, activeModuleIndex - 1);
  renderActiveModule();
  renderModuleRail();
});
$("#demoAnswerButton").addEventListener("click", fillDemoAnswersInCurrentModule);
$("#nextModuleButton").addEventListener("click", () => {
  if (document.querySelector("[data-adaptive-loop-page='true']") || activeModuleIndex === currentModules.length - 1) {
    finishLessonAndSeedProfile();
    return;
  }
  activeModuleIndex = Math.min(currentModules.length - 1, activeModuleIndex + 1);
  renderActiveModule();
  renderModuleRail();
});
$("#copyJsonButton").addEventListener("click", async () => {
  if (!lastResult) return;
  await navigator.clipboard.writeText(JSON.stringify(lastResult, null, 2));
  setStatus("json copied");
});

setupTabs();
window.addEventListener("pageshow", (event) => {
  if (event.persisted && document.body.classList.contains("lesson-mode")) {
    resetGeneratedLessonState("restored page reset; rebuild lesson");
  }
});
loadSample("physics").catch(() => setStatus("ready"));
