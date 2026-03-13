(function () {
  const copyButtons = document.querySelectorAll("[data-copy-target]");
  copyButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const textarea = document.querySelector("textarea[name='cleaned_text']");
      if (!textarea) {
        return;
      }
      textarea.select();
      try {
        document.execCommand("copy");
        button.textContent = "Copied";
        setTimeout(() => {
          button.textContent = "Copy";
        }, 1200);
      } catch (err) {
        console.error(err);
      }
    });
  });
})();

(function () {
  const flashes = document.querySelectorAll(".flash-success");
  if (!flashes.length) {
    return;
  }
  const hideAfterMs = 3000;
  const removeAfterMs = 3800;
  setTimeout(() => {
    flashes.forEach((flash) => flash.classList.add("hide"));
  }, hideAfterMs);
  setTimeout(() => {
    flashes.forEach((flash) => flash.remove());
  }, removeAfterMs);
})();

(function () {
  const formatButtons = document.querySelectorAll("[data-copy-format]");
  if (!formatButtons.length) {
    return;
  }

  const escapeHtml = (value) =>
    value
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  const toHtml = (text) => {
    const safe = escapeHtml(text).trim();
    if (!safe) {
      return "";
    }
    const paragraphs = safe.split(/\n{2,}/).map((chunk) => {
      const lines = chunk.split(/\n/).join("<br />");
      return `<p>${lines}</p>`;
    });
    return paragraphs.join("");
  };

  const setStatus = (button, label) => {
    const original = button.textContent;
    button.textContent = label;
    setTimeout(() => {
      button.textContent = original;
    }, 1200);
  };

  formatButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const textarea = document.querySelector("textarea[name='cleaned_text']");
      if (!textarea) {
        return;
      }
      const plainText = textarea.value || "";
      const htmlText = toHtml(plainText);
      if (!plainText.trim()) {
        setStatus(button, "Empty");
        return;
      }

      if (navigator.clipboard && window.ClipboardItem) {
        try {
          const htmlBlob = new Blob([htmlText], { type: "text/html" });
          const textBlob = new Blob([plainText], { type: "text/plain" });
          await navigator.clipboard.write([
            new ClipboardItem({
              "text/html": htmlBlob,
              "text/plain": textBlob,
            }),
          ]);
          setStatus(button, "Copied");
          return;
        } catch (err) {
          console.error(err);
        }
      }

      // Fallback: plain-text copy
      textarea.select();
      try {
        document.execCommand("copy");
        setStatus(button, "Copied");
      } catch (err) {
        console.error(err);
      }
    });
  });
})();

(function () {
  const input = document.querySelector("input[name='images']");
  const previewWrap = document.getElementById("sniper-preview");
  const canvas = document.getElementById("sniper-canvas");
  const img = document.getElementById("sniper-image");
  const selection = document.getElementById("sniper-selection");
  const clearBtn = document.getElementById("sniper-clear");
  const fieldX = document.querySelector("input[name='crop_x']");
  const fieldY = document.querySelector("input[name='crop_y']");
  const fieldW = document.querySelector("input[name='crop_w']");
  const fieldH = document.querySelector("input[name='crop_h']");

  if (!input || !previewWrap || !canvas || !img || !selection) {
    return;
  }

  let dragging = false;
  let startX = 0;
  let startY = 0;
  const isMobile = window.matchMedia("(max-width: 700px)").matches;

  const resetSelection = () => {
    selection.style.display = "none";
    selection.style.width = "0px";
    selection.style.height = "0px";
    if (fieldX) fieldX.value = "";
    if (fieldY) fieldY.value = "";
    if (fieldW) fieldW.value = "";
    if (fieldH) fieldH.value = "";
  };

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

  const updateFields = (x, y, w, h) => {
    if (fieldX) fieldX.value = Math.round(x);
    if (fieldY) fieldY.value = Math.round(y);
    if (fieldW) fieldW.value = Math.round(w);
    if (fieldH) fieldH.value = Math.round(h);
  };

  const getPoint = (event) => {
    const rect = img.getBoundingClientRect();
    const x = clamp(event.clientX - rect.left, 0, rect.width);
    const y = clamp(event.clientY - rect.top, 0, rect.height);
    return { x, y, rect };
  };

  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    if (!file) {
      previewWrap.classList.add("hidden");
      resetSelection();
      return;
    }

    const url = URL.createObjectURL(file);
    img.onload = () => {
      previewWrap.classList.remove("hidden");
      resetSelection();
      if (isMobile) {
        // Auto-apply full image selection on mobile for easier scanning.
        const rect = img.getBoundingClientRect();
        selection.style.display = "block";
        selection.style.left = "0px";
        selection.style.top = "0px";
        selection.style.width = `${rect.width}px`;
        selection.style.height = `${rect.height}px`;
        updateFields(0, 0, img.naturalWidth, img.naturalHeight);
      }
    };
    img.src = url;
  });

  canvas.addEventListener("pointerdown", (event) => {
    if (!img.src) {
      return;
    }
    dragging = true;
    const { x, y } = getPoint(event);
    startX = x;
    startY = y;
    selection.style.display = "block";
    selection.style.left = `${x}px`;
    selection.style.top = `${y}px`;
    selection.style.width = "0px";
    selection.style.height = "0px";
    event.preventDefault();
  });

  window.addEventListener("pointermove", (event) => {
    if (!dragging) {
      return;
    }
    const { x, y } = getPoint(event);
    const left = Math.min(startX, x);
    const top = Math.min(startY, y);
    const width = Math.abs(x - startX);
    const height = Math.abs(y - startY);
    selection.style.left = `${left}px`;
    selection.style.top = `${top}px`;
    selection.style.width = `${width}px`;
    selection.style.height = `${height}px`;
  });

  window.addEventListener("pointerup", (event) => {
    if (!dragging) {
      return;
    }
    dragging = false;
    const { x, y, rect } = getPoint(event);
    const left = Math.min(startX, x);
    const top = Math.min(startY, y);
    const width = Math.abs(x - startX);
    const height = Math.abs(y - startY);
    const scaleX = img.naturalWidth / rect.width;
    const scaleY = img.naturalHeight / rect.height;
    if (width < 2 || height < 2) {
      resetSelection();
      return;
    }
    updateFields(left * scaleX, top * scaleY, width * scaleX, height * scaleY);
  });

  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      resetSelection();
    });
  }
})();

(function () {
  const startBtn = document.getElementById("camera-start");
  const enableBtn = document.getElementById("camera-enable");
  const video = document.getElementById("camera-video");
  const canvas = document.getElementById("camera-canvas");
  const preview = document.getElementById("camera-preview");
  const status = document.getElementById("camera-status");
  const resultCard = document.getElementById("camera-result");
  const extractedEl = document.getElementById("camera-extracted");
  const cleanedEl = document.getElementById("camera-cleaned");
  const openLink = document.getElementById("camera-open");
  const translateBtn = document.getElementById("camera-translate-btn");
  const translateLang = document.getElementById("camera-translate-lang");
  const translationWrap = document.getElementById("camera-translation");
  const translationText = document.getElementById("camera-translation-text");
  const langSelect = document.querySelector("select[name='camera_lang']");
  const sourceSelect = document.querySelector("select[name='camera_source']");

  if (!startBtn || !enableBtn || !video || !canvas || !preview) {
    return;
  }

  let stream = null;
  let scanning = false;
  const isMobile = window.matchMedia("(max-width: 700px)").matches;
  let autoAttempts = 0;
  const MAX_AUTO_ATTEMPTS = 2;
  let lastScanId = null;
  let busyRetries = 0;
  const MAX_BUSY_RETRIES = 1;

  const setStatus = (message) => {
    if (status) {
      status.textContent = message;
    }
  };

  const stopStream = () => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      stream = null;
    }
  };

  const getConstraints = () => {
    const source = sourceSelect ? sourceSelect.value : "auto";
    let facingMode = { ideal: "environment" };
    if (source === "front") {
      facingMode = "user";
    } else if (source === "rear") {
      facingMode = { ideal: "environment" };
    }
    const videoConstraints = { facingMode };
    if (isMobile) {
      videoConstraints.width = { ideal: 1280, max: 1280 };
      videoConstraints.height = { ideal: 720, max: 720 };
    }
    return { video: videoConstraints, audio: false };
  };

  const getFallbackConstraints = () => {
    const source = sourceSelect ? sourceSelect.value : "auto";
    let facingMode = { ideal: "environment" };
    if (source === "front") {
      facingMode = "user";
    } else if (source === "rear") {
      facingMode = { ideal: "environment" };
    }
    const videoConstraints = { facingMode };
    if (isMobile) {
      videoConstraints.width = { ideal: 640, max: 640 };
      videoConstraints.height = { ideal: 480, max: 480 };
    }
    return { video: videoConstraints, audio: false };
  };

  const waitForVideoReady = () =>
    new Promise((resolve) => {
      const start = Date.now();
      const check = () => {
        if (video.videoWidth && video.videoHeight) {
          resolve(true);
          return;
        }
        if (Date.now() - start > 2000) {
          resolve(false);
          return;
        }
        requestAnimationFrame(check);
      };
      check();
    });

  const enableCamera = async (autoScan = false) => {
    stopStream();
    try {
      stream = await navigator.mediaDevices.getUserMedia(getConstraints());
      video.srcObject = stream;
      await video.play();
      preview.classList.add("active");
      setStatus(autoScan && isMobile ? "Camera ready. Auto scan starting..." : "Camera ready. Tap Start Camera to scan.");
      startBtn.textContent = "Scan Now";
      if (autoScan && isMobile) {
        autoAttempts = 0;
        setTimeout(() => {
          captureAndScan(true, false, true);
        }, 700);
      }
    } catch (err) {
      try {
        stream = await navigator.mediaDevices.getUserMedia(getFallbackConstraints());
        video.srcObject = stream;
        await video.play();
        preview.classList.add("active");
        setStatus(autoScan && isMobile ? "Camera ready (low res). Auto scan starting..." : "Camera ready (low res). Tap Start Camera to scan.");
        startBtn.textContent = "Scan Now";
        if (autoScan && isMobile) {
          autoAttempts = 0;
          setTimeout(() => {
            captureAndScan(true, false, true);
          }, 700);
        }
      } catch (fallbackErr) {
        setStatus("Camera permission denied or unavailable.");
      }
    }
  };

  enableBtn.addEventListener("click", () => {
    enableCamera(true);
  });

  const captureAndScan = async (autoMode = false, advanced = false, tiny = false) => {
    if (scanning) {
      return;
    }
    if (!autoMode) {
      busyRetries = 0;
    }

    if (!stream) {
      await enableCamera(autoMode);
      if (!stream) {
        return;
      }
    }

    const ready = await waitForVideoReady();
    if (!ready) {
      setStatus("Camera not ready. Try again.");
      return;
    }

    scanning = true;
    startBtn.disabled = true;
    setStatus(autoMode ? "Auto scanning..." : "Scanning...");

    const ctx = canvas.getContext("2d");
    const rawWidth = video.videoWidth;
    const rawHeight = video.videoHeight;
    const autoBoost = autoMode && autoAttempts > 0 && !advanced;
    let scale = 1;
    if (isMobile) {
      const maxSide = tiny ? 800 : advanced ? 1400 : autoBoost ? 1100 : 1000;
      scale = Math.min(1, maxSide / Math.max(rawWidth, rawHeight));
    }
    canvas.width = Math.round(rawWidth * scale);
    canvas.height = Math.round(rawHeight * scale);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    try {
      const quality = tiny ? 0.6 : advanced ? 0.85 : autoBoost ? 0.75 : 0.7;
      const blob = await new Promise((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", quality)
      );
      if (!blob) {
        throw new Error("Capture failed.");
      }

      const formData = new FormData();
      const selectedLang = langSelect ? langSelect.value : "eng";
      const fastLang = selectedLang.includes("+") ? selectedLang.split("+")[0] : selectedLang;
      const langForRequest = isMobile && tiny ? fastLang : selectedLang;
      formData.append("images", blob, "camera.jpg");
      formData.append("lang", langForRequest);
      formData.append("cleanup", "on");
      formData.append("detect_intent", "on");
      formData.append("autocorrect", "on");
      formData.append("student_mode", "on");
      formData.append("skip_storage", "on");
      if (isMobile) {
        formData.append("mobile", "on");
      }
      if (tiny) {
        formData.append("mobile_tiny", "on");
      }
      if (advanced) {
        formData.append("advanced_ocr", "on");
      } else if (autoMode || isMobile) {
        formData.append("fast_ocr", "on");
      }

      const controller = new AbortController();
      const timeoutMs = isMobile ? (tiny ? 60000 : 120000) : 60000;
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      const response = await fetch("/api/scans", {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      const rawText = await response.text();
      let payload = {};
      try {
        payload = rawText ? JSON.parse(rawText) : {};
      } catch (err) {
        payload = {};
      }
      if (!response.ok || !payload.ok) {
        const safeText = rawText && rawText.length < 180 && !rawText.includes("<") ? rawText : "";
        const errorMessage =
          payload.error || safeText || `OCR failed (HTTP ${response.status}). Try again.`;
        const noReadable = String(errorMessage).toLowerCase().includes("no readable");
        const busy = String(errorMessage).toLowerCase().includes("busy");
        const serverBusy =
          busy ||
          response.status === 413 ||
          response.status === 429 ||
          response.status === 503 ||
          response.status === 504 ||
          response.status >= 500;
        if (isMobile && !tiny && serverBusy) {
          scanning = false;
          startBtn.disabled = false;
          setStatus("Auto-optimizing for mobile...");
          setTimeout(() => captureAndScan(autoMode, false, true), 700);
          return;
        }
        if (isMobile && tiny && serverBusy && busyRetries < MAX_BUSY_RETRIES) {
          busyRetries += 1;
          scanning = false;
          startBtn.disabled = false;
          setStatus("Retrying mobile scan...");
          setTimeout(() => captureAndScan(autoMode, false, true), 2000);
          return;
        }
        if (isMobile && tiny && noReadable) {
          scanning = false;
          startBtn.disabled = false;
          setStatus("Trying higher quality...");
          setTimeout(() => captureAndScan(autoMode, false, false), 800);
          return;
        }
        if (autoMode && noReadable) {
          if (autoAttempts < MAX_AUTO_ATTEMPTS) {
            autoAttempts += 1;
            scanning = false;
            startBtn.disabled = false;
            setStatus("Auto scan retrying...");
            setTimeout(() => captureAndScan(true, false), 900);
            return;
          }
          setStatus("Auto scan couldn't read text. Tap Scan Now for full scan.");
          return;
        }
        if (!autoMode && noReadable && !advanced && isMobile) {
          scanning = false;
          startBtn.disabled = false;
          setStatus("Trying enhanced scan...");
          setTimeout(() => captureAndScan(false, true), 600);
          return;
        }
        throw new Error(errorMessage);
      }

      const scanId = payload.data && payload.data.id;
      lastScanId = scanId || null;
      if (scanId && openLink) {
        openLink.href = `/result/${scanId}`;
      }
      if (extractedEl) {
        extractedEl.textContent = (payload.data && payload.data.extracted_text) || "";
      }
      if (cleanedEl) {
        cleanedEl.value =
          (payload.data && payload.data.cleaned_text) ||
          (payload.data && payload.data.extracted_text) ||
          "";
      }
      if (resultCard) {
        resultCard.classList.remove("hidden");
      }
      if (translationWrap) {
        translationWrap.classList.add("hidden");
      }
      if (translationText) {
        translationText.textContent = "";
      }
      setStatus("Scan complete. Result shown below.");
    } catch (err) {
      if (err && err.name === "AbortError") {
        if (isMobile) {
          if (busyRetries < MAX_BUSY_RETRIES) {
            busyRetries += 1;
            setStatus("Retrying mobile scan...");
            setTimeout(() => captureAndScan(false, false, true), 1200);
            return;
          }
          setStatus("Server busy. Try again in a moment.");
          return;
        }
        setStatus("Server busy or slow. Please try again.");
      } else {
        setStatus(err && err.message ? err.message : "Scan failed.");
      }
    } finally {
      scanning = false;
      startBtn.disabled = false;
    }
  };

  const runTranslate = async () => {
    if (!lastScanId) {
      setStatus("Scan first, then convert language.");
      return;
    }
    if (!translateBtn) {
      return;
    }
    translateBtn.disabled = true;
    setStatus("Converting language...");
    try {
      const targetLang = translateLang ? translateLang.value : "en";
      const response = await fetch(`/api/scans/${lastScanId}/translate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_lang: targetLang }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || "Translate failed.");
      }
      if (translationText) {
        translationText.textContent = (payload.data && payload.data.translation_text) || "";
      }
      if (translationWrap) {
        translationWrap.classList.remove("hidden");
      }
      setStatus("Conversion done.");
    } catch (err) {
      setStatus(err && err.message ? err.message : "Translate failed.");
    } finally {
      translateBtn.disabled = false;
    }
  };

  if (translateBtn) {
    translateBtn.addEventListener("click", runTranslate);
  }

  startBtn.addEventListener("click", async () => {
    if (!stream) {
      await enableCamera(true);
      return;
    }
    if (isMobile) {
      captureAndScan(false, false, true);
      return;
    }
    captureAndScan(false, true);
  });

  window.addEventListener("beforeunload", () => {
    stopStream();
  });
})();

(function () {
  const form = document.querySelector('form[action="/upload"]');
  if (!form) {
    return;
  }

  const isMobile = window.matchMedia("(max-width: 700px)").matches;
  if (!isMobile) {
    return;
  }

  const status = document.getElementById("upload-status");
  const resultCard = document.getElementById("upload-result");
  const extractedEl = document.getElementById("upload-extracted");
  const cleanedEl = document.getElementById("upload-cleaned");
  const openLink = document.getElementById("upload-open");
  const submitBtn = form.querySelector('button[type="submit"]');
  const fileInput = form.querySelector('input[type="file"][name="images"]');
  let mobileBusyRetries = 0;
  const MAX_MOBILE_BUSY_RETRIES = 1;

  const setStatus = (message) => {
    if (status) {
      status.textContent = message;
    }
  };

  const loadImage = (file) =>
    new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        URL.revokeObjectURL(url);
        resolve(img);
      };
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("Image decode failed."));
      };
      img.src = url;
    });

  const compressImage = async (file, maxSide, quality) => {
    if (!file.type.startsWith("image/")) {
      return file;
    }
    try {
      const img = await loadImage(file);
      const rawWidth = img.naturalWidth || img.width;
      const rawHeight = img.naturalHeight || img.height;
      if (!rawWidth || !rawHeight) {
        return file;
      }
      const scale = Math.min(1, maxSide / Math.max(rawWidth, rawHeight));
      if (scale >= 1) {
        return file;
      }
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(rawWidth * scale);
      canvas.height = Math.round(rawHeight * scale);
      const ctx = canvas.getContext("2d");
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const blob = await new Promise((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", quality)
      );
      if (!blob) {
        return file;
      }
      const safeName = file.name ? file.name.replace(/\.[^.]+$/, ".jpg") : "upload.jpg";
      return new File([blob], safeName, { type: "image/jpeg" });
    } catch (err) {
      return file;
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    mobileBusyRetries = 0;
    if (submitBtn) {
      submitBtn.disabled = true;
    }
    if (resultCard) {
      resultCard.classList.add("hidden");
    }
    setStatus("Uploading... OCR is running.");

    try {
      const runUpload = async (useAdvanced, tiny = false) => {
        const formData = new FormData(form);
        const forceFast = isMobile || tiny;
        const userAdvanced = formData.get("advanced_ocr") === "on";
        const advancedMode = !forceFast && (userAdvanced || useAdvanced);
        const selectedLang = formData.get("lang") || "eng";
        const fastLang = selectedLang.includes("+") ? selectedLang.split("+")[0] : selectedLang;
        const langForRequest = isMobile && tiny ? fastLang : selectedLang;
        formData.set("lang", langForRequest);
        const files = formData.getAll("images");
        if (!files.length || (fileInput && !fileInput.files.length)) {
          return { ok: false, errorMessage: "Please select at least one image." };
        }
        formData.delete("images");
        if (forceFast) {
          formData.delete("advanced_ocr");
        }
        const maxSide = tiny ? 900 : advancedMode ? 1800 : forceFast ? 1200 : 1400;
        const quality = tiny ? 0.65 : advancedMode ? 0.85 : forceFast ? 0.75 : 0.8;
        const processed = await Promise.all(
          files.map((file) => compressImage(file, maxSide, quality))
        );
        processed.forEach((file) => {
          formData.append("images", file, file.name || "upload.jpg");
        });
        if (!advancedMode) {
          formData.append("fast_ocr", "on");
        } else if (!userAdvanced) {
          formData.append("advanced_ocr", "on");
        }
        formData.append("skip_storage", "on");
        if (isMobile) {
          formData.append("mobile", "on");
        }
        if (tiny) {
          formData.append("mobile_tiny", "on");
        }

        try {
          const controller = new AbortController();
          const timeoutMs = isMobile ? (tiny ? 60000 : 120000) : 60000;
          const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
          const response = await fetch("/api/scans", {
            method: "POST",
            body: formData,
            signal: controller.signal,
          });
          clearTimeout(timeoutId);
          const rawText = await response.text();
        let payload = {};
        try {
          payload = rawText ? JSON.parse(rawText) : {};
        } catch (err) {
          payload = {};
        }
        if (!response.ok || !payload.ok) {
          const safeText =
            rawText && rawText.length < 180 && !rawText.includes("<") ? rawText : "";
          const errorMessage =
            payload.error || safeText || `OCR failed (HTTP ${response.status}). Try again.`;
          const noReadable = String(errorMessage).toLowerCase().includes("no readable");
          const busy =
            String(errorMessage).toLowerCase().includes("busy") ||
            response.status === 413 ||
            response.status === 429 ||
            response.status === 503 ||
            response.status === 504 ||
            response.status >= 500;
          return { ok: false, errorMessage, noReadable, userAdvanced, busy };
        }
        return { ok: true, payload, userAdvanced };
        } catch (err) {
          return {
            ok: false,
            errorMessage: err && err.message ? err.message : "Upload failed.",
            aborted: err && err.name === "AbortError",
          };
        }
      };

      const filesNow = fileInput && fileInput.files ? Array.from(fileInput.files) : [];
      const totalSize = filesNow.reduce((sum, file) => sum + (file.size || 0), 0);
      const largestFile = filesNow.reduce((max, file) => Math.max(max, file.size || 0), 0);
      const preferTiny = isMobile && (totalSize > 12 * 1024 * 1024 || largestFile > 6 * 1024 * 1024);
      if (preferTiny) {
        setStatus("Optimizing for mobile...");
      }
      let attempt = await runUpload(false, preferTiny);
      if (isMobile && preferTiny && !attempt.ok && attempt.noReadable) {
        setStatus("Trying higher quality...");
        attempt = await runUpload(false, false);
      }
      if (
        isMobile &&
        !attempt.ok &&
        (attempt.aborted || attempt.busy)
      ) {
        setStatus("Auto-optimizing for mobile...");
        attempt = await runUpload(false, true);
      }
      if (
        isMobile &&
        !attempt.ok &&
        (attempt.aborted || attempt.busy) &&
        mobileBusyRetries < MAX_MOBILE_BUSY_RETRIES
      ) {
        mobileBusyRetries += 1;
        setStatus("Retrying mobile upload...");
        attempt = await runUpload(false, true);
      }
      if (!attempt.ok && attempt.noReadable && !attempt.userAdvanced) {
        setStatus("Trying enhanced scan...");
        attempt = await runUpload(true, false);
      }
      if (!attempt.ok) {
        throw new Error(attempt.errorMessage || "OCR failed.");
      }

      const payload = attempt.payload || {};

      const scan = payload.data || {};
      if (openLink && scan.id) {
        openLink.href = `/result/${scan.id}`;
      }
      if (extractedEl) {
        extractedEl.textContent = scan.extracted_text || "";
      }
      if (cleanedEl) {
        cleanedEl.value = scan.cleaned_text || scan.extracted_text || "";
      }
      if (resultCard) {
        resultCard.classList.remove("hidden");
      }

      const warnings = payload.warnings || [];
      setStatus(warnings.length ? `OCR complete. ${warnings[0]}` : "OCR complete.");
    } catch (err) {
      if (err && err.name === "AbortError") {
        if (isMobile) {
          setStatus("Auto-optimizing for mobile...");
        } else {
          setStatus("Server busy or slow. Please try again.");
        }
      } else {
        setStatus(err && err.message ? err.message : "Upload failed.");
      }
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
      }
    }
  });
})();

(function () {
  const installBtn = document.getElementById("install-button");
  if (!installBtn) {
    return;
  }

  const isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone;
  if (isStandalone) {
    installBtn.hidden = true;
    return;
  }

  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  let deferredPrompt = null;

  const showInstall = () => {
    installBtn.hidden = false;
    installBtn.disabled = false;
  };

  const hideInstall = () => {
    installBtn.hidden = true;
  };

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    showInstall();
  });

  window.addEventListener("appinstalled", () => {
    deferredPrompt = null;
    hideInstall();
  });

  if (isIos) {
    showInstall();
  }

  installBtn.addEventListener("click", async () => {
    if (isIos && !deferredPrompt) {
      alert('iPhone/iPad: Safari menu > "Add to Home Screen" se install karein.');
      return;
    }

    if (!deferredPrompt) {
      installBtn.textContent = "Use browser menu";
      setTimeout(() => {
        installBtn.textContent = "Install App";
      }, 1600);
      return;
    }

    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    hideInstall();
  });
})();

(function () {
  const STORAGE_KEY = "visiontext_lang";
  const selectors = [
    'select[name="lang"]',
    'select[name="camera_lang"]',
    'select[data-lang-picker="ocr"]',
  ];
  const selects = Array.from(
    document.querySelectorAll(selectors.join(","))
  ).filter(Boolean);
  if (!selects.length) {
    return;
  }

  const setSelectValue = (select, value) => {
    const optionValues = Array.from(select.options).map((opt) => opt.value);
    if (optionValues.includes(value)) {
      select.value = value;
      return true;
    }
    return false;
  };

  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    selects.forEach((select) => setSelectValue(select, saved));
  }

  selects.forEach((select) => {
    select.addEventListener("change", () => {
      const value = select.value;
      localStorage.setItem(STORAGE_KEY, value);
      selects.forEach((other) => {
        if (other !== select) {
          setSelectValue(other, value);
        }
      });
    });
  });
})();
