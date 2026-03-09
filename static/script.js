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
