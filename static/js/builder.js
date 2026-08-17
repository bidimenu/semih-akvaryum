document.addEventListener("DOMContentLoaded", () => {

    const form = document.getElementById("builderForm");

    if (!form) {
        return;
    }

    const steps = Array.from(
        document.querySelectorAll(".builder-step")
    );

    const progressItems = Array.from(
        document.querySelectorAll(".progress-item")
    );

    const mobileStepText = document.getElementById("mobileStepText");
    const mobileProgressBar = document.getElementById("mobileProgressBar");

    let currentStep = 1;

    function getStepElement(stepNumber) {
        return steps.find(
            step => Number(step.dataset.step) === stepNumber
        );
    }

    function clearValidation() {
        document
            .querySelectorAll(".builder-field-error")
            .forEach(element => {
                element.classList.remove("builder-field-error");
            });

        document
            .querySelectorAll(".builder-validation-message")
            .forEach(element => {
                element.remove();
            });
    }

    function showValidationMessage(step, text) {
        const navigation = step.querySelector(".builder-navigation");

        const message = document.createElement("div");
        message.className = "builder-validation-message";
        message.textContent = text;

        navigation.parentNode.insertBefore(message, navigation);
    }

    function validateCurrentStep() {
        clearValidation();

        const step = getStepElement(currentStep);

        const requiredInputs = Array.from(
            step.querySelectorAll("[required]")
        );

        const radioGroups = new Map();

        for (const input of requiredInputs) {

            if (input.type === "radio") {

                if (!radioGroups.has(input.name)) {
                    radioGroups.set(
                        input.name,
                        Array.from(
                            step.querySelectorAll(
                                `input[type="radio"][name="${input.name}"]`
                            )
                        )
                    );
                }

                continue;
            }

            if (!String(input.value).trim()) {

                const wrapper = input.closest(
                    ".builder-input-card, .budget-input-wrap, .livestock-input, .dream-field"
                );

                if (wrapper) {
                    wrapper.classList.add("builder-field-error");
                }

                input.focus();

                showValidationMessage(
                    step,
                    "Devam etmek için bu alanı doldur."
                );

                return false;
            }
        }

        for (const [, radios] of radioGroups.entries()) {

            const selected = radios.some(
                radio => radio.checked
            );

            if (!selected) {

                const wrapper = radios[0].closest(
                    ".choice-grid, .style-choice-grid"
                );

                if (wrapper) {
                    wrapper.classList.add("builder-field-error");
                }

                showValidationMessage(
                    step,
                    "Devam etmek için bir seçenek seç."
                );

                return false;
            }
        }

        return true;
    }

    function updateProgress() {

        progressItems.forEach((item, index) => {

            const stepNumber = index + 1;

            item.classList.toggle(
                "active",
                stepNumber === currentStep
            );

            item.classList.toggle(
                "complete",
                stepNumber < currentStep
            );
        });

        if (mobileStepText) {
            mobileStepText.textContent = `ADIM ${currentStep} / 5`;
        }

        if (mobileProgressBar) {
            mobileProgressBar.style.width = `${currentStep * 20}%`;
        }
    }

    function goToStep(stepNumber) {

        if (stepNumber < 1 || stepNumber > 5) {
            return;
        }

        clearValidation();

        currentStep = stepNumber;

        steps.forEach(step => {
            step.classList.toggle(
                "active",
                Number(step.dataset.step) === currentStep
            );
        });

        updateProgress();

        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });
    }

    document
        .querySelectorAll("[data-next]")
        .forEach(button => {

            button.addEventListener("click", () => {

                if (validateCurrentStep()) {
                    goToStep(currentStep + 1);
                }
            });
        });

    document
        .querySelectorAll("[data-prev]")
        .forEach(button => {

            button.addEventListener("click", () => {
                goToStep(currentStep - 1);
            });
        });

    progressItems.forEach((item, index) => {

        item.addEventListener("click", () => {

            const targetStep = index + 1;

            if (targetStep < currentStep) {
                goToStep(targetStep);
            }
        });
    });

    /* ============================================
       VOLUME CALCULATOR
    ============================================ */

    const lengthInput = document.getElementById("length");
    const widthInput = document.getElementById("width");
    const heightInput = document.getElementById("height");
    const volumeOutput = document.getElementById("volumeOutput");

    function updateVolume() {

        const length = Number(lengthInput?.value);
        const width = Number(widthInput?.value);
        const height = Number(heightInput?.value);

        if (length > 0 && width > 0 && height > 0) {

            const liters = (length * width * height) / 1000;

            volumeOutput.textContent = `${liters.toFixed(1)} litre`;

        } else {

            volumeOutput.textContent = "Ölçüleri gir";
        }
    }

    [
        lengthInput,
        widthInput,
        heightInput
    ].forEach(input => {

        input?.addEventListener(
            "input",
            updateVolume
        );
    });

    /* ============================================
       QUICK SPECIES
    ============================================ */

    const livestockInput = document.getElementById("livestock");

    document
        .querySelectorAll("[data-species]")
        .forEach(button => {

            button.addEventListener("click", () => {

                const species = button.dataset.species;
                const current = livestockInput.value.trim();

                if (!current) {

                    livestockInput.value = species;

                } else if (
                    !current
                        .toLowerCase()
                        .includes(species.toLowerCase())
                ) {

                    livestockInput.value = `${current}, ${species}`;
                }

                livestockInput.focus();
            });
        });

    /* ============================================
       DREAM CHARACTER COUNTER
    ============================================ */

    const dream = document.getElementById("dream");
    const dreamCounter = document.getElementById("dreamCounter");

    function updateDreamCounter() {

        if (!dream || !dreamCounter) {
            return;
        }

        dreamCounter.textContent =
            `${dream.value.length} / 1200`;
    }

    dream?.addEventListener(
        "input",
        updateDreamCounter
    );

    updateDreamCounter();


    /* ============================================
       FINAL SUBMIT VALIDATION
       Validate every step ourselves so hidden
       browser-required fields never block silently.
    ============================================ */

    function validateAllSteps() {

        clearValidation();

        for (let stepNumber = 1; stepNumber <= 5; stepNumber++) {

            const step = getStepElement(stepNumber);

            if (!step) {
                continue;
            }

            const requiredInputs = Array.from(
                step.querySelectorAll("[required]")
            );

            const radioGroups = new Map();

            for (const input of requiredInputs) {

                if (input.type === "radio") {

                    if (!radioGroups.has(input.name)) {
                        radioGroups.set(
                            input.name,
                            Array.from(
                                step.querySelectorAll(
                                    `input[type="radio"][name="${input.name}"]`
                                )
                            )
                        );
                    }

                    continue;
                }

                if (!String(input.value).trim()) {

                    goToStep(stepNumber);

                    window.setTimeout(() => {

                        const wrapper = input.closest(
                            ".builder-input-card, .budget-input-wrap, .livestock-input, .dream-field"
                        );

                        if (wrapper) {
                            wrapper.classList.add("builder-field-error");
                        }

                        showValidationMessage(
                            step,
                            "Devam etmek için bu alanı doldur."
                        );

                        input.focus();

                    }, 80);

                    return false;
                }
            }

            for (const [, radios] of radioGroups.entries()) {

                const selected = radios.some(
                    radio => radio.checked
                );

                if (!selected) {

                    goToStep(stepNumber);

                    window.setTimeout(() => {

                        const wrapper = radios[0].closest(
                            ".choice-grid, .style-choice-grid"
                        );

                        if (wrapper) {
                            wrapper.classList.add("builder-field-error");
                        }

                        showValidationMessage(
                            step,
                            "Devam etmek için bir seçenek seç."
                        );

                    }, 80);

                    return false;
                }
            }
        }

        return true;
    }


    function showAiLoading() {

        const loading =
            document.getElementById("builderLoading");

        const loadingText =
            document.getElementById("builderLoadingText");

        const submitButton =
            form.querySelector(".builder-generate");

        if (submitButton) {
            submitButton.disabled = true;
            submitButton.style.opacity = "0.72";
            submitButton.style.cursor = "wait";
        }

        if (loading) {
            loading.classList.add("active");
            loading.setAttribute("aria-hidden", "false");
        }

        const messages = [
            "Tank ölçülerini ve canlı tercihlerini değerlendiriyoruz...",
            "Biyolojik yük ve canlı uyumunu kontrol ediyoruz...",
            "Ekipman ve bitki planını oluşturuyoruz...",
            "Bakım rutini ve kurulum takvimini hazırlıyoruz..."
        ];

        let messageIndex = 0;

        if (loadingText) {

            loadingText.textContent =
                messages[0];

            window.setInterval(() => {

                messageIndex =
                    (messageIndex + 1) % messages.length;

                loadingText.textContent =
                    messages[messageIndex];

            }, 2200);
        }
    }


    form.addEventListener("submit", event => {

        event.preventDefault();

        if (!validateAllSteps()) {
            return;
        }

        showAiLoading();

        /*
         * Native form.submit() bypasses this submit listener.
         * This prevents an accidental event loop and sends the POST
         * directly to Flask after our own validation succeeds.
         */
        window.setTimeout(() => {
            form.submit();
        }, 120);

    });


    updateProgress();
    updateVolume();

});
