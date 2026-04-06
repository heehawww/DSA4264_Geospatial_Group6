document.addEventListener("DOMContentLoaded", function () {
  if (typeof mermaid === "undefined") return;

  const codeBlocks = document.querySelectorAll("pre code.language-mermaid");
  codeBlocks.forEach((codeEl, idx) => {
    const pre = codeEl.parentElement;
    if (!pre) return;
    const wrapper = document.createElement("div");
    wrapper.className = "mermaid";
    wrapper.id = "mermaid-" + idx;
    wrapper.textContent = codeEl.textContent || "";
    pre.replaceWith(wrapper);
  });

  mermaid.initialize({ startOnLoad: false, theme: "default" });
  mermaid.run();
});
