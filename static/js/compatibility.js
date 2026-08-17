document.addEventListener("DOMContentLoaded", () => {

    const form =
        document.getElementById(
            "compatForm"
        );

    if (!form) {
        return;
    }

    const volumeOutput =
        document.getElementById(
            "compatVolume"
        );

    const loading =
        document.getElementById(
            "compatLoading"
        );

    const loadingText =
        document.getElementById(
            "compatLoadingText"
        );

    const candidateButtons =
        document.querySelectorAll(
            "[data-candidate]"
        );


    function clearValidation() {

        document
            .querySelectorAll(
                ".compat-field-error"
            )
            .forEach(element => {
                element.classList.remove(
                    "compat-field-error"
                );
            });

        document
            .querySelectorAll(
                ".compat-validation"
            )
            .forEach(element => {
                element.remove();
            });

    }


    function showValidation(
        message,
        target
    ) {

        const validation =
            document.createElement(
                "p"
            );

        validation.className =
            "compat-validation";

        validation.textContent =
            message;

        const firstPanel =
            target?.closest(
                ".compat-panel"
            )
            || form.querySelector(
                ".compat-panel"
            );

        if (firstPanel) {
            firstPanel.appendChild(
                validation
            );
        }

    }


    function validateForm() {

        clearValidation();

        const requiredInputs =
            Array.from(
                form.querySelectorAll(
                    "[required]"
                )
            );


        for (
            const input
            of requiredInputs
        ) {

            if (
                !String(
                    input.value
                ).trim()
            ) {

                const wrapper =
                    input.closest(
                        ".compat-field"
                    )
                    || input.closest(
                        ".compat-dimensions > label"
                    )
                    || input.closest(
                        ".compat-candidate-card label"
                    );

                wrapper
                    ?.classList
                    .add(
                        "compat-field-error"
                    );

                showValidation(
                    "Uyumu kontrol etmek için yıldızlı alanları doldur.",
                    input
                );

                input.focus();

                return false;
            }

        }


        const quantity =
            Number(
                form
                    .querySelector(
                        '[name="candidate_quantity"]'
                    )
                    ?.value
            );


        if (
            !Number.isFinite(quantity)
            || quantity <= 0
        ) {

            const quantityInput =
                form.querySelector(
                    '[name="candidate_quantity"]'
                );

            quantityInput
                ?.closest(
                    ".compat-candidate-card label"
                )
                ?.classList
                .add(
                    "compat-field-error"
                );

            showValidation(
                "Eklemek istediğin canlı adedi 1 veya daha büyük olmalı.",
                quantityInput
            );

            quantityInput?.focus();

            return false;
        }


        return true;
    }


    function updateVolume() {

        const length =
            parseFloat(
                form
                    .querySelector(
                        '[name="length"]'
                    )
                    ?.value
            );

        const width =
            parseFloat(
                form
                    .querySelector(
                        '[name="width"]'
                    )
                    ?.value
            );

        const height =
            parseFloat(
                form
                    .querySelector(
                        '[name="height"]'
                    )
                    ?.value
            );


        if (
            Number.isFinite(length)
            && Number.isFinite(width)
            && Number.isFinite(height)
            && length > 0
            && width > 0
            && height > 0
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


    candidateButtons.forEach(
        button => {

            button.addEventListener(
                "click",
                () => {

                    const input =
                        form.querySelector(
                            '[name="candidate"]'
                        );

                    if (!input) {
                        return;
                    }

                    input.value =
                        button.dataset
                            .candidate
                        || "";

                    input.focus();

                }
            );

        }
    );


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
            "Tank hacmi ve taban alanı değerlendiriliyor...",
            "Mevcut canlılarla davranışsal uyum inceleniyor...",
            "Yetişkin boyutu ve sosyal ihtiyaç kontrol ediliyor...",
            "Su koşulları ve biyolojik yük karşılaştırılıyor...",
            "Uyum kararı ve alternatifler hazırlanıyor...",
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
                1900
            );

        }

    }


    form.addEventListener(
        "submit",
        event => {

            event.preventDefault();


            if (
                !validateForm()
            ) {
                return;
            }


            const submitButton =
                form.querySelector(
                    ".compat-submit"
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

});
