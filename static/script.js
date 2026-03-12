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
  const langSelect = document.querySelector("select[name='camera_lang']");
  const sourceSelect = document.querySelector("select[name='camera_source']");

  if (!startBtn || !enableBtn || !video || !canvas || !preview) {
    return;
  }

  let stream = null;
  let scanning = false;
  const isMobile = window.matchMedia("(max-width: 700px)").matches;

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
    return { video: { facingMode }, audio: false };
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
        setTimeout(() => {
          captureAndScan(true);
        }, 700);
      }
    } catch (err) {
      setStatus("Camera permission denied or unavailable.");
    }
  };

  enableBtn.addEventListener("click", () => {
    enableCamera(true);
  });

  const captureAndScan = async (autoMode = false) => {
    if (scanning) {
      return;
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
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    try {
      const blob = await new Promise((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", 0.92)
      );
      if (!blob) {
        throw new Error("Capture failed.");
      }

      const formData = new FormData();
      formData.append("images", blob, "camera.jpg");
      formData.append("lang", langSelect ? langSelect.value : "eng");
      formData.append("cleanup", "on");
      formData.append("autocorrect", "on");
      formData.append("detect_intent", "on");
      formData.append("student_mode", "on");
      formData.append("advanced_ocr", "on");

      const response = await fetch("/api/scans", {
        method: "POST",
        body: formData,
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) {
        throw new Error(payload.error || "OCR failed. Try again.");
      }

      const scanId = payload.data && payload.data.id;
      if (scanId) {
        window.location.href = `/result/${scanId}`;
        return;
      }
      setStatus("Scan complete. Open History to view results.");
    } catch (err) {
      setStatus(err && err.message ? err.message : "Scan failed.");
    } finally {
      scanning = false;
      startBtn.disabled = false;
    }
  };

  startBtn.addEventListener("click", async () => {
    if (!stream) {
      await enableCamera(true);
      return;
    }
    captureAndScan(false);
  });

  window.addEventListener("beforeunload", () => {
    stopStream();
  });
})();
