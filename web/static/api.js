function $(selector) {
  return document.querySelector(selector);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function structuredCloneSafe(value) {
  return JSON.parse(JSON.stringify(value ?? {}));
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.readAsDataURL(file);
  });
}

function jsonPayloadBytes(payload) {
  return new TextEncoder().encode(JSON.stringify(payload ?? {})).length;
}

async function postJsonWithTimeout(url, payload, timeoutMs) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const body = JSON.stringify(payload);
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      signal: controller.signal,
    });
    const text = await response.text();
    let result = {};
    try {
      result = text ? JSON.parse(text) : {};
    } catch (_error) {
      throw new Error(response.ok
        ? "Local backend returned an invalid JSON response."
        : `Local backend returned HTTP ${response.status}.`);
    }
    if (!response.ok || result.error) {
      throw new Error(result.error?.message || "Could not generate the Track B plan.");
    }
    return result;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("Generation took too long. The request was waiting on live model/RAG providers. Try again; cached provider results should be reused when available.");
    }
    if (error instanceof TypeError || /NetworkError|Failed to fetch/i.test(error.message || "")) {
      throw new Error("Could not reach the local backend. Make sure the ProofMark server is running; if this happened during a PDF upload, restart the server so the larger upload limit is active.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function base64ToBlob(base64, mimeType) {
  const binary = atob(base64 || "");
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: mimeType });
}
