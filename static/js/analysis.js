document.addEventListener("DOMContentLoaded", () => {

    const form =
        document.getElementById("analysisForm");

    if (!form) {
        return;
    }

    const steps =
        Array.from(
            document.querySelectorAll(
                "[data-analysis-step]"
            )
        );

    const navItems =
        Array.from(
            document.querySelectorAll(
                "[data-analysis-step-nav]"
            )
        );

    const stepText =
        document.getElementById(
            "analysisStepText"
        );

    const nextButtons =
        document.querySelectorAll(
            "[data-analysis-next]"
        );

    const backButtons =
        document.querySelectorAll(
            "[data-analysis-back]"
        );

    const upload =
        document.getElementById(
            "analysisUpload"
        );

    const fileInput =
        document.getElementById(
            "aquariumPhoto"
        );

    const previewImage =
        document.getElementById(
            "analysisPreviewImage"
        );

    const removePhoto =
        document.getElementById(
            "analysisRemovePhoto"
        );

    const description =
        document.getElementById(
            "analysisDescription"
        );

    const charCount =
        document.getElementById(
            "analysisCharCount"
        );

    const volumeOutput =
        document.getElementById(
            "analysisVolume"
        );

    const loading =
        document.getElementById(
            "analysisLoading"
        );

    const loadingText =
        document.getElementById(
            "analysisLoadingText"
        );

    let currentStep = 1;


    function getStepElement(
        stepNumber
    ) {
        return steps.find(
            step =>
                Number(
                    step.dataset.analysisStep
                )
                === stepNumber
        );
    }


    function clearValidation() {

        document
            .querySelectorAll(
                ".analysis-field-error"
            )
            .forEach(element => {
                element.classList.remove(
                    "analysis-field-error"
                );
            });

        document
            .querySelectorAll(
                ".analysis-validation"
            )
            .forEach(element => {
                element.remove();
            });

    }


    function showValidation(
        step,
        text
    ) {

        const message =
            document.createElement("p");

        message.className =
            "analysis-validation";

        message.textContent =
            text;

        step.appendChild(message);

    }


    function goToStep(
        stepNumber
    ) {

        currentStep =
            Math.max(
                1,
                Math.min(
                    3,
                    stepNumber
                )
            );

        steps.forEach(step => {

            step.classList.toggle(
                "active",
                Number(
                    step.dataset.analysisStep
                )
                === currentStep
            );

        });


        navItems.forEach(item => {

            item.classList.toggle(
                "active",
                Number(
                    item.dataset.analysisStepNav
                )
                === currentStep
            );

        });


        if (stepText) {
            stepText.textContent =
                `0${currentStep} / 03`;
        }


        window.scrollTo({
            top:
                Math.max(
                    0,
                    form
                        .getBoundingClientRect()
                        .top
                    + window.scrollY
                    - 110
                ),
            behavior: "smooth",
        });

    }


    function validateStep(
        stepNumber
    ) {

        clearValidation();

        const step =
            getStepElement(
                stepNumber
            );

        if (!step) {
            return true;
        }

        const requiredInputs =
            Array.from(
                step.querySelectorAll(
                    "[required]"
                )
            );

        const radioGroups =
            new Map();


        for (
            const input
            of requiredInputs
        ) {

            if (
                input.type
                === "radio"
            ) {

                if (
                    !radioGroups
                        .has(input.name)
                ) {
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


            if (
                !String(
                    input.value
                ).trim()
            ) {

                const wrapper =
                    input.closest(
                        ".analysis-field"
                    )
                    || input.closest(
                        ".analysis-dimensions > label"
                    );

                wrapper
                    ?.classList
                    .add(
                        "analysis-field-error"
                    );

                showValidation(
                    step,
                    "Devam etmek için gerekli alanları doldur."
                );

                input.focus();

                return false;
            }

        }


        for (
            const [, radios]
            of radioGroups
        ) {

            if (
                !radios.some(
                    radio =>
                        radio.checked
                )
            ) {

                const grid =
                    radios[0]
                        ?.closest(
                            ".analysis-choice-grid"
                        );

                grid
                    ?.classList
                    .add(
                        "analysis-field-error"
                    );

                showValidation(
                    step,
                    "Devam etmek için bir seçenek seç."
                );

                return false;
            }

        }

        return true;
    }


    nextButtons.forEach(
        button => {

            button.addEventListener(
                "click",
                () => {

                    if (
                        !validateStep(
                            currentStep
                        )
                    ) {
                        return;
                    }

                    goToStep(
                        currentStep + 1
                    );

                }
            );

        }
    );


    backButtons.forEach(
        button => {

            button.addEventListener(
                "click",
                () => {
                    clearValidation();

                    goToStep(
                        currentStep - 1
                    );
                }
            );

        }
    );


    function updateVolume() {

        const lengthInput =
            form.querySelector(
                '[name="length"]'
            );

        const widthInput =
            form.querySelector(
                '[name="width"]'
            );

        const heightInput =
            form.querySelector(
                '[name="height"]'
            );

        const length =
            parseFloat(
                lengthInput?.value
            );

        const width =
            parseFloat(
                widthInput?.value
            );

        const height =
            parseFloat(
                heightInput?.value
            );

        if (
            Number.isFinite(length)
            && Number.isFinite(width)
            && Number.isFinite(height)
        ) {

            const liters =
                (
                    length
                    * width
                    * height
                )
                / 1000;

            volumeOutput.textContent =
                `${liters.toFixed(1)} L`;

        } else {

            volumeOutput.textContent =
                "— L";

        }

    }


    [
        "length",
        "width",
        "height",
    ].forEach(name => {

        form
            .querySelector(
                `[name="${name}"]`
            )
            ?.addEventListener(
                "input",
                updateVolume
            );

    });


    function updateCharacterCount() {

        if (
            !description
            || !charCount
        ) {
            return;
        }

        charCount.textContent =
            description.value.length;

    }


    description
        ?.addEventListener(
            "input",
            updateCharacterCount
        );


    function clearImagePreview() {

        if (!fileInput) {
            return;
        }

        fileInput.value = "";

        if (previewImage) {
            previewImage.removeAttribute(
                "src"
            );
        }

        upload
            ?.classList
            .remove(
                "has-image"
            );

    }


    function previewFile(
        file
    ) {

        if (!file) {
            clearImagePreview();
            return;
        }

        const allowedTypes = [
            "image/jpeg",
            "image/png",
            "image/webp",
        ];


        if (
            !allowedTypes.includes(
                file.type
            )
        ) {
            alert(
                "JPG, PNG veya WEBP fotoğraf kullan."
            );

            clearImagePreview();

            return;
        }


        if (
            file.size
            > 8 * 1024 * 1024
        ) {
            alert(
                "Fotoğraf en fazla 8 MB olabilir."
            );

            clearImagePreview();

            return;
        }


        const reader =
            new FileReader();


        reader.onload =
            event => {

                previewImage.src =
                    event.target.result;

                upload
                    ?.classList
                    .add(
                        "has-image"
                    );

            };


        reader.readAsDataURL(
            file
        );

    }


    fileInput
        ?.addEventListener(
            "change",
            () => {
                previewFile(
                    fileInput.files[0]
                );
            }
        );


    removePhoto
        ?.addEventListener(
            "click",
            event => {

                event.preventDefault();
                event.stopPropagation();

                clearImagePreview();

            }
        );


    if (upload) {

        [
            "dragenter",
            "dragover",
        ].forEach(
            eventName => {

                upload.addEventListener(
                    eventName,
                    event => {

                        event.preventDefault();

                        upload
                            .classList
                            .add(
                                "dragover"
                            );

                    }
                );

            }
        );


        [
            "dragleave",
            "drop",
        ].forEach(
            eventName => {

                upload.addEventListener(
                    eventName,
                    event => {

                        event.preventDefault();

                        upload
                            .classList
                            .remove(
                                "dragover"
                            );

                    }
                );

            }
        );


        upload.addEventListener(
            "drop",
            event => {

                const file =
                    event
                        .dataTransfer
                        .files[0];

                if (!file) {
                    return;
                }

                const transfer =
                    new DataTransfer();

                transfer.items.add(
                    file
                );

                fileInput.files =
                    transfer.files;

                previewFile(
                    file
                );

            }
        );

    }


    function showLoading() {

        if (!loading) {
            return;
        }

        loading.classList.add(
            "active"
        );

        loading.setAttribute(
            "aria-hidden",
            "false"
        );


        const messages = [
            "Kurulum bilgilerini değerlendiriyoruz...",
            "Canlı uyumu ve biyolojik yük kontrol ediliyor...",
            "Filtrasyon, ışık ve bitki dengesi inceleniyor...",
            "Bakım rutini ve su verileri yorumlanıyor...",
            "Öncelikli aksiyon planın hazırlanıyor...",
        ];

        let index = 0;

        if (loadingText) {

            loadingText.textContent =
                messages[0];

            window.setInterval(
                () => {

                    index =
                        (
                            index + 1
                        )
                        % messages.length;

                    loadingText.textContent =
                        messages[index];

                },
                2100
            );

        }

    }


    form.addEventListener(
        "submit",
        event => {

            event.preventDefault();

            for (
                let step = 1;
                step <= 3;
                step++
            ) {

                if (
                    !validateStep(
                        step
                    )
                ) {
                    goToStep(step);

                    return;
                }

            }


            const submitButton =
                form.querySelector(
                    ".analysis-submit"
                );

            if (submitButton) {
                submitButton.disabled =
                    true;
            }

            showLoading();


            window.setTimeout(
                () => {
                    form.submit();
                },
                120
            );

        }
    );


    updateVolume();
    updateCharacterCount();
    goToStep(1);

});
