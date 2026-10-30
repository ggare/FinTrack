/* FinTrack web UI helpers: toasts + inline-form niceties for HTMX. */
(function () {
  "use strict";

  function showToast(message, isError) {
    var root = document.getElementById("toast-root");
    if (!root) return;
    var toast = document.createElement("div");
    toast.className =
      "pointer-events-auto max-w-xs rounded-xl px-4 py-3 text-sm font-medium text-white shadow-lg " +
      (isError ? "bg-rose-500" : "bg-slate-900");
    toast.textContent = message;
    root.appendChild(toast);
    setTimeout(function () {
      toast.style.transition = "opacity 300ms ease";
      toast.style.opacity = "0";
      setTimeout(function () {
        toast.remove();
      }, 300);
    }, 2800);
  }
  window.showToast = showToast;

  // Successful transaction submit: clear the form and show a toast
  document.addEventListener("htmx:afterRequest", function (evt) {
    var elt = evt.detail.elt;
    if (!evt.detail.successful || !elt || !elt.id) return;
    if (elt.id === "tx-form") {
      elt.reset();
      showToast("Transaction added");
    }
    if (elt.id === "budget-add-form") {
      elt.reset();
      showToast("Budget saved");
    }
  });

  // HTMX request errors: show the server-provided text
  document.addEventListener("htmx:responseError", function (evt) {
    var text = (evt.detail.xhr && evt.detail.xhr.responseText) || "";
    showToast(text || "Something went wrong", true);
  });
})();
