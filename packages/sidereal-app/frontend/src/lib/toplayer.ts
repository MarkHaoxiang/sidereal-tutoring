// A modal `<dialog>` sits in the browser's top layer, where no z-index reaches it — so the
// toasts live in the top layer too, and are re-promoted above each dialog as it opens.

let host: HTMLElement | null = null;

/** Puts the element back on top; false when the browser has no top layer to put it in. */
function raise(element: HTMLElement): boolean {
  if (typeof (element as { showPopover?: unknown }).showPopover !== "function") {
    return false;
  }
  try {
    if (element.matches(":popover-open")) {
      element.hidePopover();
    }
    element.showPopover();
    return true;
  } catch {
    return false;
  }
}

/**
 * Called by the toast host once it is in the document. `popover` is set here rather than in
 * JSX because React 18's types do not carry it — and it is taken off again where the browser
 * will not open it, since an unopened popover is `display: none`.
 */
export function holdToasts(element: HTMLElement | null): void {
  host = element;
  if (element === null) {
    return;
  }
  element.setAttribute("popover", "manual");
  if (!raise(element)) {
    element.removeAttribute("popover");
  }
}

/** What a newly opened dialog calls: it has just taken the top of the top layer. */
export function raiseToasts(): void {
  if (host?.isConnected === true && host.hasAttribute("popover")) {
    raise(host);
  }
}
