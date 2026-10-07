/**
 * Scroll-reveal for any element with [data-reveal] (Problem 10).
 * One IntersectionObserver for the whole app; a MutationObserver picks up elements
 * rendered later (async product grids, route changes). Respects prefers-reduced-motion.
 */
export function startReveal(): () => void {
  const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const show = (el: Element) => el.classList.add("is-visible");
  if (reduce || !("IntersectionObserver" in window)) {
    document.querySelectorAll("[data-reveal]").forEach(show);
    const mo = new MutationObserver(() => document.querySelectorAll("[data-reveal]:not(.is-visible)").forEach(show));
    mo.observe(document.body, { childList: true, subtree: true });
    return () => mo.disconnect();
  }
  const io = new IntersectionObserver(
    (entries) => entries.forEach((e) => {
      if (e.isIntersecting) {
        show(e.target);
        io.unobserve(e.target);
      }
    }),
    { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
  );
  const scan = () => document.querySelectorAll("[data-reveal]:not(.is-visible)").forEach((el) => io.observe(el));
  scan();
  const mo = new MutationObserver(scan);
  mo.observe(document.body, { childList: true, subtree: true });
  return () => {
    io.disconnect();
    mo.disconnect();
  };
}
