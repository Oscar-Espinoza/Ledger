(function () {
  "use strict";

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function initializeBootstrapComponents() {
    if (typeof bootstrap === "undefined") {
      return;
    }

    document.querySelectorAll('[data-bs-toggle="popover"]').forEach((element) => {
      bootstrap.Popover.getOrCreateInstance(element, {
        animation: !reducedMotion,
        container: "body",
        trigger: "focus",
      });
    });

    document.querySelectorAll("[data-app-toast]").forEach((element) => {
      bootstrap.Toast.getOrCreateInstance(element, {
        animation: !reducedMotion,
        autohide: true,
        delay: 6000,
      }).show();
    });

    const welcomeModal = document.getElementById("welcomeModal");
    if (welcomeModal && welcomeModal.dataset.autoShow === "true") {
      bootstrap.Modal.getOrCreateInstance(welcomeModal).show();
    }
  }

  function initializeExpenseForm() {
    const form = document.querySelector("[data-expense-form]");
    if (!form) {
      return;
    }

    const splitType = form.querySelector("#id_split_type");
    const amountInput = form.querySelector("#id_amount");
    const shareFields = form.querySelector("#share-fields");
    const shareInputs = Array.from(form.querySelectorAll(".share-input"));
    const shareUnits = form.querySelectorAll(".share-unit");
    const instruction = form.querySelector("#split-instruction");
    const totalOutput = form.querySelector("#share-total");

    if (!splitType || !amountInput || !shareFields || !instruction || !totalOutput) {
      return;
    }

    function numericValue(input) {
      const value = Number.parseFloat(input.value);
      return Number.isFinite(value) ? value : 0;
    }

    function updateTotal() {
      if (splitType.value === "equal") {
        totalOutput.textContent = "";
        totalOutput.className = "share-total";
        return;
      }

      const total = shareInputs.reduce((sum, input) => sum + numericValue(input), 0);
      const isPercentage = splitType.value === "percentage";
      const target = isPercentage ? 100 : numericValue(amountInput);
      const unit = isPercentage ? "%" : "";
      const targetReady = isPercentage || numericValue(amountInput) > 0;
      const matched = targetReady && Math.abs(total - target) < 0.005;

      if (!targetReady) {
        totalOutput.textContent = `${total.toFixed(2)} entered — add the expense amount above.`;
        totalOutput.className = "share-total";
        return;
      }

      totalOutput.textContent = `${total.toFixed(2)}${unit} of ${target.toFixed(2)}${unit} entered${matched ? " — ready" : ""}.`;
      totalOutput.className = `share-total ${matched ? "is-matched" : "is-unmatched"}`;
    }

    function updateSplitFields() {
      const split = splitType.value;
      const isEqual = split === "equal";
      shareFields.hidden = isEqual;
      shareInputs.forEach((input) => {
        input.disabled = isEqual;
      });

      if (isEqual) {
        instruction.textContent = "Equal split divides the expense across every group member. No shares are needed.";
      } else if (split === "exact") {
        instruction.textContent = "Enter each person's amount. The running total must match the expense amount.";
      } else {
        instruction.textContent = "Enter each person's percentage. The running total must equal exactly 100%.";
      }

      shareUnits.forEach((unit) => {
        unit.textContent = split === "percentage" ? "%" : "amount";
      });
      updateTotal();
    }

    splitType.addEventListener("change", updateSplitFields);
    amountInput.addEventListener("input", updateTotal);
    shareInputs.forEach((input) => input.addEventListener("input", updateTotal));
    updateSplitFields();
  }

  initializeBootstrapComponents();
  initializeExpenseForm();
})();
