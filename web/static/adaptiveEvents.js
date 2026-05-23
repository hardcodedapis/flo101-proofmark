function setupQuizInteractions() {
  setupDrawingImageUploads();
  document.querySelectorAll("[data-quiz-card] .choice-list button").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest("[data-quiz-card]");
      card.querySelectorAll(".choice-list button").forEach((choice) => choice.classList.remove("selected", "correct", "wrong"));
      button.classList.add("selected", button.dataset.correct === "true" ? "correct" : "wrong");
      const feedback = card.querySelector(".quiz-feedback");
      const isCorrect = button.dataset.correct === "true";
      feedback.textContent = isCorrect
        ? "Good. Sending this evidence to update the next plan..."
        : "Not quite. Sending this misconception evidence to update the next plan...";
      await submitLearnerEvent(card, buildLearnerEvent(card, {
        answer: button.textContent.trim(),
        activityType: "mcq",
        modality: "choice",
        selectedChoiceText: button.textContent.trim(),
      }));
    });
  });
  document.querySelectorAll("[data-self-check]").forEach((button) => {
    button.addEventListener("click", async () => {
      const card = button.closest("[data-quiz-card]");
      const answer = card.querySelector("textarea")?.value.trim() || card?.dataset.demoAnswer || "";
      const feedback = card.querySelector(".quiz-feedback");
      if (card?.dataset.drawingCheck !== undefined) {
        const selected = Array.from(card.querySelectorAll("[data-drawing-feature]:checked")).map((item) => item.value);
        const drawingImage = drawingImageEvidence(card);
        if (!drawingImage && answer.length < 32) {
          feedback.textContent = "Attach the drawing image, or describe the labels/arrows in enough detail.";
          return;
        }
        if (selected.length < 2) {
          feedback.textContent = "Tick at least two features you included so the backend has structured visual evidence.";
          return;
        }
        button.classList.add("selected");
        feedback.textContent = drawingImage
          ? `Saved drawing image and features: ${selected.join(", ")}. Updating the next reteach/test page...`
          : `Saved visual evidence: ${selected.join(", ")}. Updating the next reteach/test page...`;
        await submitLearnerEvent(card, buildLearnerEvent(card, {
          answer: answer || `Uploaded drawing image: ${drawingImage?.name || "drawing"}.`,
          activityType: "visual_map",
          modality: "drawing",
          selectedFeatures: selected,
          expectedFeatures: Array.from(card.querySelectorAll("[data-drawing-feature]")).map((item) => item.value),
          drawingImage,
        }));
        return;
      }
      const requiresAnswer = card?.dataset.requiresAnswer === "true";
      if ((requiresAnswer || answer) && answer.length < 24) {
        feedback.textContent = "Write a specific answer before submitting. Include the reasoning link.";
        return;
      }
      button.classList.add("selected");
      feedback.textContent = answer
        ? "Marked. Sending reasoning evidence to update the next plan..."
        : "Marked. Sending completion evidence to update the next plan...";
      await submitLearnerEvent(card, buildLearnerEvent(card, {
        answer,
        activityType: card.dataset.checkType || "typed_explanation",
        modality: "typed",
      }));
    });
  });
}

function setupDrawingImageUploads() {
  document.querySelectorAll("[data-drawing-image]").forEach((input) => {
    if (input.dataset.bound === "true") return;
    input.dataset.bound = "true";
    input.addEventListener("change", async () => {
      const card = input.closest("[data-quiz-card]");
      const feedback = card?.querySelector(".quiz-feedback");
      const preview = card?.querySelector("[data-drawing-image-preview]");
      const file = input.files?.[0];
      clearDrawingImageEvidence(card, preview);
      if (!file) return;
      if (!file.type.startsWith("image/")) {
        if (feedback) feedback.textContent = "Use an image file for the drawing upload.";
        return;
      }
      if (feedback) feedback.textContent = "Preparing drawing image...";
      try {
        const evidence = await imageFileToEvidence(file);
        card.dataset.drawingImage = JSON.stringify(evidence);
        if (preview) {
          preview.classList.remove("hidden");
          preview.innerHTML = `
            <img src="${escapeHtml(evidence.data_url)}" alt="">
            <div>
              <strong>${escapeHtml(evidence.name)}</strong>
              <small>${escapeHtml(`${evidence.width}x${evidence.height}, ${Math.ceil(evidence.encoded_bytes / 1024)} KB`)}</small>
            </div>
          `;
        }
        if (feedback) feedback.textContent = "Drawing image attached. Tick the features you included, then save evidence.";
      } catch (_error) {
        if (feedback) feedback.textContent = "Could not read that image. Try a PNG, JPG, or WebP screenshot.";
      }
    });
  });
}

function buildLearnerEvent(card, options = {}) {
  const concept = inferCardConcept(card);
  const answer = options.answer || "";
  const activityType = options.activityType || card?.dataset.checkType || "checkpoint";
  const isVisual = activityType === "visual_map" || options.modality === "drawing";
  return {
    identity: {
      event_id: `live-${Date.now()}-${++learnerEventCounter}`,
      session_id: typeof currentSessionId === "function" ? currentSessionId() : "browser-demo-session",
      learner_id: "demo-learner",
      timestamp: new Date().toISOString(),
    },
    learning_context: {
      objective: lastPayload?.learning_objective || "",
      domain: lastPayload?.constraints?.exam_context || "",
      topic: currentModules[activeModuleIndex]?.title || "",
      concepts: [concept].filter(Boolean),
      difficulty: currentModules[activeModuleIndex]?.difficulty || 0.5,
      bloom_level: "understand",
    },
    activity: {
      stage: currentModules[activeModuleIndex]?.id || `module-${activeModuleIndex + 1}`,
      mode: isVisual ? "visual" : options.modality || "typed",
      activity_type: activityType,
      prompt_variant: card?.dataset.prompt || card?.querySelector("strong")?.textContent || "",
      expected_output: isVisual ? "drawing evidence plus labels" : "short explanation or choice",
      support_level: "embedded_checkpoint",
    },
    response_quality: {
      raw_response: answer,
      client_observation: "raw checkpoint evidence; server computes score and correctness",
    },
    interaction: {
      selected_choice_text: options.selectedChoiceText || "",
      selected_features: options.selectedFeatures || [],
      expected_features: options.expectedFeatures || [],
      answer_length: answer.length,
      drawing_image: options.drawingImage || null,
    },
    metacognition: {
      self_reported_confidence: 0.5,
      calibration_label: "server_to_estimate",
    },
    temporal_behavior: {
      total_response_time_seconds: 45,
      idle_time_seconds: 0,
      revision_count: answer.length > 120 ? 1 : 0,
    },
    hint_behavior: {
      hint_requested: false,
      hint_count: 0,
      max_hint_level: "none",
      improvement_after_hint: 0,
    },
    visual_interaction: {
      selected_nodes: options.selectedFeatures || [],
      correct_edges_identified: isVisual ? options.selectedFeatures || [] : [],
      incorrect_edges_identified: [],
      uploaded_image: options.drawingImage ? {
        name: options.drawingImage.name,
        type: options.drawingImage.type,
        width: options.drawingImage.width,
        height: options.drawingImage.height,
      } : null,
    },
  };
}

function drawingImageEvidence(card) {
  if (!card?.dataset.drawingImage) return null;
  try {
    return JSON.parse(card.dataset.drawingImage);
  } catch (_error) {
    return null;
  }
}

function clearDrawingImageEvidence(card, preview) {
  if (card) delete card.dataset.drawingImage;
  if (preview) {
    preview.classList.add("hidden");
    preview.innerHTML = "";
  }
}

function imageFileToEvidence(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error);
    reader.onload = () => {
      resizeImageDataUrl(String(reader.result || ""), file.type)
        .then((resized) => resolve({
          name: file.name,
          type: resized.type,
          original_size: file.size,
          encoded_bytes: Math.round((resized.dataUrl.length * 3) / 4),
          width: resized.width,
          height: resized.height,
          data_url: resized.dataUrl,
        }))
        .catch(reject);
    };
    reader.readAsDataURL(file);
  });
}

function resizeImageDataUrl(dataUrl, sourceType) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const maxWidth = 1200;
      const maxHeight = 900;
      const scale = Math.min(1, maxWidth / image.width, maxHeight / image.height);
      const width = Math.max(1, Math.round(image.width * scale));
      const height = Math.max(1, Math.round(image.height * scale));
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) {
        reject(new Error("Canvas unavailable"));
        return;
      }
      context.drawImage(image, 0, 0, width, height);
      const type = sourceType === "image/png" ? "image/png" : "image/jpeg";
      resolve({
        dataUrl: canvas.toDataURL(type, type === "image/jpeg" ? 0.82 : undefined),
        width,
        height,
        type,
      });
    };
    image.onerror = () => reject(new Error("Image decode failed"));
    image.src = dataUrl;
  });
}

function inferCardConcept(card) {
  const explicit = card?.dataset.concept || "";
  const concepts = (lastResult?.content_graph?.concepts || []).map((concept) => concept.name).filter(Boolean);
  const text = `${explicit} ${card?.dataset.prompt || ""} ${card?.textContent || ""}`.toLowerCase();
  return concepts.find((concept) => text.includes(String(concept).toLowerCase())) || explicit || concepts[0] || "";
}

async function submitLearnerEvent(card, event) {
  const feedback = card?.querySelector(".quiz-feedback");
  if (!lastPayload) {
    if (feedback) feedback.textContent = "Generate a learning bundle first, then this evidence can update the backend plan.";
    return;
  }
  if (card?.dataset.adapting === "true") return;
  card.dataset.adapting = "true";
  const refreshAdaptiveLoop = Boolean(document.querySelector("[data-adaptive-loop-page='true']"));
  setStatus("updating adaptive plan");
  try {
    const basePayload = structuredCloneSafe(lastPayload);
    basePayload.learner_events = [...sessionLearnerEvents];
    const result = await postJsonWithTimeout(
      "/api/track-b/adapt",
      { base_payload: basePayload, learner_event: event },
      GENERATION_TIMEOUT_MS,
    );
    sessionLearnerEvents.push(event);
    lastPayload.learner_events = [...sessionLearnerEvents];
    lastResult = result;
    currentModules = buildDisplayModules(result);
    renderModuleRail();
    const update = result.adaptive_update || {};
    const nextReview = update.next_review || {};
    if (feedback) {
      feedback.textContent = [
        `Server scored: ${update.latest_server_score || "recorded"}`,
        `Route: ${String(update.dominant_anchor || "balanced").replaceAll("_", " ")}`,
        update.next_mode ? `next mode: ${String(update.next_mode).replaceAll("_", " ")}` : "",
        nextReview.concept ? `review ${nextReview.concept} in ${nextReview.review_in_days}d` : "",
      ].filter(Boolean).join(" · ");
    }
    if (refreshAdaptiveLoop && typeof renderAdaptiveSeriesPage === "function") {
      window.setTimeout(() => renderAdaptiveSeriesPage(result), 650);
    }
    setStatus("adaptive plan updated");
  } catch (error) {
    if (feedback) {
      feedback.textContent = `Evidence saved locally, but backend regeneration failed: ${error.message || "unknown error"}`;
    }
    setStatus("adaptive update failed");
  } finally {
    if (card) card.dataset.adapting = "false";
  }
}

function setupVoiceControls() {
  const button = $("#voiceSummaryButton");
  if (!button) return;
  button.addEventListener("click", async () => {
    const status = $("#voiceSummaryStatus");
    const audio = $("#voiceSummaryAudio");
    button.disabled = true;
    button.textContent = "Generating audio...";
    status.textContent = "Creating a short spoken explanation with the backend demo voice.";
    try {
      const result = await postJsonWithTimeout("/api/track-b/voice-summary", {
        text: button.dataset.voiceScript || "",
      }, 600000);
      const blob = base64ToBlob(result.audio_mpeg_base64, result.mime_type || "audio/mpeg");
      audio.src = URL.createObjectURL(blob);
      audio.classList.remove("hidden");
      status.textContent = result.disclaimer || "Audio generated with the configured demo voice.";
      audio.play().catch(() => {});
    } catch (error) {
      status.textContent = error.message || "Could not generate voice audio.";
    } finally {
      button.disabled = false;
      button.textContent = "Generate voice summary";
    }
  });
}

function setupAdaptiveSeriesControls() {
  const button = $("#adaptiveSeriesButton");
  if (!button || !lastResult) return;
  button.addEventListener("click", () => renderAdaptiveSeriesPage(lastResult));
}
