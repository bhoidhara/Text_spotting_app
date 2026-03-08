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
